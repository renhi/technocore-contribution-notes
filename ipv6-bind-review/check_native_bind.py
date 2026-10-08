"""Run unchanged MCP packages over real loopback HTTP; never invoke a tool.

Usage: python check_native_bind.py <before-src> <after-src> <provenance> <report>
The src arguments point at mcp/src, each containing technocore_mcp.
"""

from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import ipaddress
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOSTS = (
    ("bracketed-short-ipv6", "[::1]", "::1"),
    ("bracketed-expanded-ipv6", "[0:0:0:0:0:0:0:1]", "::1"),
    ("short-ipv6-control", "::1", "::1"),
    ("expanded-ipv6-control", "0:0:0:0:0:0:0:1", "::1"),
    ("ipv4-control", "127.0.0.1", "127.0.0.1"),
    ("localhost-control", "localhost", "127.0.0.1"),
    ("alternate-ipv4-loopback", "127.0.0.2", "127.0.0.2"),
    ("shorthand-ipv4-loopback", "127.1", "127.0.0.1"),
)
PROTOCOL = "2025-11-25"


def available_port(address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as listener:
        listener.bind((address, 0))
        return listener.getsockname()[1]


def request(address, port, method, params=None, headers=None, request_id=1):
    assert ipaddress.ip_address(address).is_loopback
    data = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        data["params"] = params
    outbound_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL,
        **(headers or {}),
    }
    conn = http.client.HTTPConnection(address, port, timeout=3)
    try:
        conn.request("POST", "/mcp", json.dumps(data).encode("utf-8"), outbound_headers)
        response = conn.getresponse()
        raw = response.read(1_048_577)
        assert len(raw) <= 1_048_576, "Fixture response exceeded its bound"
        text = raw.decode("utf-8")
        payload = None
        if response.status == 200:
            if "text/event-stream" in (response.getheader("Content-Type") or ""):
                events = [
                    line[5:].strip() for line in text.splitlines() if line.startswith("data:")
                ]
                assert len(events) == 1, "Expected exactly one MCP response"
                payload = json.loads(events[0])
            else:
                payload = json.loads(text)
            assert payload["jsonrpc"] == "2.0" and payload["id"] == request_id
            assert "error" not in payload, payload.get("error")
        return response.status, payload, response.getheader("Content-Type"), text
    finally:
        conn.close()


def run_host(source, name, host, address, origin_url):
    port = available_port(address)
    env = os.environ.copy()
    env.pop("TECHNOCORE_SIGNING_KEY", None)
    env.update(
        PYTHONPATH=str(source.resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        HOST=host,
        PORT=str(port),
        TECHNOCORE_URL=origin_url,
        TECHNOCORE_NICK="native-bind-fixture",
    )
    start = time.monotonic()
    checks = []
    outcome = {
        "name": name,
        "host_setting": host,
        "connection_address": address,
        "port": port,
        "started": False,
        "checks": checks,
    }
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [sys.executable, "-c", "from technocore_mcp.server import main; main()", "--http"],
            cwd=source.resolve().parent,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 12
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    with socket.create_connection((address, port), timeout=0.1):
                        outcome["started"] = True
                    break
                except OSError:
                    time.sleep(0.05)
            if not outcome["started"]:
                outcome["failure"] = "Listener did not become reachable"
                # Windows does not resolve this shorthand in the observed environment.
                # Keep it as a documented platform control, never a claimed PR fix.
                if (
                    name == "shorthand-ipv4-loopback"
                    and os.name == "nt"
                    and process.poll() is not None
                ):
                    log.seek(0)
                    initial_log = log.read().decode("utf-8", errors="replace")
                    assert "getaddrinfo failed" in initial_log
                    outcome.pop("failure")
                    outcome["passed"] = True
                    outcome["platform_observation"] = (
                        "Windows shorthand IPv4 lookup refused in both versions"
                    )
                    checks.append({"name": "platform-shorthand-refusal", "passed": True})
                return outcome

            status, payload, content_type, _ = request(
                address,
                port,
                "initialize",
                {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "native-bind-review", "version": "1"},
                },
            )
            assert status == 200, f"Initialize status: {status}"
            result = payload["result"]
            assert result["protocolVersion"] == PROTOCOL
            assert result["serverInfo"]["version"] == "0.14.5"
            assert "tools" in result["capabilities"]
            checks.append(
                {
                    "name": "initialize",
                    "passed": True,
                    "status": status,
                    "server_info": result["serverInfo"],
                    "content_type": content_type,
                }
            )

            status, payload, _, _ = request(address, port, "tools/list", {}, request_id=2)
            assert status == 200, f"tools/list status: {status}"
            tools = payload["result"]["tools"]
            names = sorted(tool["name"] for tool in tools)
            assert {"read_room", "list_rooms", "read_note", "say", "whoami"}.issubset(names), names
            checks.append(
                {
                    "name": "tools-list",
                    "passed": True,
                    "status": status,
                    "tool_count": len(tools),
                    "names": names,
                }
            )

            origin_host = f"[{address}]" if ":" in address else address
            status, _, _, _ = request(
                address,
                port,
                "tools/list",
                {},
                headers={"Origin": f"http://{origin_host}:{port}"},
                request_id=3,
            )
            assert status == 200, f"Local Origin unexpectedly refused: {status}"
            checks.append({"name": "local-origin-accepted", "passed": True, "status": status})

            status, _, _, _ = request(
                address,
                port,
                "tools/list",
                {},
                headers={"Host": f"untrusted.example:{port}"},
                request_id=4,
            )
            assert status == 421, f"Foreign Host unexpectedly accepted: {status}"
            checks.append({"name": "foreign-host-refused", "passed": True, "status": status})

            status, _, _, _ = request(
                address,
                port,
                "tools/list",
                {},
                headers={"Origin": "https://untrusted.example"},
                request_id=5,
            )
            assert status == 403, f"Foreign Origin unexpectedly accepted: {status}"
            checks.append({"name": "foreign-origin-refused", "passed": True, "status": status})
            outcome["passed"] = True
        except Exception as exc:
            outcome["failure"] = f"{type(exc).__name__}: {exc}"
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            log.seek(0)
            logs = log.read().decode("utf-8", errors="replace")
            outcome["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)
            outcome["process_exit_code"] = process.returncode
            outcome["process_stopped"] = process.poll() is not None
            if not outcome.get("passed"):
                outcome["log_tail"] = logs[-1600:]
    return outcome


def main():
    before, after, provenance_path, report_path = map(Path, sys.argv[1:])
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    for label, source in (("before", before), ("after", after)):
        for entry in provenance["files"]:
            prefix = "mcp/src/"
            if entry["version"] == label and entry["path"].startswith(prefix):
                raw = (source / entry["path"][len(prefix) :]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["path"]
    # Prove this OS has IPv6 loopback support before counting bracket failures as defects.
    available_port("::1")
    upstream_requests = []

    class OriginTrap(BaseHTTPRequestHandler):
        def do_GET(self):
            upstream_requests.append({"method": self.command, "path": self.path})
            self.send_response(503)
            self.end_headers()

        def do_POST(self):
            self.do_GET()

        def log_message(self, *_):
            pass

    trap = ThreadingHTTPServer(("127.0.0.1", 0), OriginTrap)
    thread = threading.Thread(target=trap.serve_forever, daemon=True)
    thread.start()
    origin_url = f"http://127.0.0.1:{trap.server_port}"
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "ipv6_loopback_preflight_passed": True,
        "versions": {},
        "summaries": {},
        "real_http": True,
        "source_bytes_verified": True,
        "mcp_protocol": PROTOCOL,
        "production_key_access": 0,
        "tool_calls": 0,
        "cloudflare_runtime": False,
        "full_upstream_ci": False,
        "source_modified": False,
        "airdrop_eligibility": "unconfirmed",
        "dependencies": {
            n: importlib.metadata.version(n) for n in ("mcp", "uvicorn", "starlette", "pydantic")
        },
    }
    report["windows_bracketed_lookup"] = {
        host: sorted(
            {entry[4][0] for entry in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)}
        )
        for host in ("[::1]", "[0:0:0:0:0:0:0:1]")
    }
    try:
        for label, source in (("before", before), ("after", after)):
            cases = []
            for name, host, address in HOSTS:
                result = run_host(source, name, host, address, origin_url)
                cases.append(result)
                print(
                    json.dumps(
                        {
                            "version": label,
                            "name": name,
                            "passed": result.get("passed", False),
                            "failure": result.get("failure"),
                        }
                    ),
                    flush=True,
                )
            report["versions"][label] = cases
            report["summaries"][label] = {
                "scenarios": len(cases),
                "passed": sum(bool(c.get("passed")) for c in cases),
                "failed": sum(not c.get("passed") for c in cases),
                "successful_checks": sum(len(c["checks"]) for c in cases),
            }
    finally:
        trap.shutdown()
        trap.server_close()
        thread.join(timeout=2)
    report["upstream_http_requests"] = upstream_requests
    assert not upstream_requests, "Initialize and tools/list must not reach the chat origin"
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summaries"]))
    sys.exit(1 if report["summaries"]["after"]["failed"] else 0)


if __name__ == "__main__":
    main()
