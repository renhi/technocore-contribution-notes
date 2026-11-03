"""Exercise pinned main() argument handling without starting benchmark workers."""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import math
import sys
from pathlib import Path

root, kit = map(Path, sys.argv[1:])
p = json.loads((kit / "source-provenance.json").read_text())
for file in p["files"]:
    assert hashlib.sha256((root / file["label"] / file["path"]).read_bytes()).hexdigest() == file["sha256"]

cases = [
    ("blocking", "lobby", None), ("deferred", "spread", None),
    ("oppo,batched,none", "lobby,mixed,spread", None),
    ("every0,every1e-3,every-1,every+2", "mixed", None),
    ("blocking,,batched,", ",lobby,", None),
    ("blockng", "lobby", "unknown --arms name"),
    ("blocking,blockng", "lobby", "unknown --arms name"),
    ("blocking, batched", "lobby", "unknown --arms name"),
    ("Blocking", "lobby", "unknown --arms name"),
    ("blocking", "loby", "unknown --mixes name"),
    ("blocking", "lobby,loby", "unknown --mixes name"),
    ("blocking", "lobby, spread", "unknown --mixes name"),
    ("every", "spread", "invalid --arms interval"),
    ("everybad", "spread", "invalid --arms interval"),
    ("everynan", "spread", "invalid --arms interval"),
    ("every+inf", "spread", "invalid --arms interval"),
    ("every-Infinity", "spread", "invalid --arms interval"),
    ("every1e309", "spread", "invalid --arms interval"),
    ("every0,everyNaN", "spread", "invalid --arms interval"),
    ("every1.2.3", "spread", "invalid --arms interval"),
]
report = []
for label in ("base", "main", "candidate"):
    path = root / label / "bench/counters.py"
    tree = ast.parse(path.read_bytes())
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
        or isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in {"ARMS", "MIXES"} for t in node.targets
        )
    ]
    assert len(selected) == 3
    calls = []
    ns = dict(argparse=argparse, math=math, __doc__=ast.get_docstring(tree), run=lambda *a: calls.append(a))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), ns)
    rows = []
    for arms, mixes, error in cases:
        calls.clear()
        old = sys.argv
        sys.argv = ["counters.py", "--arms", arms, "--mixes", mixes]
        stderr, stdout = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                ns["main"]()
        except SystemExit as exc:
            code = exc.code
        finally:
            sys.argv = old
        expected_args = ([a for a in arms.split(",") if a], [m for m in mixes.split(",") if m])
        matches = (code == 2 and not calls and not stdout.getvalue() and error in stderr.getvalue()
                   if error else code == 0 and len(calls) == 1 and calls[0][:2] == expected_args)
        rows.append(dict(arms=arms, mixes=mixes, expected_error=error, code=code,
                         run_calls=len(calls), matches=matches, stderr=stderr.getvalue()))
    report.append(dict(label=label, cases=len(rows), matches=sum(r["matches"] for r in rows), rows=rows))
(kit / "native-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print([(r["label"], r["matches"], r["cases"]) for r in report])
assert report[-1]["matches"] == len(cases)
