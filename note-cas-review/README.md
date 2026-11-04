# Note reads that can safely feed compare-and-set

Independent transport validation of [PR #183](https://github.com/flop-labs/technocore-chat/pull/183), credited to crazywriter1 and the proposal's existing regressions. This reproduces a known framing problem; it is not a first discovery or an upstream fix claim. It is separate from prior room-list caching, mailbox syntax and signed-write nonce reviews.

## Result

Historical base and current main each match 6/38 conditions; the proposed head matches 38/38. The 32 framing combinations exercise eight stored values, budget footer present/absent, and trailing newline present/absent. Values include Korean, emoji, literal `# budget:` prefixes, caller text resembling the untrusted banner, URL punctuation, and 8,192 Korean characters. Each case reads the value, passes the exact returned string to `write_note(if_matches=...)`, then simulates a competing writer before a second guarded write. All stale writes are refused and the competing value remains intact. Six controls cover HTTP 400/404/409/422/429 propagation and retention of the untrusted banner on room reads. The 32 old-version failures are variants of the known framing defect, not 32 vulnerabilities.

Three complete unchanged MCP packages run as child processes through the real MCP SDK stdio client and native urllib/TCP. Executed package paths and SHA256 hashes are checked inside each child; all 25 pinned source blobs are checked before/after. The final run made 114 local GETs and 192 local POSTs (306 local HTTP requests), plus three unsigned whoami tool calls without HTTP. No signing key is configured in test children. No test writes touch the public service or the Devnet wallet.

## Scope

The HTTP origin is a disposable in-memory note fixture with explicit equality-based compare-and-set and response framing, not the real Linux app/store, filesystem locking, expiry or distributed concurrency. Only the banner constant is read from app.py using AST literal evaluation; the complete MCP implementation is imported normally without extraction or patches. Optional footer and terminal-newline combinations are controlled framing inputs, not claims about every production response. The 8,192-character case checks client transport and preservation, not server-side size enforcement. No browser/humans execution, Cloudflare deployment, full repository suite, upstream CI, merge compatibility or maintainer adoption is claimed. No official role, reward or airdrop eligibility is established.

## Reproduce

Use Python with `mcp==2.2.0` (see exact installed version in native-results.json). From this folder, `python fetch_sources.py source-provenance.json SNAPSHOT_ROOT` obtains immutable public files, then `python check_note_cas.py SNAPSHOT_ROOT native-results.json` runs the local comparison. The downloader verifies Git blob SHA1 and SHA256 and refuses inconsistent existing bytes. No account, wallet or credential is required.
