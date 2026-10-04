// Independently authored fixture checker. The reviewed external reader is not redistributed.
import fs from 'node:fs';
import crypto from 'node:crypto';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const [sourcePath, provenancePath, reportPath] = process.argv.slice(2);
if (!sourcePath || !provenancePath || !reportPath) throw new Error('Expected comment JSON, provenance JSON and output JSON paths');
const comment = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const provenance = JSON.parse(fs.readFileSync(provenancePath, 'utf8'));
const bodyHash = crypto.createHash('sha256').update(comment.body, 'utf8').digest('hex');
assert.equal(comment.id, provenance.comment_id);
assert.equal(bodyHash, provenance.body_sha256);
const blocks = [...comment.body.matchAll(/```js\r?\n([\s\S]*?)```/g)].map(m => m[1]);
const selected = blocks.filter(b => /async function readSince\(room, cursor\)/.test(b));
assert.equal(selected.length, 1);
const source = selected[0];
const cases = [];
const row = (seq, text = `record-${seq}`) => ({seq, text});
const range = (start, end) => Array.from({length: end - start + 1}, (_, i) => row(start + i));
const jsonl = rows => rows.map(r => JSON.stringify(r)).join('\n') + '\n';
const scenario = (messages, exports, readGeneration = 7) => ({
  read: {status: 200, generation: readGeneration, body: {
    generation: readGeneration, first_seq: messages[0]?.seq ?? null,
    last_seq: messages.at(-1)?.seq ?? 10, messages}},
  exports: exports.map(e => ({status: 200, generation: 7, ...e}))
});

async function exercise(name, classification, fixture, check) {
  const operations = [];
  let exportIndex = 0;
  const fakeFetch = async (url, options) => {
    const parsed = new URL(url);
    assert.equal(parsed.origin, 'https://technocore.chat');
    assert.ok(options.signal);
    assert.ok(['/r/fixture-read', '/r/fixture-read/export'].includes(parsed.pathname));
    const isExport = parsed.pathname.endsWith('/export');
    if (!isExport) {
      assert.equal(parsed.searchParams.get('since'), '10');
      assert.equal(parsed.searchParams.get('limit'), '200');
    }
    const response = isExport
      ? fixture.exports[Math.min(exportIndex++, fixture.exports.length - 1)]
      : fixture.read;
    assert.ok(response, 'Unexpected fetch: fixture exhausted');
    operations.push({lane: isExport ? 'export' : 'since', status: response.status,
      generation: response.generation});
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      headers: {get: key => key.toLowerCase() === 'x-room-generation'
        ? String(response.generation) : null},
      json: async () => JSON.parse(JSON.stringify(response.body)),
      text: async () => response.text
    };
  };
  // Reviewed source only. vm supplies fixture globals; it is not a security sandbox.
  const context = vm.createContext({fetch: fakeFetch, AbortSignal: {timeout: ms => ({timeout: ms})}, Date});
  const reader = new vm.Script(source + '\nreadSince').runInContext(context, {timeout: 1000});
  let result;
  try {
    result = JSON.parse(JSON.stringify(await reader('fixture-read', 10)));
    assert.ok(operations.length <= 4, 'Reader exceeded the fixture request budget');
    check(result, operations);
    cases.push({name, classification, passed: true, result, operations});
  } catch (error) {
    cases.push({name, classification, passed: false, failure: String(error.message), result, operations});
  }
}

const recovered = (r, last) => {
  assert.equal(r.ok, true); assert.equal(r.cursor, last);
  assert.deepEqual(r.rows.map(x => x.seq), Array.from({length: last - 10}, (_, i) => i + 11));
};
const incomplete = r => assert.equal(r.ok, false, 'Reader must not report verified recovery for this fixture');

await exercise('contiguous-since', 'control', scenario(range(11, 13), []), r => recovered(r, 13));
await exercise('tail-gap-recovered', 'control', scenario(range(13, 14), [{text: jsonl(range(11, 14))}]), r => recovered(r, 14));
await exercise('retention-floor-loss-is-explicit', 'control', scenario(range(15, 18), [{text: jsonl(range(15, 18))}]), r => {
  incomplete(r); assert.deepEqual(r.lost, [11, 14]);
});
await exercise('interior-export-loss-is-explicit', 'control', scenario(range(14, 14), [{text: jsonl([row(11), row(13), row(14)])}]), r => {
  incomplete(r); assert.deepEqual(r.lost, [12, 12]);
});
await exercise('empty-since-falls-back', 'control', scenario([], [{text: jsonl(range(11, 12))}]), r => recovered(r, 12));
await exercise('empty-export-preserves-cursor', 'control', scenario([], [{text: ''}]), (r, ops) => {
  incomplete(r); assert.equal(r.cursor, 10); assert.equal(ops.length, 4);
});
await exercise('export-503-is-bounded', 'control', scenario(range(13, 14), [{status: 503, text: 'unavailable'}]), (r, ops) => {
  incomplete(r); assert.equal(r.cursor, 10); assert.equal(ops.length, 4);
});
await exercise('failed-export-then-recovery', 'control', scenario(range(13, 14), [
  {status: 503, text: 'unavailable'}, {text: jsonl(range(11, 14))}
]), (r, ops) => { recovered(r, 14); assert.equal(ops.length, 3); });
await exercise('pre-cursor-records-excluded', 'control', scenario(range(13, 14), [{text: jsonl(range(8, 14))}]), r => recovered(r, 14));
const korean = [row(11, '한글 원문'), row(12, '\ud55c\uae00'), row(13, 'e\u0301')];
await exercise('unicode-export-preserved', 'control', scenario([korean[2]], [{text: jsonl(korean)}]), r => {
  recovered(r, 13); assert.deepEqual(r.rows, korean);
});

// These are consumer-safety requirements, not a claim every fixture occurred in production.
// The caller's persisted checkpoint is room generation 7, cursor 10.
await exercise('new-generation-on-since-must-be-distinguished', 'safety-invariant',
  scenario(range(11, 13), [], 8), incomplete);
await exercise('generation-changes-before-export-must-be-distinguished', 'safety-invariant',
  scenario(range(13, 14), [{generation: 8, text: jsonl(range(11, 14))}], 7), incomplete);
await exercise('interior-since-gap-must-not-be-success', 'safety-invariant',
  scenario([row(11), row(13)], []), incomplete);
await exercise('export-short-of-observed-head-must-not-be-complete', 'safety-invariant',
  scenario(range(14, 15), [{text: jsonl(range(11, 13))}]), incomplete);
await exercise('malformed-export-line-must-not-be-silently-discarded', 'safety-invariant',
  scenario([row(12)], [{text: JSON.stringify(row(11)) + '\nnot-json\n' + JSON.stringify(row(12)) + '\n'}]), incomplete);
await exercise('incomplete-final-export-line-must-not-be-silently-discarded', 'safety-invariant',
  scenario([row(12)], [{text: JSON.stringify(row(11)) + '\n{"seq":12,"text":"unfinished'}]), incomplete);

const report = {checked_at: new Date().toISOString(), node: process.version, platform: process.platform,
  source_url: comment.html_url, source_comment_id: comment.id, source_body_sha256: bodyHash,
  reader_sha256: crypto.createHash('sha256').update(source, 'utf8').digest('hex'),
  checker_sha256: crypto.createHash('sha256').update(fs.readFileSync(process.argv[1])).digest('hex'),
  tests: cases.length, passed: cases.filter(c => c.passed).length,
  failed: cases.filter(c => !c.passed).length, cases,
  real_network_requests: 0, production_incident_established: false, patch_proposed: false,
  full_upstream_ci: false, airdrop_eligibility: 'unconfirmed'};
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({tests: report.tests, passed: report.passed, failed: report.failed}));
process.exitCode = report.failed ? 1 : 0;
