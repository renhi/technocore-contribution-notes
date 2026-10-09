# Native Windows MCP nonce-floor recovery evidence — PR #930

This independently authored checker complements [omerbek's PR #930](https://github.com/flop-labs/technocore-chat/pull/930)
for [maho0638's issue #916](https://github.com/flop-labs/technocore-chat/issues/916).
The defect and fix were already reported; bdunn77 and ShalyX also published Linux
validation. Credit belongs to those contributors. This is additional native Windows
wire/crypto evidence, not a new discovery, implementation or merge approval.

When another signer has used a higher nonce for the same key, the configured MCP signer
can mint a lower nonce from its millisecond clock. The refused request names the floor.
The candidate learns it, signs again above it, and limits recovery to two re-signs.

## Sources and actual execution

- Main/base: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.
- PR head: `f2eb208eb6fdf150cf7aaac161d1b196f68f8676`.
- 18 immutable source files were checked against public Git blob hashes; loaded bytes
  are checked again by the independent checker. Neither source package is modified.
- Native Windows, Python 3.12.14, MCP 2.2.0, Uvicorn 0.54.0, Starlette 1.7.0,
  cryptography 50.0.1 and PyNaCl 1.6.2; full package versions are in the result JSON.
- The actual console `main()` serves streamable HTTP. Actual JSON-RPC initialize and
  tools/call traverse the MCP SDK, tool validation, original handlers and urllib.
- Both versions use actual upstream `src/didkey.py` and PyNaCl to independently verify
  every origin request. Altering each canonical string must invalidate its signature.
  No SDK, tool handler, fetch seam, nonce clock or crypto module is mocked.

**The origin is a controlled local HTTP fixture, not the Linux chat server.** Its nonce
floors and refusals are scripted with the main server's wording. It does not implement
the store, ownership authorization/CAS, retention, rate limiter or concurrent isolates.
`accepted_in_fixture` is a fixture counter; it is not an actual retained server record.

## Results

Each of the three signed tools (`say_signed`, `claim_room`, `set_room_allow`) runs the
same nine scenarios: one refusal then recovery, two refusals then recovery, recovery
followed by another call, a continuously moving floor, a caller-supplied signature,
ordinary success, and HTTP 429 / 422 / 409 controls.

| Observation | Unmodified main | PR candidate |
| --- | --- | --- |
| Scenario expectations matched | 18/27 | 27/27 |
| Recovery scenario mismatches | 9 | 0 |
| Actual origin POSTs | 30 | 48 |
| Actual MCP HTTP requests (initialize + 30 tools/call) | 31 | 31 |
| Verified signatures and rejected altered canonicals | 30 each | 48 each |

The nine mismatches are manifestations of the existing recovery gap, not nine different
bugs. Every recovered candidate request is re-signed above the named floor. Continuous
contention ends after three total POSTs with a tool error and zero fixture acceptances.
The configured signer does not re-sign an externally supplied tuple: one POST, nonce 9
unchanged, and the refusal returned to the caller. Complete 429/422/409 bodies are
preserved, and each of those controls sends exactly one POST. These findings cover the
tested bodies; arbitrary proxy/refusal text and all parser inputs are not proven safe.

Message cases carry Korean NFC text, Hangul jamo, an emoji, a newline and a zero-width
character. The original raw text stays identical on every request; signatures cover
the documented single-line sweep, with no Unicode normalization. Floor values are
legal 19-digit integers starting at `9007199254740993001`, beyond JavaScript's exact
integer range, and travel as exact decimal strings.

The follow-up `claim_room` uses a new room: a successful create-only claim cannot be
repeated for the same room. Its new-room floor starts at zero; the learned process
nonce remains high. Main's first claim fails but its new-room follow-up succeeds;
the full two-call expectation still fails. This is not an ownership/CAS test.

## Reproduction and limitations

`check_native_nonce.py` accepts a snapshot root containing `before/` and `after/`,
the supplied source-provenance JSON and an output JSON path. Each snapshot contains
the exact recorded source paths. With the recorded dependencies and local socket
permission, it launches two temporary MCP listeners and checks both versions. Its
exit code is zero when the candidate matches all 27 scenarios; main's nine expected
mismatches remain in the report. Ruff lint and format checks pass using the pinned
upstream configuration.

All HTTP requests are to 127.0.0.1. Disposable keys are generated in memory and supplied
only in child environments, never command arguments, report files or MCP tool fields.
Externally supplied signatures are public signature data. No user key, remote service,
wallet or financial transaction is involved. Listener processes are stopped afterward.

The original PR test modules and full Linux repository CI were not run here. No real
Cloudflare/Pyodide deployment, actual concurrent isolate, nonce-space exhaustion or
platform timeout was tested. The candidate and official source/installed package were
not changed. No new PR, upstream comment or public chat message was posted.
Official adoption, third-party use and airdrop eligibility remain unconfirmed.
AI-assisted research and checker authoring.
