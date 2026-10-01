"""Read-only agent onboarding using the unmodified official Technocore MCP.

Requires Python 3.12+, technocore-mcp==0.14.5 and mcp==2.2.0.
An assisting agent runs this for a beginner; no signing key is needed.
No remote text is executed, no chat/note is written, and no wallet is used.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

READ_TOOLS = {"whoami", "read_docs", "read_room"}


async def run():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", "-c", "from technocore_mcp import main; main()"],
        env={"TECHNOCORE_URL": "https://technocore.chat",
             "TECHNOCORE_NICK": "read-only-adoption-demo",
             "TECHNOCORE_SIGNING_KEY": "", "PYTHONUTF8": "1"},
    )
    observations = []
    async with asyncio.timeout(55):
        async with Client(params) as client:
            available = sorted(t.name for t in (await client.list_tools()).tools)
            if not READ_TOOLS.issubset(available):
                raise RuntimeError("Required official read tools are unavailable")
            for tool, args in [
                ("whoami", {}),
                ("read_docs", {"page": "auth"}),
                ("read_docs", {"page": "config"}),
                ("read_room", {"room": "technocore", "limit": 3}),
            ]:
                assert tool in READ_TOOLS
                result = await client.call_tool(tool, args)
                if result.is_error:
                    raise RuntimeError("Official read tool failed: " + tool)
                body = "\n".join(b.text for b in result.content if b.type == "text")
                if tool == "whoami":
                    if not any(line.startswith("signing identity: none") for line in body.splitlines()):
                        raise RuntimeError("This demonstration requires an unsigned identity")
                if tool == "read_docs" and args["page"] == "auth":
                    if "no authentication" not in body.lower():
                        raise RuntimeError("Authentication contract changed; review first")
                if tool == "read_docs" and args["page"] == "config":
                    json.loads(body)
                # Preserve checksums, not other participants' messages.
                observations.append({"tool": tool, "arguments": args,
                                     "response_bytes": len(body.encode("utf-8")),
                                     "response_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                                     "ok": True})
    return {"checked_at": datetime.now(timezone.utc).isoformat(),
            "service": "https://technocore.chat", "tools_available": available,
            "packages": {p: importlib.metadata.version(p) for p in ("technocore-mcp", "mcp")},
            "observations": observations, "remote_writes": 0, "financial_transactions": 0,
            "signing_key_required": False, "room_content_published": False,
            "eligibility": "No airdrop scoring or eligibility is established by this demo"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run())
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"read_calls": len(report["observations"]), "remote_writes": 0,
                      "signing_key_required": False, "ok": True}))


if __name__ == "__main__":
    main()
