# PR #973 follow-up: project-native regression for author incorporation

Prepared by **renhi**, assisted by Codex, 2026-10-10. Original standalone Matrix bridge/durable retry implementation: **osr21**. This follows up the [earlier function-level transport evidence](../matrix-transport-review/) by providing a combined patch with a test file in the **original project's directory layout**. No duplicate issue/PR or change to the author's branch is created.

Target: [PR #973](https://github.com/flop-labs/technocore-chat/pull/973), head `5d5c7fcbdb350ede03b8a62ed54362c38d666049`, checked against main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. The bridge is absent from main; this is a PR-original/companion comparison.

`integration.patch` changes only:

- `contrib/technocore-matrix/bridge.py`: import http.client; catch HTTPException in the two existing transport handlers. Existing retry/reconciliation behavior and controls are retained.
- **New** `contrib/technocore-matrix/tests/test_transport.py`: 19 unittest methods use native localhost HTTP framing, original transport/crypto code, real sleeps and disposable in-memory keys. The shipped test imports the **complete bridge normally**, including real fcntl on Linux. It has no production-function extraction, monkeypatch, fcntl shim or persisted user credentials.

The original `tests/test_bridge.py` with 35 methods is **byte-identical**. This is not a reorganization/rewrite of the author's tests. The combined patch passes `git apply --check` on the exact PR source. New test lint/format and proposal/test syntax checks pass.

## What was actually executed

Windows cannot import the complete bridge unchanged, and local WSL is unavailable. Our current GitHub connection lacks permission to add CI workflow files, so no new Linux CI workflow was created or dispatched. **The shipped project-native test file has not yet been run through a complete bridge import on Linux.**

We validated the new test fixtures on Windows by replacing **only their bridge-import bootstrap in the independent local checker**, then executing them against the prior AST-selected original/proposal transport namespace. Result: original9/19, proposal19/19, zero unexpected unittest errors. The test source itself is unchanged by that checker; its intended Linux bootstrap remains normal. `windows-fixture-check.json` explicitly records the replaced bootstrap and this boundary. Workspace paths are normalized in the public output. This is not a 54-test Linux result, full-module validation, upstream CI or durable-restart proof.

The 19 scenarios retain complete-response/refusal controls, three incomplete framing variants, accepted signed-write readback without another POST, one retry of an unaccepted signed write, and deterministic Matrix PUT retry identity. Fixture acceptance is not real Matrix/Technocore storage. There is no general exactly-once guarantee; deadline, redirects/TLS, retention and durable state are outside the new transport regression.

## Review and incorporation requested

The author can apply the single patch at the pinned head and run the original35 plus new19 methods on Linux:

```text
python -m unittest discover -s contrib/technocore-matrix/tests -p 'test*.py'
```

**54 methods is the intended suite size, not a reported successful run.** Please also run relevant repository gates, resolve overlap if the PR head advances, and fold the fix/tests into the existing PR only after review. Upstream acceptance/merge is controlled by the author and maintainers, not by this companion publication.

The exact user-authorized review request is in `review-comment.en.md`; a delivery receipt is added after one comment is posted/read back. A subsequent DID summary attests the actual preparation and delivery, **not that incorporation already happened**. Earlier signed summaries are not repeated.

## Review request delivered

One authorized [author-review comment](https://github.com/flop-labs/technocore-chat/pull/973#issuecomment-6095100395) was posted by renhi and read back byte-for-byte. No author response, acceptance or incorporation is claimed. See `github-review-delivery.json`.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`16525426`, server timestamp `2026-10-10T07:25:59.483258Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
