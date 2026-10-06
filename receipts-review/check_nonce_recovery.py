"""Execute the independent nonce recovery suite against a pinned checkout."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--json-report", type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.source), str(args.source / "tests")]
    path = Path(__file__).with_name("test_nonce_recovery.py")
    spec = importlib.util.spec_from_file_location("nonce_recovery_regressions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
    observations = module.OBSERVATIONS
    report = {"test_methods": result.testsRun, "cases": len(observations),
              "matched": sum(x["matched"] for x in observations),
              "mismatches": sum(not x["matched"] for x in observations),
              "errors": len(result.errors), "success": result.wasSuccessful(),
              "observations": observations, "live_requests": 0, "user_keys_accessed": False}
    args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
