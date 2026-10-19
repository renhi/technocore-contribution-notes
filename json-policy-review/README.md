# Duplicate-name policy comparison — 19 October 2026

Independent Codex-assisted contribution by renhi. This supplies a reproducible compatibility matrix for maintainers choosing between the two existing responses to issue #925. It does not open a competing fix or claim a new vulnerability.

Pinned official main: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.

- [PR #926](https://github.com/flop-labs/technocore-chat/pull/926), maho0638, head `3f7eb94069e323d7512d4bfc67f4ba4a2fcc9a8e`: reject repeated **top-level** decoded names; nested duplicates remain accepted deliberately.
- [PR #996](https://github.com/flop-labs/technocore-chat/pull/996), ShalyX, head `2a6f1436d480b620b79416bb61eb56226c6ee03b`: reject duplicates at **all object depths**. Its manual explicitly says so.

Both remained open/unmerged on the fresh check. These are alternative policies, not evidence that #926 bypasses its own stated contract. Credit issue #925, Jennycruzy's helper work, boomelant's nested-contract observation, and WIZARDspace/bdunn77's previous reviews. Their Linux/CI counts are not ours.

## Results

The same **44 inputs per version** produced **132 offline decoder executions**. The 38 explicitly expected outcomes per version matched **114/114**. Six additional depth observations per version all returned a dictionary without an escaped exception on this Python3.12.14 Windows run; these 18 observations are not included in the 114 policy assertions.

| Input class | Inputs/version | Main | PR926 | PR996 |
| --- | ---: | --- | --- | --- |
| Repeated root names | 10 | accepts final value | refuses | refuses |
| Nested repeated names | 6 | accepts | accepts, deliberately | refuses |
| Valid controls | 12 | accepts | accepts | accepts |
| Malformed/non-object controls | 10 | refuses | refuses | refuses |
| Depth observations | 6 | accepts in fixture | accepts in fixture | accepts in fixture |

Root cases include identical values, escaped equivalent names, empty names, escaped slashes, literal emoji versus surrogate-pair spellings, and repeated conditional flags/tokens. Nested cases include objects inside arrays. Controls include independent sibling scopes, strings containing colons or JSON-looking text, case-distinct names, Unicode spellings without normalization, non-finite numbers, invalid UTF-8 and lone surrogates. Values are synthetic; no user identity is used in these tests.

The `204` decoder outcome in the report is a **fixture label for a returned dictionary**. It is not an HTTP status observed from Technocore. `400` comes from the selected official decoder's error response object.

## Execution boundary and limits

The checker selects the final three post-upload statements from each unchanged `read_json` with Python AST, plus #996's unchanged duplicate hook. Decoder calls and exception handling remain unchanged. #926's `src/strictjson.py` is imported as a **whole, unchanged module**. The error-text adapter uses Starlette's `PlainTextResponse`. Hashes and selected line ranges are retained. Eight fetched source blobs, including both manuals, match their Git object IDs and remain unchanged.

This does **not** execute complete `read_json`, the streaming/deadline layer, the real app, storage, room/note handlers, signatures, write side effects or access gates. No `fcntl` or store emulation is installed. A native HTTP fixture was attempted but could not start in the restricted runtime: Windows asyncio stalled while establishing its internal socket pair. It produced no HTTP results and is **not** part of this published checker. Ordinary shell access to remote GitHub also failed; connected GitHub tools supplied and publish the artifacts. Do not attribute these environment limitations to a Technocore defect.

Full Linux tests, repository-wide gates, upstream CI, production behavior, performance and browser/Worker behavior remain unverified. Depth acceptance is a bounded observation, not a portable depth guarantee. No fix or original PR branch was modified, and there is no claimed author incorporation or merge approval.

## Reproducing the offline check

For a reviewer with a prepared Python3.12 environment, install orjson3.12.0 and Starlette1.7.0, retain the pinned snapshots as `SOURCE/{main,root-only,all-depth}/src/app.py` and `SOURCE/root-only/src/strictjson.py`, and run `check_decoder_policy.py SOURCE REPORT.json`. `cases_json_policy.py` must be beside it. Fetch the exact commits in `source-provenance.json` and verify their blob IDs before use. No account, wallet or DID key is needed for the check. The user's beginner workflow is agent-managed; this is an optional maintainer reproduction description.

Checker lint/format uses the pinned main's Ruff configuration; syntax and the recorded artifact hashes are checked separately. `validation.json` is the immutable manifest. Subsequent signature receipts bind its SHA256 and this contribution's scope; they do not attest to air­drop entitlement. See `event-review.json` for the separately scoped official-event search.
