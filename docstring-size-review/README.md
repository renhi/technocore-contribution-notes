# Docstring-adjacent code: whole-tool and CLI validation

Independent Codex-assisted validation by renhi,30October2026. Credit **almondous PR1052** for the original token-span fix and regression suite. This is a new contribution area for this workspace: standalone code-size enforcement, separate from prior network/Worker/signature checks. It is not a first-discovery or competing-fix claim.

- [Official PR #1052](https://github.com/flop-labs/technocore-chat/pull/1052), pinned open/unmerged head `0ee11b31ffca4fd7236aa1a79a08341d4dd808ba`.
- Main/base `73a732497a19cac11aff4dcb527bae3c52b02f73`.

## What the evidence adds

On main, a real statement sharing a physical line with a docstring can disappear from the code-line count. `"doc"; x = 1` and an inline function are examples. PR1052 excludes just the docstring expression's tokens, including UTF-8 byte-coordinate handling, preserving adjacent code and free docstring separators.

The checker normally imports the **whole unchanged `sz.py`** from each pinned snapshot and launches actual native Python CLI processes. It does not extract the measurement algorithm, patch imports, fake a server or reimplement AST-span filtering as its oracle.

| Verification set | Main | Candidate |
| --- | ---: | ---: |
| Independent explicit measurement expectations | 17/85 | 85/85 |
| Synthetic CLI policy decisions | 26/32 | 32/32 |
| Exact proposed original tests | 8passed/13failed | 21passed/0failed |

The matrix contains function/class/module and docstring-only constructions, ASCII/Korean/accented identifiers, Unicode text, parenthesized/multiline/continued docstrings, spacing, async/decorators and non-docstring controls. Expected code-line counts are explicit from these small constructions. Token-density expectations are explicit for84/85 cases; the f-string control checks code-line count only. Related cases exercise shared exclusion/coordinate logic, not68 independent production bugs.

Synthetic policy projects exercise `--caps` and `--check` with zero ceilings, exactly-at-limit acceptance, ratchet growth under a higher cap and missing-cap refusal. All policy/baseline writes occur in new local test fixtures, never the official snapshot baseline. No `--update-baseline` is run.

Across both versions there are **170 measurement executions,64 synthetic CLI executions and6 actual-snapshot CLI executions**. Original tests add42 pytest case executions with their own subprocess checks; those nested subprocesses are not included in the64+6 counts. The exact proposed test file is copied byte-for-byte into the baseline snapshot for comparison, not claimed to exist in main's committed tests.

## Actual project measurements and the inherited ratchet

Both tools measure the same six pinned actual source files. Their **entire measurement dictionaries are identical**, including raw/code/comment lines and token density. The6 source files and both official baselines stay byte-identical; no source, baseline, cap or changelog policy is changed.

Both actual-snapshot `--caps` commands succeed. Both `--check` commands return the identical pre-existing `core/store.py 1029 -> 1030 (cap1030)` ratchet diagnostic. **1030 equals its cap**, so this is not a cap breach, and the candidate adds no new difference to this standalone comparison. This does not waive a required check or imply the project's full gates are green.

## Reproduction and limits

Python3.12.14 on Windows; original module tests run with pytest9.1.1 and plugin autoload disabled. Dependencies were reused from the workspace cache, not installed globally. The original proposed test module is executed normally with an isolated configuration boundary; the Linux-dependent root conftest/full server is not loaded. No original test body is edited. The21 original tests are focused evidence, **not** the author's940-test repository run or upstream CI.

For a maintainer with Python3.12 and pytest9.1.1 installed, reproduce using `check_size_policy.py SOURCE_ROOT REPORT.json` beside `source-provenance.json`. Retain exact main/candidate snapshots and the listed source files; also apply only the unchanged proposed test module at the same path in the main snapshot. The checker creates new local fixture directories and records detailed pytest logs there. No account, DID key, production request or wallet is required. This optional reproduction description is for reviewers; the beginner user's operations are agent-managed.

All21 fetched Git blobs, original-test bytes, normal module paths and tool/baseline hashes are checked. Checker Ruff lint/format follows pinned main's configuration; syntax checks pass. It is a bounded matrix of valid Python snippets, not a formal proof of arbitrary Python grammar or a proposal to change which files size policy enumerates. The real source files are read and parsed, never imported or executed. Full repository tests, ty, coverage, other Python versions/platforms and upstream integration remain unverified.

`validation.json` hashes the checker/results/provenance/official-event review. README and later delivery receipts remain mutable companion descriptions. The existing-DID summary binds the immutable manifest URL and SHA256; actual delivery is only confirmed after live record readback. No new peer comment, PR, source-branch edit, author incorporation or official role is claimed.

The [official verification page](https://flop.finance/official/) still has no live airdrop, and the [public testnet profile](https://ask.flop.finance/networks/testnet) remains planned/unreleased with no verified public enrollment.3November is a working target. This technical verification and DID posting do not establish reward entitlement or settled compute.
