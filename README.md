# Technocore PR #238 — offline regression contribution

Published companion materials; upstream acceptance is pending. This is a companion test suite and minimal patch for an existing proposal, not a competing verifier implementation or an airdrop registration tool.

## Credit and scope

- Original verifier: [dhasap, PR #238](https://github.com/flop-labs/technocore-chat/pull/238).
- Existing canonical-signature finding: [osr21's review comment](https://github.com/flop-labs/technocore-chat/pull/238#issuecomment-5512590300).
- This contribution adds CLI regression coverage, a proposed patch, and before/after evidence. Prepared with Codex assistance for the user-provided GitHub account [renhi](https://github.com/renhi). Publication and review receipts are tracked separately.

Review target: `93bdfd0331de9c30c2693141a0ce166cfb69f186`, `scripts/verify.py`.
Main reference: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`, `src/didkey.py`.

The candidate accepts nonzero base64url pad bits, unlike the official verifier. The patch restricts the final character to `AQgw` and updates the malformed-input diagnostic. The live service is not claimed to be vulnerable; the unmodified main verifier already rejects these encodings.

## Evidence

Windows, Python 3.12.14, cryptography 50.0.1. The offline main reference additionally used PyNaCl 1.6.2. The CLI suite itself depends only on cryptography and Python's standard library.

| Run | Test methods | CLI cases | Mismatched outcomes |
|---|---:|---:|---:|
| Pinned original PR | 9 | 47 | 30 |
| With proposed patch | 9 | 47 | 0 |

The 30 mismatches are all 15 alternative pad-bit spellings for a genuine signature on each of the `say` and `set` lanes. They decode to the same bytes but should be rejected as malformed with exit 2. Other cases cover Korean text, a 19-digit nonce above JavaScript's exact integer range, zero nonce as an offline tuple, Unicode sweeping, changed content/context, wrong key, malformed DID/signature, and invalid nonce spelling. The suite uses freshly generated disposable keys only in memory.

The unmodified main verifier was checked offline separately: two canonical signatures accepted, 30 aliases rejected as malformed. The regression suite was entirely offline; full upstream server/CI checks were not run. Separate publication uses the production DID, as recorded in public-identity.json. Offline verification does not test server replay counters or contribution eligibility.

## Files

- `canonical-signature.patch`: narrow patch for the pinned candidate, not main.
- `test_verify_cli.py`: standalone CLI regression suite, suitable for adaptation to upstream's test layout.
- `before.json`, `after.json`: individual observed CLI results.
- `validation.json`: environment, source hashes, revisions, limits and summary.
- `review-comment.en.md`: submitted follow-up for the existing PR, with prior discovery credited.
- `evidence-ledger.json`: publication receipts and artifact hashes; not an official proof schema.

## Reproduce — for reviewers or the assisting agent

The beginner operator does not need to type these commands. In a Python 3.12+ environment with cryptography, point the suite at the exact original or patched candidate:

```text
python test_verify_cli.py --verifier /path/to/scripts/verify.py --json-report results.json
```

The original must fail with 30 mismatched cases. Applying `canonical-signature.patch` to the pinned candidate must produce zero mismatches. Read the file before running any downloaded script, and re-check the PR head and discussion before submitting work. Do not treat a changed target as the reviewed version.

## 한국어 안내

이 자료는 다른 사람이 제안한 도구에 검사를 보태는 기여 자료입니다. 같은 문제를 먼저 발견한 분을 밝혔으며, 새 발견이라고 주장하지 않습니다. 본인 DID나 지갑을 만들지 않고, 서버에 글을 보내지 않고 검사했습니다. 검사 통과는 에어드랍 자격을 뜻하지 않습니다. 게시 이후의 검토·채택 여부는 별도 기록으로 확인합니다.

## Prepared operator identity

Public DID: `did:key:z6MkgEXs2orgM1daYv7jk42one2mKbo54ecoSx1PPmx97UoM`. `public-identity.json` and `identity-check.json` contain only public identity/signature data. The local check proves possession of the key, not GitHub ownership or airdrop eligibility. The regression suite still uses disposable test keys. This package follows the upstream Apache-2.0 license (see `LICENSE`).

## Publication receipts

- [Submitted PR follow-up](https://github.com/flop-labs/technocore-chat/pull/238#issuecomment-5928199715).
- [Public DID note](https://technocore.chat/kv/did-da/cadf96e18768c8), world-writable and unsigned.
- [Technocore room](https://technocore.chat/r/technocore), announcement sequence `13943024`. The room is a rolling buffer; the exact signed record and canonical input are preserved in `public-identity.json` and were verified using the pinned official verifier.

Publication is complete. Upstream review, adoption and airdrop eligibility remain unconfirmed.

## Follow-up documentation correction — 2026-10-01

There has been no new reviewer response and the PR head is unchanged. The existing osr21 review also identified an inaccurate record-persistence description; `review-completion.patch` now addresses it together with the original encoding fix. Apply the combined patch **instead of** `canonical-signature.patch`; do not apply both.

Newer signed message records retain `from`, `sig` and integer `nonce`. Legacy records missing `sig` are not re-verifiable. If a nonce was originally signed as `007`, stored `7` cannot reconstruct that tuple. The verifier remains an explicit-tuple CLI without fetching records or checking server replay admission. Ordinary note reads are not claimed to retain these message fields.

The combined patch applies to the pinned PR source. The unchanged 47-case suite passes; three additional direct offline checks cover the actual previously published signature and the original-versus-normalized leading-zero nonce boundary. All 50 observed outcomes match expectations. `followup-after.json` holds the 47 automated results; `followup-validation.json` records the three supplementary checks and source/patch scope. The historical `before.json`, `after.json`, and `validation.json` remain the original run records. No additional Technocore message or full upstream CI was performed for the follow-up. The existing PR comment is updated rather than creating another comment or competing PR.

## Reusable MCP onboarding example

A separate [read-only agent onboarding example](adoption/README.md) helps another assisting agent connect to the official Technocore MCP. It performed four real read-tool calls without a signing key or wallet; its report contains checksums instead of participants' messages. This is distinct from the PR #238 regression contribution and creates no settled-spend or airdrop eligibility record.

The example now also provides a tested hosted HTTP client for agents that do not
launch a local MCP subprocess, plus a [Korean beginner guide](adoption/한국어-연결-안내.md).
The hosted path passed four real read calls and nine separate offline tests.
Its report preserves the advertised-versus-reported version discrepancy.

## Windows validation of a newer MCP fix — 2026-10-03

[PR #944 Windows review](redirect-review/README.md) independently exercises the
unchanged urllib transport and shared request layer through two local HTTP origins.
The same 27-case checker has 16 expected failures on pinned main and zero failures
on the pinned PR head. It covers redirected writes before/after fixture storage,
missing Location, read controls and Korean JSON. No hosted writes or production
keys are used. The original fix is credited to Bornoz and the integrated Worker
supplement to almondous; this companion adds Windows evidence only.

## Behavioural pending-CI notice review — 2026-10-04

[PR #735 behavioural evidence](ci-notice-review/README.md) executes the two unchanged
embedded JavaScript bodies against in-memory GitHub API fixtures. Sixteen controls
pass; a cross-head notice-deletion invariant fails in five controlled repetitions.
This adds an executable reproduction to earlier lifecycle/race reviews. It does
not change the workflow, claim a deployed incident or establish an airdrop score.


## Reader recovery boundaries — 2026-10-05

[Independent issue #919 reader fixture review](reader-review/README.md): 10 controls pass; six additional consumer-safety requirements remain unmet in the corrected discussion example. Generation transitions, interior gaps, observed-head coverage and malformed lines are scoped separately. No production incident, adopted client, replacement fix or airdrop credit is claimed. The external source is fetched separately, not redistributed.


### Reader review follow-up: rate-limit guidance

The current reader-review report has 17 fixtures: 10 controls pass, seven consumer-safety requirements are unmet. The additional fixture shows that an export 429 with Retry-After 60 is retried three times without waiting/defer. Only in-memory responses were used. The preceding 16-case record is historical.


## Windows native health-response validation — 2026-10-05

[PR #957 native transport evidence](healthz-review/README.md): the unchanged 8-second deadline and real loopback HTTP/native fetch were exercised on Windows. Same nine modes: main 6 pass/3 fail; candidate 9 pass/0 fail. Stalled bodies, reset sockets and invalid gzip show the extra main fallback request removed by the candidate. Cloudflare runtime/full CI/production behavior were not claimed. Original fix and earlier tests remain credited to their authors.


## PR #238 project-test integration (2026-10-06)

[Executable integration packet](verifier-integration/README.md) adds the correction and pytest integration of the byte-identical original 47-case fixture, 128 server/CLI terminal comparisons, and original-nonce spelling regressions. On pinned current main 0e47f770, 139 pytest items pass (179 CLI invocations). The unchanged original verifier produces 121 failures / 18 passes. A corrected but stale PR-head checkout still produces 120 server-parity failures; rebase to current main before incorporating the extension. Project lint, formatting and core caps passed; ty was blocked by Windows sandbox canonicalization and the full coverage suite could not collect without Linux fcntl. The official PR has not been updated, upstream CI was not run, and no adoption or airdrop eligibility is implied. Credit: dhasap (verifier), osr21 (canonical-signature finding), renhi (test integration and independent validation).


## External receipts tool: integer nonce recovery (2026-10-06)

[Independent reproduction and proposed correction](receipts-review/README.md) reviews HE-Lingfeng/technocore-receipts e0782019, introduced in upstream issue #965. A tuple signed with nonce 007 can be stored as integer 7 and falsely fail the auditor. The proposed bounded recovery accepts only a cryptographically verified original spelling (at most 19 checks), preserves exact string handling and numeric ordering, and records recovered versus stored nonce. Original 40 author tests pass unchanged; nine new methods cover 76 fixtures (original 34 matched / 42 unmet, candidate all 76 matched); combined candidate suite has 49 passing methods. Synthetic offline evidence only; no full native-server CI, live participant records, user keys, upstream changes, new PR/comments, adoption or airdrop eligibility. Credit to HE-Lingfeng for the auditor and original tests.


## Korean Windows signer validation (PR #966)
See [signer-encoding-review](signer-encoding-review/) for a native Windows CP949/CP932/ASCII/CP1252/UTF-8 matrix of Packae's existing fix. 40 child-process runs: base 14 successful / 6 known encoding failures; candidate 20 successful. Also 34 valid signatures, 34 tamper rejections and 42 note-consumer assertions. No production writes, full Linux CI, adoption or reward claim.


## Native CPython export framing review (PR #842)
See [export-framing-review](export-framing-review/) for a real Windows loopback HTTP regression and scoped Content-Length/exception correction. Original head14/20 expectations matched; proposal19/20. One missing chunked terminator remains unresolved, explicitly documented. No full Linux/MCP SDK CI, production writes, upstream change or airdrop claim.


## Native Windows MCP IPv6 compatibility (PR #946)
See [ipv6-bind-review](ipv6-bind-review/) for real MCP initialize/tools-list and Host/Origin guards on seven working Windows listener spellings. Both main and PR head work here, including bracketed IPv6: the reported startup defect was NOT reproduced on this Windows machine. An eighth setting (127.1) is unsupported here in both versions. No upstream source edits, tool calls, public-service requests, Linux CI or airdrop claim.


## Native Windows MCP nonce recovery (PR #930)
See [nonce-transport-review](nonce-transport-review/) for actual MCP/urllib HTTP and upstream PyNaCl checks against a controlled local origin. The existing PR's recovery gap appears in nine scenarios: main18/27, candidate27/27. All78 origin signatures verify, 78 altered canonicals refuse; external signatures and tested 429/422/409 bodies are not retried. The origin is a scripted fixture, not the real Linux server. No live-service calls, user keys, source edits, full Linux CI or airdrop claim.


## Windows header configuration boundary matrix (PR #923)
See [header-config-review](header-config-review/) for 418 native process imports per version, covering the representable ASCII alphabet, embedded Latin-1, Unicode lookalikes, Korean text and all HTTP token punctuation. The existing PR candidate matches all418 expected outcomes; main matches 175/418. Credit RobGenins for the fix and bdunn77 for earlier validation. This expands offline Windows configuration evidence; it does not run the Linux app, proxy, full CI or production requests, and carries no airdrop claim.


## DID-linked follow-up evidence index (2026-10-09)
See [the evidence index](did-updates/2026-10-09/) for twelve later evidence bundles pinned to immutable source/results, with the limitations retained. The initial signed PR238 announcement is not repeated. A subsequent signed Technocore delivery record is saved in that directory when verified; signatures show key possession, not acceptance or rewards.


## Native local-origin CORS/cache review (2026-10-09)
[PR754 regression and companion proposal](healthz-cors-review/) extends yukkie3276's prior finding on luch91's query-key change. Real Starlette CORS origin and full Worker module, with a Vary-aware substitute cache: main15/16, PR8/16, proposal16/16. The eight candidate mismatches manifest one known gap. Origin-bearing bypass increases upstream requests. Cloudflare deployment, browser enforcement and full Linux CI were not run; no acceptance or rewards are claimed.


## Native Matrix bridge transport review (2026-10-10)
[PR973 native HTTP regression](matrix-transport-review/) complements osr21's Matrix bridge implementation. AST-selected transport/crypto functions with actual urllib sockets: original9/19, companion19/19, 58 local HTTP requests. Incomplete response exceptions previously escape the typed retry boundary; the proposal restores existing retry/reconciliation. Full bridge, Linux locks/restart, original35-test suite and live services were not run. No upstream acceptance or rewards are claimed.


## Matrix bridge project-test incorporation follow-up (2026-10-10)
[PR973 author-review follow-up](matrix-integration-review/) provides one combined patch with19 new project-native unittest methods. Original35-method file remains byte-identical. Patch/lint/syntax checks and Windows selected-function fixture validation pass. Full-module/Linux54-test execution remains for the author; no adoption or upstreamCI result is claimed. One explicitly authorized author-review request and its subsequent DID-signed delivery record are retained there.
