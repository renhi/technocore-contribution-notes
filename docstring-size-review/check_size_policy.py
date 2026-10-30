"""Whole standalone sz.py imports and actual CLI processes; no AST extraction.

Expected code-line/token counts come from explicit small grammar constructions.
All altered policy files are synthetic fixtures; official snapshots stay unchanged.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tool(snapshot, label):
    spec = importlib.util.spec_from_file_location("size_review_" + label, snapshot / "sz.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve() == (snapshot / "sz.py").resolve()
    return module


def cases():
    rows = []
    docs = ['"memo"', '"説明😀"', '"""first\nlast"""', '("one"\n "two")']
    separators = ["; ", " ; ", " \\\n; "]

    def add(name, source, lines, tokens=None):
        compile(source, name, "exec")
        rows.append(
            {
                "name": name,
                "source": source,
                "expected_code_lines": lines,
                "expected_tokens": tokens,
            }
        )

    for name_index, name in enumerate(("f", "함수", "café")):
        for doc_index, doc in enumerate(docs):
            for sep_index, sep in enumerate(separators):
                source = f"def {name}(): {doc}{sep}return 7\n"
                count = 2 if "\n" in doc or "\n" in sep else 1
                add(f"function-{name_index}-{doc_index}-{sep_index}", source, count, 7)
    for doc_index, doc in enumerate(docs):
        for sep_index, sep in enumerate(separators):
            add(f"module-{doc_index}-{sep_index}", f"{doc}{sep}x = 1\n", 1, 3)
            count = 2 if "\n" in doc or "\n" in sep else 1
            add(f"class-{doc_index}-{sep_index}", f"class 보기: {doc}{sep}x = 1\n", count, 6)
            add(f"doc-only-{doc_index}-{sep_index}", f"{doc}{sep.rstrip()}\n", 0, 0)
    for name, source, lines, tokens in [
        ("empty", "", 0, 0),
        ("comment-only", "# comment\n", 0, 0),
        ("ordinary-assignment", "x = 1\n", 1, 3),
        ("assigned-string", 'x = "not a docstring"\n', 1, 3),
        ("assigned-multiline", 'x = """one\ntwo"""\n', 1, 3),
        ("f-string-not-doc", 'f"not a docstring"\n', 1, None),
        ("byte-string-not-doc", 'b"not a docstring"\n', 1, 1),
        ("later-expression", 'x = 1\n"not first"\n', 2, 4),
        ("decorated-inline", '@decorator\ndef café(): "doc"; return 1\n', 2, 9),
        ("async-inline", 'async def 함수(): "doc"; return 1\n', 1, 8),
        ("two-inline-functions", 'def f(): "a"; return 1\ndef g(): "b"; return 2\n', 2, 14),
        ("unicode-line-separator", '"doc\u2028part"; x = 1\n', 1, 3),
        ("comments-in-doc-parens", '("one" # literal\n "two") ; # separator\n', 0, 0),
    ]:
        add(name, source, lines, tokens)
    return rows


def run_original(snapshot, label, provenance, local):
    test = provenance["original_test_path"]
    canonical = next(r["sha256"] for r in provenance["files"] if r["path"] == test)
    assert sha(snapshot / test) == canonical
    junit = local / (label + "-original-tests.xml")
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pytest",
        str(snapshot / test),
        "-c",
        str(snapshot / "pyproject.toml"),
        "--confcutdir=" + str(snapshot / "tests/unit"),
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(local / (label + "-pytest-temp")),
        "--junitxml=" + str(junit),
        "-q",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    (local / (label + "-pytest.log")).write_text(
        result.stdout + "\nSTDERR\n" + result.stderr, encoding="utf-8"
    )
    suite = ET.parse(junit).getroot().find("testsuite")
    assert suite is not None
    total, failed, errors, skipped = [
        int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")
    ]
    assert sha(snapshot / test) == canonical
    return {
        "tests": total,
        "passed": total - failed - errors - skipped,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "exit_code": result.returncode,
        "proposed_test_bytes_unchanged": True,
        "scope": "Exact proposed module normally imported; baseline receives only the unchanged test file. No root conftest/full Linux suite.",
    }


def run_cli_fixture(module, snapshot, label, local, index, source, expected_lines, policy, flag):
    directory = local / f"{label}-cli-{index}"
    directory.mkdir()
    (directory / "sz.py").write_bytes((snapshot / "sz.py").read_bytes())
    for relative in (*module.CORE_FILES, *module.EXTRA_FILES):
        target = directory / relative
        target.parent.mkdir(exist_ok=True)
        target.write_text(source if relative == module.CORE_FILES[0] else "", encoding="utf-8")
    labels = ["core/" + Path(name).name for name in module.CORE_FILES]
    cap = 0 if policy == "zero" else expected_lines if policy == "at" else 10
    previous = expected_lines if policy == "at" else 0
    caps = {name: cap if name == labels[0] else 0 for name in labels} | {"core_total": cap}
    if policy == "missing":
        caps.pop("core_total")
    baseline = {
        "core_total": previous,
        "caps": caps,
        "files": {name: {"code_lines": previous if name == labels[0] else 0} for name in labels},
    }
    baseline_file = directory / "sz-baseline.json"
    baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
    before = sha(baseline_file)
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(directory / "sz.py"), flag],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert sha(baseline_file) == before
    expected_fail = (
        policy == "missing"
        or (policy == "zero" and expected_lines > 0)
        or (policy == "ratchet" and flag == "--check" and expected_lines > 0)
    )
    expected_exit = int(expected_fail)
    return {
        "source": source,
        "expected_code_lines": expected_lines,
        "policy": policy,
        "mode": flag,
        "expected_exit": expected_exit,
        "actual_exit": result.returncode,
        "matches_expected": result.returncode == expected_exit,
        "stderr": result.stderr.strip(),
        "baseline_unchanged": True,
    }


def main(source, report):
    provenance = json.loads((report.parent / "source-provenance.json").read_text())
    for row in provenance["files"]:
        assert sha(source / row["version"] / row["path"]) == row["sha256"]
    local = source / ("native-run-" + str(time.time_ns()))
    assert local.resolve().is_relative_to(source.resolve())
    local.mkdir()
    versions = []
    for label in ("main", "candidate"):
        snapshot = source / label
        module = load_tool(snapshot, label)
        before = sha(snapshot / "sz.py")
        measurements = []
        for index, case in enumerate(cases()):
            sample = local / f"{label}-measure-{index}.py"
            sample.write_text(case["source"], encoding="utf-8")
            measured = module.measure(sample)
            expected_density = (
                round(case["expected_tokens"] / case["expected_code_lines"], 2)
                if case["expected_code_lines"] and case["expected_tokens"] is not None
                else 0.0
            )
            density_ok = (
                case["expected_tokens"] is None or measured["tokens_per_line"] == expected_density
            )
            measurements.append(
                case
                | {
                    "measurement": measured,
                    "line_count_matches": measured["code_lines"] == case["expected_code_lines"],
                    "token_density_matches": density_ok,
                    "matches_expected": measured["code_lines"] == case["expected_code_lines"]
                    and density_ok,
                }
            )
        cli = []
        for source_text, lines in [
            ('"doc"; x = 1\n', 1),
            ('def f(): """one\ntwo"""; return 1\n', 2),
            ('("one"\n "two") ;\n', 0),
            ("x = 1\n", 1),
        ]:
            for policy in ("zero", "at", "ratchet", "missing"):
                for flag in ("--caps", "--check"):
                    cli.append(
                        run_cli_fixture(
                            module,
                            snapshot,
                            label,
                            local,
                            len(cli),
                            source_text,
                            lines,
                            policy,
                            flag,
                        )
                    )
        real_measurements = module.measure_all(snapshot)
        real_cli = []
        protected_before = sha(snapshot / "sz-baseline.json")
        for flags in ([], ["--caps"], ["--check"]):
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(snapshot / "sz.py"), *flags],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
            )
            real_cli.append(
                {"args": flags, "exit_code": result.returncode, "stderr": result.stderr.strip()}
            )
        assert sha(snapshot / "sz-baseline.json") == protected_before
        original = run_original(snapshot, label, provenance, local)
        assert sha(snapshot / "sz.py") == before
        versions.append(
            {
                "version": label,
                "whole_module_sha256": before,
                "matrix_cases": len(measurements),
                "matrix_matches": sum(r["matches_expected"] for r in measurements),
                "measurement_rows": measurements,
                "synthetic_CLI_cases": len(cli),
                "synthetic_CLI_matches": sum(r["matches_expected"] for r in cli),
                "CLI_rows": cli,
                "real_source_measurements": real_measurements,
                "real_source_CLI": real_cli,
                "original_proposed_tests": original,
                "original_baseline_and_tool_unchanged": True,
            }
        )
    for row in provenance["files"]:
        assert sha(source / row["version"] / row["path"]) == row["sha256"]
    equal = versions[0]["real_source_measurements"] == versions[1]["real_source_measurements"]
    result = {
        "python": sys.version,
        "platform": sys.platform,
        "pytest": importlib.metadata.version("pytest"),
        "versions": versions,
        "matrix_executions": sum(v["matrix_cases"] for v in versions),
        "synthetic_CLI_executions": sum(v["synthetic_CLI_cases"] for v in versions),
        "real_source_CLI_executions": 6,
        "all_six_real_file_measurement_dictionaries_equal": equal,
        "all_source_blobs_unchanged": True,
        "HTTP_requests": 0,
        "protected_user_key_loaded": False,
        "scope": "Whole unchanged sz.py normal import and native Python CLI. Actual six source files are measured, never imported. Synthetic policy baselines confined to new local fixtures; no --update-baseline or official baseline changes. Exact proposed test module only, not whole repository or CI.",
    }
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "matrix_executions": result["matrix_executions"],
                "synthetic_CLI_executions": result["synthetic_CLI_executions"],
                "real_file_metrics_equal": equal,
                "versions": [
                    {
                        k: v[k]
                        for k in (
                            "version",
                            "matrix_cases",
                            "matrix_matches",
                            "synthetic_CLI_cases",
                            "synthetic_CLI_matches",
                            "original_proposed_tests",
                            "real_source_CLI",
                        )
                    }
                    for v in versions
                ],
            }
        )
    )
    assert equal
    assert versions[1]["matrix_matches"] == versions[1]["matrix_cases"]
    assert versions[1]["synthetic_CLI_matches"] == versions[1]["synthetic_CLI_cases"]
    assert (
        versions[1]["original_proposed_tests"]["failed"]
        == versions[1]["original_proposed_tests"]["errors"]
        == 0
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
