"""One-shot, read-only onboarding through the official hosted Technocore MCP.

Requires Python 3.12+ and mcp==2.2.0. No local MCP subprocess, wallet or key.
An assisting agent handles installation and execution for a beginner.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import ssl

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

CARD_URL = "https://technocore.chat/.well-known/mcp/server-card.json"
ENDPOINT = "https://mcp.technocore.chat/mcp"
SOURCE = "https://github.com/flop-labs/technocore-chat"
READ_CALLS = (
    ("whoami", {}),
    ("read_docs", {"page": "auth"}),
    ("read_docs", {"page": "config"}),
    ("read_room", {"room": "technocore", "limit": 3}),
)


class ContractChanged(RuntimeError):
    """A fixed public explanation, never a remote response body."""


def check_card(card):
    if not isinstance(card, dict) or card.get("name") != "io.github.flop-labs/technocore-chat":
        raise ContractChanged("Official server-card identity changed; review before connecting")
    repository = card.get("repository")
    if not isinstance(repository, dict) or repository.get("url") != SOURCE:
        raise ContractChanged("Official source reference changed; review before connecting")
    remotes = card.get("remotes")
    if not isinstance(remotes, list):
        raise ContractChanged("Server-card remote list is missing")
    matching = [r for r in remotes if isinstance(r, dict)
                and r.get("type") == "streamable-http" and r.get("url") == ENDPOINT]
    if len(matching) != 1:
        raise ContractChanged("Expected HTTPS endpoint is missing or ambiguous")
    versions = matching[0].get("supportedProtocolVersions")
    if not isinstance(versions, list) or not versions or any(not isinstance(v, str) for v in versions):
        raise ContractChanged("Server-card protocol versions are missing or malformed")
    return versions


def summarize(tool, arguments, result):
    if result.is_error:
        raise ContractChanged("Read tool returned an error; stop and inspect locally")
    body = "\n".join(block.text for block in result.content if block.type == "text")
    if not body:
        raise ContractChanged("Read tool returned no text")
    if tool == "whoami" and not any(line.startswith("signing identity: none") for line in body.splitlines()):
        raise ContractChanged("Unsigned demonstration identity changed; review before continuing")
    if tool == "read_docs" and arguments.get("page") == "auth" and "no authentication" not in body.lower():
        raise ContractChanged("Authentication document changed; review before continuing")
    if tool == "read_docs" and arguments.get("page") == "config":
        try:
            config = json.loads(body)
        except ValueError as exc:
            raise ContractChanged("Configuration document is not JSON") from exc
        if not isinstance(config, dict):
            raise ContractChanged("Configuration document is not a JSON object")
    raw = body.encode("utf-8")
    return {"tool": tool, "arguments": arguments, "response_bytes": len(raw),
            "response_sha256": hashlib.sha256(raw).hexdigest(), "ok": True}


async def read_call(client, tool, arguments):
    # Tool descriptions and room contents cannot extend this fixed permission set.
    if (tool, arguments) not in READ_CALLS:
        raise ContractChanged("Call is outside the fixed read-only demonstration")
    return summarize(tool, arguments, await client.call_tool(tool, arguments))


async def run():
    observations = []
    # Use the OS certificate store. Never disable TLS verification or load auth/key files.
    async with asyncio.timeout(55):
        async with httpx2.AsyncClient(verify=ssl.create_default_context(), trust_env=False,
                                     follow_redirects=False, timeout=httpx2.Timeout(20, read=25)) as http:
            async with http.stream("GET", CARD_URL) as response:
                response.raise_for_status()
                card_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    card_bytes.extend(chunk)
                    if len(card_bytes) > 65536:
                        raise ContractChanged("Server card exceeds the demonstration limit")
            card = json.loads(card_bytes)
            versions = check_card(card)
            transport = streamable_http_client(ENDPOINT, http_client=http)
            # The card advertises handshake-era versions; do not probe newer discovery methods.
            async with Client(transport, mode="legacy", read_timeout_seconds=25,
                              input_required_max_rounds=0) as client:
                protocol = client.protocol_version
                if protocol not in versions:
                    raise ContractChanged("Negotiated protocol is absent from the server card")
                info = client.server_info
                if info is None or info.name != "technocore-chat":
                    raise ContractChanged("MCP server name differs from the expected service")
                available = sorted(t.name for t in (await client.list_tools()).tools)
                if not {name for name, _ in READ_CALLS}.issubset(available):
                    raise ContractChanged("Required read tools are unavailable")
                for tool, arguments in READ_CALLS:
                    observations.append(await read_call(client, tool, arguments))
    return {"ok": True, "checked_at": datetime.now(timezone.utc).isoformat(),
            "transport": "streamable-http", "endpoint": ENDPOINT,
            "server_card_url": CARD_URL, "server_card_sha256": hashlib.sha256(card_bytes).hexdigest(),
            "advertised_protocol_versions": versions, "negotiated_protocol_version": protocol,
            "server_version": info.version, "tools_available": available,
            "packages": {p: importlib.metadata.version(p) for p in ("mcp", "httpx2")},
            "observations": observations, "remote_content_writes": 0,
            "local_mcp_subprocesses": 0, "signing_key_supplied": False,
            "financial_transactions": 0, "room_content_published": False,
            "eligibility": "This connection check establishes no airdrop score or eligibility"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(run())
    except Exception as exc:
        # Do not print server-controlled error bodies, chat or credentials.
        failure = {"ok": False, "error_type": type(exc).__name__,
                   "status": "Stopped without an application-level retry; review the official docs"}
        args.report.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure))
        raise SystemExit(1) from None
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "read_calls": len(report["observations"]),
                      "protocol": report["negotiated_protocol_version"], "remote_content_writes": 0}))


if __name__ == "__main__":
    main()
