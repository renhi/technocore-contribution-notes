"""Check the real config import with independently specified HTTP token cases.

No server, protected identity, network, fcntl replacement, or config patch is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", re.ASCII)
PROBE = r"""
import importlib.util, json, sys
sys.dont_write_bytecode = True
try:
    spec = importlib.util.spec_from_file_location('reviewed_config', sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except ValueError as error:
    if 'CHAT_CLIENT_IP_HEADER' not in str(error):
        raise
    print(json.dumps({'status': 'refused', 'error_type': type(error).__name__,
                      'error': str(error)}, ensure_ascii=True))
else:
    print(json.dumps({'status': 'accepted', 'value': module.CLIENT_IP_HEADER,
                      'store_loaded': 'store' in sys.modules,
                      'app_loaded': 'app' in sys.modules}, ensure_ascii=True))
"""


def cases() -> list[dict]:
    rows = []
    # NUL is not representable in a Windows process environment and is excluded.
    for code in range(1, 128):
        for shape, value in (("single", chr(code)), ("embedded", "x" + chr(code) + "y")):
            rows.append({"id": f"ascii-{code:02x}-{shape}", "group": "ascii", "input": value})
    for code in range(128, 256):
        rows.append({"id": f"latin1-{code:02x}", "group": "latin1", "input": "x" + chr(code) + "y"})
    unicode_cases = [
        ("kelvin", "\u212a"),
        ("kelvin-header", "\u212a-Client-IP"),
        ("long-s", "\u017f"),
        ("dotted-i", "\u0130"),
        ("dotless-i", "\u0131"),
        ("sharp-s", "\u00df"),
        ("snowman", "\u2603"),
        ("korean", "x-\ud55c\uae00"),
        ("korean-jamo", "x-\u1112\u1161\u11ab"),
        ("emoji", "x-\U0001f680"),
        ("fullwidth-ascii", "\uff38-\uff23\uff4c\uff49\uff45\uff4e\uff54"),
        ("cyrillic-lookalike", "x-cl\u0456ent-ip"),
        ("hebrew", "x-\u05d0"),
        ("combining", "x-e\u0301"),
        ("precomposed", "x-\u00e9"),
        ("zwsp", "x\u200by"),
        ("zwj", "x\u200dy"),
        ("bidi", "x\u202ey"),
        ("bom", "\ufeffx-header"),
        ("line-separator", "x\u2028y"),
        ("paragraph-separator", "x\u2029y"),
        ("nbsp-edge", "\u00a0X-Client-IP\u00a0"),
        ("ideographic-edge", "\u3000X-Client-IP\u3000"),
        ("unicode-whitespace-only", "\u2000\u3000"),
    ]
    rows.extend({"id": name, "group": "unicode", "input": value} for name, value in unicode_cases)
    controls = [
        ("unset", None),
        ("empty", ""),
        ("space-only", " \t\r\n "),
        ("normal", "cf-connecting-ip"),
        ("mixed-case", "X-Forwarded-For"),
        ("trimmed", " \tCF-Connecting-IP\r\n"),
        ("all-punctuation", "!#$%&'*+-.^_`|~"),
        ("all-letters-digits", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"),
        ("colon", "bad:header"),
        ("comma", "bad,header"),
        ("internal-space", "bad header"),
        ("internal-crlf", "x\r\nInjected:y"),
    ]
    rows.extend({"id": name, "group": "controls", "input": value} for name, value in controls)
    return rows


def oracle(value: str | None) -> dict:
    # Preserve the existing operator setting's .strip() and lowercase convention.
    # HTTP token acceptance itself comes from RFC 9110 section 5.6.2.
    trimmed = (value or "").strip()
    if not trimmed or TOKEN.fullmatch(trimmed):
        return {"status": "accepted", "value": trimmed.lower()}
    return {"status": "refused"}


def run(source: Path) -> dict:
    clean = {key: value for key, value in os.environ.items() if not key.startswith("CHAT_")}
    clean.pop("WEB_CONCURRENCY", None)
    clean["PYTHONIOENCODING"] = "utf-8"
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    rows = []
    for case in cases():
        env = clean.copy()
        if case["input"] is not None:
            env["CHAT_CLIENT_IP_HEADER"] = case["input"]
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", PROBE, str(source.resolve())],
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=10,
            check=False,
        )
        expected = oracle(case["input"])
        if result.returncode:
            actual = {
                "status": "unexpected_process_error",
                "returncode": result.returncode,
                "stderr_tail": result.stderr[-600:],
            }
        else:
            actual = json.loads(result.stdout)
        matches = actual["status"] == expected["status"]
        if expected["status"] == "accepted":
            matches = matches and actual.get("value") == expected["value"]
        if actual["status"] == "accepted":
            matches = matches and not actual["store_loaded"] and not actual["app_loaded"]
        rows.append({**case, "expected": expected, "actual": actual, "matches": matches})
    return {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "cases": len(rows),
        "matched": sum(row["matches"] for row in rows),
        "mismatched": sum(not row["matches"] for row in rows),
        "unexpected_process_errors": sum(
            row["actual"]["status"] == "unexpected_process_error" for row in rows
        ),
        "expected_accepts": sum(row["expected"]["status"] == "accepted" for row in rows),
        "expected_refusals": sum(row["expected"]["status"] == "refused" for row in rows),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "oracle": "RFC 9110 section 5.6.2 ASCII token, following existing strip/lower configuration convention",
        "excluded": [
            "NUL in process environment",
            "unpaired UTF-16 surrogates",
            "live proxy and full Linux server",
        ],
        "remote_service_requests": 0,
        "user_key_access": 0,
        "before": run(args.before),
        "after": run(args.after),
    }
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                lane: {key: value for key, value in report[lane].items() if key != "results"}
                for lane in ("before", "after")
            },
            indent=2,
        )
    )
    if report["after"]["mismatched"] or report["before"]["unexpected_process_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
