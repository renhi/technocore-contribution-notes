"""Native subprocess/HTTP fault tests for the independent read-only auditor."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import audit_skill

RESULTS = []
CASES = (
    "correct_lf",
    "correct_crlf_pin",
    "changed_byte",
    "crlf_changed_after_lf_pin",
    "added_bom",
    "removed_trailing_newline",
    "unicode_normalization_change",
    "self_consistent_wrong_document",
    "wrong_digest",
    "missing_digest",
    "wrong_version",
    "duplicate_target_entry",
    "missing_target_entry",
    "index_not_object",
    "skills_not_array",
    "non_object_entry",
    "invalid_json",
    "invalid_utf8",
    "wrong_type",
    "cross_origin_url",
    "wrong_path_url",
    "query_url",
    "index404",
    "index429",
    "index_redirect",
    "index_wrong_media",
    "index_oversize",
    "skill404",
    "skill429",
    "skill_redirect",
    "skill_wrong_media",
    "skill_unexpected_encoding",
    "skill_oversize",
    "skill_short_content_length",
)


def exercise(case):
    correct = "---\nname: technocore-chat\n---\nFixture café\n".encode()
    if case == "correct_crlf_pin":
        correct = correct.replace(b"\n", b"\r\n")
    expected = hashlib.sha256(correct).hexdigest()
    body = correct
    if case == "changed_byte":
        body = correct.replace(b"Fixture", b"Changed")
    elif case == "crlf_changed_after_lf_pin":
        body = correct.replace(b"\n", b"\r\n")
    elif case == "added_bom":
        body = b"\xef\xbb\xbf" + correct
    elif case == "removed_trailing_newline":
        body = correct.rstrip(b"\n")
    elif case == "unicode_normalization_change":
        body = correct.replace("é".encode(), "e\u0301".encode())
    elif case == "self_consistent_wrong_document":
        body = b"different document, with its own internally consistent advertised digest"
    elif case == "skill_oversize":
        body = b"x" * (audit_skill.SKILL_LIMIT + 1)
    requests = []
    fixture_errors = []
    server = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests.append({"method": "GET", "path": self.path})
            if self.path == "/.well-known/agent-skills/index.json":
                entry = {
                    "name": "technocore-chat",
                    "type": "skill-md",
                    "url": f"http://127.0.0.1:{server.server_port}/skill.md",
                    "digest": "sha256:" + expected,
                    "version": "fixture-v1",
                }
                index = {"skills": [entry]}
                if case == "self_consistent_wrong_document":
                    entry["digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
                elif case == "wrong_digest":
                    entry["digest"] = "sha256:" + "0" * 64
                elif case == "missing_digest":
                    del entry["digest"]
                elif case == "wrong_version":
                    entry["version"] = "different-version"
                elif case == "duplicate_target_entry":
                    index["skills"].append(entry.copy())
                elif case == "missing_target_entry":
                    entry["name"] = "another-skill"
                elif case == "index_not_object":
                    index = []
                elif case == "skills_not_array":
                    index["skills"] = "not an array"
                elif case == "non_object_entry":
                    index["skills"] = [42]
                elif case == "wrong_type":
                    entry["type"] = "executable"
                elif case == "cross_origin_url":
                    entry["url"] = "https://example.invalid/untrusted"
                elif case == "wrong_path_url":
                    entry["url"] = f"http://127.0.0.1:{server.server_port}/other"
                elif case == "query_url":
                    entry["url"] += "?different=1"
                raw = json.dumps(index).encode()
                if case == "invalid_json":
                    raw = b"not JSON"
                elif case == "invalid_utf8":
                    raw = b"\xff"
                elif case == "index_oversize":
                    raw = b" " * (audit_skill.INDEX_LIMIT + 1)
                mime = "text/html" if case == "index_wrong_media" else "application/json"
                status = (
                    404
                    if case == "index404"
                    else 429
                    if case == "index429"
                    else 302
                    if case == "index_redirect"
                    else 200
                )
            elif self.path == "/skill.md":
                raw = body
                mime = (
                    "text/html" if case == "skill_wrong_media" else "text/markdown; charset=utf-8"
                )
                status = (
                    404
                    if case == "skill404"
                    else 429
                    if case == "skill429"
                    else 302
                    if case == "skill_redirect"
                    else 200
                )
            else:
                fixture_errors.append("unvalidated URL or redirect target was followed")
                self.send_error(500)
                return
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header(
                "Content-Length",
                str(
                    len(raw)
                    + (
                        30
                        if case == "skill_short_content_length" and self.path == "/skill.md"
                        else 0
                    )
                ),
            )
            if status == 302:
                self.send_header("Location", "/must-not-follow")
            if status == 429:
                self.send_header("Retry-After", "1")
            if case == "skill_unexpected_encoding" and self.path == "/skill.md":
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A bounded reader is allowed to close an oversized response.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(Path(audit_skill.__file__).resolve()),
                "--base",
                f"http://127.0.0.1:{server.server_port}",
                "--expected-sha256",
                expected,
                "--expected-version",
                "fixture-v1",
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=15,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    expected_success = case.startswith("correct_")
    document = json.loads(process.stdout)
    expected_requests = (
        2
        if case.startswith("correct_")
        or case.startswith("skill_")
        or case in ("skill404", "skill429")
        or case
        in (
            "changed_byte",
            "crlf_changed_after_lf_pin",
            "added_bom",
            "removed_trailing_newline",
            "unicode_normalization_change",
        )
        else 1
    )
    passed = (
        process.returncode == (0 if expected_success else 1)
        and document["passed"] == expected_success
        and len(requests) == expected_requests
        and not fixture_errors
        and not process.stderr
    )
    if expected_success:
        passed = passed and document["skill_sha256"] == expected
    row = {
        "case": case,
        "passed": passed,
        "expected_success": expected_success,
        "exit_code": process.returncode,
        "requests": requests,
        "request_count": len(requests),
        "result": document,
        "fixture_errors": fixture_errors,
    }
    RESULTS.append(row)
    return row


class IntegrityTests(unittest.TestCase):
    pass


def install_test(case):
    def test(self):
        row = exercise(case)
        self.assertTrue(row["passed"], row)

    setattr(IntegrityTests, "test_" + case, test)


for _case in CASES:
    install_test(_case)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(IntegrityTests)
    )
    report = {
        "cases": len(RESULTS),
        "passed": sum(row["passed"] for row in RESULTS),
        "http_requests": sum(row["request_count"] for row in RESULTS),
        "unexpected_errors": len(result.errors),
        "auditor_sha256": hashlib.sha256(Path(audit_skill.__file__).read_bytes()).hexdigest(),
        "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "results": RESULTS,
        "scope": "Full auditor subprocess and actual loopback TCP HTTP. Synthetic document/index fixtures, not evidence of production corruption. No retries, writes, installed skills, protected keys or source execution.",
    }
    Path(__file__).with_name("fixture-validation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("cases", "passed", "http_requests", "unexpected_errors")}
        )
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
