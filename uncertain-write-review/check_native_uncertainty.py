"""Whole MCP packages against real loopback response-loss fixtures, not live servers.

Usage: python check_native_uncertainty.py SOURCE_ROOT PROVENANCE_JSON REPORT_JSON
Disposable signing keys stay inside this process/child environment; never user keys.
"""

from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PROTOCOL = "2025-11-25"
MODES = ("complete", "accepted-close", "notaccepted-close", "truncated200", "error422", "error429")
TOOLS = ("say", "write_note", "say_signed", "claim_room", "set_room_allow")


def rpc(port, method, params, number):
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        con.request(
            "POST",
            "/mcp",
            json.dumps(
                {"jsonrpc": "2.0", "id": number, "method": method, "params": params}
            ).encode(),
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": PROTOCOL,
            },
        )
        response = con.getresponse()
        raw = response.read(1024 * 1024 + 1)
        assert response.status == 200 and len(raw) <= 1024 * 1024
        body = raw.decode()
        if "text/event-stream" in (response.getheader("Content-Type") or ""):
            events = [s[5:].strip() for s in body.splitlines() if s.startswith("data:")]
            assert len(events) == 1
            answer = json.loads(events[0])
        else:
            answer = json.loads(body)
        assert answer["id"] == number and "error" not in answer
        return answer["result"]
    finally:
        con.close()


def text(result):
    return "\n".join(c.get("text", "") for c in result.get("content", []))


def verifier(root):
    spec = importlib.util.spec_from_file_location("fixture_didkey", root / "main/src/didkey.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_version(label, snapshot, key, did, official):
    state = {"case": None}

    class Origin(BaseHTTPRequestHandler):
        def answer(self, mode, message):
            if mode in {"accepted-close", "notaccepted-close"}:
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            status = {"error422": 422, "error429": 429}.get(mode, 200)
            raw = message.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header(
                "Content-Length", str(len(raw) + (100 if mode == "truncated200" else 0))
            )
            self.send_header("Connection", "close")
            if mode == "error429":
                self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()
            self.close_connection = True

        def do_POST(self):
            case = state["case"]
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            mode = case["mode"]
            tool = case["tool"]
            signature_valid = False
            try:
                if tool in {"say_signed", "claim_room", "set_room_allow"}:
                    assert payload["did"] == did and isinstance(payload["nonce"], str)
                    value = payload["text"] if tool == "say_signed" else payload["value"]
                    assert value == ("한글 fixture" if tool == "say_signed" else did)
                    canonical = (
                        f"mb-fixture|{payload['nonce']}|{value}"
                        if tool == "say_signed"
                        else f"{self.path.split('/')[2]}|d-fixture|{payload['nonce']}|{value}"
                    )
                    official.verify(did, payload["sig"], canonical)
                    signature_valid = True
                else:
                    assert payload.get("text", payload.get("value")) == "한글 fixture"
            except Exception as exc:
                case["fixture_errors"].append(f"{type(exc).__name__}: {exc}")
            accepted = mode in {"complete", "accepted-close", "truncated200"}
            if accepted:
                case["accepted"] += 1
            case["posts"].append(
                {
                    "path": self.path,
                    "payload_sha256": hashlib.sha256(
                        json.dumps(payload, sort_keys=True).encode()
                    ).hexdigest(),
                    "signature_verified": signature_valid,
                    "fixture_accepted": accepted,
                }
            )
            self.answer(
                mode,
                f"{422 if mode == 'error422' else 429} fixture refusal; no retry\n"
                if mode.startswith("error")
                else "fixture stored\n",
            )

        def do_GET(self):
            case = state["case"]
            case["gets"].append(self.path)
            # Readback is a later independent tool request, never an implicit write retry.
            if case.get("observer"):
                self.answer("complete", f"fixture accepted-count: {case['accepted']}\n")
            else:
                self.answer(
                    case["mode"],
                    "429 fixture refusal; no retry\n"
                    if case["mode"] == "error429"
                    else "fixture read\n",
                )

        def log_message(self, *_):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    threading.Thread(target=origin.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str((snapshot / "mcp/src").resolve()),
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        HOST="127.0.0.1",
        PORT=str(port),
        TECHNOCORE_URL=f"http://127.0.0.1:{origin.server_port}",
        TECHNOCORE_SIGNING_KEY=key.private_bytes_raw().hex(),
        NO_PROXY="127.0.0.1,localhost",
    )
    rows = []
    with tempfile.TemporaryFile() as log:
        child = subprocess.Popen(
            [sys.executable, "-c", "from technocore_mcp.server import main; main()", "--http"],
            cwd=snapshot / "mcp",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            ready = False
            until = time.monotonic() + 20
            while child.poll() is None and time.monotonic() < until:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        ready = True
                    break
                except OSError:
                    time.sleep(0.05)
            assert ready, "MCP listener unavailable"
            rpc(
                port,
                "initialize",
                {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "uncertainty-review", "version": "1"},
                },
                1,
            )
            listing = rpc(port, "tools/list", {}, 2)
            assert set(TOOLS).issubset({t["name"] for t in listing["tools"]})
            assert "signing identity: " + did in text(
                rpc(port, "tools/call", {"name": "whoami", "arguments": {}}, 3)
            )
            number = 4
            for tool in TOOLS:
                for mode in MODES:
                    case = {
                        "name": tool + "/" + mode,
                        "tool": tool,
                        "mode": mode,
                        "posts": [],
                        "gets": [],
                        "accepted": 0,
                        "fixture_errors": [],
                    }
                    state["case"] = case
                    if tool == "say":
                        args = {"room": "fixture", "text": "한글 fixture", "nick": "local"}
                        observer = {"name": "read_room", "arguments": {"room": "fixture"}}
                    elif tool == "write_note":
                        args = {
                            "namespace": "fixture",
                            "key": "note",
                            "value": "한글 fixture",
                            "if_absent": True,
                        }
                        observer = {
                            "name": "read_note",
                            "arguments": {"namespace": "fixture", "key": "note"},
                        }
                    elif tool == "say_signed":
                        args = {"room": "mb-fixture", "text": "한글 fixture"}
                        observer = {"name": "read_room", "arguments": {"room": "mb-fixture"}}
                    else:
                        args = {"room": "d-fixture"}
                        if tool == "set_room_allow":
                            args["dids"] = did
                        observer = {
                            "name": "read_note",
                            "arguments": {
                                "namespace": "room-owners"
                                if tool == "claim_room"
                                else "room-allow",
                                "key": "d-fixture",
                            },
                        }
                    result = rpc(port, "tools/call", {"name": tool, "arguments": args}, number)
                    number += 1
                    message = text(result)
                    if mode == "complete":
                        diagnostic = (
                            not result.get("isError", False) and "fixture stored" in message
                        )
                    elif mode.startswith("error"):
                        diagnostic = (
                            result.get("isError", False) and "fixture refusal; no retry" in message
                        )
                    else:
                        diagnostic = (
                            result.get("isError", False)
                            and "write was not confirmed" in message
                            and "before retrying" in message
                            and "cannot reach" not in message
                        )
                    case["observer"] = True
                    observed = rpc(port, "tools/call", observer, number)
                    number += 1
                    expected_count = int(mode in {"complete", "accepted-close", "truncated200"})
                    matched = (
                        diagnostic
                        and len(case["posts"]) == 1
                        and case["accepted"] == expected_count
                        and not case["fixture_errors"]
                    )
                    matched = (
                        matched
                        and f"fixture accepted-count: {expected_count}" in text(observed)
                        and not observed.get("isError", False)
                    )
                    rows.append(
                        case
                        | {
                            "diagnostic_matches": bool(diagnostic),
                            "tool_text": message,
                            "is_error": result.get("isError", False),
                            "later_readback": text(observed),
                            "matched": bool(matched),
                        }
                    )
            for mode in ("complete", "accepted-close", "truncated200", "error429"):
                case = {
                    "name": "read_room/" + mode,
                    "tool": "read_room",
                    "mode": mode,
                    "posts": [],
                    "gets": [],
                    "accepted": 0,
                    "fixture_errors": [],
                }
                state["case"] = case
                result = rpc(
                    port,
                    "tools/call",
                    {"name": "read_room", "arguments": {"room": "fixture"}},
                    number,
                )
                number += 1
                message = text(result)
                if mode == "complete":
                    diagnostic = not result.get("isError", False) and "fixture read" in message
                elif mode == "error429":
                    diagnostic = result.get("isError", False) and "429 fixture refusal" in message
                else:
                    diagnostic = (
                        result.get("isError", False)
                        and "cannot reach" in message
                        and "write was not confirmed" not in message
                    )
                rows.append(
                    case
                    | {
                        "diagnostic_matches": bool(diagnostic),
                        "tool_text": message,
                        "matched": bool(diagnostic and len(case["gets"]) == 1),
                    }
                )
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
            origin.shutdown()
            origin.server_close()
    return {
        "version": label,
        "cases": len(rows),
        "matched": sum(r["matched"] for r in rows),
        "mismatched": sum(not r["matched"] for r in rows),
        "mcp_HTTP_requests": number - 1,
        "origin_POST_requests": sum(len(r["posts"]) for r in rows),
        "origin_GET_requests": sum(len(r["gets"]) for r in rows),
        "disposable_signatures_verified": sum(
            p["signature_verified"] for r in rows for p in r["posts"]
        ),
        "process_stopped": child.poll() is not None,
        "rows": rows,
    }


def main():
    root, provenance, output = map(Path, sys.argv[1:])
    assert not output.exists()
    prov = json.loads(provenance.read_text(encoding="utf-8"))

    def check_sources():
        for p in prov["files"]:
            raw = (root / p["version"] / p["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == p["sha256"]

    check_sources()
    official = verifier(root)
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw()
    number = int.from_bytes(b"\xed\x01" + public, "big")
    chars, alphabet = "", "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    while number:
        number, digit = divmod(number, 58)
        chars = alphabet[digit] + chars
    did = "did:key:z" + chars
    results = [
        run_version(label, root / label, key, did, official)
        for label in ("main", "candidate", "proposed")
    ]
    del key
    check_sources()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "main": prov["main"],
        "head": prov["head"],
        "versions": results,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "proposed_fetch_sha256": hashlib.sha256(
            (root / "proposed/mcp/src/technocore_mcp/fetch.py").read_bytes()
        ).hexdigest(),
        "runtime": {
            "python": sys.version.split()[0],
            **{
                p: importlib.metadata.version(p)
                for p in ("mcp", "starlette", "uvicorn", "cryptography", "PyNaCl")
            },
        },
        "source_blobs_unchanged": len(prov["files"]),
        "whole_MCP_modules_executed": True,
        "SDK_and_transport_mocked": False,
        "origin_is_nonpersisting_local_fixture": True,
        "actual_server_storage_or_owner_policy_tested": False,
        "full_Linux_repository_original_tests_or_upstream_CI": False,
        "protected_user_key_or_wallet_access": False,
        "live_service_test_writes": 0,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    k: r[k]
                    for k in (
                        "version",
                        "cases",
                        "matched",
                        "mismatched",
                        "mcp_HTTP_requests",
                        "origin_POST_requests",
                        "origin_GET_requests",
                        "disposable_signatures_verified",
                    )
                }
                for r in results
            ]
        )
    )


if __name__ == "__main__":
    main()
