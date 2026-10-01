"""Offline regression contribution for technocore-chat PR #238.

Builds on osr21's existing canonical-base64 finding, not a new vulnerability report:
https://github.com/flop-labs/technocore-chat/pull/238#issuecomment-5512590300

Run with Python 3.12+ and cryptography installed:
    python test_verify_cli.py --verifier /path/to/scripts/verify.py

All signing keys are disposable test keys, generated only in memory. This suite
does not contact Technocore, write keys, or claim any contribution credit.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
VERIFIER: Path
OBSERVATIONS: list[dict] = []


def did_for(key: Ed25519PrivateKey) -> str:
    n = int.from_bytes(b"\xed\x01" + key.public_key().public_bytes_raw(), "big")
    encoded = ""
    while n:
        n, remainder = divmod(n, 58)
        encoded = B58[remainder] + encoded
    return "did:key:z" + encoded


class VerifyCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = Ed25519PrivateKey.generate()
        cls.did = did_for(cls.key)
        cls.nonce = "9007199254740993001"  # 19 digits, beyond exact JS Number range.
        cls.text = "한글 서명 검증 · 안녕하세요"
        cls.room = "offline-review"
        cls.namespace = "offline-review"
        cls.note_key = "result"

    def signature(self, canonical: str) -> str:
        return base64.urlsafe_b64encode(self.key.sign(canonical.encode("utf-8"))).decode().rstrip("=")

    def arguments(self, lane: str, text: str | None = None):
        value = self.text if text is None else text
        fields = [self.room] if lane == "say" else [self.namespace, self.note_key]
        canonical = "|".join([*fields, self.nonce, value])
        sig = self.signature(canonical)
        return [lane, self.did, sig, self.nonce, *fields, value]

    def check_cli(self, args: list[str], expected: int, case: str):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", str(VERIFIER), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        OBSERVATIONS.append({"case": case, "expected": expected, "actual": completed.returncode})
        self.assertEqual(
            completed.returncode, expected,
            f"{case}: stdout={completed.stdout!r}; stderr={completed.stderr!r}",
        )
        if expected == 0:
            self.assertIn(f"OK {self.did}", completed.stdout)
        if expected == 2:
            self.assertNotIn("OK ", completed.stdout)
            self.assertTrue(completed.stderr.strip())

    def test_valid_korean_say_and_set(self):
        for lane in ("say", "set"):
            with self.subTest(lane=lane):
                self.check_cli(self.arguments(lane), 0, f"{lane}: Korean, exact 19-digit nonce")

    def test_all_noncanonical_padbit_aliases(self):
        for lane in ("say", "set"):
            args = self.arguments(lane)
            original = args[2]
            start = B64.index(original[-1])
            self.assertEqual(start % 16, 0)
            raw = base64.urlsafe_b64decode(original + "==")
            for delta in range(1, 16):
                with self.subTest(lane=lane, pad_bits=delta):
                    alias = original[:-1] + B64[start + delta]
                    self.assertEqual(base64.urlsafe_b64decode(alias + "=="), raw)
                    altered = [*args]
                    altered[2] = alias
                    self.check_cli(altered, 2, f"{lane}: nonzero pad bits {delta}")

    def test_changed_text_is_rejected(self):
        for lane in ("say", "set"):
            with self.subTest(lane=lane):
                args = self.arguments(lane)
                args[-1] += " 변경"
                self.check_cli(args, 3, f"{lane}: changed text")

    def test_wrong_room_or_namespace_is_rejected(self):
        for lane in ("say", "set"):
            with self.subTest(lane=lane):
                args = self.arguments(lane)
                args[4] = "another-context"
                self.check_cli(args, 3, f"{lane}: changed context")

    def test_wrong_key_is_rejected(self):
        args = self.arguments("say")
        args[1] = did_for(Ed25519PrivateKey.generate())
        self.check_cli(args, 3, "say: wrong public key")

    def test_bad_encoding_is_rejected(self):
        args = self.arguments("say")
        for label, sig in (("truncated", args[2][:-1]), ("padded", args[2] + "=="),
                           ("invalid alphabet", "!" + args[2][1:])):
            with self.subTest(label=label):
                modified = [*args]
                modified[2] = sig
                self.check_cli(modified, 2, f"say: {label}")
        args[1] = "did:key:invalid"
        self.check_cli(args, 2, "say: malformed DID")

    def test_nonce_format_is_rejected(self):
        for nonce in ("１２３", "1" * 20, "-1"):
            with self.subTest(nonce=nonce):
                args = self.arguments("say")
                args[3] = nonce
                self.check_cli(args, 1, f"say: invalid nonce {nonce}")

    def test_zero_nonce_is_valid_for_offline_tuple(self):
        args = self.arguments("say")
        args[3] = "0"
        args[2] = self.signature(f"{self.room}|0|{self.text}")
        self.check_cli(args, 0, "say: zero nonce tuple (not server replay admission)")

    def test_sweep_matches_signed_visible_text(self):
        for lane in ("say", "set"):
            with self.subTest(lane=lane):
                args = self.arguments(lane, "안녕 하세요")
                args[-1] = "  안녕\u200b하세요\n"
                self.check_cli(args, 0, f"{lane}: Unicode sweep")


def main():
    global VERIFIER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verifier", required=True, type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    VERIFIER = args.verifier.resolve(strict=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerifyCLI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "test_methods": result.testsRun,
        "cli_cases": len(OBSERVATIONS),
        "mismatches": sum(row["expected"] != row["actual"] for row in OBSERVATIONS),
        "errors": len(result.errors),
        "success": result.wasSuccessful(),
        "external_requests": 0,
        "production_identity_created": False,
        "observations": OBSERVATIONS,
    }
    if args.json_report:
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
