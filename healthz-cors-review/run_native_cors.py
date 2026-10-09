"""Run an actual Starlette CORS origin and native Node Worker probe on loopback."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import threading
import time
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    log = []

    async def health(request: Request):
        status = 503 if request.headers.get("X-Status") == "503" else 200
        return PlainTextResponse(
            "busy\n" if status == 503 else "ok\n",
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )

    async def reset(_request: Request):
        log.clear()
        return PlainTextResponse("reset")

    async def audit(_request: Request):
        return JSONResponse(log.copy())

    app = CORSMiddleware(
        Starlette(
            routes=[
                Route("/healthz", health),
                Route("/reset", reset, methods=["POST"]),
                Route("/audit", audit),
            ]
        ),
        allow_origins=["https://allowed-a.example", "https://allowed-b.example"],
        allow_methods=["GET", "HEAD"],
        allow_headers=["*"],
    )

    async def observed(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/healthz":
            headers = dict(scope["headers"])
            log.append(
                {
                    "method": scope["method"],
                    "query": scope["query_string"].decode("ascii"),
                    "origin": headers.get(b"origin", b"").decode("latin1"),
                    "probe": headers.get(b"x-probe", b"").decode("latin1"),
                }
            )
        await app(scope, receive, send)

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(observed, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Loopback fixture did not start")
            time.sleep(0.02)
        result = subprocess.run(
            [
                args.node,
                str(Path(__file__).with_name("check_cors_cache.mjs")),
                str(args.sources.resolve()),
                f"http://127.0.0.1:{port}",
                str(args.output.resolve()),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
            check=False,
        )
        print(result.stdout.strip())
        if result.returncode:
            print(result.stderr[-1600:])
            raise SystemExit(result.returncode)
        report = json.loads(args.output.read_text(encoding="utf-8"))
        report["python_fixture_source"] = "run_native_cors.py"
        report["local_origin_thread_shutdown_confirmed"] = False
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("Loopback origin did not stop")
    report["local_origin_thread_shutdown_confirmed"] = True
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
