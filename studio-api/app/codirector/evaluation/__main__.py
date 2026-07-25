"""CLI entrypoint for Co-Director evaluation fixtures."""

from __future__ import annotations

import json
import sys

from .runner import EvaluationRunner


def main() -> int:
    runner = EvaluationRunner()
    results = runner.run_all()
    payload = [result.to_dict() for result in results]
    print(json.dumps(payload, indent=2))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
