# PR #238: repository-test integration and current-main validation

This is a proposed extension of **dhasap's existing PR #238**, not an update to that PR, an approval, or a new competing PR. The canonical base64url finding belongs to **osr21**; renhi prepared the regression integration and independent Windows validation.

The [October 6 review](https://github.com/flop-labs/technocore-chat/pull/238#issuecomment-6005784804) correctly distinguishes useful companion evidence from changes actually incorporated into the PR. That distinction still applies to this packet.

## Concrete changes

- Require canonical 86-character signatures ending in `AQgw`, matching the server on the verified PR base and current main.
- Correct the module's storage explanation: new signed message records retain `sig`, legacy records can lack it, and integer `nonce` cannot always recover the original signed spelling. The tool verifies a supplied original tuple; note reads are not signed-write receipts.
- Add `tests/unit/test_verify_cli.py` to the ordinary pytest discovery path. It integrates the previously published 47 CLI cases without rewriting their bodies: the byte-identical Python source is retained as `tests/fixtures/verify_cli_regression.txt` and loaded by the test adapter.
- Add 128 checks comparing all 64 possible signature terminal characters in both lanes against the actual server verifier, plus two original-nonce tests that each invoke the CLI for `007` and `7`.

There are **139 pytest items**, representing **179 CLI invocations** in the passing run. These are not 139 newly discovered bugs. The server comparison imports `src/didkey.py`; it does not call a hosted server or exercise write admission/replay counters. Signing keys are disposable and generated in memory.

## Results and the stale-branch prerequisite

| Code evaluated | Passed | Failed | Meaning |
|---|---:|---:|---|
| Current main plus original PR verifier | 18 | 121 | Regression detects the existing verifier mismatch |
| Current main plus integrated correction | 139 | 0 | Targeted regressions pass on the proposed integration |
| Exact stale PR head plus correction/tests | 19 | 120 | Its old server verifier still allows noncanonical terminal characters |

The exact PR head `93bdfd0331de9c30c2693141a0ce166cfb69f186` contains an older `src/didkey.py` with the unconstrained `{86}` pattern. The PR base `019b57ad8ea051e44411f465e366c163536e71fc` and current main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc` already enforce `{85}[AQgw]`. The parity tests expose that stale source boundary; they must not be weakened to make the old checkout green. The failing stale-head comparison is recorded in `pytest-pr-head-summary.json`.

## Applying to the existing PR

Preferred: rebase the existing PR onto the verified current main, then apply `pr238-extension.patch`. It corrects the existing proposed script and adds the project tests. Alternatively, `main-integration.patch` adds the complete corrected verifier and the same tests onto pinned current main. **Use one patch, not both.** Both are plain unified patches; `apply-checks.txt` records the application checks.

For the PR author or maintainer, on Linux after incorporation:

```sh
uv sync --frozen
uv run pytest tests/unit/test_verify_cli.py -q
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run sz.py --caps
uv run coverage run -m pytest tests -q
uv run coverage report
```

Run the current repository's remaining CI gates as applicable. The full CI also covers packaging, image and Worker checks; this report does not establish those results. Fetch main again before applying if it has moved.

## Validation limits

Windows CPython 3.12.14; current-main frozen dependencies, including cryptography 50.0.1, PyNaCl 1.6.2, pytest 9.1.1 and ruff 0.16.8. Targeted pytest, repository-wide lint/format, core caps and patch application checks passed.

`ty check` stopped before analysis because sandbox Windows path canonicalization was denied. The full coverage suite was attempted but stopped with 19 collection errors because the Linux-only `fcntl` module is unavailable. The subsequent coverage report is consequently not meaningful and fails the project floor. No `fcntl` stub or server replacement was used. Linux execution and upstream CI were not run; the current GitHub login lacks workflow scope. See `environment-limitations.txt`.

**The official PR remains unchanged.** This is executable integration material and scoped validation, not merge evidence. No live Technocore writes, user signing keys, additional comments, X posts, financial activity or airdrop eligibility claims are involved.

Sources: [official protocol](https://technocore.chat/llms.txt), [authentication and signature rules](https://technocore.chat/auth.md), [usage patterns](https://technocore.chat/patterns.md), [original PR](https://github.com/flop-labs/technocore-chat/pull/238). Exact source hashes and document hashes are in `source-provenance.json`.
