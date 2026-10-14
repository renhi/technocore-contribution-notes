# Native MCP uncertain-write response review (2026-10-14)

Independent native Windows evidence for [osr21 PR987](https://github.com/flop-labs/technocore-chat/pull/987), head `1d6f682249f0b15a97be539c3990e562b1fa79de`, main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. Credit vanilla3/#982 and bdunn77/vanilla3/ShalyX's earlier mocked-boundary/Linux reviews. This adds real socket acceptance/response-loss cases across five write tools; it is not a new production vulnerability or six independent framing bugs.

## Actual execution

Whole official MCP package entrypoint/server/signing/fetch execute unchanged on main and candidate, with the real MCP2.2.0 SDK, Starlette/Uvicorn and urllib sockets. A companion snapshot changes only `fetch.py`. No AST extraction, transport/SDK/clock mock or fcntl shim is used.

**34 cases each: main18/34; candidate28/34; companion34/34.** Across three versions:201 MCP HTTP,90 origin POST,102 origin GET,54 ephemeral Ed25519 signatures independently checked with unchanged official PyNaCl verifier. Every write sends once. A later separate read tool observes the fixture's volatile acceptance count. Three child processes stop.

Write tools: say, write_note, say_signed, claim_room and set_room_allow. Per tool: complete200; accept then close before response headers; do not accept then close; accept then short200 Content-Length body; complete422; complete429. Four read controls: complete, close, short200 and429. Accepted-vs-notaccepted cases deliberately have the same lost response, so the diagnostic must not assert which happened.

The PR correctly replaces `cannot reach` with `write was not confirmed` for actual OSError connection loss. However all five short200 write replies and the short200 read still yield generic SDK tool errors: urllib's successful body read raises IncompleteRead outside that boundary. The narrow companion converts only that success-branch IncompleteRead to OSError so the existing shared handler can produce the appropriate read/write wording. No write retry is added and no broad HTTPException catch is proposed.

The local origin only records payload receipt/counts in memory. It is not Technocore storage, Matrix, ownership/allow policy, rate/CAS semantics or durable acceptance. The generated signing seed stays inside trusted parent/child memory/environment and is never in reports/arguments/output; no user key is used by tests. No production test write or real timeout/DNS/TLS/Worker test is run. Partial HTTP-error body handling is unchanged and untested; other protocol failures/concurrency are outside scope.

Source18 original blobs stay unchanged. Checker/companion Ruff lint+format under pinned project config, syntax and patch apply-check pass. Original81-test suite, full Linux/upstream CI and author incorporation are not run or claimed. The companion applies to PR987, not unmodified main by itself.

## Reproduce

Use Python3.12+ with the reported MCP/Starlette/Uvicorn/cryptography/PyNaCl versions. Fetch provenance-listed files into `SOURCE/main` and `SOURCE/candidate`. Copy the candidate MCP package to `SOURCE/proposed` and apply the companion patch there. Then run:

```text
python check_native_uncertainty.py SOURCE source-provenance.json new-report.json
```

This starts only loopback fixtures/listeners, generates a disposable key internally, checks original hashes before/after and refuses to overwrite a completed report. No live endpoints are called by the checker. The patch is companion material, not part of the current PR.

Official reward review is scoped to the homepage/testnet/airdrop pages. No currently redeemable event was found; the official X profile returned403, so latest social posts remain unverified. Existing interest forms are not payout approval. No wallet, token claim or testnet settlement was performed.

Prepared by renhi with Codex. The separately authorized existing-DID summary and verified public receipts will be appended here. No new peer comment or competing PR is posted.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`17580137`, server timestamp `2026-10-14T07:41:22.185243Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
