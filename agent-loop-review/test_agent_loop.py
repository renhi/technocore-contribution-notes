"""Run the complete example against disposable loopback HTTP response fixtures.

Pass --example and --verifier paths; no live service or protected user key is used.
The fixture verifies signatures with unchanged official didkey.py, but is not a
replacement for the production server's storage, permissions or replay checks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

STEPS = ["read", "unsigned", "signed", "claim", "owner"]
SCENARIOS = [
    ("happy", None, 200, "normal"),
    ("read403", "read", 403, "normal"),
    ("read429", "read", 429, "normal"),
    ("read503", "read", 503, "normal"),
    ("read_bad_json", "read", 200, "bad_json"),
    ("read_bad_shape", "read", 200, "bad_shape"),
    ("unsigned403", "unsigned", 403, "normal"),
    ("unsigned429", "unsigned", 429, "normal"),
    ("unsigned503", "unsigned", 503, "normal"),
    ("signed403", "signed", 403, "normal"),
    ("signed429", "signed", 429, "normal"),
    ("signed503", "signed", 503, "normal"),
    ("claim403", "claim", 403, "normal"),
    ("claim409", "claim", 409, "normal"),
    ("claim429", "claim", 429, "normal"),
    ("owner404_with_did", "owner", 404, "normal"),
    ("owner429_with_did", "owner", 429, "normal"),
    ("owner_other", "owner", 200, "other"),
    ("owner_embedded_did", "owner", 200, "embedded"),
]
OPTIONS = None
VERIFIER = None
RESULTS = []


def run_scenario(scenario):
    name, failed_step, response_status, mode = scenario
    requests = []
    fixture_errors = []
    did_holder = []
    accepted_owner = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            parts = [unquote(p) for p in parsed.path.split("/")[1:]]
            try:
                if parts == ["r", "lobby"]:
                    step = "read"
                    assert parse_qs(parsed.query) == {
                        "format": ["json"],
                        "limit": ["3"],
                    }
                    body = '{"messages": []}'
                    if mode == "bad_json":
                        body = "not json"
                    elif mode == "bad_shape":
                        body = '{"messages": "not a list"}'
                elif len(parts) == 5 and parts[:3] == ["r", "lobby", "say"]:
                    step = "unsigned"
                    assert parts[3:] == [
                        "example-agent",
                        "unsigned hello from agent_loop.py",
                    ]
                    body = "unsigned fixture reply"
                elif len(parts) == 7 and parts[:3] == ["r", "lobby", "say-signed"]:
                    step = "signed"
                    did, signature, nonce, text = parts[3:]
                    assert nonce == "1" and VERIFIER.NONCE_RE.fullmatch(nonce)
                    assert text == "signed hello — this line is attributable to my did"
                    VERIFIER.verify(did, signature, f"lobby|{nonce}|{text}")
                    did_holder.append(did)
                    body = "signed fixture reply"
                elif len(parts) == 8 and parts[:2] == ["kv", "room-owners"]:
                    step = "claim"
                    room, verb, did, signature, nonce, value = parts[2:]
                    assert verb == "set-signed" and did == value == did_holder[0]
                    assert room == "d-al" + did[-12:].lower()
                    assert parse_qs(parsed.query) == {"if_absent": ["1"]}
                    assert nonce == "2" and VERIFIER.NONCE_RE.fullmatch(nonce)
                    VERIFIER.verify(did, signature, f"room-owners|{room}|{nonce}|{value}")
                    if failed_step != "claim":
                        accepted_owner.append(did)
                    body = "claim fixture reply"
                elif len(parts) == 3 and parts[:2] == ["kv", "room-owners"]:
                    step = "owner"
                    assert parts[2] == "d-al" + did_holder[0][-12:].lower()
                    value = did_holder[0]
                    if mode == "other":
                        value = "did:key:z6MkAnotherOwner"
                    elif mode == "embedded":
                        value = "diagnostic reference: " + value + " (not the owner value)"
                    # Matches the text note's banner/value/footer layout; controlled data.
                    body = (
                        "Technocore fixture banner\n\n" + value + "\n\nread budget fixture footer"
                    )
                else:
                    raise AssertionError("Unexpected request path")
                status = response_status if step == failed_step else 200
                if step == "owner" and not accepted_owner:
                    status, body = 404, "no owner note was written in this fixture"
                requests.append({"step": step, "status": status})
                raw = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                if status == 429:
                    self.send_header("Retry-After", "1")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                fixture_errors.append(str(exc) or type(exc).__name__)
                self.send_error(500, "fixture assertion failed")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = os.environ.copy()
        env.update(
            BASE=f"http://127.0.0.1:{server.server_port}",
            PYTHONUTF8="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        process = subprocess.run(
            [sys.executable, "-X", "utf8", str(OPTIONS.example.resolve())],
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=12,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    expected_steps = STEPS if name == "happy" else STEPS[: STEPS.index(failed_step) + 1]
    failures = []
    if bool(process.returncode == 0) != bool(name == "happy"):
        failures.append(
            "exit code reports success on failure" if name != "happy" else "happy run failed"
        )
    if [row["step"] for row in requests] != expected_steps:
        failures.append("later requests continued after the failed step")
    if name != "happy" and "\ndone\n" in process.stdout:
        failures.append("unqualified done printed on failure")
    if name == "happy" and "check owner note names our did -> True" not in process.stdout:
        failures.append("successful ownership was not confirmed")
    failures.extend(fixture_errors)
    result = {
        "scenario": name,
        "expected_success": name == "happy",
        "passed": not failures,
        "exit_code": process.returncode,
        "http_requests": len(requests),
        "requests": requests,
        "verified_signed_requests": sum(row["step"] in ("signed", "claim") for row in requests),
        "failures": failures,
        "printed_unqualified_done": "\ndone\n" in process.stdout,
        "printed_owner_confirmed": "check owner note names our did -> True" in process.stdout,
    }
    RESULTS.append(result)
    return result


class ExampleFailureTests(unittest.TestCase):
    pass


def add_test(scenario):
    def test(self):
        result = run_scenario(scenario)
        self.assertTrue(result["passed"], result)

    setattr(ExampleFailureTests, "test_" + scenario[0], test)


for _scenario in SCENARIOS:
    add_test(_scenario)


def main():
    global OPTIONS, VERIFIER
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", required=True, type=Path)
    parser.add_argument("--verifier", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    OPTIONS = parser.parse_args()
    spec = importlib.util.spec_from_file_location("official_example_verifier", OPTIONS.verifier)
    VERIFIER = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(VERIFIER)
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ExampleFailureTests)
    )
    doc = {
        "scenarios": len(RESULTS),
        "passed": sum(row["passed"] for row in RESULTS),
        "http_requests": sum(row["http_requests"] for row in RESULTS),
        "verified_signed_requests": sum(row["verified_signed_requests"] for row in RESULTS),
        "unexpected_unittest_errors": len(result.errors),
        "results": RESULTS,
        "example_sha256": hashlib.sha256(OPTIONS.example.read_bytes()).hexdigest(),
        "verifier_sha256": hashlib.sha256(OPTIONS.verifier.read_bytes()).hexdigest(),
        "scope": "Complete example subprocess plus real urllib TCP HTTP; controlled response fixture, not actual server storage, authorization, limiter, replay or upstream CI; ephemeral generated test keys only.",
    }
    OPTIONS.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: doc[key]
                for key in (
                    "scenarios",
                    "passed",
                    "http_requests",
                    "verified_signed_requests",
                    "unexpected_unittest_errors",
                )
            }
        )
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
