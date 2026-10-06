# Independent review of technocore-receipts: integer nonce spelling recovery

Target: **HE-Lingfeng/technocore-receipts**, commit `e07820196035ce60aa34408052550ce11518a659`, introduced in [Technocore issue #965](https://github.com/flop-labs/technocore-chat/issues/965). This is an external companion tool, not an adopted FLOP Labs component. Credit to HE-Lingfeng for the auditor and its original 40 tests. renhi prepared this independent reproduction, proposed correction and additional regressions.

## Reproduced compatibility problem

A protocol-valid nonce spelling such as `007` is signed verbatim. The server's signature checker accepts that tuple; the message route then passes `int(nonce)` to storage. Thus a native record can retain `nonce: 7` and a signature over `room|007|text`.

At the pinned tool version, an integer record is checked only as `room|7|text` and is reported as `signature_mismatch`. The existing leading-zero test uses a **string** nonce, so it does not exercise the server's integer storage conversion. This is a false negative for a producer-compatible synthetic record, not evidence of a forged signature or a production incident.

References on official main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`: [message write route](https://github.com/flop-labs/technocore-chat/blob/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/src/app.py#L1389), [integer conversion](https://github.com/flop-labs/technocore-chat/blob/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/src/app.py#L1400), [retained nonce and signature](https://github.com/flop-labs/technocore-chat/blob/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/src/store.py#L2634), [protocol](https://technocore.chat/auth.md).

## Proposed correction

`nonce-recovery.patch` changes the external auditor, its English README and adds `tests/test_nonce_recovery.py`. It does not change Technocore's server or the original tests.

- First try the integer's shortest decimal spelling, preserving the normal fast path.
- Only after a signature mismatch on an **integer** nonce, test the remaining leading-zero spellings up to 19 digits. Accept only a spelling that verifies with the supplied public key, room, text and signature.
- There are at most **19 total cryptographic checks per record**, including the original check. Explicit string nonces remain exact and are never padded; malformed encodings, booleans and floats remain rejected.
- On recovery, the report's `nonce` is the recovered signed spelling. Optional `stored_nonce` and `nonce_spelling_recovered: true` fields explain the difference. Numeric nonce ordering, input bytes and hashes remain unchanged.

This is bounded cryptographic recovery, not guessing a valid signature or claiming that any stored integer alone proves an original spelling. It requires the retained signature and all other signed fields. A changed text, room, signer or numeric nonce still fails.

## Validation

Windows CPython 3.12.14, cryptography 50.0.1; all synthetic keys generated in memory and discarded.

| Validation | Original pinned source | Proposed candidate |
|---|---:|---:|
| Original author tests | 40 pass | 40 pass, unchanged |
| New test methods / fixture cases | 9 / 76 | 9 / 76 |
| New fixture expectations matched | 34 | 76 |
| New fixture expectations unmet | 42 | 0 |
| Combined unittest discovery | — | 49 methods pass |

The 42 unmet expectations are manifestations and recovery-bound expectations around one missing recovery path, not 42 independent bugs. The 76 fixtures cover all allowed widths for integers 7, 12 and a 19-digit value, exact string behavior, tampering, 15 noncanonical pad-bit aliases, invalid nonce types, actual verification-call bounds, numeric replay warnings, LF/CRLF hashes, report privacy and CLI exit/report behavior.

The `007` tuple was independently accepted by the actual `src/didkey.py` verifier on pinned official main. The record is synthetic and follows the route's integer conversion; the complete server, its replay admission, and filesystem storage were not executed. No live export or participant record was downloaded for these tests.

The patch passes `git apply --check` against the unchanged pinned checkout. Its existing test files remain byte-identical. The complete external-tool test suite passed after applying the candidate. There are no additional lint/type gates defined by this external repository's AGENTS.md.

## Reproduce or integrate

For a reviewer with the pinned external checkout and cryptography installed:

```sh
python check_nonce_recovery.py --source /path/to/checkout --json-report /path/to/report.json
```

Run from the target checkout so the subprocess CLI resolves that version. Keep reports outside it. Before applying the proposal, the independent suite is expected to fail; after applying `nonce-recovery.patch`, run the project's ordinary gate:

```sh
python -m unittest discover -s tests -v
```

The independent runner uses the companion `test_nonce_recovery.py` and the author's existing `tests/test_audit.py` helper. The patch already includes the new test file; do not copy it again over a changed checkout. Fetch current upstream before applying if it has moved.

## Limits and status

The proposal can increase CPU work for invalid integer signatures by up to 19-fold in verification-call count. The existing byte and record caps remain, but are not a CPU deadline. This is not a performance benchmark, and additional report fields may require consumer review. Only the English README is updated in the proposal.

No user keys, network calls by tests, hosted writes, trading-client changes, frozen-rule changes, payments or airdrop checks. This packet is published in renhi's own evidence repository. **The author's repository and issue #965 are unchanged; no new PR or comment was sent.** Official adoption, external use and airdrop eligibility are unconfirmed. The existing native-server CI was not run; this evidence covers the independent Python tool only.

Source Git blobs and test hashes are recorded in `source-provenance.json`. `upstream-LICENSE.txt` reproduces the original MIT license for code context in the proposed patch; the original tool's authorship is retained.
