"""Native loopback HTTP regression for PR842's exact CPython export transport.

Execute unchanged fetch.py plus exact pure export-wrapper functions selected from
server.py. No server/store imports, fcntl stubs, MCP protocol simulation or live writes.
Usage: python check_export_transport.py fetch.py server.py output.json
"""

import argparse
import ast
import asyncio
import hashlib
import importlib.util
import json
import platform
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ToolError(Exception):
    """Wrapper error type injected at the exception boundary; SDK is not booted."""


LINES = [
    (json.dumps({"seq": n, "text": f"한글 기록 {n} 😀"}, ensure_ascii=False) + "\n").encode()
    for n in range(1, 6)
]
TWO = b"".join(LINES[:2])
CASES = (
    "complete_length",
    "bounded_length",
    "bounded_chunked_stall",
    "bounded_long_length",
    "empty",
    "eof_delimited",
    "complete_chunked",
    "cut_mid_line",
    "cut_at_boundary",
    "cut_empty",
    "chunked_no_end",
    "chunked_mid_chunk",
    "refusal403",
    "refusal429",
    "refusal500",
    "cut_refusal429",
    "body_stall",
    "header_stall",
    "lowercase_generation",
    "cursor_suffix",
)
ERRORS = {
    "cut_mid_line",
    "cut_at_boundary",
    "cut_empty",
    "chunked_no_end",
    "chunked_mid_chunk",
    "cut_refusal429",
    "body_stall",
    "header_stall",
}


def run(fetch_path, server_path):
    spec = importlib.util.spec_from_file_location("review_transport", fetch_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = {"_header", "_room_generation", "_export_page_marker", "_export_get"}
    tree = ast.parse(server_path.read_text(encoding="utf-8"))
    selected = [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
    ]
    assert {n.name for n in selected} == names
    tree.body = selected
    namespace = {
        "json": json,
        "urllib": urllib,
        "ToolError": ToolError,
        "_export_fetch": module.urllib_export_fetch,
        "TIMEOUT": 0.2,
        "VERSION": "review",
    }
    # Execute only reviewed local source; caller must verify the pinned hashes first.
    exec(compile(tree, str(server_path), "exec"), namespace)  # noqa: S102
    observed = []
    counts = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            mode = parsed.path.rsplit("/", 1)[-1]
            with lock:
                counts[mode] = counts.get(mode, 0) + 1
                observed.append({"mode": mode, "query": parsed.query})
            self.close_connection = True
            if mode == "header_stall":
                time.sleep(0.45)
            status = (
                int(mode[-3:])
                if mode.startswith("refusal")
                else 429
                if mode == "cut_refusal429"
                else 200
            )
            refusal = b"retry after 12 seconds"
            raw = TWO
            chunked = mode in {
                "complete_chunked",
                "bounded_chunked_stall",
                "chunked_no_end",
                "chunked_mid_chunk",
            }
            expected = len(raw)
            if mode in {
                "bounded_length",
                "bounded_long_length",
                "bounded_chunked_stall",
            }:
                raw = b"".join(LINES)
                expected = len(raw) if mode != "bounded_long_length" else len(raw) + 10000
            elif mode == "empty":
                raw, expected = b"", 0
            elif mode == "cut_mid_line":
                raw = TWO[:-9]
            elif mode == "cut_at_boundary":
                raw = LINES[0]
            elif mode == "cut_empty":
                raw = b""
            elif mode == "cursor_suffix":
                assert urllib.parse.parse_qs(parsed.query) == {"after": ["2"]}
                raw = b"".join(LINES[2:4])
                expected = len(raw)
            elif status >= 400:
                expected = len(refusal)
                raw = refusal[:8] if mode == "cut_refusal429" else refusal
            self.send_response(status)
            self.send_header("Content-Type", "application/jsonl; charset=utf-8")
            if mode == "lowercase_generation":
                self.send_header("x-room-generation", "7")
            elif mode != "eof_delimited":
                self.send_header("X-Room-Generation", "7")
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            elif mode != "eof_delimited":
                self.send_header("Content-Length", str(expected))
            self.end_headers()
            try:
                if mode == "body_stall":
                    time.sleep(0.45)
                if chunked:
                    if mode == "chunked_mid_chunk":
                        self.wfile.write(f"{len(TWO):X}\r\n".encode() + TWO[:9])
                    else:
                        body = b"".join(LINES[:3]) if mode == "bounded_chunked_stall" else raw
                        self.wfile.write(f"{len(body):X}\r\n".encode() + body + b"\r\n")
                        self.wfile.flush()
                        if mode == "bounded_chunked_stall":
                            time.sleep(0.45)
                        if mode not in {"chunked_no_end", "bounded_chunked_stall"}:
                            self.wfile.write(b"0\r\n\r\n")
                else:
                    self.wfile.write(raw)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    namespace["BASE_URL"] = f"http://127.0.0.1:{httpd.server_port}"
    rows = []
    try:
        for mode in CASES:
            start = time.monotonic()
            body = None
            kind = "success"
            try:
                body = asyncio.run(
                    namespace["_export_get"]("/" + mode, 2 if mode == "cursor_suffix" else None, 2)
                )
            except ToolError:
                kind = "tool_error"
            except Exception as exc:  # noqa: BLE001 -- record original exception classes
                kind = "untranslated_" + type(exc).__name__
            row = {
                "case": mode,
                "outcome": kind,
                "elapsed_seconds": round(time.monotonic() - start, 4),
                "requests": counts.get(mode, 0),
            }
            expected_error = mode in ERRORS or mode.startswith("refusal")
            row["expected"] = "tool_error" if expected_error else "success"
            row["matched"] = kind == row["expected"]
            if kind == "success":
                try:
                    records = [json.loads(line) for line in body.splitlines()]
                    row["all_json_lines_valid"] = True
                except ValueError:
                    records = []
                    row["all_json_lines_valid"] = False
                row["returned_body_bytes"] = len(body.encode())
                row["has_continuation"] = any(
                    r.get("_technocore_mcp") == "export_truncated" for r in records
                )
                if not expected_error:
                    assert records and records[0]["_technocore_mcp"] == "export_page", row
                    assert records[0]["room_generation"] == (
                        None if mode == "eof_delimited" else 7
                    ), row
                    assert records[0]["after"] == (2 if mode == "cursor_suffix" else None), row
                    wanted = (
                        []
                        if mode == "empty"
                        else LINES[2:4]
                        if mode == "cursor_suffix"
                        else LINES[:2]
                    )
                    actual = [line for line in body.splitlines() if '"_technocore_mcp"' not in line]
                    assert actual == [b.decode().rstrip("\n") for b in wanted], row
                    assert row["has_continuation"] == mode.startswith("bounded"), row
                    if row["has_continuation"]:
                        assert records[-1]["after"] == 2 and records[-1]["room_generation"] == 7
            assert row["requests"] == 1, row
            rows.append(row)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "fetch_sha256": hashlib.sha256(fetch_path.read_bytes()).hexdigest(),
        "server_sha256": hashlib.sha256(server_path.read_bytes()).hexdigest(),
        "cases": len(rows),
        "matched": sum(r["matched"] for r in rows),
        "mismatches": sum(not r["matched"] for r in rows),
        "rows": rows,
        "native_http": True,
        "socket_timeout_seconds": 0.2,
        "wrapper_functions": sorted(names),
        "wrapper_ast_bodies_unchanged": True,
        "sdk_exception_boundary_injected": True,
        "full_mcp_sdk_transport_run": False,
        "full_server_ci_run": False,
        "remote_service_requests": 0,
        "signing_or_private_key_access": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fetch", type=Path)
    parser.add_argument("server", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.fetch.resolve(), args.server.resolve())
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{result['cases']} native HTTP cases: {result['matched']} matched / {result['mismatches']} mismatched"
    )
    for row in result["rows"]:
        if not row["matched"]:
            print(row["case"], row["outcome"], "expected", row["expected"])
    raise SystemExit(0 if result["mismatches"] == 0 else 1)


if __name__ == "__main__":
    main()
