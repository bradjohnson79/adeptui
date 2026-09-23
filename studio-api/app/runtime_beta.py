"""Read-only Adept UI Beta runtime status (supervisor status.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db

router = APIRouter(tags=["runtime-beta"])


def _status_path() -> Path:
    return Path(settings.data_dir) / "runtime" / "beta" / "status.json"


@router.get("/runtime/beta")
def get_beta_runtime_status() -> dict[str, Any]:
    path = _status_path()
    if not path.is_file():
        return {
            "active": False,
            "state": "STOPPED",
            "message": "Beta runtime status file not present (not started via Start-AdeptUI-Beta).",
            "statusPath": str(path),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "active": False,
            "state": "FAILED",
            "message": f"Unable to read status.json: {exc}",
            "statusPath": str(path),
        }
    data["active"] = True
    data["statusPath"] = str(path)
    return data


@router.get("/runtime/local-generation")
def get_local_generation(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Active Local GPU job for the Home attention bar. Hosted API jobs are excluded."""
    from .runtime.local_generation import active_local_generation

    return active_local_generation(db)
