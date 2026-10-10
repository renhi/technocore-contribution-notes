# PR #973: incomplete HTTP response transport regression

Independent Windows/local contribution by **renhi**, assisted by Codex, 2026-10-10. The Matrix Application Service bridge and its durable partial-delivery work are **osr21's implementation** in [PR #973](https://github.com/flop-labs/technocore-chat/pull/973). This contribution adds a narrow native HTTP framing regression and companion exception-handling patch. It does not claim to implement or independently validate the original durable ledger/restart work.

Pinned PR head: `5d5c7fcbdb350ede03b8a62ed54362c38d666049`, against checked main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. This standalone package is absent from main, so the comparison is **PR original versus local companion proposal**, not main versus PR.

| Version | Matching scenarios | Mismatches | Actual local HTTP requests |
|---|---:|---:|---:|
| PR original | 9/19 | 10 | 22 |
| companion proposal | 19/19 | 0 | 36 |

Across two versions: 38 scenarios and 58 native loopback HTTP requests. Ten mismatches are manifestations of the same missing HTTP protocol exception handling in two transport functions; they are not ten independent production bugs.

## Failure and narrow proposal

CPython urllib's actual `HTTPResponse.read()` raises `http.client.IncompleteRead` when a declared Content-Length is short, a chunk is truncated, or the final chunk terminator is missing. This is an [HTTPException](https://docs.python.org/3.12/library/http.client.html#http.client.IncompleteRead), not an OSError. The PR's `_http_json` and `technocore_get` handlers omit it, so the original protocol exception escapes their documented `MatrixError`/`RetryableError` boundary. This prevents bounded retry and, for a signed write whose reply was truncated after acceptance, prevents the existing read-back reconciliation step from running.

The companion patch imports `http.client` and catches its `HTTPException` in those two existing transport handlers. It uses the existing retry limits, sleeps and error classes. Complete 400/404 refusals retain their permanent paths; complete 429/503, malformed JSON and non-object responses retain their controls. It adds no new replay/durable-state design.

The real HTTP fixture covers:

- `_http_json`: complete Korean/emoji JSON, three incomplete framing variants, invalid JSON, non-object JSON, permanent400, retryable429/503. Single-attempt probes preserve the typed boundary.
- `technocore_get`: complete body, three incomplete variants, permanent404 and bounded503. Proposed transient cases make exactly four requests, then raise RetryableError.
- Signed write accepted before a Content-Length or chunk-terminator failure: the proposal sends exactly one POST, reads the room, verifies the exact retained fixture tuple using actual cryptography, and returns the existing reconciliation result0. No duplicate accepted fixture record.
- Signed write not accepted before the first truncated reply: one read-back sees no record, one fresh-nonce retry is accepted, giving two POSTs and one accepted fixture record.
- Matrix PUT after a truncated reply: two actual PUTs use the **same deterministic path and body**. This verifies client retry identity, not a real homeserver's transaction deduplication.

Seven disposable-key signed POSTs across both versions were cryptographically checked by the local fixture. The fixture scripts response framing and acceptance; its accepted-record counter is not production or durable storage evidence. Real sockets, urllib/http.client, real sleeps, crypto and signing functions are used; these are not mocked. Local origin is stopped at completion.

## Windows execution boundary

The complete bridge imports Linux `fcntl` and uses POSIX locks and directory fsync. It cannot run unchanged on this Windows setup; WSL is unavailable. No fcntl replacement or platform stub is installed. Instead, the independent checker **AST-selects 18 original function/class definitions without editing their bodies**, supplying their stdlib/cryptography imports and matching documented constants. The selected list and entire source SHA256 are recorded in results. This is function-level transport evidence, **not a complete module import or Application Service integration**.

No original 35-test suite, full Linux repository checks, process restart, persisted ledgers, filesystem locks, real Matrix homeserver, live Technocore service or production credentials were exercised. The author's 35-test report is their evidence, not our run. This patch is companion material and is not already in the PR. Redirect/TLS policy, total body deadlines, retained-history gaps and all process-lifecycle guarantees remain outside this regression. Existing signed-write retry behavior without a marker is unchanged; this does not establish general exactly-once delivery.

## Reproduction for maintainers

Tested on native Windows Python3.12.14 with cryptography50.0.1. Fetch `contrib/technocore-matrix/bridge.py` at the exact PR commit, preserving bytes and checking hashes in `source-provenance.json`. Copy it into a separate proposal tree and apply `incomplete-http.patch` there. Keep original/reference tests intact. Then:

```text
python -X utf8 check_transport.py --source source/contrib/technocore-matrix/bridge.py --proposal proposal/contrib/technocore-matrix/bridge.py --output native-results.json
```

Exit zero requires all proposal expectations. Original failures are deliberately retained, not hidden. A fixture-only Ed25519 key is created in memory and never persisted or printed. No user's protected key is touched during tests. `validation.json` pins the checker, output, patch and provenance hashes and records the narrower validation boundary.

DID signing, if delivered, attests the supplied statement and immutable validation digest. It is not correctness, upstream acceptance, an official role, testnet settlement or airdrop approval.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`16522065`, server timestamp `2026-10-10T07:08:23.714737Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
