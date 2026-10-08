# Native Windows MCP loopback compatibility evidence — PR #946

This independently authored artifact checks the actual console entry point, MCP SDK,
Uvicorn listener and HTTP security middleware on Windows. It complements Bornoz's
[PR #946](https://github.com/flop-labs/technocore-chat/pull/946) and its original tests;
bdunn77 already published an independent source/test review. Credit belongs to them
for the reported defect, patch and prior validation. No new implementation is proposed.

**Important counter-evidence: the reported bracketed IPv6 startup failure did not
reproduce on this Windows machine.** Both main and the candidate started successfully
with `[::1]` and `[0:0:0:0:0:0:0:1]`. Native Winsock `getaddrinfo` resolves those spellings
to `::1` here. This does not refute a failure on another OS and is not a Linux merge gate.

## Immutable sources and environment

- Main/base: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.
- PR head: `509de7dca711098ac40b2cdd7dea9cd09d79a0c3`.
- Python 3.12.14 on native Windows; MCP 2.2.0, Uvicorn 0.54.0 and Starlette 1.7.0.
- All four Python package files per version verified against the public Git blob and
  SHA-256 before execution. Snapshot files and installed packages were not modified.
- The actual `technocore_mcp.server.main()` runs in a child process with `--http`.
  No SDK replacement, extracted function or socket mock is used.

## Results

| Observation | Main | PR head |
| --- | --- | --- |
| Seven supported listener spellings start and answer initialize | 7/7 | 7/7 |
| Actual tools/list returns 13 tool schemas | 7/7 | 7/7 |
| Local Origin permitted | 7/7 | 7/7 |
| Foreign Host refused with HTTP 421 | 7/7 | 7/7 |
| Foreign Origin refused with HTTP 403 | 7/7 | 7/7 |
| `127.1` shorthand startup | Unsupported here | Unsupported here |

The seven successful settings are `[::1]`, `[0:0:0:0:0:0:0:1]`, `::1`,
`0:0:0:0:0:0:0:1`, `127.0.0.1`, `localhost` and `127.0.0.2`.
They account for 35 actual loopback HTTP requests per version. The eighth scenario
records Windows' `127.1` name-resolution refusal (process exit 3) in both versions;
it is a platform observation, not a fix or successful listener. All 8 scenario
expectations / 36 checks matched per version. These counts are not separate defects.

The PR preserves the tested MCP handshake, schema listing and Host/Origin guards on
this Windows setup. It must not be presented as reproducing the Linux startup defect
or fixing a Windows startup failure. Timing values are single-run observations.

## Reproducibility and boundaries

`check_native_bind.py` accepts four paths: main's `mcp/src`, head's `mcp/src`,
`source-provenance.json`, and the output JSON. Use those exact source commits and the
dependency versions recorded in `native-results.json`; the checker verifies source
bytes, starts/stops temporary listeners, performs initialize/tools/list, and fails
if the origin trap receives a request. It needs local socket permission and IPv6.
The `127.1` observation is specific to this Windows resolver, not a portable promise.

All HTTP traffic in the checker is loopback. It lists schemas but invokes no tools.
`TECHNOCORE_SIGNING_KEY` is removed from child environments and the chat origin is a
local trap that received zero requests. No production identity, remote writes, protected
key, wallet, transaction, automatic retry or public room data is involved. Child
processes are stopped after each scenario; their post-test termination codes do not
mean a successful listener failed at startup.

Upstream's original test module, full Linux server/CI, browser gates, Cloudflare runtime
and alternative SDK versions were not run. Ruff lint/format checks pass using the
pinned upstream configuration. This artifact is AI-assisted compatibility evidence;
upstream adoption, third-party use and airdrop eligibility remain unconfirmed.

Files: independent checker, final native results, immutable source provenance, and
validation summary. No upstream source is redistributed in this directory.
