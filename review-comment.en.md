Building on [osr21's existing pad-bit finding](https://github.com/flop-labs/technocore-chat/pull/238#issuecomment-5512590300), I prepared a CLI regression suite and a minimal fix for `scripts/verify.py` at `93bdfd0331de9c30c2693141a0ce166cfb69f186`. Credit to dhasap for the verifier and osr21 for identifying the mismatch.

The suite exercises all 15 noncanonical base64url pad-bit variants of a real signature on both the `say` and `set` lanes. Each variant decodes to the same bytes, but should exit 2 as malformed, matching `src/didkey.py` at main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`.

On Windows with Python 3.12.14 and cryptography 50.0.1:

- Original candidate: 9 test methods, 47 CLI cases, 30 mismatched outcomes (the 15 variants on each lane are incorrectly accepted).
- After the narrow patch below: all 47 CLI outcomes match expectations.
- The remaining cases cover Korean UTF-8 text, a 19-digit nonce beyond JavaScript's exact integer range, zero nonce for an offline tuple, Unicode sweeping, content/context tampering, wrong key, malformed DID/signature, and invalid nonce spelling.
- Independently, the unmodified main verifier accepted two canonical test signatures and rejected all 30 aliases as malformed.

```diff
-    if not re.fullmatch(rf"[A-Za-z0-9_-]{{{SIG_CHARS}}}", sig or ""):
-        _die2(f"bad signature: expected {SIG_CHARS} base64url characters")
+    if not re.fullmatch(rf"[A-Za-z0-9_-]{{{SIG_CHARS - 1}}}[AQgw]", sig or ""):
+        _die2(f"bad signature: expected {SIG_CHARS} base64url characters ending AQgw")
```

This is additional regression coverage for the existing report, not a newly discovered live-service vulnerability. The tests are offline and use disposable keys held only in memory. Full upstream server/CI checks and live signed writes were not run. The separate documentation concern already raised in the thread remains outside this patch.

The companion files are `test_verify_cli.py`, `canonical-signature.patch`, `before.json`, `after.json`, and `validation.json`. The suite can be adapted into the project's existing test layout; this follow-up does not open a competing verifier PR. Prepared with Codex assistance.

Companion repository: https://github.com/renhi/technocore-contribution-notes

- [Regression suite](https://github.com/renhi/technocore-contribution-notes/blob/main/test_verify_cli.py)
- [Proposed patch](https://github.com/renhi/technocore-contribution-notes/blob/main/canonical-signature.patch)
- [Validation evidence](https://github.com/renhi/technocore-contribution-notes/blob/main/validation.json)
