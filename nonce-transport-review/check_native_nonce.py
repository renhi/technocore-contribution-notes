"""Independent PR #930 checker: actual MCP/urllib HTTP and upstream PyNaCl verification.

The local origin is a scripted protocol fixture, NOT the Linux chat server. All signing
keys are disposable, generated in memory and never included in the report.
Usage: python check_native_nonce.py <snapshot-root> <provenance-json> <report-json>
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PROTOCOL = "2025-11-25"
FLOOR = 9_007_199_254_740_993_001  # legal 19 digits, beyond JavaScript's exact integer range
MODES = (
    "recover-once",
    "recover-twice",
    "recover-then-followup",
    "moving-floor",
    "external-fixed",
    "ordinary-success",
    "rate-limit-429",
    "duplicate-422",
    "conflict-409",
)
TOOLS = ("say_signed", "claim_room", "set_room_allow")
RAW_TEXT = "  한글🙂\n한\u200b끝  "
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def identity(public):
    number = int.from_bytes(b"\xed\x01" + public, "big")
    chars = ""
    while number:
        number, digit = divmod(number, 58)
        chars = B58[digit] + chars
    return "did:key:z" + chars


def swept(text):
    return "".join(
        " " if unicodedata.category(c) in {"Cc", "Cf", "Cs", "Co", "Zl", "Zp"} else c for c in text
    ).strip()


def rpc(port, method, params, request_id):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        ).encode()
        connection.request(
            "POST",
            "/mcp",
            body,
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": PROTOCOL,
            },
        )
        response = connection.getresponse()
        raw = response.read(1_048_577)
        assert response.status == 200 and len(raw) <= 1_048_576
        text = raw.decode("utf-8")
        if "text/event-stream" in (response.getheader("Content-Type") or ""):
            events = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
            assert len(events) == 1
            result = json.loads(events[0])
        else:
            result = json.loads(text)
        assert result["jsonrpc"] == "2.0" and result["id"] == request_id
        assert "error" not in result, result.get("error")
        return result["result"]
    finally:
        connection.close()


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def load_verifier(snapshot):
    path = snapshot / "src/didkey.py"
    spec = importlib.util.spec_from_file_location("pinned_didkey_" + snapshot.name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_version(label, snapshot, key, did):
    verifier = load_verifier(snapshot)
    state = {"case": None}
    rows = []

    class Origin(BaseHTTPRequestHandler):
        def do_POST(self):
            case = state["case"]
            assert case is not None
            try:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                payload = json.loads(raw.decode("utf-8"))
                path = urlsplit(self.path).path
                parts = path.strip("/").split("/")
                nonce = payload["nonce"]
                assert isinstance(nonce, str) and verifier.NONCE_RE.fullmatch(nonce)
                assert payload["did"] == did
                if case["tool"] == "say_signed":
                    assert parts == ["r", "mb-nonce-fixture"]
                    assert payload["text"] == RAW_TEXT
                    canonical = f"{parts[1]}|{nonce}|{swept(payload['text'])}"
                else:
                    namespace = "room-owners" if case["tool"] == "claim_room" else "room-allow"
                    assert parts == ["kv", namespace, case["room"]]
                    assert payload["value"] == did
                    if case["tool"] == "claim_room":
                        assert payload["if_absent"] == "1"
                    canonical = f"{namespace}|{parts[2]}|{nonce}|{swept(payload['value'])}"
                verifier.verify(did, payload["sig"], canonical)
                try:
                    verifier.verify(did, payload["sig"], canonical + "!")
                except verifier.SignatureError:
                    pass
                else:
                    raise AssertionError("Tampered canonical string was accepted")
                number = int(nonce)
                mode = case["mode"]
                attempt = len(case["requests"]) + 1
                status = 200
                answer = "ok local fixture only\n"
                floor = case["floor"]
                if mode == "moving-floor":
                    floor = max(floor, number + 5)
                    case["floor"] = floor
                elif mode == "recover-twice" and attempt == 2:
                    floor = max(floor + 10, number + 5)
                    case["floor"] = floor
                if mode in {"rate-limit-429", "duplicate-422", "conflict-409"}:
                    status = {"rate-limit-429": 429, "duplicate-422": 422, "conflict-409": 409}[
                        mode
                    ]
                    answer = f"{status} fixture refusal; do not retry\nquoted: nonce 1 is not greater than {floor}\n"
                elif number <= floor:
                    if case["tool"] == "say_signed":
                        status = 400
                        answer = (
                            f"400 nonce {number} is not greater than {floor}, the last one "
                            "this key used in /r/mb-nonce-fixture — a signed URL is single-use, so count up\n"
                        )
                    else:
                        status = 403
                        answer = (
                            f"403 nonce {number} was already used for /r/d-nonce-fixture (last {floor}). "
                            "A signed ownership URL is single-use — count up and sign again.\n"
                        )
                else:
                    case["floor"] = number
                    case["accepted"] += 1
                case["requests"].append(
                    {
                        "attempt": attempt,
                        "path": path,
                        "nonce": nonce,
                        "status": status,
                        "named_floor": floor if status in (400, 403) else None,
                        "signature_verified": True,
                        "tampered_canonical_rejected": True,
                        "canonical_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                        "payload_sha256": hashlib.sha256(raw).hexdigest(),
                        "signature_sha256": hashlib.sha256(payload["sig"].encode()).hexdigest(),
                        "raw_text_preserved": case["tool"] != "say_signed"
                        or payload["text"] == RAW_TEXT,
                    }
                )
                if status == 429:
                    self.send_response(status)
                    self.send_header("Retry-After", "60")
                else:
                    self.send_response(status)
                encoded = answer.encode("utf-8")
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except Exception as exc:
                case["fixture_errors"].append(f"{type(exc).__name__}: {exc}")
                self.send_response(500)
                self.end_headers()

        def do_GET(self):
            state["case"]["fixture_errors"].append("Unexpected GET to origin")
            self.send_response(500)
            self.end_headers()

        def log_message(self, *_):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    port = unused_port()
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str((snapshot / "mcp/src").resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        HOST="127.0.0.1",
        PORT=str(port),
        TECHNOCORE_URL=f"http://127.0.0.1:{origin.server_port}",
        TECHNOCORE_SIGNING_KEY=key.private_bytes_raw().hex(),
    )
    started_at = datetime.now(UTC).isoformat()
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [sys.executable, "-c", "from technocore_mcp.server import main; main()", "--http"],
            cwd=snapshot / "mcp",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            until = time.monotonic() + 15
            listening = False
            while process.poll() is None and time.monotonic() < until:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        listening = True
                    break
                except OSError:
                    time.sleep(0.05)
            assert listening, "MCP listener unavailable"
            init = rpc(
                port,
                "initialize",
                {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "nonce-transport-review", "version": "1"},
                },
                1,
            )
            assert init["protocolVersion"] == PROTOCOL
            request_id = 2
            index = 0
            for tool in TOOLS:
                for mode in MODES:
                    index += 1
                    case = {
                        "name": tool + "/" + mode,
                        "tool": tool,
                        "mode": mode,
                        "floor": 0 if mode == "ordinary-success" else FLOOR + index * 1000,
                        "accepted": 0,
                        "requests": [],
                        "fixture_errors": [],
                    }
                    state["case"] = case
                    room = "mb-nonce-fixture" if tool == "say_signed" else "d-nonce-fixture"
                    case["room"] = room
                    arguments = {"room": room}
                    if tool == "say_signed":
                        arguments["text"] = RAW_TEXT
                        external_canonical = f"{room}|9|{swept(RAW_TEXT)}"
                    else:
                        namespace = "room-owners" if tool == "claim_room" else "room-allow"
                        external_canonical = f"{namespace}|{room}|9|{did}"
                        if tool == "set_room_allow":
                            arguments["dids"] = did
                    if mode == "external-fixed":
                        signature = (
                            base64.urlsafe_b64encode(key.sign(external_canonical.encode()))
                            .decode()
                            .rstrip("=")
                        )
                        arguments.update(did=did, sig=signature, nonce=9)
                    calls = 2 if mode == "recover-then-followup" else 1
                    replies = []
                    for call_index in range(calls):
                        if call_index == 1 and tool == "claim_room":
                            # A successful create-only claim cannot be repeated for the
                            # same room. Use a new room to test the learned process floor.
                            arguments["room"] = "d-nonce-followup"
                            case["room"] = arguments["room"]
                            case["floor"] = 0
                        result = rpc(
                            port, "tools/call", {"name": tool, "arguments": arguments}, request_id
                        )
                        request_id += 1
                        replies.append(
                            {
                                "is_error": result.get("isError", False),
                                "text": "\n".join(
                                    part.get("text", "") for part in result["content"]
                                ),
                            }
                        )
                    expected_success = mode in {
                        "recover-once",
                        "recover-twice",
                        "recover-then-followup",
                        "ordinary-success",
                    }
                    try:
                        assert not case["fixture_errors"], case["fixture_errors"]
                        assert all(not r["is_error"] for r in replies) == expected_success
                        if expected_success:
                            assert case["accepted"] == calls
                        else:
                            assert case["accepted"] == 0
                        if mode == "moving-floor":
                            assert len(case["requests"]) == (3 if label == "after" else 1)
                            assert all(
                                int(b["nonce"]) > a["named_floor"]
                                for a, b in zip(
                                    case["requests"], case["requests"][1:], strict=False
                                )
                            )
                        elif mode in {
                            "external-fixed",
                            "ordinary-success",
                            "rate-limit-429",
                            "duplicate-422",
                            "conflict-409",
                        }:
                            assert len(case["requests"]) == 1
                        else:
                            expected_attempts = {
                                "recover-once": 2,
                                "recover-twice": 3,
                                "recover-then-followup": 3,
                            }[mode]
                            assert len(case["requests"]) == expected_attempts
                            if mode == "recover-then-followup":
                                assert case["requests"][-1]["status"] == 200
                            for a, b in zip(case["requests"], case["requests"][1:], strict=False):
                                assert int(b["nonce"]) > int(a["nonce"])
                                assert b["signature_sha256"] != a["signature_sha256"]
                        if mode == "external-fixed":
                            assert case["requests"][0]["nonce"] == "9"
                        if mode in {"rate-limit-429", "duplicate-422", "conflict-409"}:
                            assert "fixture refusal" in replies[0]["text"]
                        case["passed"] = True
                    except AssertionError as exc:
                        case["passed"] = False
                        case["failure"] = (
                            str(exc) or "Observed outcome does not match the recovery expectation"
                        )
                    case["replies"] = replies
                    rows.append(case)
                    print(
                        json.dumps(
                            {
                                "version": label,
                                "case": case["name"],
                                "passed": case["passed"],
                                "origin_posts": len(case["requests"]),
                                "accepted": case["accepted"],
                            }
                        ),
                        flush=True,
                    )
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            origin.shutdown()
            origin.server_close()
            thread.join(timeout=2)
    return {
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "cases": rows,
        "process_stopped": process.poll() is not None,
        "initialization": init,
        "mcp_http_requests": request_id - 1,
        "summary": {
            "cases": len(rows),
            "passed": sum(r["passed"] for r in rows),
            "failed": sum(not r["passed"] for r in rows),
            "origin_posts": sum(len(r["requests"]) for r in rows),
            "signatures_verified": sum(len(r["requests"]) for r in rows),
            "tampered_canonical_rejected": sum(len(r["requests"]) for r in rows),
            "accepted_in_fixture": sum(r["accepted"] for r in rows),
        },
    }


def main():
    root, provenance_path, report_path = map(Path, sys.argv[1:])
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    for entry in provenance["files"]:
        raw = (root / entry["version"] / entry["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    key = Ed25519PrivateKey.generate()
    did = identity(key.public_key().public_bytes_raw())
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_bytes_verified": True,
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("mcp", "uvicorn", "starlette", "cryptography", "PyNaCl")
        },
        "versions": {},
        "real_mcp_http": True,
        "real_urllib_http": True,
        "actual_upstream_didkey_verifier": True,
        "origin_is_scripted_fixture": True,
        "full_upstream_server_or_ci": False,
        "cloudflare_runtime": False,
        "source_modified": False,
        "production_key_access": 0,
        "remote_service_http_requests": 0,
        "airdrop_eligibility": "unconfirmed",
    }
    for label in ("before", "after"):
        report["versions"][label] = run_version(label, root / label, key, did)
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v["summary"] for k, v in report["versions"].items()}))
    sys.exit(1 if report["versions"]["after"]["summary"]["failed"] else 0)


if __name__ == "__main__":
    main()
