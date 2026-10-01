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
