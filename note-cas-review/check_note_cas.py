"""Whole pinned MCP packages, real SDK stdio and urllib, disposable HTTP note fixture.

Run: python check_note_cas.py SNAPSHOT_ROOT REPORT_JSON
The fixture implements explicit framing/CAS semantics; it is not the Linux server.
No protected identity, live service or chain wallet is used in these tests.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib.metadata
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters


def text(response):
    return "\n".join(block.text for block in response.content if block.type == "text")


async def run_version(label, snapshot):
    tree = ast.parse((snapshot / "src/app.py").read_text(encoding="utf-8"))
    banner = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "BANNER" for t in node.targets)
    )
    state = {
        "value": "",
        "status": 200,
        "requests": [],
        "footer": False,
        "newline": False,
    }

    class Origin(BaseHTTPRequestHandler):
        def answer(self, status, body):
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            if status == 429:
                self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            state["requests"].append({"method": "GET", "path": self.path})
            if state["status"] != 200:
                self.answer(
                    state["status"], f"{state['status']} local note fixture refusal"
                )
            elif self.path.startswith("/r/"):
                self.answer(200, banner + "\n\n[1] fixture room\nnext: 1\n")
            else:
                body = banner + "\n\n" + state["value"]
                if state["footer"]:
                    body += "\n# budget: 1 of 8 reads left"
                if state["newline"]:
                    body += "\n"
                self.answer(200, body)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(
                {"method": "POST", "path": self.path, "payload": payload}
            )
            if payload.get("if") != state["value"]:
                self.answer(409, "409 local fixture compare-and-set conflict")
            else:
                state["value"] = payload["value"]
                self.answer(200, "ok local fixture note updated")

        def log_message(self, *_):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        not in {"TECHNOCORE_SIGNING_KEY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    }
    env.update(
        PYTHONPATH=str((snapshot / "mcp/src").resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        TECHNOCORE_SIGNING_KEY="",
        TECHNOCORE_URL=f"http://127.0.0.1:{origin.server_port}",
        NO_PROXY="127.0.0.1,localhost",
        REVIEW_EXPECTED_DIRECTORY=str((snapshot / "mcp/src/technocore_mcp").resolve()),
        REVIEW_EXPECTED_MODULES=json.dumps(
            {
                name: hashlib.sha256(
                    (snapshot / "mcp/src/technocore_mcp" / name).read_bytes()
                ).hexdigest()
                for name in ("__init__.py", "server.py", "fetch.py", "signing.py")
            }
        ),
    )
    bootstrap = """import os,json,hashlib
from pathlib import Path
import technocore_mcp.server as module
directory=Path(module.__file__).resolve().parent
assert directory == Path(os.environ['REVIEW_EXPECTED_DIRECTORY'])
for name, expected in json.loads(os.environ['REVIEW_EXPECTED_MODULES']).items():
    assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected
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
        async with (
            asyncio.timeout(100),
            Client(parameters, read_timeout_seconds=10) as client,
        ):
            who = text(await client.call_tool("whoami", {}))
            assert "signing identity: none" in who.lower() and "did:key:" not in who
            values = [
                "v1",
                "한국어 메모",
                "emoji🙂",
                "# budget: personal note",
                "# budget:",
                "!! UNTRUSTED CONTENT caller text",
                "a?b&c=%/#",
                "한" * 8192,
            ]
            for index, value in enumerate(values):
                for footer in (False, True):
                    for newline in (False, True):
                        state.update(
                            value=value,
                            footer=footer,
                            newline=newline,
                            status=200,
                            requests=[],
                        )
                        key = f"case-{index}-{int(footer)}-{int(newline)}"
                        current = await client.call_tool(
                            "read_note", {"namespace": "local-cas", "key": key}
                        )
                        observed = text(current)
                        updated = await client.call_tool(
                            "write_note",
                            {
                                "namespace": "local-cas",
                                "key": key,
                                "value": "updated",
                                "if_matches": observed,
                            },
                        )
                        success_value = state["value"]
                        state["value"] = "concurrent-writer"
                        stale = await client.call_tool(
                            "write_note",
                            {
                                "namespace": "local-cas",
                                "key": key,
                                "value": "must-not-win",
                                "if_matches": observed,
                            },
                        )
                        requests = list(state["requests"])
                        assert [r["method"] for r in requests] == [
                            "GET",
                            "POST",
                            "POST",
                        ]
                        assert all(
                            r["path"] == f"/kv/local-cas/{key}" for r in requests
                        )
                        assert requests[1]["payload"] == {
                            "value": "updated",
                            "if": observed,
                        }
                        assert requests[2]["payload"] == {
                            "value": "must-not-win",
                            "if": observed,
                        }
                        match = (
                            not current.is_error
                            and observed == value
                            and not updated.is_error
                            and success_value == "updated"
                            and stale.is_error
                            and "409" in text(stale)
                            and state["value"] == "concurrent-writer"
                        )
                        rows.append(
                            {
                                "case": key,
                                "value_characters": len(value),
                                "value_sha256": hashlib.sha256(
                                    value.encode()
                                ).hexdigest(),
                                "footer": footer,
                                "trailing_newline": newline,
                                "matches_contract": bool(match),
                                "exact_read": observed == value,
                                "successful_cas": not updated.is_error,
                                "stale_guard_refused": stale.is_error,
                                "concurrent_value_preserved": state["value"]
                                == "concurrent-writer",
                                "origin_GETs": 1,
                                "origin_POSTs": 2,
                            }
                        )
            for status in (400, 404, 409, 422, 429):
                state.update(status=status, requests=[])
                response = await client.call_tool(
                    "read_note", {"namespace": "local-cas", "key": "error"}
                )
                assert len(state["requests"]) == 1
                rows.append(
                    {
                        "case": f"read-error-{status}",
                        "matches_contract": bool(
                            response.is_error
                            and f"{status} local note fixture refusal" in text(response)
                        ),
                        "origin_GETs": 1,
                        "origin_POSTs": 0,
                    }
                )
            state.update(status=200, requests=[])
            response = await client.call_tool(
                "read_room", {"room": "fixture", "limit": 1}
            )
            rows.append(
                {
                    "case": "room-banner-preserved",
                    "matches_contract": not response.is_error
                    and text(response).startswith(banner),
                    "origin_GETs": len(state["requests"]),
                    "origin_POSTs": 0,
                }
            )
    finally:
        origin.shutdown()
        origin.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
    return {
        "label": label,
        "cases": len(rows),
        "matches": sum(r["matches_contract"] for r in rows),
        "rows": rows,
        "origin_GETs": sum(r["origin_GETs"] for r in rows),
        "origin_POSTs": sum(r["origin_POSTs"] for r in rows),
        "unsigned_whoami_confirmed": True,
        "whole_executed_module_paths_and_hashes_verified": True,
        "listener_and_child_closed": True,
    }


async def main(source, report):
    provenance = json.loads(
        (report.parent / "source-provenance.json").read_text(encoding="utf-8")
    )

    def check_sources():
        for row in provenance["files"]:
            assert (
                hashlib.sha256(
                    (source / row["label"] / row["path"]).read_bytes()
                ).hexdigest()
                == row["sha256"]
            )

    check_sources()
    versions = [
        await run_version(label, source / label)
        for label in ("base", "main", "candidate")
    ]
    check_sources()
    assert all(row["matches_contract"] for row in versions[-1]["rows"])
    document = {
        "python": sys.version,
        "platform": sys.platform,
        "mcp": importlib.metadata.version("mcp"),
        "versions": versions,
        "origin_GETs": sum(v["origin_GETs"] for v in versions),
        "origin_POSTs": sum(v["origin_POSTs"] for v in versions),
        "live_test_writes": 0,
        "full_linux_server_or_upstream_ci": False,
        "source_hashes_unchanged": True,
    }
    report.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "versions": [
                    {"label": v["label"], "matches": v["matches"], "cases": v["cases"]}
                    for v in versions
                ],
                "GETs": document["origin_GETs"],
                "POSTs": document["origin_POSTs"],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
