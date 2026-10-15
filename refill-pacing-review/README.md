# Refill advice: exact arithmetic and native real-clock pacing (2026-10-15)

Independent evidence for [noviceborsaeng PR979](https://github.com/flop-labs/technocore-chat/pull/979), head `67809ef383eaea13c0290e1b5337f6023da0385d` against main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. Credit WIZARDspace and finegel's prior high-rate rounding finding and integer-floor proposal. This complements their review with observed isolated HTTP pacing; neither the issue nor the one-line companion is claimed as a new discovery.

## What executed

An exact Fraction oracle interprets actual advice text as a client interval and compares it with60/per_min. It checks integer1..1200/min, including1..59 period form and60..1200 rate form. It also checks the same phrase is present in the actual selected429 body and write budget footer.

Main has696/1200 safe advice values; PR979 has725/1200 and fixes all low-rate period values. Its unchanged high-rate branch still overstates475 budgets, the previously reported issue. The credited one-line companion floors that branch:1200/1200 safe in this scope. These are input variations of two shared rounding branches, not hundreds of distinct bugs.

Native integration uses **five unchanged AST-selected functions and exact state assignments**, a whole genuine config module, real Starlette/Uvicorn sockets, actual time.monotonic and time.sleep. It does NOT import the whole Linux limit/store/app. There is no fcntl/store shim or clock patch. A fixture text callback supplies PlainTextResponse, not the official app's headers/adapter.

Six rates per version (11,30,45,60,63,70),54 native HTTP GETs total. For each, an isolated burst1 bucket grants once, refuses the immediate repeat, then receives a request paced from the refusal's advertised **refill cadence**, not Retry-After. Original/candidate/companion show4/1/0 observed early refusals. All18 elapsed-time classifications match the observed bucket behavior. Native timing has a1ms uncertainty margin; full timestamps/waits are retained and oversleep may mask an unsafe instruction. Exact arithmetic, not wall-clock samples alone, establishes the bounded advice invariant.

This is one caller/no competing traffic and burst1, not the production minute-sized burst/default configuration, fairness, limiter throughput or general scheduling guarantee. Retry-After rounding/PR887, clocks beyond tested observations, fractional/daily budgets, huge integers, Worker/proxy/CDN/concurrency and full Linux/upstream CI remain outside scope. The companion applies on top of PR979, not main alone. No new PR/comment or upstream incorporation.

All8 original Git blobs remain unchanged. Executed hashes, checker Ruff lint/format under pinned project config, syntax and companion patch apply-check pass. No protected user key or wallet is used by the checker, and no public service is contacted.

## Reproduce

Use Python3.12+, Starlette/Uvicorn versions from validation. Retrieve provenance files into `SOURCE/main` and `SOURCE/candidate`; copy candidate `src/limit.py` and `src/config.py` to `SOURCE/proposed/src`, and apply `safe-rate-companion.patch`. Run:

```text
python check_refill_pacing.py SOURCE source-provenance.json new-report.json
```

This starts/stops local listeners, performs real sleeps (roughly40seconds total depending on scheduling), checks original hashes and refuses to overwrite a completed report. It executes selected trusted source functions; no whole-server compatibility is claimed.

Prepared by renhi with Codex. The separately authorized existing-DID factual summary and readback receipts will be retained here. No official role, airdrop qualification, settled compute or project adoption is established.
