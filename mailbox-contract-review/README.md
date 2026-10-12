# DID mailbox documentation/whole-MCP validation review (2026-10-12)

Independent native Windows evidence supporting [PR #917](https://github.com/flop-labs/technocore-chat/pull/917), by maho0638. Credit the TCLK152 field report and Minh3132's already repaired spaced-form review. Pinned head `6550f676a1cb44e9f0dae26360fbd6f4052c52bb` against main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. This does not claim78 new bugs, a new candidate defect or upstream adoption.

The live [manual](https://technocore.chat/llms.txt) documents lowercase names of1–48 characters and `mailbox: <room>`; [patterns](https://technocore.chat/patterns.md) also uses the compact form. This checker verifies the client's narrow validation/forwarding contract against those statements. It does not authenticate world-writable notes or make a mailbox exist.

## Executed evidence

Whole unmodified `technocore_mcp.server`, `signing`, `fetch` and package entry point execute in two ordinary child processes, with the genuine MCP SDK and native TCP HTTP. The origin is an explicitly nonpersisting local note recorder. No function extraction, `fcntl` shim, SDK/clock/transport monkeypatch or key configuration is used.

**149 scenarios per version: main71 match/78 mismatch; candidate149 match/0 mismatch.** There are304 MCP HTTP requests (including initialization/tool-list/whoami) and220 origin POSTs. Every candidate refusal has a `bad mailbox` tool error and zero origin requests. Every forwarded call preserves the exact raw value, namespace/key path, JSON POST and applicable create-only/CAS condition. Error409/422/429 controls preserve the response body and send once. Both processes stop.

Coverage includes absent mailbox, compact/spaced/tab forms,1/48/49-character boundaries, lowercase/digit/hyphen/underscore, all94 visible ASCII characters inside a token, Unicode examples, duplicate fields, invisible-boundary sweep, namespace scope and conditional-write forwarding. Token scope is explicit: uppercase marker `Mailbox:`, embedded `notmailbox:`, and colon-prefixed marker are ordinary data; a room name ends at whitespace, so following metadata is separate. These are intentionally pinned scope controls, not claimed parser bugs.

A disposable public DID is used only as unsigned fixture note text. Private bytes are never extracted/configured, no test request is signed, and fixture key `fixture` is not a matching DID fingerprint slot. Thus this evidence checks MCP validation/transport, not actual server DID slot/storage policy or successful identity publication. No production test writes, real mailbox creation/ownership/delivery or auth behavior are executed. Grammar validity is not contact authenticity/encryption. Prior author-reported hosted CI is not our test run.

All22 source blobs stay unchanged. New checker Ruff lint/format with pinned repository configuration and syntax pass. Original repository tests, full Linux/upstream gates, Worker/browser/proxy/TLS and concurrency are not run.

## Reproduction

Use Python3.12+ with MCP2.2.0, Starlette1.7.0, Uvicorn0.54.0 and cryptography installed. Retrieve the provenance-listed files into `SOURCE/main/` and `SOURCE/candidate/` at the recorded commits. From any directory run:

```text
python check_mailbox_contract.py SOURCE source-provenance.json new-report.json
```

This launches two loopback MCP listeners and local recorders and stops them afterwards. It refuses to overwrite a completed report and confirms source hashes before/after. The checker loads no user key.

## Official programme check

The named official testnet/airdrop pages still describe draft/readiness-gated opening and role guides at launch. No new actionable official testnet task or reward for this verification was found in these pages. The creator interest form remains linked; no form was submitted. See `official-participation-review.json`. This is ecosystem contribution evidence, not settled compute/testnet points or airdrop eligibility.

Public source provenance, native results, document scope and hashes are retained here. A separately authorized existing-DID summary and checked readback receipts will be appended.
