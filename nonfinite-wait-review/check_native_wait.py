"""Whole unchanged MCP packages, real SDK stdio and native urllib/loopback HTTP.

This fixture responds immediately: it tests request construction and response
propagation, not real long-poll timing or the Linux service/storage.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters


def cases():
    rows = []
    for seconds in [
        "nan",
        "NaN",
        "+nan",
        "-nan",
        " nan ",
        "inf",
        "+inf",
        "Infinity",
        "-inf",
        "-Infinity",
        "0",
        "-0",
        "0.001",
        "9.5",
        "10",
        "60",
        "300",
        "1e300",
        "-1e300",
        "-1",
        "1e-300",
        0,
        1,
        2.5,
    ]:
        rows.append({"seconds": seconds, "status": 200, "valid": True})
    for seconds in (None, "not-a-number", ""):
        rows.append({"seconds": seconds, "status": 200, "valid": False})
    for status in (400, 403, 422, 429):
        for seconds in ("nan", 1):
            rows.append({"seconds": seconds, "status": status, "valid": True})
    rows.append({"omitted": True, "status": 200, "valid": True})
    return rows


def service_reader(snapshot):
    path = snapshot / "src/app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seconds")
    namespace = {"MAX_WAIT": 10.0}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_seconds"]


async def run_version(label, snapshot):
    state = {"requests": [], "status": 200}
    seconds_reader = service_reader(snapshot)

    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            raw_wait = query.get("wait", [None])[0]
            hold = seconds_reader(raw_wait)
            assert math.isfinite(hold) and 0 <= hold <= 10
            state["requests"].append(
                {
                    "method": "GET",
                    "path": parsed.path,
                    "query": query,
                    "fixture_effective_wait": hold,
                }
            )
            status = state["status"]
            answer = (
                f"local immediate fixture; effective_wait={hold:g}; messages=0\n"
                if status == 200
                else f"{status} local fixture refusal; preserve this body; do not retry\n"
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(answer)))
            if status == 429:
                self.send_header("Retry-After", "1")
            self.end_headers()
            self.wfile.write(answer)

        def do_POST(self):
            raise AssertionError("Read-only test must never POST")

        def log_message(self, *_):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"TECHNOCORE_SIGNING_KEY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    }
    env.update(
        PYTHONPATH=str((snapshot / "mcp/src").resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        TECHNOCORE_SIGNING_KEY="",
        TECHNOCORE_URL=f"http://127.0.0.1:{origin.server_port}",
        NO_PROXY="127.0.0.1,localhost",
    )
    env["REVIEW_EXPECTED_MODULES"] = json.dumps(
        {
            name: hashlib.sha256(
                (snapshot / "mcp/src/technocore_mcp" / name).read_bytes()
            ).hexdigest()
            for name in ("__init__.py", "server.py", "fetch.py", "signing.py")
        }
    )
    env["REVIEW_EXPECTED_DIRECTORY"] = str((snapshot / "mcp/src/technocore_mcp").resolve())
    bootstrap = """import os,json,hashlib
from pathlib import Path
import technocore_mcp.server as module
directory = Path(module.__file__).resolve().parent
assert directory == Path(os.environ['REVIEW_EXPECTED_DIRECTORY'])
for name, expected in json.loads(os.environ['REVIEW_EXPECTED_MODULES']).items():
    assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected
module.main()
"""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", "-c", bootstrap],
        env=env,
        cwd=str(snapshot / "mcp"),
    )
    rows = []
    try:
        async with asyncio.timeout(90), Client(parameters, read_timeout_seconds=8) as client:
            tools = await client.list_tools()
            assert "wait_for_message" in {tool.name for tool in tools.tools}
            identity = await client.call_tool("whoami", {})
            identity_text = "\n".join(
                block.text for block in identity.content if block.type == "text"
            )
            assert (
                "did:key:" not in identity_text
                and "signing identity: none" in identity_text.lower()
            ), identity_text
            for index, case in enumerate(cases()):
                state["requests"].clear()
                state["status"] = case["status"]
                arguments = {"room": f"wait-case-{index:02}", "since": 1}
                if not case.get("omitted"):
                    arguments["seconds"] = case["seconds"]
                start = time.monotonic()
                async with asyncio.timeout(8):
                    response = await client.call_tool("wait_for_message", arguments)
                elapsed = time.monotonic() - start
                body = "\n".join(block.text for block in response.content if block.type == "text")
                requests = list(state["requests"])
                is_nan = (
                    case["valid"] and not case.get("omitted") and math.isnan(float(case["seconds"]))
                )
                known_main_failure = label == "main" and is_nan
                expected_count = int(case["valid"] and not known_main_failure)
                expected_error = not case["valid"] or case["status"] >= 400
                expected_seconds = (
                    10.0
                    if case.get("omitted")
                    else float(case["seconds"])
                    if case["valid"]
                    else None
                )
                forwarded = None
                if requests:
                    assert len(requests) == 1
                    query = requests[0]["query"]
                    assert query["since"] == ["1"]
                    forwarded = float(query["wait"][0])
                    assert (
                        math.isnan(forwarded) and math.isnan(expected_seconds)
                    ) or forwarded == expected_seconds
                meaningful_reply = (
                    (
                        "local immediate fixture" in body
                        if case["status"] == 200
                        else f"{case['status']} local fixture refusal" in body
                    )
                    if case["valid"]
                    else response.is_error
                )
                policy_match = (
                    response.is_error == expected_error
                    and len(requests) == int(case["valid"])
                    and bool(meaningful_reply)
                )
                predicted_observation_match = len(requests) == expected_count and (
                    response.is_error if known_main_failure else policy_match
                )
                rows.append(
                    {
                        "case": index,
                        "arguments": arguments,
                        "fixture_status": case["status"],
                        "input_valid": case["valid"],
                        "is_nan": is_nan,
                        "sdk_is_error": response.is_error,
                        "reply": body,
                        "origin_requests": requests,
                        "elapsed_seconds_observed_not_deadline_test": elapsed,
                        "matches_desired_contract": bool(policy_match),
                        "matches_expected_baseline_or_candidate_observation": bool(
                            predicted_observation_match
                        ),
                    }
                )
    finally:
        origin.shutdown()
        origin.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
    return {
        "label": label,
        "tool_cases": len(rows),
        "desired_contract_matches": sum(row["matches_desired_contract"] for row in rows),
        "expected_observations_match": all(
            row["matches_expected_baseline_or_candidate_observation"] for row in rows
        ),
        "origin_GETs": sum(len(row["origin_requests"]) for row in rows),
        "rows": rows,
        "whoami_unsigned_confirmed": True,
        "executed_whole_package_path_and_hashes_verified_in_child": True,
        "child_and_listener_closed": True,
    }


async def main(source, report):
    provenance = json.loads((report.parent / "source-provenance.json").read_text())
    for row in provenance["files"]:
        assert (
            hashlib.sha256((source / row["version"] / row["path"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    versions = [await run_version(label, source / label) for label in ("main", "candidate")]
    for row in provenance["files"]:
        assert (
            hashlib.sha256((source / row["version"] / row["path"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    document = {
        "python": sys.version,
        "platform": sys.platform,
        "mcp": importlib.metadata.version("mcp"),
        "pydantic": importlib.metadata.version("pydantic"),
        "versions": versions,
        "tool_case_calls": sum(v["tool_cases"] for v in versions),
        "additional_whoami_calls": 2,
        "origin_GETs": sum(v["origin_GETs"] for v in versions),
        "origin_POSTs": 0,
        "all_source_blobs_unchanged": True,
        "protected_user_key_loaded": False,
        "scope": "Whole unmodified MCP package with actual SDK stdio validation and native urllib to local immediate HTTP fixture. Unchanged AST-selected service _seconds with fixture ceiling10, not whole app/store. No actual long-poll timing, timeout ceilings, Linux/full repository suite, Worker or production evidence.",
    }
    report.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "tool_cases": document["tool_case_calls"],
                "origin_GETs": document["origin_GETs"],
                "versions": [
                    {
                        k: v[k]
                        for k in (
                            "label",
                            "desired_contract_matches",
                            "tool_cases",
                            "expected_observations_match",
                            "origin_GETs",
                        )
                    }
                    for v in versions
                ],
            }
        )
    )
    assert all(v["expected_observations_match"] for v in versions)
    assert versions[1]["desired_contract_matches"] == versions[1]["tool_cases"]


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
