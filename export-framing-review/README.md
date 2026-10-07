# Native Windows export framing regression and scoped correction

Independent offline review by renhi, assisted by Codex, for
[burak33bb's existing PR #842](https://github.com/flop-labs/technocore-chat/pull/842).
The export tool, pagination and Worker deadline fix are the original author's work;
the platform-signal approach is credited to almondous's PR #958. This packet adds actual
CPython/socket framing evidence, not another duplicate export implementation or PR.

## Reproduced problem

Pinned head `7dd9c8f7353bc21ce54a945aceb40a5761eb9a47`, based on current main
`0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. The exact source Git blobs and SHA-256
values are in `source-provenance.json`.

The CPython export adapter iterates over `urllib`'s HTTPResponse by lines. On native
CPython 3.12.14, reaching EOF this way does not reliably reject an incomplete HTTP body.
For example, a test origin advertises two complete records in Content-Length but sends
only the first and closes. The unchanged adapter returns HTTP200 and the partial prefix;
the unchanged export wrapper emits a page marker without a continuation. No service
outage or actual user data loss is claimed: these are synthetic loopback responses.

## Executed checks

Twenty native loopback HTTP scenarios were executed against the unchanged head and
the proposed transport correction on Windows 11/CPython 3.12.14/anyio. The server-wrapper
functions are exact AST bodies selected from the original file, not rewritten behavior.
Only the SDK ToolError boundary is injected; the MCP SDK protocol and server/store are
not booted. `urllib_export_fetch` itself is imported unchanged and uses real sockets.

| Result against desired transport contract | Original PR head | Companion proposal |
| --- | ---: | ---: |
| Matching cases | 14/20 | 19/20 |
| Mismatches | 6/20 | 1/20 |

Three premature Content-Length EOF cases (mid-JSON, at a record boundary, empty body)
are rejected by the proposal rather than returned as successful pages. Two native
HTTP framing exceptions (mid-chunk and truncated 429 body) are translated into OSError,
which the unchanged wrapper turns into its expected ToolError. These five corrected
cases are not five independent server bugs.

Controls preserve complete Korean/emoji JSONL record strings, generation headers,
cursor forwarding, empty exports, EOF-delimited success, complete chunked success,
complete 403/429/500 refusals, socket-stall errors, and deliberate bounded early return.
An early page stop is allowed even with unread advertised bytes; checking Content-Length
unconditionally would break normal pagination. The probe uses a 0.2-second idle socket
timeout to keep synthetic stall tests short, not a claimed whole-call wall-clock deadline.
Each case makes exactly one request; the tool does not retry.

## The proposal is deliberately incomplete

**`chunked_no_end` still fails after the correction.** A valid-looking prefix delivered
as chunked HTTP without the final zero chunk is still accepted by CPython line iteration.
This packet records that behavior explicitly; the patch is **not** a complete framing
solution, complete backup proof, or evidence that PR #842 is fixed or ready to merge.
The correction enforces a promised Content-Length at natural EOF and translates framing
exceptions that actually propagate. An EOF-delimited response without length/chunk
framing cannot by itself prove how many records the origin intended to send.

The regression checker intentionally exits 1 for the original six mismatches and for
the proposal's remaining single mismatch. Never turn those into an "all tests passed"
claim. Full Linux repository tests, original HTTP/MCP test module, typing, Worker runtime,
and upstream CI were not run. Ruff lint and format checks passed for the independent
checker and proposed fetch.py. `git apply --check` passed against the pinned source.

## Reproduce and inspect

For a technical reviewer: Python3.12 and anyio are sufficient. Acquire the pinned original
fetch.py and server.py, verify the supplied hashes, and inspect them before execution.

```text
python check_export_transport.py original/fetch.py original/server.py before.json
python check_export_transport.py corrected/fetch.py original/server.py after.json
```

Apply `export-framing.patch` only to the pinned PR version, then use its corrected fetch.py
for the second invocation. Both invocations presently exit nonzero as explained above.
The tests run a local HTTP server and issue GETs to 127.0.0.1 only. No production chat
requests, keys, signatures, wallet operations, remote messages or persistent service changes.

Published in the user's evidence repository only; no new upstream PR or comment was
posted. Official adoption, external use and airdrop eligibility are unconfirmed.
Protocol context: [Technocore export reference](https://technocore.chat/llms.txt).
