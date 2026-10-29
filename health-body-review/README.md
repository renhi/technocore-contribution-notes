# Health response-body failure: native HTTP follow-up

Independent Codex-assisted validation by renhi, 29 October 2026. This examines **PR957's liveness response-body boundary**, separate from our earlier CORS/header review and PR1027's NaN wait. Credit **almondous**, **zeycan1 PR705**, the offered supplement and prior native finding, plus bdunn77/pepedesigner reviews. No first-discovery or competing-fix claim.

- [Official PR #957](https://github.com/flop-labs/technocore-chat/pull/957), head `fbcbbf3ab5c3f831ab5a81c4fcd4dfe2af3fd57c`, open/unmerged on the fresh check.
- Current main `73a732497a19cac11aff4dcb527bae3c52b02f73`; the PR's historical base is `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.

## Why this helps

`fetch()` resolves when headers arrive; the body can still stall or break. On main, a failed200 body read escapes the inner liveness guard into the outer fallback, which fetches the origin again without that guard's explicit deadline. The patch reads successful bodies inside the existing guard and returns503/no-store after one fetch. Cache-operation failures keep their separate, existing fallback policy.

Our local origin makes any second request deliberately healthy and quick. This makes the unexpected retry observable without hanging a test on the fallback's missing explicit deadline. A fallback200 in these fixtures is synthetic evidence of that control path, not a claimed observed production health incident.

## Results

| Whole Worker version | Desired outcomes matched | Native origin GETs |
| --- | ---: | ---: |
| Main | 11/14 | 17 |
| PR957 | 14/14 | 14 |

Across both: **28 case comparisons,30 Worker entrypoint invocations and31 real local HTTP GETs**, no POST. Each version has15 invocations because one cache-reuse case invokes the Worker twice.

The three main mismatches are **body reset, a short Content-Length response, and a stalled body**: each produces two origin requests and the synthetic fallback200. Candidate returns503/no-store after one. These are related manifestations of the known guard boundary, not three newly discovered production vulnerabilities.

Controls cover healthy/empty/delayed-complete bodies, header timeout, explicit404/429/503, cached response, reuse after a successful fill, and separate cache match/put failures. Retry-After is preserved on429. Both versions retain **two origin requests on a synthetic Cache.put failure**; this is an explicit policy-preservation control, not a claim that the patch removes all retries. Health requests never consult stored snapshot assets.

## What is real and what is supplied locally

The checker imports the **whole unchanged Worker body**, replacing only its generated `routing.json` import with a small explicit fixture. That fixture selects `/healthz` for a10-second cache, matching the checked source policy. The generated JSON is not tracked at `edge/src/routing.json`; it is supplied at build time. No claim is made to have loaded a deployed routing manifest.

Native Node24.22.1 HTTP, `fetch`, Request/Response, body streams, socket resets and `AbortSignal.timeout` execute without monkeypatching. The source's **8,000ms timeout remains unchanged**. Header/body stalls exceed it; the checker retains observed durations rather than claiming a hard real-time SLA. Only Cloudflare's Cache/ASSETS/ctx bindings are supplied locally. Cache hit/put/exception behavior is therefore a fixture, not evidence of actual Cloudflare cache durability, TTL or outages.

Ten pinned source blobs and before/after Worker hashes are verified. Both listeners and connections close. The source and adapted-module SHA256s are retained. `node --check` passes for the checker. Original project tests, full Linux/Python/repository gates, Cloudflare workerd, production deployment, TLS/CDN/proxy behavior, HEAD/method variations and arbitrary non200 streaming failures are **not tested**. The targeted guard handles200-body consumption; a non200 streaming body that fails later is outside this claim. Existing #754 CORS work and merge conflicts are not resolved by this evidence.

## Reproducing and signing

For a reviewer with Node24, retain the exact main/candidate snapshots from `source-provenance.json`, put that provenance beside this checker and run `check_native_body.mjs SOURCE_ROOT REPORT.json`. Only loopback HTTP is used; no DID key or service account is required for tests. This optional technical reproduction is for reviewers; the beginner user's operations are agent-managed.

`validation.json` binds the checker, native report, source provenance and official-event review. The README and subsequent delivery receipts remain companion descriptions outside that manifest's hash set. The user's existing DID signs a summary containing an immutable manifest URL and SHA256; a delivery receipt is only marked verified after actual service readback.

[Official verification](https://flop.finance/official/) still says no airdrop is live; the [operator testnet profile](https://ask.flop.finance/networks/testnet) has no verified public enrollment/release. Development documentation is not an opened reward programme. This technical contribution and DID signature are not token entitlement or settled compute.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`20726596`, server timestamp `2026-10-29T06:01:31.708405Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
