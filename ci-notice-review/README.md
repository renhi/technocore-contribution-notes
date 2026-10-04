# Behavioural review of Technocore's pending-CI notice (PR #735)

Prepared by renhi with Codex assistance on 2026-10-04. This companion executes the two existing embedded JavaScript bodies from [PR #735](https://github.com/flop-labs/technocore-chat/pull/735) against in-memory GitHub API fixtures. It addresses the behavioural-test limitation explicitly discussed by the author and reviewers; it does not introduce a competing workflow or change the approval gate.

Credit: WIZARDspace wrote the feature; yukkie3276 and Minh3132 raised lifecycle/race concerns; osr21 and the author identified the limits of structural tests. This builds on those reviews with executable controls and an additional cross-head interleaving, rather than claiming the whole race category as a new discovery.

## Pinned source and actual result

- Candidate: `f45dd7b9229c3c6636c477d49087a2c03c80dcfa`.
- File: `.github/workflows/queue-guard.yml` from `WIZARDspace/technocore-chat`.
- `source-provenance.json` records the Git blob; the checker verifies it before extracting either script. `behaviour-results.json` also records SHA-256 hashes and the Node version.
- Actual Windows run: **17 cases, 16 passed, 1 failed invariant**.
- The failing case uses five controlled repetitions; all finish with **zero notices while the current head's CI is still `action_required`**.

These numbers describe the embedded scripts in a fixture, not the full upstream suite or a deployed Actions workflow. Exit 1 from the checker intentionally reports the reproduced invariant failure. There is no proposed fix or after-fix result in this package.

## The failing interleaving

The `ci-not-run` post-write reconciliation is tied to its event's old `pr.head.sha`, but it deletes a comment using a shared marker with no head identity. Two `synchronize` jobs can overlap:

1. Job A observes head A's CI as `action_required` and creates the marker comment.
2. Before A performs its post-write recheck, the PR advances to head B.
3. Job B observes B as `action_required`. It reuses the same notice (the fixed body is identical), rechecks B and returns with the notice present.
4. Job A resumes and finds **A's** CI now successful.
5. Job A locates the shared marker and deletes it. Head B remains gated with no notice.

The harness injects B after A's fixture comment has been committed but before A's awaited create call returns. This represents A being delayed at an asynchronous boundary; B's actual unchanged script runs fully before A resumes. No sleeps or real GitHub requests are used. The JSON trace records each job, head query and comment operation.

The existing `ci-not-run-clear` job handles an old completion event correctly in a separate positive control: it finds no open PR whose current head matches A and leaves B's notice alone. The demonstrated failure is the **older posting job's own post-write deletion**, not that clear-job branch.

The pinned YAML has no concurrency group. GitHub documents that jobs/workflow runs can overlap by default: [workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency). This supports the scheduling premise; it does not establish that the failure has occurred in production.

## Passing controls

The other 16 cases cover creating/updating/deduplicating a notice, unknown or late-listed CI, matching CI by path, success/failure cleanup, same-repository early return, preservation of a human's marker, reconciliation when the **same** head is released during the write, unknown post-write state, push/gated completion exclusions, fork completion with an empty `pull_requests` array, and preservation of a newer-head notice by the clear job.

## Reproduce — reviewer or assisting agent

Use Node.js 24 (the actual run used the version recorded in the report). No package install is needed. Download and review the pinned workflow from:

https://raw.githubusercontent.com/WIZARDspace/technocore-chat/f45dd7b9229c3c6636c477d49087a2c03c80dcfa/.github/workflows/queue-guard.yml

Then run:

```text
node test_notice_behaviour.mjs queue-guard.yml source-provenance.json results.json
```

The script rejects a source Git blob mismatch. The beginner operator does not need to type commands; their assisting agent does this. Only run reviewed source. Node's `vm` is used to supply mock globals; it is not advertised as a security sandbox for arbitrary untrusted code.

## Requested review direction and limits

Please make notice reconciliation aware of the current PR head across overlapping posting jobs and preserve a current gated head's notice. The controlled cross-head trace is available as a regression. Merely re-reading A's run again cannot establish B's state. No particular patch is claimed correct here; it needs the author's design and regression review.

No actual GitHub comment was created, edited or deleted by the checker. No approval, setting change, credential, Technocore write or transaction was used. Workflow triggers, job permissions, Actions scheduling and the GitHub runner were not executed; the tests drive the two script bodies directly. Official adoption, other users' usage and airdrop eligibility are unconfirmed.

## 한국어 안내

공식 기여가 바로 반영되지 않는 이유 중 하나는 자동 검사가 관리자 승인을 기다리는 것입니다. 이번 자료는 그 상태를 알려주는 알림 기능을 검사했습니다. 이전 수정본 작업과 새 수정본 작업이 겹치면, 이전 작업이 아직 필요한 새 알림을 지우는 상황이 가짜 GitHub 환경에서 재현됐습니다. 실제 댓글을 반복해서 보내거나 지우지는 않았습니다. 재현 자료를 제공하는 기여이며, 운영 서비스에서 실제로 발생했다거나 수정까지 끝났다고 주장하지 않습니다.

Code: Apache-2.0; see the companion repository's root LICENSE.
