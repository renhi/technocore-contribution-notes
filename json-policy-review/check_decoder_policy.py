"""Synchronous decoder comparison. No networking, full app, ASGI or store emulation.

Select the exact post-upload decoding statements from read_json, leaving the
original decoder calls and error handling unchanged. Import PR926 strictjson whole.
The streaming/deadline layer is deliberately outside this executable fixture.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import orjson
from cases_json_policy import cases
from starlette.responses import PlainTextResponse, Response


def decode_function(source, version):
    path = source / version / "src/app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    read = next(
        n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "read_json"
    )
    start = next(
        i
        for i, n in enumerate(read.body)
        if isinstance(n, ast.Try)
        and any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "loads"
            for c in ast.walk(n)
        )
    )
    selected = read.body[start:]
    wrapper = ast.parse("def decode(raw):\n    pass\n").body[0]
    wrapper.body = selected
    module_body = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_reject_duplicate_names"
    ] + [wrapper]
    namespace = {
        "orjson": orjson,
        "json": json,
        "text": lambda body, status=200: PlainTextResponse(body, status_code=status),
    }
    helper_sha = None
    if version == "root-only":
        helper = source / version / "src/strictjson.py"
        spec = importlib.util.spec_from_file_location("review_strictjson", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        namespace["strictjson"] = module
        helper_sha = hashlib.sha256(helper.read_bytes()).hexdigest()
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=module_body, type_ignores=[])),
            str(path),
            "exec",
        ),
        namespace,
    )
    return namespace["decode"], {
        "app_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "strictjson_sha256": helper_sha,
        "selected_statement_count": len(selected),
        "selected_first_line": selected[0].lineno,
        "selected_last_line": selected[-1].end_lineno,
        "ast_statement_fingerprint": hashlib.sha256(
            ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False).encode()
        ).hexdigest(),
    }


def run(source, output):
    results, versions = [], {}
    for version in ("main", "root-only", "all-depth"):
        decode, metadata = decode_function(source, version)
        for case in cases():
            exception, probe_ok = None, True
            try:
                value = decode(case["body"])
                status = value.status_code if isinstance(value, Response) else 204
                if case["probe"] and not isinstance(value, Response):
                    probe_ok = value.get(case["probe"][0]) == case["probe"][1]
            except Exception as error:
                exception, status = type(error).__name__, None
            expected = case["expected"][version] if case["expected"] else None
            results.append(
                {
                    "version": version,
                    "name": case["name"],
                    "group": case["group"],
                    "request_sha256": hashlib.sha256(case["body"]).hexdigest(),
                    "decoder_outcome": status,
                    "expected_outcome": expected,
                    "matches_expected": status == expected and probe_ok
                    if expected is not None
                    else None,
                    "escaped_exception": exception,
                }
            )
        metadata["source_unchanged"] = (
            metadata["app_sha256"]
            == hashlib.sha256((source / version / "src/app.py").read_bytes()).hexdigest()
        )
        versions[version] = metadata
    checked = [r for r in results if r["matches_expected"] is not None]
    report = {
        "python": sys.version,
        "platform": sys.platform,
        "recursion_limit": sys.getrecursionlimit(),
        "orjson": orjson.__version__,
        "versions": versions,
        "cases_per_version": len(cases()),
        "decoder_executions": len(results),
        "explicit_policy_checks": len(checked),
        "matched_policy_checks": sum(r["matches_expected"] for r in checked),
        "rows": results,
        "actual_HTTP_requests": 0,
        "official_app_or_store_imported": False,
        "scope": "Unchanged selected post-upload decoder statements and duplicate hook; whole PR926 strictjson module. 204 denotes returned dict in this fixture, not an observed HTTP response. Streaming, body caps, deadlines, actual write gates, Linux and upstream CI untested.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "cases_per_version",
                    "decoder_executions",
                    "explicit_policy_checks",
                    "matched_policy_checks",
                )
            }
        )
    )
    print(json.dumps([r for r in results if r["expected_outcome"] is None]))
    assert all(r["matches_expected"] for r in checked)
    assert all(v["source_unchanged"] for v in versions.values())


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
