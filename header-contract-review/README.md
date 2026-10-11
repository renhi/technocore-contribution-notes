# Official header-limit/API declaration review (2026-10-11)

Independent evidence supporting [PR #622](https://github.com/flop-labs/technocore-chat/pull/622), credited to Elfet for the already reported missing431 documentation. Pinned head `1b3c3fb2bb433502fb552e75903521e4a5e5ff4c` against checked main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. This does not claim a new vulnerability or31 different bugs.

## Actual document and executable boundary checks

Read-only capture of the [deployed OpenAPI document](https://technocore.chat/openapi.json) shows31 public operations, all missing a431 response declaration. The official manual publishes a48-header /8192-byte limit. No oversized requests or test writes were sent to the public service.

The checker runs unchanged selected `HeaderLimits`, `text`, `_REF` and constant assignments from both exact sources inside minimal real Starlette/Uvicorn/h11 TCP fixtures. **Main14/14; candidate14/14**,28 actual local requests. Cases cover47/48/49 headers,8191/8192/8193bytes, simultaneous/independent cap boundaries, duplicate tuples, non-ASCII UTF8 value byte accounting, and refusals before a local POST handler or unknown-route handler. At the exact two limits the request passes; either limit+1 returns431. Accepted scopes match the transmitted tuple count/byte sum; rejected requests never reach the inner fixture.

Candidate moves the two literal caps to `manifest.py` and uses its original `manifest.MAX_*` bindings; the checker supplies only those extracted immutable constants, not a fake full store or `fcntl` shim. Ref-token queries are not used, so that unrelated branch is not exercised. Full official app import is not performed.

## Declaration controls

The exact candidate's declaration suffix and unchanged `_plain` helper run on **copies of the captured current live JSON**. This yields a431 declaration for all31 operations, with the two cap values and text/plain media, while leaving the captured pre-existing data unchanged. Six controls pass, including preservation of an existing explicit431 response and idempotence. This is suffix-level evidence, **not full candidate manifest generation, an actual candidate endpoint or deployed patch evidence**.

The same seven pinned source blobs stay unchanged. New checker Ruff lint/format under the pinned project's configuration and syntax pass. No Linux full suite or upstream CI is claimed; the existing PR remains open/unmerged at this review. No new PR or author comment was posted.

## Reproduce and scope

With Python3.12+, Starlette and Uvicorn, retrieve the pinned main/candidate `src/app.py` and `src/manifest.py` into a source tree and capture the public OpenAPI document as `live-openapi.json`. Run:

```text
python check_header_contract.py --source-root SOURCE_TREE --output OUTPUT_DIRECTORY
```

`SOURCE_TREE/main/src/` and `SOURCE_TREE/candidate/src/` are separate snapshots. The checker writes `boundary-results.json` and `declaration-results.json`; original sources are not edited. The selected definitions use genuine native sockets and framework responses, but the minimal inner handler is not Technocore routing/storage. Full app, ref accounting, rate/auth/filesystem behavior, production edge/CDN/TLS, alternate parser, full candidate generator and repository CI remain untested. This is known-gap regression/documentation evidence, not merge approval.

Prepared by renhi with Codex. Source provenance, live operation inventory and validation hashes are retained alongside the executable checker. The separately authorized existing-DID summary/verified delivery receipts will be appended. No role, settled testnet computing or airdrop entitlement is established.
