"""Exact advice arithmetic plus selected unchanged limiter code over native real-clock HTTP.

Usage: python check_refill_pacing.py SOURCE_ROOT PROVENANCE_JSON REPORT_JSON
Does not import full Linux-dependent limit/store/app modules or fake fcntl/store.
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
import math
import re
import sys
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

FUNCTIONS = {"client_ip", "take", "refill_rate", "limited", "budget_note"}
STATE = {
    "MAX_BUCKETS",
    "MAX_IDENTITIES",
    "_buckets",
    "_buckets_lock",
    "_requests",
    "_identities",
    "_proxy_evidence",
    "PROXY_IP_HEADERS",
    "FREE_PATHS",
}
RATES = (11, 30, 45, 60, 63, 70)


def load_selected(snapshot):
    path = snapshot / "src/limit.py"
    spec = importlib.util.spec_from_file_location(
        "pacing_config_" + snapshot.name, snapshot / "src/config.py"
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            selected.append(node)
            found.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in STATE for t in targets):
                selected.append(node)
    assert found == FUNCTIONS
    namespace = {
        "OrderedDict": OrderedDict,
        "threading": threading,
        "time": time,
        "math": math,
        "Request": Request,
        "Response": Response,
        "config": config,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def interval(phrase):
    period = re.fullmatch(r"one token every (\d+)s", phrase)
    if period:
        return Fraction(int(period.group(1)))
    rate = re.fullmatch(r"(\d+\.\d) tokens/s", phrase)
    assert rate is not None, phrase
    return 1 / Fraction(rate.group(1))


def text_reply(body, status):
    return PlainTextResponse(body, status_code=status)


def exact_advice(namespace):
    rows = []
    for rate in range(1, 1201):
        phrase = namespace["refill_rate"](rate)
        stated_interval = interval(phrase)
        real_interval = Fraction(60, rate)
        refusal = namespace["limited"]("read", rate, 1.1, text=text_reply, max_wait=10)
        footer = namespace["budget_note"]("write", 0, rate)
        consistent = phrase in refusal.body.decode() and phrase in footer
        rows.append(
            {
                "per_min": rate,
                "advice": phrase,
                "stated_interval_exact": str(stated_interval),
                "actual_interval_exact": str(real_interval),
                "no_early_pacing": stated_interval >= real_interval,
                "body_footer_consistent": consistent,
            }
        )
    return {
        "budgets": len(rows),
        "safe_advice": sum(r["no_early_pacing"] for r in rows),
        "early_advice": sum(not r["no_early_pacing"] for r in rows),
        "low_rate_unsafe": sum(not r["no_early_pacing"] for r in rows if r["per_min"] < 60),
        "high_rate_unsafe": sum(not r["no_early_pacing"] for r in rows if r["per_min"] >= 60),
        "body_footer_consistent": all(r["body_footer_consistent"] for r in rows),
        "rows": rows,
    }


def native_pacing(namespace):
    state = {"case": None}

    async def gate(request):
        case = state["case"]
        assert int(request.query_params["rate"]) == case["per_min"]
        stamp = time.monotonic()
        left, wait = namespace["take"](request, "read", case["per_min"], burst=1)
        case["server_observations"].append({"monotonic": stamp, "wait": wait, "left": left})
        if wait:
            return namespace["limited"]("read", case["per_min"], wait, text=text_reply, max_wait=10)
        return PlainTextResponse("fixture granted; no real room/store\n")

    app = Starlette(routes=[Route("/pace", gate)])
    # Real listening socket stays owned until uvicorn has taken it; no free-port race.
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="off")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    until = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < until:
        time.sleep(0.02)
    assert server.started
    rows = []

    def get(rate):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            connection.request("GET", "/pace?rate=" + str(rate))
            response = connection.getresponse()
            raw = response.read(65537)
            assert len(raw) <= 65536
            return {
                "status": response.status,
                "text": raw.decode(),
                "retry_after": response.getheader("Retry-After"),
            }
        finally:
            connection.close()

    try:
        for rate in RATES:
            namespace["_buckets"].clear()
            case = {"per_min": rate, "server_observations": []}
            state["case"] = case
            first, empty = get(rate), get(rate)
            assert first["status"] == 200 and empty["status"] == 429
            phrase = namespace["refill_rate"](rate)
            assert phrase in empty["text"]
            delay = float(interval(phrase))
            # Sleep is the advertised refill cadence, NOT Retry-After. No clock mock.
            time.sleep(delay)
            paced = get(rate)
            stamps = case["server_observations"]
            assert len(stamps) == 3
            elapsed = stamps[2]["monotonic"] - stamps[0]["monotonic"]
            theoretical = float(Fraction(60, rate))
            early = elapsed < theoretical - 0.001
            clearly_late = elapsed > theoretical + 0.001
            expected = 429 if early else (200 if clearly_late else None)
            matched = expected is None or paced["status"] == expected
            if interval(phrase) >= Fraction(60, rate):
                matched = matched and paced["status"] == 200
            rows.append(
                case
                | {
                    "advice": phrase,
                    "slept_seconds": delay,
                    "elapsed_since_initial_grant": elapsed,
                    "ideal_refill_seconds": theoretical,
                    "responses": [first, empty, paced],
                    "timing_resolution_margin_seconds": 0.001,
                    "arrival_was_early": early,
                    "actual_early_refusal": early and paced["status"] == 429,
                    "timing_boundary_inconclusive": expected is None,
                    "bucket_matches_observed_elapsed": matched,
                }
            )
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
    assert not thread.is_alive()
    return {
        "scenarios": len(rows),
        "HTTP_requests": len(rows) * 3,
        "bucket_elapsed_checks_passed": sum(r["bucket_matches_observed_elapsed"] for r in rows),
        "early_refusals_observed": sum(r["actual_early_refusal"] for r in rows),
        "all_native_resources_stopped": True,
        "rows": rows,
    }


def main():
    source, provenance_path, output = map(Path, sys.argv[1:])
    assert not output.exists()
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    def sources_unchanged():
        for p in provenance["files"]:
            assert (
                hashlib.sha256((source / p["version"] / p["path"]).read_bytes()).hexdigest()
                == p["sha256"]
            )

    sources_unchanged()
    versions = []
    for label in ("main", "candidate", "proposed"):
        namespace = load_selected(source / label)
        versions.append(
            {
                "version": label,
                "arithmetic": exact_advice(namespace),
                "native": native_pacing(namespace),
                "executed_limit_source_sha256": hashlib.sha256(
                    (source / label / "src/limit.py").read_bytes()
                ).hexdigest(),
            }
        )
    sources_unchanged()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "main": provenance["main"],
        "head": provenance["head"],
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": versions,
        "selected_unmodified_functions": sorted(FUNCTIONS),
        "clock_or_sleep_mocked": False,
        "whole_config_module_loaded": True,
        "full_limit_store_app_imported": False,
        "fixture_burst": 1,
        "fixture_only_one_client_no_competing_requests": True,
        "full_Linux_or_upstream_CI": False,
        "live_service_requests": 0,
        "protected_key_or_wallet_access": False,
        "runtime": {
            "python": sys.version.split()[0],
            **{p: importlib.metadata.version(p) for p in ("starlette", "uvicorn")},
        },
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "version": v["version"],
                    "safe_of_1200": v["arithmetic"]["safe_advice"],
                    "unsafe_low": v["arithmetic"]["low_rate_unsafe"],
                    "unsafe_high": v["arithmetic"]["high_rate_unsafe"],
                    "native_early_refusals": v["native"]["early_refusals_observed"],
                    "native_HTTP": v["native"]["HTTP_requests"],
                    "native_elapsed_checks": v["native"]["bucket_elapsed_checks_passed"],
                }
                for v in versions
            ]
        )
    )


if __name__ == "__main__":
    main()
