"""Independent regression extension for HE-Lingfeng/technocore-receipts.

By renhi, with credit to HE-Lingfeng for the auditor and existing test helpers.
All keys are disposable in memory; records are synthetic and never posted.
"""

import base64
import copy
import hashlib
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from technocore_receipts.audit import audit_stream, public_key
from test_audit import did_for

OBSERVATIONS = []


class NonceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.did = did_for(self.key)
        self.room = "demo-room"
        self.text = "한글 복원 시험 · synthetic only"

    def record(self, spelling="007", seq=1):
        signature = base64.urlsafe_b64encode(
            self.key.sign(f"{self.room}|{spelling}|{self.text}".encode("utf-8"))
        ).decode().rstrip("=")
        return {"seq": seq, "ts": "2026-10-06T00:00:00Z", "from": self.did,
                "nonce": int(spelling), "text": self.text, "sig": signature}

    def raw(self, records, newline="\n"):
        return "".join(json.dumps(r, ensure_ascii=True) + newline for r in records).encode()

    def audit(self, records, room=None):
        return audit_stream(io.BytesIO(self.raw(records)), room=room or self.room)

    def observe(self, case, actual, expected):
        OBSERVATIONS.append({"case": case, "actual": actual, "expected": expected,
                             "matched": actual == expected})
        self.assertEqual(actual, expected, case)

    def test_integer_nonce_spellings_round_trip(self):
        for number in (7, 12, 9007199254740993001):
            shortest = str(number)
            for width in range(len(shortest), 20):
                spelling = shortest.zfill(width)
                with self.subTest(number=number, width=width):
                    report = self.audit([self.record(spelling)])
                    entry = report["records"][0]
                    recovered = spelling != shortest
                    actual = {"status": report["status"], "signature": entry["signature"],
                              "nonce": entry.get("nonce"),
                              "recovered": entry.get("nonce_spelling_recovered", False),
                              "stored_nonce": entry.get("stored_nonce")}
                    expected = {"status": "passed", "signature": "valid", "nonce": spelling,
                                "recovered": recovered, "stored_nonce": number if recovered else None}
                    self.observe(f"integer-{number}-width-{width}", actual, expected)

    def test_explicit_nonce_strings_are_not_guessed(self):
        for spelling, expected in [("007", "passed"), ("7", "failed")]:
            with self.subTest(spelling=spelling):
                record = self.record("007")
                record["nonce"] = spelling
                self.observe("explicit-string-" + spelling,
                             self.audit([record])["status"], expected)

    def test_tampering_is_still_rejected(self):
        for field in ("text", "nonce", "from", "room"):
            with self.subTest(field=field):
                record = self.record()
                room = self.room
                if field == "text":
                    record["text"] += " changed"
                elif field == "nonce":
                    record["nonce"] = 8
                elif field == "from":
                    record["from"] = did_for(Ed25519PrivateKey.generate())
                else:
                    room = "other-room"
                self.observe("tampered-" + field, self.audit([record], room=room)["status"], "failed")

    def test_signature_padbit_aliases_remain_malformed(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        original = self.record()
        start = alphabet.index(original["sig"][-1])
        self.assertEqual(start % 16, 0)
        for delta in range(1, 16):
            with self.subTest(delta=delta):
                record = copy.deepcopy(original)
                record["sig"] = original["sig"][:-1] + alphabet[start + delta]
                self.observe(f"padbit-alias-{delta}", self.audit([record])["records"][0]["issues"],
                             ["invalid_signature_encoding"])

    def test_invalid_nonce_types_remain_rejected(self):
        values = (True, False, 7.0, -7, None, "１２３", "1e1", "1" * 20)
        for index, value in enumerate(values):
            with self.subTest(index=index):
                record = self.record()
                record["nonce"] = value
                self.observe(f"invalid-nonce-{index}", self.audit([record])["records"][0]["issues"],
                             ["invalid_nonce"])

    def test_failed_recovery_has_a_protocol_bound(self):
        for number, limit in [(7, 19), (12, 18), (9007199254740993001, 1)]:
            with self.subTest(number=number):
                record = self.record(str(number))
                record["text"] += " changed"
                verifier = Mock(wraps=public_key(self.did))
                with patch("technocore_receipts.audit.public_key", return_value=verifier):
                    report = self.audit([record])
                self.observe(f"bounded-failure-{number}",
                             {"status": report["status"], "checks": verifier.verify.call_count},
                             {"status": "failed", "checks": limit})

    def test_numeric_nonce_order_is_preserved(self):
        for next_spelling, status in [("0007", "failed"), ("0008", "passed")]:
            with self.subTest(next_spelling=next_spelling):
                report = self.audit([self.record("007", 1), self.record(next_spelling, 2)])
                actual = {"status": report["status"],
                          "valid": report["summary"]["signatures"]["valid"],
                          "nonce_warning": "nonce_not_increasing" in report["records"][1]["issues"]}
                self.observe("nonce-order-" + next_spelling, actual,
                             {"status": status, "valid": 2, "nonce_warning": status == "failed"})

    def test_input_hashes_and_output_privacy_are_preserved(self):
        for label, newline in [("lf", "\n"), ("crlf", "\r\n")]:
            with self.subTest(label=label):
                raw = self.raw([self.record()], newline)
                report = audit_stream(io.BytesIO(raw), room=self.room)
                actual = {"status": report["status"],
                          "file_hash": report["evidence"]["sha256"] == hashlib.sha256(raw).hexdigest(),
                          "line_hash": report["records"][0]["line_sha256"] == hashlib.sha256(raw).hexdigest(),
                          "body_omitted": self.text not in json.dumps(report, ensure_ascii=False),
                          "history_verified": report["coverage"]["whole_room_history_verified"]}
                self.observe("hash-privacy-" + label, actual,
                             {"status": "passed", "file_hash": True, "line_hash": True,
                              "body_omitted": True, "history_verified": False})

    def test_actual_cli_exit_and_report(self):
        for room, expected_exit, expected_status in [(self.room, 0, "passed"),
                                                      ("other-room", 1, "failed")]:
            with self.subTest(room=room):
                p = subprocess.run([sys.executable, "-X", "utf8", "-m", "technocore_receipts",
                                    "-", "--room", room], input=self.raw([self.record()]),
                                   capture_output=True, timeout=10)
                report = json.loads(p.stdout)
                self.observe("cli-" + room, {"exit": p.returncode, "status": report["status"]},
                             {"exit": expected_exit, "status": expected_status})


if __name__ == "__main__":
    unittest.main()
