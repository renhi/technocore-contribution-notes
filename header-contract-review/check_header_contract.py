"""Independent header-limit boundary evidence; no live oversized requests/writes.

Runs unchanged selected HeaderLimits/text definitions in a minimal Uvicorn fixture.
The entire Linux-dependent app/server is NOT imported or executed. Separately runs
the candidate's declaration suffix on a copy of the captured live OpenAPI data,
not the full manifest generator. Both boundaries are preserved in the reports.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import http.client
import json
import re
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from starlette.responses import PlainTextResponse


def segment(source, node):
    return "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno]) + "\n"


def selected_namespace(app_path, manifest_path):
    source = app_path.read_text(encoding="utf-8")
    nodes = ast.parse(source).body
    namespace = {"PlainTextResponse": PlainTextResponse, "re": re}
    manifest_constants = {}
    for node in ast.parse(manifest_path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("MAX_HEADERS", "MAX_HEADER_BYTES")
            for t in node.targets
        ):
            manifest_constants[node.targets[0].id] = ast.literal_eval(node.value)
    namespace["manifest"] = SimpleNamespace(**manifest_constants)
    names = []
    hashes = {}
    for node in nodes:
        name = (
            node.name
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            else node.targets[0].id
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            else None
        )
        if name in ("MAX_HEADERS", "MAX_HEADER_BYTES", "_REF", "text", "HeaderLimits"):
            raw = segment(source, node)
            exec(compile(raw, str(app_path), "exec"), namespace)
            names.append(name)
            hashes[name] = hashlib.sha256(raw.encode()).hexdigest()
    assert set(names) == {"MAX_HEADERS", "MAX_HEADER_BYTES", "_REF", "text", "HeaderLimits"}
    assert (namespace["MAX_HEADERS"], namespace["MAX_HEADER_BYTES"]) == (48, 8192)
    return namespace, hashes


CASES = [
    ("count47", 47, None, "GET", "/healthz", False),
    ("count48", 48, None, "GET", "/healthz", False),
    ("count49", 49, None, "GET", "/healthz", False),
    ("bytes8191", 2, 8191, "GET", "/healthz", False),
    ("bytes8192", 2, 8192, "GET", "/healthz", False),
    ("bytes8193", 2, 8193, "GET", "/healthz", False),
    ("both_exact", 48, 8192, "GET", "/healthz", False),
    ("count_only_over", 49, 8192, "GET", "/healthz", False),
    ("bytes_only_over", 48, 8193, "GET", "/healthz", False),
    ("duplicate_header_sum", 3, 8193, "GET", "/healthz", False),
    ("utf8_value_exact", 2, 8192, "GET", "/healthz", True),
    ("utf8_value_over", 2, 8193, "GET", "/healthz", True),
    ("post_before_handler", 2, 8193, "POST", "/fixture-write", False),
    ("unknown_route_before_handler", 49, None, "GET", "/absent", False),
]


def run_boundaries(app_path, manifest_path):
    namespace, hashes = selected_namespace(app_path, manifest_path)
    received = []

    async def inner(scope, receive, send):
        received.append(
            {
                "count": len(scope["headers"]),
                "bytes": sum(len(k) + len(v) + 4 for k, v in scope["headers"]),
            }
        )
        await PlainTextResponse(
            "fixture only", status_code=200 if scope["path"] != "/absent" else 404
        )(scope, receive, send)

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            namespace["HeaderLimits"](inner),
            lifespan="off",
            http="h11",
            log_level="error",
            timeout_keep_alive=1,
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    started = time.monotonic()
    while not server.started:
        if not thread.is_alive() or time.monotonic() - started > 6:
            raise RuntimeError("local fixture did not start")
        time.sleep(0.01)
    results = []
    try:
        for name, count, size, method, path, utf8 in CASES:
            headers = [(b"host", f"127.0.0.1:{port}".encode())] + [(b"x", b"a")] * (count - 2)
            remaining = (
                (size - sum(len(k) + len(v) + 4 for k, v in headers) - 9) if size is not None else 1
            )
            assert remaining >= 0
            value = (
                (b"\xc3\xa9" * (remaining // 2) + b"x" * (remaining % 2))
                if utf8
                else b"x" * remaining
            )
            headers.append((b"x-pad", value))
            computed = sum(len(k) + len(v) + 4 for k, v in headers)
            assert len(headers) == count and (size is None or computed == size)
            before = len(received)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
                for key, item in headers:
                    connection.putheader(key, item)
                connection.endheaders()
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                status = response.status
            finally:
                connection.close()
            expected = 431 if count > 48 or computed > 8192 else 200
            passed = status == expected and len(received) - before == (0 if expected == 431 else 1)
            if expected == 431:
                passed = (
                    passed
                    and f"{count} headers / {computed} bytes" in body
                    and "max 48 / 8192" in body
                )
            else:
                passed = passed and received[-1] == {"count": count, "bytes": computed}
            results.append(
                {
                    "case": name,
                    "count": count,
                    "bytes": computed,
                    "method": method,
                    "path": path,
                    "expected_status": expected,
                    "actual_status": status,
                    "inner_handler_calls": len(received) - before,
                    "passed": passed,
                }
            )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()
    return {
        "cases": len(results),
        "passed": sum(x["passed"] for x in results),
        "native_local_HTTP_requests": len(results),
        "selected_definition_sha256": hashes,
        "source_sha256": hashlib.sha256(app_path.read_bytes()).hexdigest(),
        "results": results,
        "scope": "Unchanged selected class/text/constant definitions with actual Starlette response and Uvicorn/h11 TCP HTTP. Minimal inner app fixture only; full official app, filesystem, rate/ref accounting and production edge are not exercised.",
    }


def declaration_checks(manifest_path, live_path):
    source = manifest_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    namespace = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("MAX_HEADERS", "MAX_HEADER_BYTES")
        ):
            exec(compile(segment(source, node), str(manifest_path), "exec"), namespace)
        elif isinstance(node, ast.FunctionDef) and node.name == "_plain":
            exec(compile(segment(source, node), str(manifest_path), "exec"), namespace)
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "openapi_document"
    )
    first = next(
        i
        for i, n in enumerate(function.body)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "header_block"
    )
    suffix = function.body[first:]
    assert isinstance(suffix[-1], ast.Return)
    suffix_source = "\n".join(segment(source, n).rstrip() for n in suffix[:-1])
    # Dedent just the function indentation; statement bodies otherwise stay byte-identical.
    import textwrap

    suffix_source = textwrap.dedent(suffix_source) + "\n"
    live = json.loads(live_path.read_bytes())
    methods = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}

    def operations(doc):
        return [o for item in doc["paths"].values() for m, o in item.items() if m in methods]

    def apply(doc):
        scope = dict(namespace, document=doc)
        exec(compile(suffix_source, str(manifest_path), "exec"), scope)
        return doc

    transformed = apply(copy.deepcopy(live))
    original_operations, transformed_operations = operations(live), operations(transformed)
    tests = []
    tests.append(
        {
            "check": "all captured live operations gain declared431",
            "passed": all("431" in o["responses"] for o in transformed_operations),
        }
    )
    tests.append(
        {
            "check": "description caps agree with enforced bindings",
            "passed": all(
                "48 headers / 8192" in o["responses"]["431"]["description"]
                for o in transformed_operations
            ),
        }
    )
    tests.append(
        {
            "check": "declared431 media is text/plain",
            "passed": all(
                set(o["responses"]["431"]["content"]) == {"text/plain"}
                for o in transformed_operations
            ),
        }
    )
    restored = copy.deepcopy(transformed)
    for operation in operations(restored):
        operation["responses"].pop("431", None)
    tests.append(
        {"check": "existing captured data unchanged besides431", "passed": restored == live}
    )
    control = copy.deepcopy(live)
    operations(control)[0]["responses"]["431"] = {"description": "existing explicit response"}
    changed = apply(control)
    tests.append(
        {
            "check": "setdefault preserves an existing explicit431",
            "passed": operations(changed)[0]["responses"]["431"]
            == {"description": "existing explicit response"},
        }
    )
    again = apply(copy.deepcopy(transformed))
    tests.append({"check": "declaration suffix is idempotent", "passed": again == transformed})
    return {
        "live_operation_count": len(original_operations),
        "live_missing431": sum("431" not in o.get("responses", {}) for o in original_operations),
        "source_suffix_applied_to_captured_live_missing431": sum(
            "431" not in o.get("responses", {}) for o in transformed_operations
        ),
        "control_checks": len(tests),
        "passed": sum(t["passed"] for t in tests),
        "tests": tests,
        "source_suffix_sha256": hashlib.sha256(suffix_source.encode()).hexdigest(),
        "scope": "Exact candidate declaration suffix and _plain helper on captured current live JSON copy; NOT full candidate OpenAPI generator import or server response.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    boundaries = {
        name: run_boundaries(
            args.source_root / name / "src/app.py", args.source_root / name / "src/manifest.py"
        )
        for name in ("main", "candidate")
    }
    declaration = declaration_checks(
        args.source_root / "candidate/src/manifest.py", args.source_root / "live-openapi.json"
    )
    args.output.joinpath("boundary-results.json").write_text(
        json.dumps(boundaries, indent=2) + "\n", encoding="utf-8"
    )
    args.output.joinpath("declaration-results.json").write_text(
        json.dumps(declaration, indent=2) + "\n", encoding="utf-8"
    )
    passed = (
        all(r["passed"] == r["cases"] for r in boundaries.values())
        and declaration["passed"] == declaration["control_checks"]
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "boundaries": {k: f"{v['passed']}/{v['cases']}" for k, v in boundaries.items()},
                "declaration_controls": f"{declaration['passed']}/{declaration['control_checks']}",
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
