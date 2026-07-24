from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "studio-api"
WEB_DIR = ROOT / "studio-web"

STARTUP_CHECK = """
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app, job_queue
from app.routers import api
job_queue.start = lambda: None
api.job_queue.enqueue = AsyncMock()
with TestClient(app) as client:
    response = client.get("/")
    assert response.status_code == 200, response.text
print("FastAPI startup smoke check passed")
""".strip()


def run_check(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except FileNotFoundError as exc:
        return_code = 127
        stdout = ""
        stderr = str(exc)

    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "returncode": return_code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout,
        "stderr": stderr,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase 0 checks with backend data isolated from production."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optionally write the JSON results to this path.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        help="Python interpreter for API checks (defaults to studio-api/.venv when present).",
    )
    return parser.parse_args()


def api_python(requested: Path | None) -> str:
    candidates = [
        requested,
        Path(os.environ["STUDIO_API_PYTHON"]) if os.environ.get("STUDIO_API_PYTHON") else None,
        API_DIR / ".venv" / "Scripts" / "python.exe",
        API_DIR / "venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.expanduser().is_file():
            return str(candidate.expanduser().resolve())
    return sys.executable


def main() -> int:
    args = parse_args()
    npm = shutil.which("npm")
    npm_command = npm or "npm"
    python = api_python(args.python)

    with tempfile.TemporaryDirectory(prefix="aivideostudio-phase0-run-") as temp:
        isolated_data = Path(temp).resolve()
        production_data = (ROOT / "data").resolve()
        if isolated_data == production_data or production_data in isolated_data.parents:
            raise RuntimeError("Refusing to run baseline checks against production data")

        env = os.environ.copy()
        env["STUDIO_DATA_DIR"] = str(isolated_data)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        checks = [
            run_check(
                "typescript",
                [npm_command, "exec", "tsc", "--", "-b", "--pretty", "false"],
                WEB_DIR,
                env,
            ),
            run_check(
                "web_build",
                [npm_command, "run", "build"],
                WEB_DIR,
                env,
            ),
            run_check(
                "api_startup",
                [python, "-c", STARTUP_CHECK],
                API_DIR,
                env,
            ),
            run_check(
                "backend_smoke",
                [python, "-m", "pytest", "tests", "-q"],
                API_DIR,
                env,
            ),
        ]

    result = {
        "ok": all(check["returncode"] == 0 for check in checks),
        "production_data_used": False,
        "checks": checks,
    }
    rendered = json.dumps(result, indent=2)
    print(rendered)

    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
