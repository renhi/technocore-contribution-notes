"""Independent native-process encoding matrix. No service requests or persistent keys.

Run with Python 3.12 and cryptography installed; pass unchanged base and candidate sign.py
paths plus an output JSON path. All signing seeds are disposable, memory-only fixtures.
"""

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
import platform
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from cryptography import __version__ as crypto_version
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

CODECS = ("cp949", "cp932", "ascii", "cp1252", "utf-8")
NONCE = "9007199254740993001"
RAW = "\t한글 안내\n\u200b첫 기여 😀\r"
CLEAN = "한글 안내  첫 기여 😀"


def load(path, label):
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verifies(public, sig, message):
    try:
        public.verify(base64.urlsafe_b64decode(sig + "=="), message.encode("utf-8"))
        return True
    except InvalidSignature:
        return False


def consumers(module, command, root, wrong_root, record, agent, xpublic):
    """Exercise original pure note consumers, including two tamper controls."""
    body = "mailbox: mb-p-review " + record
    if command == "e2e":
        assert module.e2e_key(root, body) == (xpublic, "mb-p-review", int(NONCE))
        assert module.e2e_key(wrong_root, body) is None
        assert module.e2e_key(root, body.replace("mb-p-review", "mb-p-other")) is None
    else:
        fields = record.split()
        assert fields[1:3] == [agent, "r:lobby"] and fields[4] == NONCE
        with redirect_stdout(io.StringIO()):
            assert module.check_note(root, body) == 1
            assert module.check_note(wrong_root, body) == 0
            assert module.check_note(root, body.replace("r:lobby", "r:other")) == 0
    return 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    before, candidate = args.before.resolve(), args.candidate.resolve()
    old, new = before.read_bytes(), candidate.read_bytes()
    assert old.count(" — the note of ".encode()) == 2
    assert old.replace(" — the note of ".encode(), b" - the note of ") == new
    signing_seed = os.urandom(32)
    signing_key = Ed25519PrivateKey.from_private_bytes(signing_seed)
    public = signing_key.public_key()
    reference = load(candidate, "candidate_signer")
    root = reference.did_of(signing_key)
    agent = reference.did_of(Ed25519PrivateKey.generate())
    wrong_root = reference.did_of(Ed25519PrivateKey.generate())
    xpublic = (
        base64.urlsafe_b64encode(
            X25519PrivateKey.generate().public_key().public_bytes_raw()
        )
        .decode()
        .rstrip("=")
    )
    commands = {
        "delegate": ["delegate", agent, "r:lobby", "7", NONCE],
        "e2e": ["e2e", xpublic, "mb-p-review", NONCE],
        "say": ["say", "lobby", NONCE, RAW],
        "set": ["set", "review", "korean", NONCE, RAW],
    }
    rows = []
    for lane, script in (("before", before), ("candidate", candidate)):
        module = load(script, lane + "_signer")
        for codec in CODECS:
            for command, argv in commands.items():
                env = os.environ.copy()
                env["SIGN_SEED"] = signing_seed.hex()
                env["PYTHONIOENCODING"] = codec + ":strict"
                process = subprocess.run(
                    [sys.executable, str(script), *argv],
                    env=env,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                # Never record arguments, seed, env, or arbitrary raw stderr.
                row = {
                    "lane": lane,
                    "codec": codec,
                    "command": command,
                    "exit_code": process.returncode,
                    "signature_verified": False,
                    "consumer_assertions_passed": 0,
                }
                expected_failure = (
                    lane == "before"
                    and command in ("delegate", "e2e")
                    and codec in ("cp949", "cp932", "ascii")
                )
                if expected_failure:
                    error = process.stderr.decode("ascii", errors="replace")
                    assert (
                        process.returncode != 0
                        and b"delegate:" not in process.stdout
                        and b"e2e:" not in process.stdout
                    )
                    assert "UnicodeEncodeError" in error and "\\u2014" in error
                    row["observed"] = (
                        "UnicodeEncodeError U+2014 before signed record output"
                    )
                else:
                    assert process.returncode == 0 and not process.stderr, row
                    lines = process.stdout.decode(codec, errors="strict").splitlines()
                    row["output_is_ascii"] = process.stdout.isascii()
                    if lane == "candidate" or command in ("say", "set"):
                        assert row["output_is_ascii"], row
                    if command in ("delegate", "e2e"):
                        assert len(lines) == 3 and lines[0].startswith("# append to ")
                        record = lines[2]
                        fields = record.split()
                        assert fields[0] == command + ":"
                        if command == "delegate":
                            assert len(fields) == 6
                        else:
                            assert len(fields) == 5
                        canonical = command + "|" + root + "|" + "|".join(fields[1:-1])
                        row["consumer_assertions_passed"] = consumers(
                            module, command, root, wrong_root, record, agent, xpublic
                        )
                    else:
                        assert len(lines) == 2 and lines[0] == root
                        fields = [None, lines[1]]
                        prefix = "lobby" if command == "say" else "review|korean"
                        canonical = prefix + "|" + NONCE + "|" + CLEAN
                    assert verifies(public, fields[-1], canonical), row
                    assert not verifies(public, fields[-1], canonical + "x"), row
                    row["signature_verified"] = True
                    row["changed_payload_rejected"] = True
                    row["observed"] = (
                        "Successful output, valid original UTF-8 signature"
                    )
                row["matches_expected_behavior"] = True
                rows.append(row)
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cryptography": crypto_version,
        "source_sha256": {
            "before": hashlib.sha256(old).hexdigest(),
            "candidate": hashlib.sha256(new).hexdigest(),
        },
        "stdout_configuration": "PYTHONIOENCODING=<codec>:strict; captured native child processes; not interactive console detection",
        "process_runs": len(rows),
        "before_successful_outputs": 14,
        "before_encoding_failures": 6,
        "candidate_successful_outputs": 20,
        "verified_signatures": sum(r["signature_verified"] for r in rows),
        "changed_payload_rejections": sum(
            r.get("changed_payload_rejected", False) for r in rows
        ),
        "note_consumer_assertions": sum(r["consumer_assertions_passed"] for r in rows),
        "korean_say_set_successful_outputs": sum(
            r["signature_verified"] for r in rows if r["command"] in ("say", "set")
        ),
        "synthetic_nonce": NONCE,
        "rows": rows,
        "network_requests": 0,
        "user_identity_key_accessed": False,
        "persistent_fixture_seeds": False,
        "full_linux_suite_run": False,
    }
    assert (
        result["process_runs"],
        result["verified_signatures"],
        result["note_consumer_assertions"],
        result["korean_say_set_successful_outputs"],
    ) == (40, 34, 42, 20)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "40 process runs: base 14 successful / 6 encoding failures; candidate 20 successful."
    )
    print(
        "34 signature verifications, 34 tamper rejections, 42 note-consumer assertions passed."
    )


if __name__ == "__main__":
    main()
