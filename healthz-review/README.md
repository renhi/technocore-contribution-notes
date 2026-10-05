# Windows native-fetch validation of PR #957

Prepared by renhi with Codex assistance on 2026-10-05. This independently authored probe executes the Worker modules from pinned official main and [PR #957](https://github.com/flop-labs/technocore-chat/pull/957), using **real loopback HTTP, Node native fetch and the unchanged 8000 ms origin deadline**. It adds Windows transport evidence rather than a competing fix.

Credit to almondous for the fix and existing regression/hosted validation, and to zeycan1 for the related complete-response guard and scope discussion in #705. This does not claim the initial discovery or production deployment.

## Pinned sources and actual result

- Before: official main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.
- After: candidate `fbcbbf3ab5c3f831ab5a81c4fcd4dfe2af3fd57c`.
- File: `edge/src/worker.js`; Git blob and SHA-256 are checked before execution.
- Actual environment: Windows, Node version recorded in `native-results.json`.
- Same nine modes per version: **before 6 pass / 3 fail; after 9 pass / 0 fail**.

| Mode | Main | Candidate |
| --- | --- | --- |
| Healthy GET | One fetch, 200; shared cache write | Same |
| Empty healthy body | One fetch, 200; shared cache write | Same |
| Origin 503 | One fetch, 503; no cache write | Same |
| HEAD | One fetch, empty body; no cache write | Same |
| Cache hit | No origin request | Same |
| Cache match throws | Existing fail-open: one fetch without origin-deadline signal | Same; deliberately outside this fix |
| Headers received; body never completes | Two fetches; second fixture response 200 | One fetch, 503, `no-store`; about 8 seconds |
| Headers/partial body received; socket resets | Two fetches; second fixture response 200 | One fetch, 503, `no-store` |
| Invalid gzip response body | Native decompression fails; two fetches; second response 200 | One fetch, 503, `no-store` |

The stalled-body sample took 8032.17 ms on main and 8046.99 ms on the candidate. This is not a speedup claim: the meaningful difference is the extra unbounded request and returned status. The fixture intentionally answers the second request healthily so the old fallback can be observed without hanging. These are single local observations, not production performance estimates or a universal exact wall-clock guarantee.

## What is real and what is supplied

The HTTP server binds only `127.0.0.1` at a dynamically assigned port. Requests use Node's native fetch and actual socket/body/decompression behavior. The fetch wrapper counts requests and delegates to native fetch unchanged; it does not synthesize the response-body failures or add a deadline to fallback requests.

The routing import is replaced with a minimal `/healthz` platform binding; no other Worker code or timeout constant is changed. `caches.default` is an in-memory binding, and `ASSETS.fetch` fails the test if touched. The cache-error case explicitly preserves the existing fail-open policy. A 20-second harness watchdog bounds a broken case; it is not the Worker's origin deadline.

Cloudflare's deployed runtime, its real Cache API, query canonicalization from #754, the #705 combined branch, and full upstream CI were not executed. This confirms the isolated PR's Node/Windows transport behavior, not all deployment behavior. Remote-service requests, private-key usage and financial transactions are zero. The author has already supplied separate validation; this package is complementary evidence, not merge approval.

## Reproduce with an assisting agent

Download and review `edge/src/worker.js` from these immutable references:

- `https://raw.githubusercontent.com/flop-labs/technocore-chat/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/edge/src/worker.js`
- `https://raw.githubusercontent.com/almondous/technocore-chat/fbcbbf3ab5c3f831ab5a81c4fcd4dfe2af3fd57c/edge/src/worker.js`

Save them as `before-worker.js` and `after-worker.js`, and run Node 24:

```text
node native_healthz_probe.mjs before-worker.js after-worker.js source-provenance.json results.json
```

No package installation is needed. The probe checks both hashes before importing the reviewed code. It imports complete Worker modules with the routing binding supplied; this is not a security sandbox for arbitrary code. The beginner user need not type the command. Expect roughly 16 seconds of deliberate origin-timeout waiting plus local overhead.

`native-results.json` includes both summaries, all 18 observations, request/deadline counts, cache writes and local durations. `validation.json` summarizes the scope and verified checker hash. Source files are fetched separately, not redistributed here. The assisting agent also checked the current PR head before publication.

## 한국어 설명

서버 상태를 확인할 때 응답의 앞부분만 도착하고 나머지가 멈추거나 끊어질 수 있습니다. 기존 코드는 이때 추가 요청을 하지만, 수정안은 약 8초의 대기 시간 안에서 처리하거나 즉시 오류를 반환했습니다. 실제 로컬 연결로 같은 9가지 상황을 비교해 수정안의 결과를 확인했습니다. 운영 서버를 점검·변경한 것이 아니며, 공식 채택이나 에어드랍 인정은 미확인입니다.

Independently authored probe: Apache-2.0; see the companion repository root LICENSE.
