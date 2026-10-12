"""Exercise whole pinned MCP packages over native TCP against a local POST recorder.

Usage: python check_mailbox_contract.py SNAPSHOT_ROOT PROVENANCE_JSON REPORT_JSON
The recorder is not the official server. It performs no note persistence or auth.
No signing key is configured, no protected key is accessed, and no live writes occur.
"""

from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import json
import os
import platform
import re
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
GRAMMAR = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")


def fixture_did():
    # A disposable public identity makes the note examples syntactically usable.
    # Its private bytes are never extracted/configured; no test request is signed.
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    del private
    number = int.from_bytes(b"\xed\x01" + public, "big")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    chars = ""
    while number:
        number, digit = divmod(number, 58)
        chars = alphabet[digit] + chars
    return "did:key:z" + chars


IDENTITY = fixture_did()


def scenarios():
    rows = []

    def add(name, value, reject=False, namespace="did-fa", status=200, **conditions):
        rows.append(
            {
                "name": name,
                "arguments": {"namespace": namespace, "key": "fixture", "value": value}
                | conditions,
                "expected_local_reject": reject,
                "fixture_status": status,
            }
        )

    add("no-mailbox", IDENTITY)
    for label, separator in (
        ("compact", ""),
        ("space", " "),
        ("tab", "\t"),
        ("spaces-tabs", " \t  "),
    ):
        add(label, f"{IDENTITY} mailbox:{separator}mb-p-room")
    for label, room in (
        ("one-character", "a"),
        ("digit-first", "0-room"),
        ("max48", "a" * 48),
        ("max48-mb-prefix", "mb-p-" + "a" * 43),
        ("trailing-hyphen", "mb-p-room-"),
        ("trailing-underscore", "mb-p-room_"),
    ):
        add(label, f"{IDENTITY} mailbox: {room}")
    for label, room in (
        ("empty", ""),
        ("uppercase", "mb-p-ydrMAw8RUo73zoje"),
        ("leading-hyphen", "-room"),
        ("leading-underscore", "_room"),
        ("length49", "a" * 49),
        ("slash", "mb-p/a"),
        ("colon", "mb-p:a"),
        ("period", "mb-p.a"),
        ("percent", "mb-p%20a"),
        ("url", "https://example.invalid/room"),
        ("hangul", "mb-p-한글"),
        ("emoji", "mb-p-🙂"),
        ("fullwidth", "ｍｂ-p-room"),
        ("accent", "mb-p-é"),
    ):
        add(label, f"{IDENTITY} mailbox: {room}", True)
    for namespace in ("did", "did-00", "did-ff"):
        add(f"scope-{namespace}-bad", f"{IDENTITY} mailbox:UPPER", True, namespace)
        add(f"scope-{namespace}-good", f"{IDENTITY} mailbox:mb-p-room", False, namespace)
    for namespace in ("profile", "did-custom", "did-0", "did-000", "did-gg"):
        add(f"generic-{namespace}", "mailbox:UPPER", False, namespace)
    add("two-good-fields", f"{IDENTITY} mailbox:mb-p-a mailbox: mb-p-b")
    add("good-then-bad", f"{IDENTITY} mailbox:mb-p-a mailbox: UPPER", True)
    add("bad-then-good", f"{IDENTITY} mailbox:UPPER mailbox: mb-p-b", True)
    add("separate-lines", f"{IDENTITY}\nmailbox:\tmb-p-room")
    add("invisible-field-boundary", f"{IDENTITY}\u200bmailbox:UPPER", True)
    add("invisible-after-colon", f"{IDENTITY} mailbox:\u200bmb-p-room")
    add("upper-field-is-not-lower-field", f"{IDENTITY} Mailbox:UPPER")
    add("embedded-marker-is-not-a-field", f"{IDENTITY} notmailbox:UPPER")
    add("colon-prefix-is-not-a-field", f"{IDENTITY} prefix:mailbox:UPPER")
    add("value-is-only-first-token", f"{IDENTITY} mailbox:mb-p-a further-metadata")
    add("nbsp-token-delimiter", f"{IDENTITY} mailbox:mb-p-a\u00a0further-metadata")
    add("new-line-is-swept-separator", f"{IDENTITY} mailbox:mb-p-a\nfurther-metadata")
    add("create-only-accepted", f"{IDENTITY} mailbox: mb-p-room", if_absent=True)
    add("cas-accepted", f"{IDENTITY} mailbox: mb-p-room", if_matches="previous 한글")
    add("create-only-refused-first", f"{IDENTITY} mailbox:UPPER", True, if_absent=True)
    add("cas-refused-first", f"{IDENTITY} mailbox:UPPER", True, if_matches="previous")
    # Every visible ASCII character, embedded inside one room token. Oracle is the
    # documented name grammar, independent of the candidate mailbox parser.
    for point in range(33, 127):
        room = "mb-p-a" + chr(point) + "b"
        add(
            f"visible-ascii-{point}",
            f"{IDENTITY} mailbox: {room}",
            GRAMMAR.fullmatch(room) is None,
        )
    for status in (409, 422, 429):
        add(f"origin-error-{status}", f"{IDENTITY} mailbox: mb-p-room", status=status)
    return rows


def rpc(port, method, params, request_id):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        connection.request(
            "POST",
            "/mcp",
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            ).encode(),
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": PROTOCOL,
            },
        )
        response = connection.getresponse()
        raw = response.read(1024 * 1024 + 1)
        assert response.status == 200 and len(raw) <= 1024 * 1024
        text = raw.decode()
        if "text/event-stream" in (response.getheader("Content-Type") or ""):
            data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
            assert len(data) == 1
            answer = json.loads(data[0])
        else:
            answer = json.loads(text)
        assert answer["jsonrpc"] == "2.0" and answer["id"] == request_id
        assert "error" not in answer, answer.get("error")
        return answer["result"]
    finally:
        connection.close()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_version(label, snapshot, cases):
    state = {"case": None}

    class Origin(BaseHTTPRequestHandler):
        def do_POST(self):
            case = state["case"]
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            payload = json.loads(raw)
            case["requests"].append(
                {
                    "method": "POST",
                    "path": self.path,
                    "payload": payload,
                    "content_type": self.headers.get("Content-Type"),
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            status = case["fixture_status"]
            answer = (
                "ok local nonpersisting note recorder\n"
                if status == 200
                else f"{status} local fixture refuses; no automatic retry\n"
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(answer)))
            if status == 429:
                self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(answer)

        def do_GET(self):
            state["case"]["requests"].append({"method": "GET", "path": self.path})
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    threading.Thread(target=origin.serve_forever, daemon=True).start()
    port = free_port()
    env = os.environ.copy()
    # Never inherit signing custody or a user-supplied origin into this experiment.
    env.pop("TECHNOCORE_SIGNING_KEY", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    env.pop("ALL_PROXY", None)
    env.update(
        PYTHONPATH=str((snapshot / "mcp/src").resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        HOST="127.0.0.1",
        PORT=str(port),
        TECHNOCORE_URL=f"http://127.0.0.1:{origin.server_port}",
        NO_PROXY="127.0.0.1,localhost",
    )
    rows = []
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
            listening = False
            deadline = time.monotonic() + 20
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        listening = True
                    break
                except OSError:
                    time.sleep(0.05)
            assert listening, "MCP process did not listen"
            initialized = rpc(
                port,
                "initialize",
                {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "mailbox-contract-review", "version": "1"},
                },
                1,
            )
            assert initialized["protocolVersion"] == PROTOCOL
            listed = rpc(port, "tools/list", {}, 2)
            tools = {tool["name"]: tool for tool in listed["tools"]}
            assert "write_note" in tools
            state["case"] = {"requests": []}
            who = rpc(port, "tools/call", {"name": "whoami", "arguments": {}}, 3)
            who_text = "\n".join(c.get("text", "") for c in who.get("content", []))
            assert "signing identity: none —" in who_text
            assert state["case"]["requests"] == []
            for index, case in enumerate(cases, 4):
                current = case | {"requests": []}
                state["case"] = current
                response = rpc(
                    port,
                    "tools/call",
                    {"name": "write_note", "arguments": case["arguments"]},
                    index,
                )
                text = "\n".join(c.get("text", "") for c in response.get("content", []))
                error = response.get("isError", False)
                requests = current["requests"]
                assertions = {}
                if case["expected_local_reject"]:
                    assertions.update(
                        local_tool_error=error and "bad mailbox" in text,
                        no_origin_request=len(requests) == 0,
                    )
                else:
                    assertions["one_origin_request"] = len(requests) == 1
                    assertions["expected_tool_error"] = error == (case["fixture_status"] != 200)
                    if requests:
                        arguments = case["arguments"]
                        expected = {"value": arguments["value"]}
                        if arguments.get("if_absent"):
                            expected["if_absent"] = "1"
                        if "if_matches" in arguments:
                            expected["if"] = arguments["if_matches"]
                        assertions.update(
                            original_value_and_conditions_preserved=requests[0].get("payload")
                            == expected,
                            exact_note_path=requests[0]["path"]
                            == f"/kv/{arguments['namespace']}/{arguments['key']}",
                            json_post=requests[0].get("content_type") == "application/json"
                            and requests[0]["method"] == "POST",
                        )
                    if case["fixture_status"] != 200:
                        assertions["origin_error_body_preserved"] = (
                            f"{case['fixture_status']} local fixture refuses" in text
                        )
                rows.append(
                    case
                    | {
                        "observed_error": error,
                        "origin_requests": requests,
                        "assertions": assertions,
                        "matched": all(assertions.values()),
                        "tool_text": text,
                    }
                )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            origin.shutdown()
            origin.server_close()
    return {
        "version": label,
        "cases": len(rows),
        "matched": sum(row["matched"] for row in rows),
        "mismatched": sum(not row["matched"] for row in rows),
        "mcp_HTTP_requests": len(rows) + 3,
        "origin_HTTP_requests": sum(len(row["origin_requests"]) for row in rows),
        "no_signing_key_confirmed": True,
        "process_stopped": process.poll() is not None,
        "write_note_description": tools["write_note"]["description"],
        "rows": rows,
    }


def main():
    snapshot, provenance_path, report_path = map(Path, sys.argv[1:])
    assert not report_path.exists(), "Existing completed report; do not overwrite."
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    def check_sources():
        for source in provenance["files"]:
            raw = (snapshot / source["version"] / source["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == source["sha256"]
            assert (
                hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                == source["git_blob"]
            )

    check_sources()
    cases = scenarios()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "main": provenance["main"],
        "head": provenance["head"],
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            **{name: importlib.metadata.version(name) for name in ("mcp", "starlette", "uvicorn")},
        },
        "expected_local_refusals_per_version": sum(c["expected_local_reject"] for c in cases),
        "versions": [
            run_version(label, snapshot / label, cases) for label in ("main", "candidate")
        ],
        "whole_unmodified_mcp_modules": True,
        "transport_or_sdk_mocking": False,
        "ast_definition_extraction": False,
        "origin_is_nonpersisting_fixture": True,
        "actual_official_server_storage_auth_executed": False,
        "original_repository_test_module_executed": False,
        "full_linux_or_upstream_ci": False,
        "live_service_test_writes": 0,
        "protected_key_or_wallet_access": False,
    }
    check_sources()
    report["all_source_blobs_unchanged_after_run"] = len(provenance["files"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in ("runtime", "expected_local_refusals_per_version")}))
    print(
        json.dumps(
            [
                {
                    k: v[k]
                    for k in (
                        "version",
                        "cases",
                        "matched",
                        "mismatched",
                        "mcp_HTTP_requests",
                        "origin_HTTP_requests",
                    )
                }
                for v in report["versions"]
            ]
        )
    )


if __name__ == "__main__":
    main()
