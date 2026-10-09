// Independently authored native HTTP checker; Workers Cache API is an explicit substitute.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const [base, origin, output] = process.argv.slice(2);
assert.ok(output, 'Expected source root, loopback origin, and output file');
const nativeFetch = globalThis.fetch;
const originalCaches = globalThis.caches;
const A = 'https://allowed-a.example';
const B = 'https://allowed-b.example';
const D = 'https://denied.example';
const input = (site = null, query = '', method = 'GET', extra = {}) => ({site, query, method, extra});
const scenarios = [
  {name: 'no-origin-query-collapse', requests: [input(null, '?n=1'), input(null, '?n=2'), input(null, '?n=%E2%98%83&x=3')], originCalls: 1},
  {name: 'no-origin-exact-cache-hit', requests: [input(), input()], originCalls: 1},
  {name: 'allowed-a-b-a-same-key', requests: [input(A), input(B), input(A)]},
  {name: 'allowed-b-a-same-key', requests: [input(B), input(A)]},
  {name: 'no-origin-then-allowed', requests: [input(), input(A)]},
  {name: 'allowed-then-no-origin', requests: [input(A), input()]},
  {name: 'denied-then-allowed', requests: [input(D), input(A)]},
  {name: 'allowed-then-denied', requests: [input(A), input(D)]},
  {name: 'empty-origin-then-allowed', requests: [input(''), input(A)]},
  {name: 'allowed-query-variants', requests: [input(A, '?n=1'), input(B, '?n=2'), input(A, '?x=%ED%95%9C%EA%B8%80')]},
  {name: 'allowed-same-site-repeat', requests: [input(A, '?n=1'), input(A, '?n=1')]},
  {name: 'denied-repeat', requests: [input(D), input(D)]},
  {name: 'head-allowed-sites', requests: [input(A, '?n=1', 'HEAD'), input(B, '?n=2', 'HEAD')], originCalls: 2},
  {name: 'preflight-allowed-sites', requests: [input(A, '', 'OPTIONS', {'Access-Control-Request-Method': 'GET'}), input(B, '', 'OPTIONS', {'Access-Control-Request-Method': 'GET'})], originCalls: 2},
  {name: 'post-not-cached', requests: [input(A, '', 'POST'), input(B, '', 'POST')], originCalls: 2},
  {name: '503-not-cached', requests: [input(null, '', 'GET', {'X-Status': '503'}), input(null, '', 'GET', {'X-Status': '503'})], originCalls: 2},
];

class VaryCacheFixture {
  constructor() { this.entries = []; this.matches = 0; this.puts = 0; this.hits = 0; }
  async match(request) {
    this.matches++;
    const row = this.entries.find(entry => entry.url === request.url &&
      entry.vary.every(name => entry.headers.get(name) === request.headers.get(name)));
    if (!row) return undefined;
    this.hits++;
    return row.response.clone();
  }
  async put(request, response) {
    assert.equal(request.method, 'GET');
    this.puts++;
    const vary = (response.headers.get('Vary') ?? '').split(',').map(name => name.trim().toLowerCase()).filter(Boolean);
    assert.ok(!vary.includes('*'));
    this.entries = this.entries.filter(entry => !(entry.url === request.url &&
      entry.vary.every(name => entry.headers.get(name) === request.headers.get(name))));
    this.entries.push({url: request.url, headers: new Headers(request.headers), vary, response: response.clone()});
  }
}

async function load(label) {
  const source = await fs.readFile(`${base}/${label}/edge/src/worker.js`);
  const routing = JSON.parse(await fs.readFile(`${base}/${label === 'proposed' ? 'candidate' : label}/routing-fixture.json`, 'utf8'));
  const binding = 'import ROUTING from "./routing.json";';
  const text = source.toString('utf8');
  assert.equal(text.split(binding).length, 2);
  // Only the deployment's generated JSON binding changes; execute the whole Worker module.
  const bound = text.replace(binding, `const ROUTING = ${JSON.stringify(routing)};`);
  const worker = (await import(`data:text/javascript;base64,${Buffer.from(bound).toString('base64')}#${label}`)).default;
  return {worker, source_sha256: crypto.createHash('sha256').update(source).digest('hex'), routing};
}

const results = [];
const sourceMetadata = {};
try {
  for (const label of ['main', 'candidate', 'proposed']) {
    const loaded = await load(label);
    sourceMetadata[label] = {source_sha256: loaded.source_sha256, routing: loaded.routing};
    for (const scenario of scenarios) {
      await nativeFetch(`${origin}/reset`, {method: 'POST'});
      const cache = new VaryCacheFixture();
      let fetches = 0;
      globalThis.caches = {default: cache};
      globalThis.fetch = async (request, options) => {
        fetches++;
        assert.equal(new URL(request.url).origin, origin);
        assert.equal(new URL(request.url).pathname, '/healthz');
        return nativeFetch(request, options);
      };
      const observations = [];
      const failures = [];
      for (const [position, row] of scenario.requests.entries()) {
        const headers = new Headers({'X-Probe': 'native-cors-boundary', ...row.extra});
        if (row.site !== null) headers.set('Origin', row.site);
        const request = new Request(`${origin}/healthz${row.query}`, {method: row.method, headers});
        const response = await loaded.worker.fetch(request, {
          ASSETS: {fetch: async () => assert.fail('No static fallback is permitted for health checks')}
        }, {waitUntil: () => assert.fail('Health checks must not enter the rooms revalidation lane')});
        const body = await response.text();
        const expectedOrigin = [A, B].includes(row.site) ? row.site : null;
        const expectedStatus = row.method === 'POST' ? 405 : row.extra['X-Status'] === '503' ? 503 : 200;
        const expectedBody = row.method === 'HEAD' ? '' : row.method === 'OPTIONS' ? 'OK' :
          row.method === 'POST' ? 'Method Not Allowed' : expectedStatus === 503 ? 'busy\n' : 'ok\n';
        const observed = {position, ...row, status: response.status, body,
          acao: response.headers.get('Access-Control-Allow-Origin'), vary: response.headers.get('Vary'),
          cache_control: response.headers.get('Cache-Control'), expectedOrigin};
        observations.push(observed);
        if (observed.acao !== expectedOrigin) failures.push(`request${position}: ACAO=${observed.acao}, expected ${expectedOrigin}`);
        if (response.status !== expectedStatus || body !== expectedBody) failures.push(`request${position}: status/body contract`);
        if (label === 'proposed' && row.method === 'GET' && row.site !== null && expectedStatus === 200 && observed.cache_control !== 'no-store') {
          failures.push(`request${position}: caller-specific successful GET is not no-store`);
        }
      }
      const log = await (await nativeFetch(`${origin}/audit`)).json();
      assert.equal(log.length, fetches, 'Worker fetch count must equal actual native HTTP requests');
      if (scenario.originCalls !== undefined && fetches !== scenario.originCalls) failures.push(`origin calls${fetches}, expected${scenario.originCalls}`);
      if (log.some(row => row.probe !== 'native-cors-boundary')) failures.push('origin request headers were dropped');
      const canonicalQuery = label !== 'main' && scenario.requests.every(row => row.method === 'GET');
      if (canonicalQuery && log.some(row => row.query !== '')) failures.push('ignored query was sent to origin');
      if (label === 'proposed' && scenario.requests.every(row => row.method === 'GET' && row.site !== null)) {
        if (cache.matches || cache.puts || fetches !== scenario.requests.length) failures.push('Origin-bearing GET touched shared cache or was not independently fetched');
      }
      results.push({label, scenario: scenario.name, passed: failures.length === 0, failures,
        observations, origin_requests: log, fetches, cache_matches: cache.matches, cache_hits: cache.hits,
        cache_puts: cache.puts, cache_entries: cache.entries.length});
    }
  }
} finally {
  globalThis.fetch = nativeFetch;
  if (originalCaches === undefined) delete globalThis.caches;
  else globalThis.caches = originalCaches;
}
const summaries = Object.fromEntries(['main', 'candidate', 'proposed'].map(label => {
  const rows = results.filter(row => row.label === label);
  return [label, {scenarios: rows.length, passed: rows.filter(row => row.passed).length,
    failed: rows.filter(row => !row.passed).length, native_origin_requests: rows.reduce((sum, row) => sum + row.fetches, 0)}];
}));
const report = {completed_at: new Date().toISOString(), node: process.version, platform: process.platform,
  source_metadata: sourceMetadata, checker_sha256: crypto.createHash('sha256').update(await fs.readFile(process.argv[1])).digest('hex'),
  native_fetch: true, origin: 'Actual Starlette CORSMiddleware + Uvicorn on loopback',
  origin_policy: {allowed: [A, B], credentials: false}, cache_api: 'In-memory substitute modeling URL and Vary request-header matching; no TTL/eviction/isolate/deployed Cache API test',
  complete_worker_script_executed: true, routing_binding_supplied: true, cloudflare_runtime_executed: false,
  actual_browser_cors_enforcement_executed: false, full_repository_ci: false, protected_user_key_used_by_tests: false,
  remote_technocore_requests_by_tests: 0, summaries, results};
await fs.writeFile(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(summaries));
assert.equal(summaries.proposed.failed, 0, 'Proposal must satisfy all local scenario expectations');
