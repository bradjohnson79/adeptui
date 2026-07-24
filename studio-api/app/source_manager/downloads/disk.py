"""Disk-space preflight for download operations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def free_bytes(path: str | Path) -> int | None:
    try:
        usage = shutil.disk_usage(str(Path(path).expanduser()))
        return int(usage.free)
    except OSError:
        return None


def calculate_required_space(
    *,
    download_bytes: int | None,
    extracted_bytes: int | None,
    temporary_overhead: int | None = None,
    safety_margin: int | None = None,
) -> dict[str, Any]:
    """
    requiredSpace = download + extracted + temporaryOverhead + safetyMargin
    Estimates are labeled when sizes are unknown.
    """
    exact = download_bytes is not None and extracted_bytes is not None
    dl = int(download_bytes or 0)
    ex = int(extracted_bytes if extracted_bytes is not None else (dl * 1.15 if dl else 0))
    overhead = temporary_overhead if temporary_overhead is not None else max(64 * 1024 * 1024, int(dl * 0.1))
    margin = safety_margin if safety_margin is not None else max(256 * 1024 * 1024, int((dl + ex) * 0.05))
    required = dl + ex + int(overhead) + int(margin)
    return {
        "requiredBytes": required,
        "downloadBytes": download_bytes,
        "extractedBytes": extracted_bytes if extracted_bytes is not None else ex,
        "temporaryOverhead": int(overhead),
        "safetyMargin": int(margin),
        "estimate": not exact,
        "label": "exact" if exact else "conservative_estimate",
    }


def preflight_disk(
    destination: str | Path,
    *,
    download_bytes: int | None,
    extracted_bytes: int | None,
) -> dict[str, Any]:
    req = calculate_required_space(
        download_bytes=download_bytes,
        extracted_bytes=extracted_bytes,
    )
    available = free_bytes(destination)
    state = "unknown"
    if available is None:
        state = "unknown"
    elif available >= req["requiredBytes"]:
        # low if under 2x required
        state = "sufficient" if available >= req["requiredBytes"] * 1.25 else "low"
    else:
        state = "insufficient"
    return {
        **req,
        "availableBytes": available,
        "state": state,
        "destination": str(destination),
        "ok": state in {"sufficient", "low", "unknown"},
        "block": state == "insufficient",
        "message": _message(state, req["requiredBytes"], available, req["estimate"]),
    }


def _message(state: str, required: int, available: int | None, estimate: bool) -> str:
    approx = "approximately " if estimate else ""
    if state == "insufficient":
        return (
            f"Not enough free space. The selected install requires {approx}"
            f"{_gb(required)} but only {_gb(available or 0)} is available."
        )
    if state == "low":
        return (
            f"Disk space is low. Required {approx}{_gb(required)}; "
            f"available {_gb(available or 0)}."
        )
    if state == "unknown":
        return "Could not determine free disk space. Proceed with caution."
    return f"Sufficient disk space ({_gb(available or 0)} available)."


def _gb(n: int) -> str:
    return f"{n / (1024**3):.1f} GB"
