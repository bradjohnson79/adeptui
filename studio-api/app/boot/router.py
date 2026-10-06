"""Read-only startup certification. Does not launch or restart runtimes."""

from __future__ import annotations

from fastapi import APIRouter

from .live import run_certification

router = APIRouter(prefix="/boot", tags=["boot"])


@router.get("/certification")
def get_boot_certification() -> dict:
    return run_certification()


@router.post("/certification/retry")
def retry_boot_certification() -> dict:
    """Re-read current health. Healthy processes stay up. Comfy is not restarted."""

    return run_certification(force=True)
