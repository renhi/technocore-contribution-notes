"""Full offline CLI subprocess fixtures; disposable keys stay inside this process.

Usage: python test_bundle.py OFFICIAL_DIDKEY_SOURCE PROVENANCE_JSON REPORT_JSON
No real room, protected key, network write or upstream test module is used.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOM = "durable-fixture"
CASES = (
    "valid-no-room-present",
    "changed-payload",
    "missing-payload",
    "changed-manifest-bytes",
    "changed-announcement-text",
    "changed-signature",
    "signature-padbit-alias",
    "missing-signature",
    "nonce-changed",
    "original-string-nonce007",
    "stored-integer-loses-signed007",
    "wrong-external-room",
    "wrong-external-did",
    "wrong-verifier-pin",
    "changed-unsigned-seq-ts",
    "reserialized-archive-still-signature-valid",
    "extra-unselected-record-not-authenticated",
    "duplicate-selected-announcement",
    "archive-nonobject",
    "archive-missing-final-lf",
    "duplicate-manifest-json-key",
    "nonfinite-manifest",
    "unknown-profile",
    "empty-file-list",
    "unsafe-dotdot-path",
    "absolute-payload-path",
    "windows-drive-path",
    "windows-backslash-path",
    "duplicate-payload-path",
    "case-ambiguous-payload-path",
    "archive-in-manifest-cycle-refused",
    "manifest-in-manifest-self-refused",
    "oversized-payload",
    "oversized-manifest",
    "oversized-archive",
    "invalid-utf8-payload-is-raw-valid",
)
POSITIVE = {
    "valid-no-room-present",
    "original-string-nonce007",
    "changed-unsigned-seq-ts",
    "reserialized-archive-still-signature-valid",
    "extra-unselected-record-not-authenticated",
    "invalid-utf8-payload-is-raw-valid",
}


def public_did(key):
    number = int.from_bytes(b"\xed\x01" + key.public_key().public_bytes_raw(), "big")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    chars = ""
    while number:
        number, digit = divmod(number, 58)
        chars = alphabet[digit] + chars
    return "did:key:z" + chars


def main():
    verifier_path, provenance_path, report_path = map(Path, sys.argv[1:])
    assert not report_path.exists()
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    source = next(
        p for p in provenance["files"] if p["version"] == "main" and p["path"] == "src/didkey.py"
    )
    verifier_sha = hashlib.sha256(verifier_path.read_bytes()).hexdigest()
    assert verifier_sha == source["sha256"]
    checker = Path(__file__).with_name("verify_bundle.py")
    rows = []
    for name in CASES:
        with tempfile.TemporaryDirectory(
            dir=report_path.parent.resolve(), prefix="bundle-fixture-"
        ) as temp:
            base = Path(temp)
            assert base.resolve().is_relative_to(report_path.parent.resolve())
            (base / "payloads").mkdir()
            report_file = base / "payloads/결과.txt"
            binary_file = base / "payloads/raw.bin"
            report_file.write_bytes("독립 검증 결과\r\n".encode())
            binary_file.write_bytes(b"\x00\xff\xfe\x80raw payload\n")
            files = [
                {
                    "path": "payloads/결과.txt",
                    "sha256": hashlib.sha256(report_file.read_bytes()).hexdigest(),
                },
                {
                    "path": "payloads/raw.bin",
                    "sha256": hashlib.sha256(binary_file.read_bytes()).hexdigest(),
                },
            ]
            manifest = {"profile": "technocore-durable-example-v1", "files": files}
            key = Ed25519PrivateKey.generate()
            did = public_did(key)
            archive = base / "signed-records.jsonl"
            manifest_path = base / "manifest.json"

            def build(
                nonce="123",
                stored_nonce=None,
                *,
                manifest_path=manifest_path,
                manifest=manifest,
                key=key,
                did=did,
                archive=archive,
            ):
                manifest_path.write_bytes(
                    (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
                )
                digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                text = "bundle:v1 manifest-sha256:" + digest
                signature = (
                    base64.urlsafe_b64encode(key.sign(f"{ROOM}|{nonce}|{text}".encode()))
                    .decode()
                    .rstrip("=")
                )
                record = {
                    "from": did,
                    "text": text,
                    "nonce": int(nonce) if stored_nonce is None else stored_nonce,
                    "sig": signature,
                    "seq": 1,
                    "ts": "synthetic-not-server",
                }
                # Synthetic export line: preserve these exact bytes before modifications.
                exported = (
                    json.dumps(record, ensure_ascii=False, separators=(", ", ": ")) + "\n"
                ).encode()
                archive.write_bytes(exported)
                assert archive.read_bytes() == exported
                return record, exported

            record, exported = build()
            expected_room, expected_did, expected_pin = ROOM, did, verifier_sha
            if name == "changed-payload":
                report_file.write_bytes(b"changed")
            elif name == "missing-payload":
                report_file.unlink()
            elif name == "changed-manifest-bytes":
                manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            elif name == "changed-announcement-text":
                record["text"] = "bundle:v1 manifest-sha256:" + "0" * 64
            elif name == "changed-signature":
                record["sig"] = ("A" if record["sig"][0] != "A" else "B") + record["sig"][1:]
            elif name == "signature-padbit-alias":
                alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                index = alphabet.index(record["sig"][-1])
                record["sig"] = record["sig"][:-1] + alphabet[index + 1]
            elif name == "missing-signature":
                record.pop("sig")
            elif name == "nonce-changed":
                record["nonce"] = 124
            elif name == "original-string-nonce007":
                record, exported = build("007", "007")
            elif name == "stored-integer-loses-signed007":
                record, exported = build("007", 7)
            elif name == "wrong-external-room":
                expected_room = "other-room"
            elif name == "wrong-external-did":
                expected_did = public_did(Ed25519PrivateKey.generate())
            elif name == "wrong-verifier-pin":
                expected_pin = "0" * 64
            elif name == "changed-unsigned-seq-ts":
                record.update(seq=999999, ts="not authenticated")
            elif name == "unknown-profile":
                manifest["profile"] = "unknown"
                record, exported = build()
            elif name == "empty-file-list":
                manifest["files"] = []
                record, exported = build()
            elif name in {
                "unsafe-dotdot-path",
                "absolute-payload-path",
                "windows-drive-path",
                "windows-backslash-path",
            }:
                files[0]["path"] = {
                    "unsafe-dotdot-path": "../outside.txt",
                    "absolute-payload-path": "/outside.txt",
                    "windows-drive-path": "C:/outside.txt",
                    "windows-backslash-path": "payloads\\raw.bin",
                }[name]
                record, exported = build()
            elif name in {"duplicate-payload-path", "case-ambiguous-payload-path"}:
                files.append(files[0].copy())
                if name == "case-ambiguous-payload-path":
                    files[-1]["path"] = "PAYLOADS/결과.TXT"
                record, exported = build()
            elif name == "archive-in-manifest-cycle-refused":
                files.append(
                    {
                        "path": "signed-records.jsonl",
                        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    }
                )
                record, exported = build()
            elif name == "manifest-in-manifest-self-refused":
                files.append(
                    {
                        "path": "manifest.json",
                        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    }
                )
                record, exported = build()
            elif name == "oversized-payload":
                report_file.write_bytes(b"x" * (1024 * 1024 + 1))
            # Re-serialization is deliberately tested as signature-valid, not raw-export authentic.
            rewrite = name in {
                "changed-announcement-text",
                "changed-signature",
                "signature-padbit-alias",
                "missing-signature",
                "nonce-changed",
                "changed-unsigned-seq-ts",
                "reserialized-archive-still-signature-valid",
            }
            if rewrite:
                archive.write_bytes((json.dumps(record, separators=(",", ":")) + "\n").encode())
            if name == "extra-unselected-record-not-authenticated":
                archive.write_bytes(
                    exported + b'{"from":"someone-else","text":"unsigned fixture data"}\n'
                )
            elif name == "duplicate-selected-announcement":
                archive.write_bytes(exported * 2)
            elif name == "archive-nonobject":
                archive.write_bytes(b"[]\n")
            elif name == "archive-missing-final-lf":
                archive.write_bytes(exported[:-1])
            elif name == "duplicate-manifest-json-key":
                manifest_path.write_bytes(b'{"profile":"one","profile":"two","files":[]}\n')
            elif name == "nonfinite-manifest":
                manifest_path.write_bytes(b'{"profile":NaN,"files":[]}\n')
            elif name == "oversized-manifest":
                manifest_path.write_bytes(b" " * (1024 * 1024 + 1))
            elif name == "oversized-archive":
                archive.write_bytes(b" " * (1024 * 1024 + 1))
            process = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(checker),
                    str(base),
                    "--did",
                    expected_did,
                    "--room",
                    expected_room,
                    "--verifier-file",
                    str(verifier_path.resolve()),
                    "--verifier-sha256",
                    expected_pin,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
            )
            try:
                result = json.loads(process.stdout)
            except json.JSONDecodeError:
                result = {"unexpected_stdout": process.stdout[-1000:]}
            expected = name in POSITIVE
            passed = (
                process.returncode == (0 if expected else 1)
                and result.get("ok") == expected
                and not process.stderr
            )
            if expected:
                passed = passed and len(result.get("payloads_verified", [])) == 2
                passed = passed and result.get("seq_ts_authenticated") is False
                passed = passed and result.get("raw_archive_byte_authenticity_established") is False
            rows.append(
                {
                    "name": name,
                    "expected_accept": expected,
                    "passed": passed,
                    "returncode": process.returncode,
                    "result": result,
                    "unexpected_stderr": process.stderr[-1000:],
                }
            )
            del build, key
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "cases": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "accepted_controls": len(POSITIVE),
        "refusal_controls": len(CASES) - len(POSITIVE),
        "complete_CLI_subprocesses": len(rows),
        "official_verifier_sha256": verifier_sha,
        "checker_sha256": hashlib.sha256(checker.read_bytes()).hexdigest(),
        "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "test_keys": "Disposable generated in memory; no private bytes output, args, configured server or public artifact.",
        "live_service_requests": 0,
        "user_protected_key_access": False,
        "room_export_is_synthetic": True,
        "full_Linux_or_upstream_CI": False,
        "historical_missing_signature_recovery": False,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "cases",
                    "passed",
                    "accepted_controls",
                    "refusal_controls",
                    "complete_CLI_subprocesses",
                )
            }
        )
    )
    assert all(r["passed"] for r in rows), "Unexpected fixture result; inspect retained report."


if __name__ == "__main__":
    main()
