# Standalone Python agent-loop failure-path review (2026-10-10)

Companion evidence for [Technocore PR #288](https://github.com/flop-labs/technocore-chat/pull/288), by xamdkx. Pinned head `775e99be8f9c48a0e5ce5ffbc0d513088de98df7`, checked current main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. Main does not contain this example: this is original PR example versus a local companion proposal, not before/after deployed server behavior.

The author already demonstrated a successful run against a disposable actual server. This contribution adds **failure-path** verification: a demonstration used in automation should fail and stop issuing later requests when one required step is rejected or its owner readback does not confirm the claimed DID.

- [bdunn77 prior evidence](https://github.com/flop-labs/technocore-chat/pull/288#issuecomment-5567468559)
- [xamdkx prior evidence](https://github.com/flop-labs/technocore-chat/pull/288#issuecomment-5652517499)

## Retained results

| Complete example | Correct scenarios | Real loopback HTTP requests | Officially verified signed request tuples |
| --- | ---: | ---: | ---: |
| Pinned PR original | 2/19 | 91 | 36 |
| Companion proposal | 19/19 | 57 | 19 |

The original passes the normal path and stops with a nonzero exit for malformed JSON. In the other17 conditions it returns exit0 after a refused step, continues later writes, accepts a malformed JSON shape, or fails to make unconfirmed ownership an unsuccessful exit. Some error bodies deliberately contain the generated DID to expose status-blind substring matching; these are controlled fault injections, not observed production responses. A refused claim is followed by a missing owner note in the fixture. Original still returns exit0 in that case.

`fail-closed.patch` adds HTTP200 checks for every required step, validates the read's JSON messages-list shape, checks the full DID value line only after successful owner readback, and exits with a short failure reason. It stops at the first failed step with **no automatic retry**, including429; earlier accepted writes are not rolled back. Successful signatures, sweep, nonce spelling, claim URL and create-only condition are preserved. The patch applies to the pinned source; new-test/proposal Ruff lint and format checks use the pinned project's configuration and pass, as do syntax checks.

## Reproduce (for project contributors)

With Python3.12+, cryptography and PyNaCl, retrieve the pinned example and `src/didkey.py`, then run:

```text
python test_agent_loop.py --example PATH/examples/agent_loop.py --verifier PATH/src/didkey.py --output result.json
```

The test suite launches the complete example normally in a child process, overrides BASE to a disposable127.0.0.1 listener, and generates ephemeral keys inside the example. No protected user key is required. Each of the19 unittest methods checks the exit result, request sequence and completion claim; the fixture also verifies the exact signed tuples and nonce1/2 with unchanged official DID verification. Applying the companion patch and repeating should change2/19 to19/19. Original failures are expected regression evidence; no unexpected unittest errors occurred.

## Boundaries and integration

Native Windows CPython urllib sockets and full standalone example execution were used; no source extraction or replacement transport. The HTTP responses and small ownership model are controlled fixtures. The real server's filesystem, authorization, nonce replay, rate limiter, redirects, TLS and actual-service delivery were not exercised. Full Linux repository CI was not run. These148 HTTP requests and55 signature verifications sum only the two retained reports; development reruns are excluded.

The exact DID line check fits the current text note banner/value/footer layout, but is not cryptographic ownership evidence. This is a demonstration completion check, not a robust resumable client. Persistent key safety, rollback and ambiguous delivery remain outside the change. The original author should review the proposal, add actual-server failure-path integration where appropriate, and run repository gates before incorporation. No new PR, author comment or CI workflow was created for this contribution; no adoption is claimed.

Original example/protocol credit remains with xamdkx and the project. Independent tests/proposal were prepared by renhi with Codex. No official role, settled testnet computing or airdrop qualification is implied. `source-provenance.json`, `before.json`, `after.json` and `validation.json` retain hashes and limits; the separately authorized public DID summary and its verified receipt will be appended after delivery.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`16576503`, server timestamp `2026-10-10T12:07:36.523306Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
