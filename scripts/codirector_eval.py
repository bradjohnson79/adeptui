#!/usr/bin/env python3
"""Run Co-Director M2.4 evaluation scenarios."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codirector.evaluation.runner import EvaluationRunner  # noqa: E402


def main() -> int:
    runner = EvaluationRunner()
    results = runner.run_all()
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.scenario_id}: {', '.join(result.checks) or 'none'}")
        for failure in result.failures:
            print(f"  - {failure}")
    print(f"\n{passed}/{total} scenarios passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
