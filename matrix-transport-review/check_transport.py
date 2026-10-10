"""Native loopback HTTP regression for selected unchanged PR973 transport definitions."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def selected_namespace(path):
    wanted = {
        "BridgeError",
        "RetryableError",
        "MatrixError",
        "_retry_after",
        "_http_json",
        "technocore_get",
        "technocore_read_room",
        "signed_frame_landed",
        "technocore_say_signed",
        "valid_ed25519_did",
        "base58btc_encode",
        "base58btc_decode",
        "did_from_private_key",
        "verified_record_did",
        "sign_message",
        "sanitize_line",
        "_fresh_nonce",
        "matrix_request",
    }
    import re
    import secrets
    import unicodedata

    namespace = {
        "__name__": "selected_pr973_transport",
        "urllib": urllib,
        "time": time,
        "json": json,
        "re": re,
        "secrets": secrets,
        "unicodedata": unicodedata,
        "base64": base64,
        "Ed25519PrivateKey": Ed25519PrivateKey,
        "Ed25519PublicKey": Ed25519PublicKey,
        "InvalidSignature": InvalidSignature,
        "serialization": serialization,
        "UA": "technocore-matrix/0.2.0",
        "MESSAGE_MAX_CHARS": 4096,
        "BASE58": "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
        "MULTICODEC_ED25519": b"\xed\x01",
        "DID_RE": re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$"),
        "_nonce_lock": threading.Lock(),
        "_last_nonce": 0,
        "http": http,
    }
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in wanted
    ]
    assert {node.name for node in nodes} == wanted
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *nodes,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = {"mode": "complete", "requests": [], "records": [], "verified_posts": 0}
    key = Ed25519PrivateKey.generate()  # Disposable key; never persisted or printed.
    namespaces = {
        "original": selected_namespace(args.source),
        "proposal": selected_namespace(args.proposal),
    }
    did = namespaces["original"]["did_from_private_key"](key)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, body, mode="complete"):
            raw = (
                json.dumps(body, ensure_ascii=False).encode()
                if not isinstance(body, bytes)
                else body
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            if mode in {"missing_chunk_end", "mid_chunk"}:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header(
                    "Content-Length", str(len(raw) + (9 if mode == "short_length" else 0))
                )
            if status == 429:
                self.send_header("Retry-After", "0")
            self.end_headers()
            if mode == "missing_chunk_end":
                self.wfile.write(f"{len(raw):x}\r\n".encode() + raw + b"\r\n")
            elif mode == "mid_chunk":
                self.wfile.write(f"{len(raw) + 9:x}\r\n".encode() + raw)
            else:
                self.wfile.write(raw)
            self.wfile.flush()
            self.close_connection = True

        def do_GET(self):  # noqa: N802
            state["requests"].append({"method": "GET", "path": self.path})
            if state["mode"].startswith("signed_"):
                self.respond(200, {"messages": state["records"]})
            else:
                self.generic()

        def generic(self):
            mode = state["mode"]
            status = int(mode[6:]) if mode.startswith("error_") else 200
            body = (
                b"{" if mode == "bad_json" else ([] if mode == "non_object" else {"ok": "한글🙂"})
            )
            if mode == "put_recover":
                mode = "short_length" if len(state["requests"]) == 1 else "complete"
            self.respond(status, body, mode)

        def do_PUT(self):  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            state["requests"].append({"method": "PUT", "path": self.path, "body": body})
            self.generic()

        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            nonce = body["nonce"]
            assert (
                isinstance(nonce, str) and nonce.isascii() and nonce.isdigit() and len(nonce) <= 19
            )
            signature = base64.urlsafe_b64decode(body["sig"] + "==")
            key.public_key().verify(signature, f"lobby|{nonce}|{body['text']}".encode())
            state["verified_posts"] += 1
            state["requests"].append({"method": "POST", "path": self.path, "nonce": nonce})
            posts = sum(row["method"] == "POST" for row in state["requests"])
            landed = state["mode"] != "signed_not_landed_then_ok" or posts > 1
            if landed:
                state["records"].append(
                    {
                        "seq": len(state["records"]) + 1,
                        "from": body["did"],
                        "nonce": int(nonce),
                        "text": body["text"],
                        "sig": body["sig"],
                    }
                )
            mode = (
                "complete"
                if posts > 1
                else (
                    "missing_chunk_end"
                    if state["mode"] == "signed_landed_chunk"
                    else "short_length"
                )
            )
            self.respond(200, {"posted": {"seq": len(state["records"])}}, mode)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    scenarios = [
        ("json", mode)
        for mode in (
            "complete",
            "short_length",
            "missing_chunk_end",
            "mid_chunk",
            "bad_json",
            "non_object",
            "error_400",
            "error_429",
            "error_503",
        )
    ]
    scenarios += [
        ("get", mode)
        for mode in (
            "complete",
            "short_length",
            "missing_chunk_end",
            "mid_chunk",
            "error_404",
            "error_503",
        )
    ]
    scenarios += [
        ("signed", mode)
        for mode in ("signed_landed_length", "signed_landed_chunk", "signed_not_landed_then_ok")
    ]
    scenarios.append(("put", "put_recover"))
    rows = []
    try:
        for label, ns in namespaces.items():
            for lane, mode in scenarios:
                state.update(mode=mode, requests=[], records=[], verified_posts=0)
                failure = None
                outcome = "returned"
                value = None
                try:
                    if lane == "json":
                        value = ns["_http_json"](
                            urllib.request.Request(base + "/probe"), timeout=2, attempts=1
                        )
                    elif lane == "get":
                        value = ns["technocore_get"](base, "/probe", timeout=2)
                    elif lane == "put":
                        value = ns["matrix_request"](
                            base,
                            "PUT",
                            "/send/m.room.message/stable-transaction",
                            "disposable-fixture-token",
                            {"body": "한글🙂"},
                            timeout=2,
                        )
                    else:
                        value = ns["technocore_say_signed"](
                            base, key, did, "lobby", "한글🙂 [mx:fixture]", marker="[mx:fixture]"
                        )
                except Exception as error:
                    outcome = type(error).__name__
                    retryable = isinstance(error, ns["MatrixError"]) and error.retryable
                    if lane == "json":
                        if mode in {
                            "short_length",
                            "missing_chunk_end",
                            "mid_chunk",
                            "bad_json",
                            "error_429",
                            "error_503",
                        }:
                            failure = (
                                None
                                if retryable
                                else "Expected retryable MatrixError, got " + outcome
                            )
                        elif mode == "error_400":
                            failure = (
                                None
                                if isinstance(error, ns["MatrixError"])
                                and error.status == 400
                                and not error.retryable
                                else "Permanent400 contract changed"
                            )
                        elif mode == "non_object":
                            failure = (
                                None
                                if isinstance(error, ns["BridgeError"])
                                and not isinstance(error, ns["MatrixError"])
                                else "Non-object contract changed"
                            )
                        else:
                            failure = "Unexpected complete-response error " + outcome
                    elif lane == "get":
                        if mode == "error_404":
                            failure = (
                                None
                                if isinstance(error, urllib.error.HTTPError) and error.code == 404
                                else "Permanent404 contract changed"
                            )
                        elif mode == "complete":
                            failure = "Unexpected complete GET error " + outcome
                        else:
                            failure = (
                                None
                                if isinstance(error, ns["RetryableError"])
                                else "Expected RetryableError, got " + outcome
                            )
                    else:
                        failure = "Expected successful retry/reconciliation, got " + outcome
                else:
                    if lane in {"json", "get"} and mode != "complete":
                        failure = "Incomplete/error response treated as success"
                    elif lane == "json" and value != {"ok": "한글🙂"}:
                        failure = "Complete JSON changed"
                    elif lane == "get" and json.loads(value) != {"ok": "한글🙂"}:
                        failure = "Complete GET changed"
                    elif lane == "signed":
                        expected_posts = 2 if mode == "signed_not_landed_then_ok" else 1
                        expected_value = 1 if expected_posts == 2 else 0
                        if (
                            value != expected_value
                            or len(state["records"]) != 1
                            or sum(r["method"] == "POST" for r in state["requests"])
                            != expected_posts
                        ):
                            failure = "Signed recovery did not preserve one accepted record"
                    elif lane == "put":
                        if (
                            value != {"ok": "한글🙂"}
                            or len(state["requests"]) != 2
                            or state["requests"][0] != state["requests"][1]
                        ):
                            failure = "PUT retry changed transaction path/body or count"
                expected_requests = 1
                if lane == "get" and mode in {
                    "short_length",
                    "missing_chunk_end",
                    "mid_chunk",
                    "error_503",
                }:
                    expected_requests = 4
                elif lane == "signed":
                    expected_requests = 3 if mode == "signed_not_landed_then_ok" else 2
                elif lane == "put":
                    expected_requests = 2
                if len(state["requests"]) != expected_requests:
                    failure = (
                        failure + "; " if failure else ""
                    ) + f"Expected {expected_requests} HTTP requests, got {len(state['requests'])}"
                rows.append(
                    {
                        "version": label,
                        "lane": lane,
                        "mode": mode,
                        "outcome": outcome,
                        "passed": failure is None,
                        "failure": failure,
                        "requests": state["requests"].copy(),
                        "accepted_records": len(state["records"]),
                        "verified_posts": state["verified_posts"],
                    }
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive()
    summaries = {
        label: {
            "scenarios": sum(r["version"] == label for r in rows),
            "passed": sum(r["version"] == label and r["passed"] for r in rows),
            "http_requests": sum(len(r["requests"]) for r in rows if r["version"] == label),
        }
        for label in namespaces
    }
    report = {
        "summaries": summaries,
        "results": rows,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {
            label: hashlib.sha256(path.read_bytes()).hexdigest()
            for label, path in (("original", args.source), ("proposal", args.proposal))
        },
        "selected_definitions": sorted(
            {
                n.name
                for n in ast.parse(args.source.read_text()).body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                and n.name in namespaces["original"]
            }
        ),
        "server_stopped": True,
        "user_key_used": False,
        "full_bridge_executed": False,
        "live_service_requests": 0,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summaries))
    assert summaries["proposal"]["passed"] == len(scenarios)


if __name__ == "__main__":
    main()
