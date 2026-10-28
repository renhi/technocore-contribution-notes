# Non-finite wait: native MCP transport follow-up

Independent Codex-assisted validation by renhi, 28 October 2026. Credit **noviceborsaeng PR1027**, **bdunn77**'s prior causal reproduction/review and pepedesigner's code review. This adds actual SDK/stdio/urllib observations to the already known NaN-timeout finding; it is not a new vulnerability discovery or competing fix.

- [Official PR #1027](https://github.com/flop-labs/technocore-chat/pull/1027), pinned open/unmerged head `c092ef74b591fdf75776351a5f59c5032dc59bfc`.
- Current main/base `73a732497a19cac11aff4dcb527bae3c52b02f73`.
- No official source branch changes, new PR, peer comment, workflow or deployment.

## What this confirms

An agent can supply `seconds: "nan"` to `wait_for_message`. SDK lax validation accepts the string as float NaN. Main derives a NaN socket timeout, and native urllib raises `ValueError` before any HTTP request reaches the fixture. The agent receives only `Error executing tool wait_for_message`. The proposal treats a nonpositive-or-NaN ask as no hold when deriving its socket timeout, while forwarding the advisory `wait` unchanged to the instance.

**36 cases per version**, using two ordinary Windows child processes, complete unchanged MCP packages and MCP2.2 SDK stdio sessions:

| Version | Desired outcomes matched | Actual origin GETs |
| --- | ---: | ---: |
| Main | 27/36 | 24 |
| PR1027 | 36/36 | 33 |

The **9 main mismatches are variants of the same known NaN guard gap**, not nine independent defects. Five textual NaN spellings lose otherwise successful fixture responses; another four NaN cases lose the specific 400/403/422/429 response bodies. Candidate reaches the fixture once and preserves each response or refusal body. Positive/negative infinity, huge/negative/fractional/zero numeric waits and omitted-default controls remain functional. Three nonnumeric/null cases are rejected by the SDK's published numeric type before origin access; this is not a claim that the service itself rejects arbitrary advisory query spellings.

There are **72 wait-tool calls**, two extra unsigned `whoami` calls, and **57 native loopback HTTP GETs**. No POST or automatic retry occurs. These counts exclude SDK initialize/tools-list protocol frames; do not describe them as a total JSON-RPC frame count. The 429 fixture provides a one-second Retry-After, but the tool returns the refusal without resending. Tests contain no protected user key or wallet.

## How it runs

`check_native_wait.py` launches each complete pinned `technocore_mcp` package normally. Each child verifies its actual module directory and all four Python module hashes before invoking the unchanged official `main()`. No transport seam, urllib, SDK validation, timeout or clock is mocked. The SDK invokes `tools/call`; native urllib makes the local HTTP request. Signing configuration is explicitly empty and `whoami` confirms it. Sixteen fetched Git blobs and executed package hashes are retained and checked unchanged.

The local origin is a synthetic **immediate-response** `ThreadingHTTPServer`, not the official service. Its query interpretation executes the unchanged AST-selected service `_seconds` with a fixture ceiling of10; it does not import the complete Linux app/store. It never holds a request. Therefore this does **not** measure real long-poll timing, the exact 30/330-second socket ceilings, timeouts of a slow body, the operator's configured ceiling, production deployment or readiness. Successful infinity/huge-value requests demonstrate no immediate timeout-argument exception, not a proven deadline duration.

Both child sessions and fixture listeners close. The checker records observed elapsed times only for transparency, not a performance guarantee. A preliminary harness assertion used the wrong unsigned-identity phrase and stopped before any wait call; the corrected final run alone supplies these counts. Original upstream tests, Linux full suite, repository-wide gates, Worker/Pyodide, TLS, proxies, browser UI, concurrency and actual storage remain outside this validation. Prior reviewers' full-suite/CI counts are not ours. Checker syntax and Ruff lint/format use pinned main's configuration.

## Reproduction and signed evidence

For maintainers with Python3.12 and MCP2.2 installed, retain exact snapshots as `SOURCE/main` and `SOURCE/candidate`, including the listed source paths in `source-provenance.json`; invoke `check_native_wait.py SOURCE REPORT.json` beside that provenance file. No account, DID key or live Technocore connection is needed for the checker. This optional technical description is for reviewers; the beginner user's steps are agent-managed.

`validation.json` binds the checker, native results, provenance and official-event review. A subsequent existing-DID summary binds its immutable GitHub address and SHA256. Public delivery receipts state whether a server record was actually read back. They do not prove upstream incorporation, an official role, token entitlement or settled compute.

The [official verification page](https://flop.finance/official/) now explicitly says no airdrop is live and gives 3 November as the working testnet target, not a promise. The [official FAQ](https://ask.flop.finance/docs/testnet-and-timeline) clarifies that DID creation and Technocore DID posts earn nothing. This validation is technical contribution evidence only.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`20519943`, server timestamp `2026-10-28T00:30:15.051418Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
