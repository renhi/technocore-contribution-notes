// Independently authored Windows/Node native-fetch probe; source is loaded separately.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import http from 'node:http';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';

const [beforePath, afterPath, provenancePath, outputPath] = process.argv.slice(2);
if (!outputPath) throw new Error('Expected before Worker, after Worker, provenance and report paths');
const provenance = JSON.parse(await fs.readFile(provenancePath, 'utf8'));
const nativeFetch = globalThis.fetch;
const originalCaches = globalThis.caches;
const cases = [];
const modes = ['healthy', 'empty', 'refused', 'head', 'cached', 'cache-match-error',
  'body-stall', 'body-reset', 'invalid-gzip'];

async function loadWorker(path, label) {
  const raw = await fs.readFile(path);
  const pinned = provenance.files.find(p => p.label === label);
  assert.ok(pinned);
  assert.equal(crypto.createHash('sha256').update(raw).digest('hex'), pinned.sha256);
  assert.equal(crypto.createHash('sha1').update(Buffer.concat([
    Buffer.from(`blob ${raw.length}\0`), raw])).digest('hex'), pinned.git_blob);
  const source = raw.toString('utf8');
  const binding = 'import ROUTING from "./routing.json";';
  assert.equal(source.split(binding).length, 2);
  assert.ok(source.includes('const ORIGIN_TIMEOUT_MS = 8000;'));
  const bound = source.replace(binding,
    'const ROUTING = {static_first: [], edge_cached: {"/healthz": 10}, types: {}};');
  // Only the routing platform binding is supplied. The production 8000ms deadline is unchanged.
  return (await import(`data:text/javascript;base64,${Buffer.from(bound).toString('base64')}#${label}`)).default;
}

async function exercise(worker, label, mode) {
  let calls = 0;
  let seen = 0;
  let puts = 0;
  const fetches = [];
  const server = http.createServer((request, response) => {
    seen++;
    assert.equal(request.url, '/healthz');
    const headers = {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store'};
    if (seen === 1 && mode === 'body-stall') {
      response.writeHead(200, headers);
      response.flushHeaders();
      response.write('partial'); // Native fetch resolves at headers, then waits for the real deadline.
      return;
    }
    if (seen === 1 && mode === 'body-reset') {
      response.writeHead(200, {...headers, 'Content-Length': '99'});
      response.flushHeaders();
      response.write('partial');
      setTimeout(() => response.destroy(), 20);
      return;
    }
    if (seen === 1 && mode === 'invalid-gzip') {
      const body = Buffer.from('not a gzip stream');
      response.writeHead(200, {...headers, 'Content-Encoding': 'gzip', 'Content-Length': String(body.length)});
      response.end(body);
      return;
    }
    const body = mode === 'empty' ? '' : mode === 'refused' ? 'busy\n' : 'ok\n';
    response.writeHead(mode === 'refused' ? 503 : 200, {...headers, 'Content-Length': String(Buffer.byteLength(body))});
    response.end(request.method === 'HEAD' ? undefined : body);
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const port = server.address().port;
  const url = `http://127.0.0.1:${port}/healthz`;
  globalThis.caches = {default: {
    match: async () => {
      if (mode === 'cache-match-error') throw new Error('fixture cache unavailable');
      return mode === 'cached' ? new Response('cached\n') : undefined;
    },
    put: async (_request, response) => { puts++; await response.arrayBuffer(); }
  }};
  globalThis.fetch = async (request, options) => {
    calls++;
    assert.equal(new URL(request.url).origin, `http://127.0.0.1:${port}`);
    assert.equal(new URL(request.url).pathname, '/healthz');
    fetches.push({attempt: calls, method: request.method, has_deadline_signal: Boolean(options?.signal)});
    return nativeFetch(request, options);
  };
  const started = performance.now();
  let watchdog;
  let result;
  try {
    const response = await Promise.race([
      worker.fetch(new Request(url, {method: mode === 'head' ? 'HEAD' : 'GET'}), {
        ASSETS: {fetch: async () => assert.fail('Health must never be answered from stored assets')}
      }, {}),
      new Promise((_, reject) => {
        watchdog = setTimeout(() => reject(new Error('Harness 20s watchdog exceeded')), 20000);
      })
    ]);
    const body = await response.text();
    result = {label, mode, status: response.status, body, calls, server_requests: seen, puts,
      cache_control: response.headers.get('Cache-Control'), elapsed_ms: Number((performance.now() - started).toFixed(2)),
      fetches};
    try {
      const fault = ['body-stall', 'body-reset', 'invalid-gzip'].includes(mode);
      const expectedCalls = mode === 'cached' ? 0 : 1;
      assert.equal(calls, expectedCalls, 'One request must not escape into a second unbounded origin fetch');
      assert.equal(seen, expectedCalls, 'Native HTTP request count must match');
      assert.equal(response.status, fault || mode === 'refused' ? 503 : 200);
      assert.equal(body, fault ? 'origin unavailable\n' : mode === 'refused' ? 'busy\n'
        : mode === 'head' || mode === 'empty' ? '' : mode === 'cached' ? 'cached\n' : 'ok\n');
      assert.equal(puts, ['healthy', 'empty'].includes(mode) ? 1 : 0);
      if (fault) assert.equal(result.cache_control, 'no-store');
      if (mode === 'healthy' || mode === 'empty') assert.equal(result.cache_control, 'public, max-age=0, s-maxage=10');
      if (mode === 'cache-match-error') assert.equal(fetches[0].has_deadline_signal, false,
        'Existing cache-error fail-open policy is outside this patch');
      else assert.ok(fetches.every(f => f.has_deadline_signal));
      if (mode === 'body-stall') assert.ok(result.elapsed_ms >= 7500 && result.elapsed_ms < 14000,
        'Original 8s deadline should be observable within an explicit local tolerance');
      result.passed = true;
    } catch (error) {
      result.passed = false;
      result.failure = error.message;
    }
  } catch (error) {
    result = {label, mode, passed: false, failure: String(error.message), calls, server_requests: seen, puts,
      elapsed_ms: Number((performance.now() - started).toFixed(2)), fetches};
  } finally {
    clearTimeout(watchdog);
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    globalThis.fetch = nativeFetch;
    if (originalCaches === undefined) delete globalThis.caches;
    else globalThis.caches = originalCaches;
  }
  cases.push(result);
  console.log(JSON.stringify({label, mode, passed: result.passed, calls: result.calls,
    status: result.status, elapsed_ms: result.elapsed_ms}));
}

const startedAt = new Date().toISOString();
const before = await loadWorker(beforePath, 'before');
const after = await loadWorker(afterPath, 'after');
for (const [label, worker] of [['before', before], ['after', after]]) {
  for (const mode of modes) await exercise(worker, label, mode);
}
const summaries = Object.fromEntries(['before', 'after'].map(label => {
  const selected = cases.filter(c => c.label === label);
  return [label, {tests: selected.length, passed: selected.filter(c => c.passed).length,
    failed: selected.filter(c => !c.passed).length}];
}));
const report = {started_at: startedAt, completed_at: new Date().toISOString(), node: process.version,
  platform: process.platform, source_provenance: provenance, origin_timeout_ms_unchanged: 8000,
  native_fetch_used: true, loopback_only: true, remote_service_requests: 0,
  routing_binding_supplied: true, cache_api_in_memory: true, cloudflare_runtime_executed: false,
  full_upstream_ci: false, new_patch_proposed: false, airdrop_eligibility: 'unconfirmed',
  checker_sha256: crypto.createHash('sha256').update(await fs.readFile(process.argv[1])).digest('hex'),
  summaries, cases};
await fs.writeFile(outputPath, JSON.stringify(report, null, 2) + '\n');
assert.equal(summaries.before.failed, 3, 'Only the three native response-body faults should fail on main');
assert.equal(summaries.after.failed, 0, 'Candidate must pass the complete native matrix');
console.log(JSON.stringify(summaries));
