// Apache-2.0. Execute reviewed PR #735 scripts with in-memory GitHub fixtures.
// No HTTP client, credentials, workflow approval or real comment mutation.
import fs from 'node:fs';
import crypto from 'node:crypto';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const [sourcePath, provenancePath, reportPath] = process.argv.slice(2);
if (!sourcePath || !provenancePath || !reportPath) throw new Error('Expected source, provenance and report paths');
const raw = fs.readFileSync(sourcePath);
const provenance = JSON.parse(fs.readFileSync(provenancePath, 'utf8'));
const blob = crypto.createHash('sha1').update(`blob ${raw.length}\0`).update(raw).digest('hex');
assert.equal(blob, provenance.git_blob, 'Downloaded source must match reviewed Git blob');
const yaml = raw.toString('utf8');
function extract(job) {
  const start = yaml.indexOf(`\n  ${job}:\n`);
  assert(start >= 0, `Missing ${job} job`);
  const rest = yaml.slice(start + 1);
  const next = rest.slice(1).search(/\n  [a-z][a-z-]*:\n/);
  const section = next < 0 ? rest : rest.slice(0, next + 1);
  const lines = section.split('\n');
  const line = lines.findIndex(x => /^          script: \|\s*$/.test(x));
  assert(line >= 0, `Missing exact script block for ${job}`);
  const code = [];
  for (const text of lines.slice(line + 1)) {
    if (text.startsWith('            ')) code.push(text.slice(12));
    else if (!text.trim()) code.push('');
    else break;
  }
  assert(code.join('\n').length > 200, 'Unexpectedly short extracted script');
  return new vm.Script(`(async () => {\n${code.join('\n')}\n})()`, {filename: job + '.js'});
}
const scripts = {notice: extract('ci-not-run'), clear: extract('ci-not-run-clear')};
const marker = '<!-- queue-guard-ci-not-run -->';
const CI = '.github/workflows/ci.yml';
const repo = {owner: 'flop-labs', repo: 'technocore-chat'};
const clone = x => JSON.parse(JSON.stringify(x));
const pr = (sha, sameRepo = false) => ({number: 735, state: 'open', head: {sha, repo: {full_name: sameRepo ? 'flop-labs/technocore-chat' : 'fixture/technocore-chat'}}, base: {repo: {full_name: 'flop-labs/technocore-chat'}}});
const run = (conclusion = 'action_required', sha = 'head-A') => ({path: CI, name: 'Display name is not the identifier', head_sha: sha, event: 'pull_request', status: 'completed', conclusion, pull_requests: []});
const oldNotice = (type = 'Bot') => ({id: 1, user: {type}, body: marker + '\nold notice'});

function fixture({responses = {}, comments = [], prs = [pr('head-A')]} = {}) {
  const state = {responses, comments: clone(comments), prs: clone(prs), trace: [], readCounts: {}, nextId: 2, afterCreate: null};
  function githubFor(actor) {
    const record = (call, details = {}) => state.trace.push({actor, call, ...details});
    const listComments = () => { throw new Error('Use paginate for fixture comments'); };
    const listPulls = () => { throw new Error('Use paginate for fixture pull requests'); };
    return {
      rest: {
        actions: {listWorkflowRunsForRepo: async args => {
          assert.equal(args.owner, repo.owner); assert.equal(args.repo, repo.repo);
          record('list-runs', {head: args.head_sha});
          const seq = state.responses[args.head_sha] || [[]];
          const n = state.readCounts[args.head_sha] || 0;
          state.readCounts[args.head_sha] = n + 1;
          return {data: {workflow_runs: clone(seq[Math.min(n, seq.length - 1)])}};
        }},
        issues: {
          listComments,
          createComment: async args => {
            assert.equal(args.issue_number, 735);
            const comment = {id: state.nextId++, user: {type: 'Bot'}, body: args.body};
            state.comments.push(comment); record('create', {id: comment.id});
            if (state.afterCreate) await state.afterCreate(actor);
            return {data: clone(comment)};
          },
          updateComment: async args => {
            const comment = state.comments.find(x => x.id === args.comment_id);
            assert(comment, 'Cannot update absent fixture comment');
            comment.body = args.body; record('update', {id: comment.id});
            return {data: clone(comment)};
          },
          deleteComment: async args => {
            assert(state.comments.some(x => x.id === args.comment_id), 'Cannot delete absent fixture comment');
            state.comments = state.comments.filter(x => x.id !== args.comment_id);
            record('delete', {id: args.comment_id});
          },
        },
        pulls: {list: listPulls},
      },
      paginate: async (method, args) => {
        assert.equal(args.owner, repo.owner); assert.equal(args.repo, repo.repo);
        if (method === listComments) {record('list-comments'); return clone(state.comments);}
        if (method === listPulls) {record('list-open-prs'); return clone(state.prs);}
        throw new Error('Unexpected GitHub operation');
      },
    };
  }
  async function execute(job, payload, actor = job) {
    const context = {repo, payload, eventName: job === 'notice' ? 'pull_request_target' : 'workflow_run'};
    const result = scripts[job].runInNewContext({
      github: githubFor(actor), context,
      setTimeout: (callback, milliseconds) => {state.trace.push({actor, call: 'simulated-delay', milliseconds}); callback();},
    }, {timeout: 1000});
    await result;
  }
  return {state, notice: (p = pr('head-A'), actor) => execute('notice', {pull_request: p}, actor), clear: r => execute('clear', {workflow_run: r})};
}

const results = [];
async function check(name, fn) {
  try {const evidence = await fn(); results.push({case: name, passed: true, evidence});}
  catch (error) {results.push({case: name, passed: false, assertion: error.message, evidence: error.evidence});}
}
const mutations = f => f.state.trace.filter(x => ['create', 'update', 'delete'].includes(x.call));
const marked = f => f.state.comments.filter(x => x.user.type === 'Bot' && x.body.startsWith(marker));

await check('gated-creates-one-notice-and-repeat-does-not-duplicate', async () => {
  const f = fixture({responses: {'head-A': [[run()]]}});
  await f.notice(); await f.notice(); assert.equal(marked(f).length, 1);
  assert.deepEqual(mutations(f).map(x => x.call), ['create']); return f.state.trace;
});
await check('gated-updates-existing-notice', async () => {
  const f = fixture({responses: {'head-A': [[run()]]}, comments: [oldNotice()]});
  await f.notice(); assert.equal(marked(f).length, 1); assert.equal(mutations(f)[0].call, 'update'); return f.state.trace;
});
await check('unknown-run-preserves-existing-notice', async () => {
  const f = fixture({comments: [oldNotice()]}); await f.notice();
  assert.equal(marked(f).length, 1); assert.equal(mutations(f).length, 0); assert.equal(f.state.readCounts['head-A'], 6); return f.state.trace;
});
await check('unknown-run-does-not-invent-notice', async () => {
  const f = fixture(); await f.notice(); assert.equal(mutations(f).length, 0); return f.state.trace;
});
await check('late-listed-gated-run-is-observed', async () => {
  const f = fixture({responses: {'head-A': [[], [], [run()]]}}); await f.notice();
  assert.equal(marked(f).length, 1); assert.equal(f.state.trace.filter(x => x.call === 'simulated-delay').length, 2); return f.state.trace;
});
await check('unrelated-workflow-is-not-CI', async () => {
  const f = fixture({responses: {'head-A': [[{...run(), path: '.github/workflows/queue-guard.yml'}]]}, comments: [oldNotice()]});
  await f.notice(); assert.equal(mutations(f).length, 0); return f.state.trace;
});
for (const conclusion of ['success', 'failure']) await check('observed-' + conclusion + '-clears-old-notice', async () => {
  const f = fixture({responses: {'head-A': [[run(conclusion)]]}, comments: [oldNotice()]});
  await f.notice(); assert.equal(marked(f).length, 0); return f.state.trace;
});
await check('same-repository-PR-returns-without-API-calls', async () => {
  const f = fixture(); await f.notice(pr('head-A', true)); assert.equal(f.state.trace.length, 0); return f.state.trace;
});
await check('human-marker-is-not-deleted-or-updated', async () => {
  const f = fixture({responses: {'head-A': [[run()]]}, comments: [oldNotice('User')]});
  await f.notice(); assert.equal(f.state.comments.find(x => x.id === 1).body, oldNotice('User').body);
  assert.deepEqual(mutations(f).map(x => x.call), ['create']); return f.state.trace;
});
await check('same-head-release-during-write-is-reconciled', async () => {
  const f = fixture({responses: {'head-A': [[run()], [run('success')]]}}); await f.notice();
  assert.equal(marked(f).length, 0); assert.deepEqual(mutations(f).map(x => x.call), ['create', 'delete']); return f.state.trace;
});
await check('unknown-after-write-does-not-delete-notice', async () => {
  const f = fixture({responses: {'head-A': [[run()], []]}}); await f.notice(); assert.equal(marked(f).length, 1); return f.state.trace;
});
await check('clear-ignores-gated-completion', async () => {
  const f = fixture({comments: [oldNotice()]}); await f.clear(run()); assert.equal(f.state.trace.length, 0); return f.state.trace;
});
await check('clear-ignores-main-push', async () => {
  const f = fixture({comments: [oldNotice()]}); await f.clear({...run('success'), event: 'push'}); assert.equal(f.state.trace.length, 0); return f.state.trace;
});
await check('clear-resolves-fork-head-with-empty-pull-request-array', async () => {
  const f = fixture({comments: [oldNotice()]}); await f.clear(run('failure')); assert.equal(marked(f).length, 0); return f.state.trace;
});
await check('clear-for-old-head-preserves-new-head-notice', async () => {
  const f = fixture({comments: [oldNotice()], prs: [pr('head-B')]}); await f.clear(run('success', 'head-A'));
  assert.equal(marked(f).length, 1); assert.equal(mutations(f).length, 0); return f.state.trace;
});
await check('older-notice-job-must-not-remove-newer-gated-head-notice', async () => {
  const repetitions = [];
  for (let i = 0; i < 5; i++) {
    const f = fixture({responses: {'head-A': [[run()], [run('success')]], 'head-B': [[run('action_required', 'head-B')]]}});
    f.state.afterCreate = async actor => {
      if (actor !== 'older-A') return;
      f.state.afterCreate = null;
      f.state.prs = [pr('head-B')];
      await f.notice(pr('head-B'), 'newer-B');
    };
    await f.notice(pr('head-A'), 'older-A');
    repetitions.push({current_head: 'head-B', current_CI_conclusion: 'action_required', remaining_notices: marked(f).length, trace: f.state.trace});
  }
  const observed = repetitions.map(x => x.remaining_notices);
  if (observed.some(count => count !== 1)) {
    const error = new Error('Current head B remains gated, but older head A removes its shared notice in all five controlled interleavings');
    error.evidence = repetitions; throw error;
  }
  return repetitions;
});

const report = {
  checked_at: new Date().toISOString(), node: process.version, platform: process.platform,
  source: provenance, source_sha256: crypto.createHash('sha256').update(raw).digest('hex'),
  checker_sha256: crypto.createHash('sha256').update(fs.readFileSync(process.argv[1])).digest('hex'),
  scope: 'Execute two unchanged embedded github-script bodies against in-memory GitHub API fixtures',
  cases: results.length, passed: results.filter(x => x.passed).length, failed: results.filter(x => !x.passed).length,
  real_network_requests: 0, real_comment_writes: 0, workflow_approvals: 0,
  full_upstream_CI: false, actual_GitHub_Actions_runtime: false, workflow_triggers_and_permissions_tested: false,
  results,
};
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify({cases: report.cases, passed: report.passed, failed: report.failed,
  findings: results.filter(x => !x.passed).map(x => ({case: x.case, assertion: x.assertion}))}));
process.exitCode = report.failed ? 1 : 0;
