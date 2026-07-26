"""Native platform awareness matrix (honest CONNECTED/PARTIAL/MISSING)."""

from __future__ import annotations

from typing import Any

from ...feature_flags import feature_flags


def _flag(name: str) -> bool:
    return bool(getattr(feature_flags, name, False))


def platform_matrix() -> list[dict[str, Any]]:
    """Document integration truth without inventing providers or fake CONNECTED rows."""

    return [
        {
            "surface": "Specialist prompt library (M2.4)",
            "status": "CONNECTED",
            "notes": "Reused under prompts/specialists; contracts + registry",
        },
        {
            "surface": "Intelligence pipeline (intent/select/run/synthesize)",
            "status": "CONNECTED",
            "notes": "M2.11 orchestrator reuses SpecialistRunner + ContextCompiler",
        },
        {
            "surface": "Production Bible conflicts/decisions",
            "status": "CONNECTED",
            "notes": "Bridges specialist conflicts into conflict_record via bible/conflicts.py",
        },
        {
            "surface": "M2.7 Production Executive",
            "status": "CONNECTED" if _flag("production_executive_v1") else "PARTIAL",
            "notes": "Dashboard coexists; jobs path reused for approvals when flag on",
        },
        {
            "surface": "M2.9 timeline / media generation",
            "status": "PARTIAL",
            "notes": "Advise-only in M2.11; no media generation in smoke; mutations require approval",
        },
        {
            "surface": "M2.10b sandbox audio providers",
            "status": "PARTIAL",
            "notes": "Not invoked by M2.11; Provider Manifest untouched; no new installs",
        },
        {
            "surface": "Hugging Face discovery / new providers",
            "status": "MISSING",
            "notes": "Explicitly out of scope for M2.11",
        },
        {
            "surface": "Silent Bible/timeline mutation",
            "status": "MISSING",
            "notes": "Forbidden by design; specialists advise through orchestrator + approval paths",
        },
    ]


def platform_summary() -> dict[str, Any]:
    rows = platform_matrix()
    counts = {"CONNECTED": 0, "PARTIAL": 0, "MISSING": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"matrix": rows, "counts": counts}
