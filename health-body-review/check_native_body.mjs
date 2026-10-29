/** Whole Worker and native Node fetch against local HTTP framing/deadline faults.
 * Only the generated routing import and Cloudflare Cache/ASSETS bindings are supplied
 * locally. Worker logic, native fetch, AbortSignal.timeout and8s budget stay unchanged.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {performance} from 'node:perf_hooks';

const sourceRoot = path.resolve(process.argv[2]);
const reportPath = path.resolve(process.argv[3]);
const provenance = JSON.parse(await readFile(path.join(path.dirname(reportPath), 'source-provenance.json'), 'utf8'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
for (const item of provenance.files) {
  assert.equal(sha(await readFile(path.join(sourceRoot, item.version, item.path))), item.sha256);
}
const modes = ['healthy', 'empty', 'origin-503', 'origin-404', 'origin-429', 'body-reset',
  'short-content-length', 'header-stall', 'body-stall', 'delayed-complete', 'cache-hit',
  'cache-match-failure', 'cache-put-failure', 'cache-reuse'];
const versions = [];
for (const version of ['main', 'candidate']) {
  const workerPath = path.join(sourceRoot, version, 'edge/src/worker.js');
  const bytes = await readFile(workerPath);
  const original = bytes.toString('utf8');
  const importLine = 'import ROUTING from "./routing.json";';
  assert.equal(original.split(importLine).length, 2);
  assert.match(original, /const ORIGIN_TIMEOUT_MS = 8000;/);
  const routing = {static_first: [], edge_cached: {'/healthz':10}, types:{}};
  const adapted = original.replace(importLine, 'const ROUTING = '+JSON.stringify(routing)+';');
  const worker = (await import(`data:text/javascript;base64,${Buffer.from(adapted).toString('base64')}#${version}`)).default;
  let active;
  const server = http.createServer((request, response) => {
    const test = active;
    test.requests.push({method:request.method, url:request.url, elapsed_ms:performance.now()-test.started});
    const ordinal = test.requests.length;
    assert.equal(request.method, 'GET');
    const mode = test.mode;
    // Every fallback is deliberately healthy and quick, so an unexpected second fetch
    // is observable without leaving this test hung on the missing fallback deadline.
    if (ordinal > 1) {
      response.writeHead(200, {'Content-Type':'text/plain', 'Cache-Control':'no-store'});
      response.end('fallback healthy\n');
      return;
    }
    if (mode === 'header-stall') {
      const timer = setTimeout(() => {response.writeHead(200); response.end('late\n');}, 10000);
      response.on('close', () => clearTimeout(timer));
      return;
    }
    const status = mode.startsWith('origin-') ? Number(mode.slice(7)) : 200;
    const headers = {'Content-Type':'text/plain; charset=utf-8', 'Cache-Control':'no-store'};
    if (status === 429) headers['Retry-After'] = '1';
    if (mode === 'short-content-length') headers['Content-Length'] = '64';
    response.writeHead(status, headers);
    response.flushHeaders();
    if (['body-reset', 'short-content-length'].includes(mode)) {
      response.write('part');
      const timer = setTimeout(() => response.destroy(), 25);
      response.on('close', () => clearTimeout(timer));
      return;
    }
    if (mode === 'body-stall') {
      response.write('part');
      const timer = setTimeout(() => response.end('late\n'), 10000);
      response.on('close', () => clearTimeout(timer));
      return;
    }
    if (mode === 'delayed-complete') {
      response.write('o');
      const timer = setTimeout(() => response.end('k\n'), 30);
      response.on('close', () => clearTimeout(timer));
      return;
    }
    response.end(mode === 'empty' ? '' : status !== 200 ? `${status} fixture refusal\n` : 'ok\n');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const rows = [];
  try {
    for (const [index, mode] of modes.entries()) {
      const cache = new Map();
      const state = {mode, requests:[], puts:0, matches:0, assets:0, started:performance.now()};
      active = state;
      const url = `http://127.0.0.1:${port}/healthz?case=${index}`;
      if (mode === 'cache-hit') cache.set(url, new Response('cached\n', {headers:{'Cache-Control':'public, max-age=0, s-maxage=10'}}));
      globalThis.caches = {default:{
        async match(request) {
          state.matches++;
          if (mode === 'cache-match-failure') throw new Error('synthetic cache match failure');
          return cache.get(request.url)?.clone();
        },
        async put(request, response) {
          state.puts++;
          if (mode === 'cache-put-failure') throw new Error('synthetic cache put failure');
          cache.set(request.url, response.clone());
        },
      }};
      const env = {ASSETS:{fetch: async () => {state.assets++; throw new Error('healthz must not use snapshot');}}};
      const ctx = {waitUntil: () => assert.fail('healthz does not refresh in background')};
      const responses = [];
      for (let invocation=0; invocation<(mode === 'cache-reuse' ? 2 : 1); invocation++) {
        const response = await worker.fetch(new Request(url), env, ctx);
        responses.push({status:response.status, body:await response.text(), cache_control:response.headers.get('Cache-Control'), retry_after:response.headers.get('Retry-After')});
      }
      const brokenBody = ['body-reset','short-content-length','body-stall'].includes(mode);
      const expectedStatus = brokenBody || mode === 'header-stall' ? 503 : mode.startsWith('origin-') ? Number(mode.slice(7)) : 200;
      const expectedRequests = mode === 'cache-hit' ? 0 : mode === 'cache-put-failure' ? 2 : 1;
      const expectedBody = brokenBody || mode === 'header-stall' ? 'origin unavailable\n' : mode === 'cache-hit' ? 'cached\n' : mode === 'empty' ? '' : mode.startsWith('origin-') ? `${expectedStatus} fixture refusal\n` : mode === 'cache-put-failure' ? 'fallback healthy\n' : 'ok\n';
      const expectedPuts = ['healthy','empty','delayed-complete','cache-reuse','cache-put-failure'].includes(mode) ? 1 : 0;
      const first = responses[0];
      const cachePolicyOK = expectedStatus === 503 || expectedStatus === 404 || expectedStatus === 429 || mode.includes('failure') ? first.cache_control === 'no-store' : first.cache_control === 'public, max-age=0, s-maxage=10';
      const desired = first.status === expectedStatus && first.body === expectedBody && state.requests.length === expectedRequests && state.puts === expectedPuts && state.assets === 0 && cachePolicyOK &&
        (mode !== 'origin-429' || first.retry_after === '1') && (mode !== 'cache-reuse' || responses[1].body === 'ok\n');
      const predicted = version === 'main' && brokenBody
        ? first.status === 200 && first.body === 'fallback healthy\n' && state.requests.length === 2 && state.puts === 0 && state.assets === 0
        : desired;
      rows.push({mode, worker_invocations:responses.length, responses, origin_requests:state.requests, cache_put_attempts:state.puts,
        cache_match_attempts:state.matches, asset_calls:state.assets, elapsed_ms:performance.now()-state.started,
        matches_desired_health_body_contract:desired, matches_expected_version_observation:predicted});
    }
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    delete globalThis.caches;
  }
  assert.equal(sha(await readFile(workerPath)), sha(bytes));
  versions.push({version, worker_sha256:sha(bytes), adapted_module_sha256:sha(adapted), cases:rows.length,
    contract_matches:rows.filter(r=>r.matches_desired_health_body_contract).length,
    expected_observations_match:rows.every(r=>r.matches_expected_version_observation),
    worker_invocations:rows.reduce((n,r)=>n+r.worker_invocations,0), origin_GETs:rows.reduce((n,r)=>n+r.origin_requests.length,0),
    listener_closed:true, rows});
}
for (const item of provenance.files) assert.equal(sha(await readFile(path.join(sourceRoot,item.version,item.path))),item.sha256);
const report = {node:process.version, platform:process.platform, versions,
  cases:versions.reduce((n,v)=>n+v.cases,0), worker_invocations:versions.reduce((n,v)=>n+v.worker_invocations,0),
  origin_GETs:versions.reduce((n,v)=>n+v.origin_GETs,0), origin_POSTs:0,
  native_fetch_and_abort_timeout_unmodified:true, origin_timeout_ms:8000, all_source_blobs_unchanged:true,
  protected_key_loaded:false,
  scope:'Whole Worker with only generated routing import replaced and local Cache/ASSETS bindings. Native Node HTTP/fetch/AbortSignal; unchanged8s. Not Cloudflare workerd/deployment/TLS/CDN, actual Linux origin, general fallback bound or proof of long-term cache TTL. Only200body failures are targeted; cache-operation failures retain existing fallback policy.'};
await writeFile(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({cases:report.cases, worker_invocations:report.worker_invocations, origin_GETs:report.origin_GETs,
  versions:versions.map(({version,cases,contract_matches,expected_observations_match,origin_GETs})=>({version,cases,contract_matches,expected_observations_match,origin_GETs}))}));
assert.ok(versions.every(v=>v.expected_observations_match));
assert.equal(versions[1].contract_matches,modes.length);
