# PR #754: native local-origin CORS/cache regression

Independent contribution by **renhi**, assisted by Codex, 2026-10-09. Original query-key change: **luch91**. The cross-origin header mixing was already reported by **yukkie3276** in [this review](https://github.com/flop-labs/technocore-chat/pull/754#issuecomment-6073595328). This is additional executable evidence and a companion proposal, not a new discovery, an upstream fix, or merge approval.

Pinned main: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.
Pinned PR head: `8cf6d7d71df4b62ef1c6ba99c659a440f24f6c97` (open, unmerged when checked).

| Version | Matching scenarios | Mismatches | Native /healthz requests |
|---|---:|---:|---:|
| main | 15/16 | 1 | 31 |
| PR head | 8/16 | 8 | 20 |
| companion proposal | 16/16 | 0 | 32 |

The 48 scenarios made 83 actual loopback `/healthz` HTTP requests. Controller reset/audit requests are separate. Main's sole mismatch is the desired query collapse. The PR's eight mismatches are different request orders exposing the same previously reported cache-key/header gap, **not eight distinct bugs**.

The unchanged complete Worker module runs under native Node Fetch/Request/Response. Its routing literal is generated from each pinned `edge/snapshot.py`; the only source substitution is the routing import. Node fetch goes to a real local Starlette `CORSMiddleware` served by Uvicorn. The origin policy allows two example sites, rejects another, and excludes credentials. Its health handler is a fixture, not the full Technocore server. HTTP/SDK responses are not fabricated.

The **cache is an in-memory substitute** matching URL plus request headers named by response `Vary`. On main, `Vary: Origin` can distinguish the original request headers in this model. The PR uses a headerless canonical cache Request but retains Origin on the real origin request, so the stored response can have the wrong `Access-Control-Allow-Origin` for subsequent callers. This model does not establish deployed Cloudflare behavior. No actual browser CORS enforcement, cache TTL/eviction/isolate behavior, Wrangler runtime/deployment, full Linux repository tests, or upstream CI was run. No production incident or private-data disclosure is claimed. See the [official Cache API documentation](https://developers.cloudflare.com/workers/runtime-apis/cache/) for deployment-specific requirements.

The narrow proposal skips shared cache lookup and storage when the incoming request **has** an Origin header, including an empty one; those successful responses receive `Cache-Control: no-store`. Origin-free requests retain canonical query collapse and cache hits. Caller headers and canonical origin URL are preserved. HEAD, OPTIONS, POST/405 and uncached 503 controls are covered. Origin-bearing repeated requests now reach the origin each time: 32 requests versus 20 for the candidate in this fixture. Other health endpoint deadline issues are outside this proposal.

## Reproduction for maintainers

Use Python 3.12 with Starlette/Uvicorn and native Node (tested Python 3.12.14, Starlette 1.7.0, Uvicorn 0.54.0, Node v24.19.0 on Windows). Download the six files per version enumerated in `source-provenance.json` into `sources/main/` and `sources/candidate/`, preserving repository-relative paths, from their exact GitHub commits. Compare SHA256 and Git blob hashes against the provenance. The original test file is an untouched reference and was not executed.

Generate each `routing-fixture.json` using this Python snippet from the directory containing `sources/`. This imports snapshot definitions only; it does not call the snapshot network/deployment entry point. Document content types are empty because only health routes are exercised.

```python
import importlib.util, json
from pathlib import Path
for label in ('main', 'candidate'):
    folder = Path('sources') / label
    spec = importlib.util.spec_from_file_location(label, folder / 'edge/snapshot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    routing = dict(static_first=sorted(module.STATIC_FIRST),
                   edge_cached=module.EDGE_CACHED,
                   edge_revalidate=module.EDGE_REVALIDATE,
                   edge_only=sorted(module.EDGE_ONLY), types={},
                   edge_key=module.edge_key() if hasattr(module, 'edge_key') else module.rooms_key())
    (folder / 'routing-fixture.json').write_text(json.dumps(routing), encoding='utf-8')
```

Copy candidate's `edge/src/worker.js` into `sources/proposed/edge/src/worker.js`, then apply `cors-cache-bypass.patch` **inside sources/proposed**, leaving both pinned versions intact. The checker uses candidate routing for the proposal. Run:

```text
python run_native_cors.py --sources sources --node <native-node-executable> --output native-results.json
```

Exit zero means the proposal satisfied this fixture's expectations. Main/candidate mismatches remain in the report and are expected evidence; it is not an assertion that all versions passed. The local server is shut down after testing. Results embed the executed checker/source hashes. `validation.json` records hashes, checks and limits; `source-provenance.json` retains original authors/review credit. No user key or live Technocore requests were used during tests.

DID signing, if delivered, attests the statement and linked validation digest; it does not prove correctness, official acceptance, a role, testnet settlement or airdrop eligibility.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`16349356`, server timestamp `2026-10-09T14:55:56.958123Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
