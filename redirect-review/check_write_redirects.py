"""Windows/CPython review of Technocore PR #944 using two loopback origins.

Run only against source you reviewed. No key, hosted-service write, or retry.
The unchanged candidate's urllib transport and shared _request layer execute.
This is not a Cloudflare runtime or full upstream server/CI test.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import sys
from threading import Thread
from unittest.mock import patch

CODES = (301, 302, 303, 307, 308)
PAYLOAD = {"from": "local-fixture", "text": "한글 전송 검사"}


def load_candidate(folder: Path):
    # Keep production signing configuration out of this isolated review.
    with patch.dict(os.environ, {"TECHNOCORE_SIGNING_KEY": "", "TECHNOCORE_URL": "http://127.0.0.1"}):
        spec = importlib.util.spec_from_file_location(
            "redirect_candidate", folder / "__init__.py",
            submodule_search_locations=[str(folder)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    server = sys.modules["redirect_candidate.server"]
    if server._signer is not None:
        raise RuntimeError("Review requires an unsigned candidate")
    return server


async def review(folder: Path):
    source_log, target_log, committed = [], [], []

    class Target(BaseHTTPRequestHandler):
        def answer(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            target_log.append({"method": self.command, "body": body})
            response = b"REDIRECT-TARGET-READ"
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response)

        do_GET = do_HEAD = do_POST = answer

        def log_message(self, *args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    target_url = f"http://127.0.0.1:{target.server_port}/target"

    class Origin(BaseHTTPRequestHandler):
        def answer(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            source_log.append({"method": self.command, "body": body})
            if self.path == "/ok":
                committed.append(body)
                self.send_response(200)
                response = b"DIRECT-WRITE-CONFIRMED"
            else:
                parts = self.path.split("/")
                code = int(parts[2])
                if parts[-1] == "committed" and self.command == "POST":
                    committed.append(body)
                self.send_response(code)
                if parts[1] == "redirect":
                    self.send_header("Location", target_url)
                response = b"LOCAL-REDIRECT"
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response)

        do_GET = do_HEAD = do_POST = answer

        def log_message(self, *args):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    threads = [Thread(target=s.serve_forever, daemon=True) for s in (origin, target)]
    for thread in threads:
        thread.start()
    module = load_candidate(folder)
    module.BASE_URL = f"http://127.0.0.1:{origin.server_port}"
    original_connect = socket.socket.connect

    def loopback_only(sock, address):
        if not isinstance(address, tuple) or address[0] != "127.0.0.1":
            raise OSError("Review blocks non-loopback connections")
        return original_connect(sock, address)

    rows = []

    async def case(name, method, path, expected_error, stored=0):
        source_log.clear()
        target_log.clear()
        committed.clear()
        text, error = "", False
        try:
            text = await module._request(
                method, path, payload=PAYLOAD if method == "POST" else None, timeout=3,
            )
        except module.ToolError as exc:
            error, text = True, str(exc)
        conditions = {"error_contract": error == expected_error,
                      "one_origin_request": len(source_log) == 1,
                      "fixture_commit_count": len(committed) == stored}
        if expected_error:
            conditions["redirect_target_not_contacted"] = not target_log
            if method == "POST":
                conditions["outcome_is_unconfirmed"] = "this write was not confirmed" in text
                conditions["check_before_retrying"] = "check whether it landed before retrying" in text
            else:
                conditions["read_appropriate_error"] = "this request was not completed" in text and "write" not in text
        elif path == "/ok":
            conditions["direct_write_response"] = text == "DIRECT-WRITE-CONFIRMED" and not target_log
        else:
            # urllib's existing HEAD redirect path becomes GET on this runtime.
            # This PR promises read-only following, not preservation of HEAD.
            allowed_methods = {"GET"} if method == "GET" else {"GET", "HEAD"}
            conditions["redirect_follows_as_read"] = len(target_log) == 1 and target_log[0]["method"] in allowed_methods
        if method == "POST" and source_log:
            conditions["unicode_body_preserved_at_origin"] = json.loads(source_log[0]["body"]) == PAYLOAD
        rows.append({"case": name, "passed": all(conditions.values()), "checks": conditions,
                     "observed_error": error, "response": text,
                     "origin_requests": len(source_log), "target_requests": len(target_log),
                     "target_methods": [r["method"] for r in target_log],
                     "fixture_commits": len(committed)})

    try:
        with patch.object(socket.socket, "connect", loopback_only), patch.dict(os.environ, {"NO_PROXY": "127.0.0.1"}):
            for code in CODES:
                await case(f"POST/{code}/not-stored", "POST", f"/redirect/{code}/pending", True)
                await case(f"POST/{code}/already-stored", "POST", f"/redirect/{code}/committed", True, stored=1)
                await case(f"POST/{code}/no-location", "POST", f"/noloc/{code}/pending", True)
                for method in ("GET", "HEAD"):
                    await case(f"{method}/{code}/follow", method, f"/redirect/{code}/pending", False)
            await case("GET/301/no-location", "GET", "/noloc/301/pending", True)
            await case("POST/200/direct", "POST", "/ok", False, stored=1)
    finally:
        for http_server in (origin, target):
            http_server.shutdown()
            http_server.server_close()
        for thread in threads:
            thread.join(timeout=3)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "scope": "Actual CPython urllib plus shared _request against two loopback-only origins",
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.py"))},
        "cases": len(rows), "passed": sum(r["passed"] for r in rows),
        "failed": sum(not r["passed"] for r in rows), "results": rows,
        "production_keys_loaded": False, "hosted_service_writes": 0,
        "non_loopback_http_requests": 0, "automatic_retries": 0,
        "full_upstream_ci": False, "cloudflare_runtime_tested": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(review(args.source.resolve()))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("cases", "passed", "failed", "scope")}, ensure_ascii=False))
    return int(bool(result["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
