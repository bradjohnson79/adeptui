"""Provenance helpers for pack claims."""

from __future__ import annotations

from typing import Any

from .schemas import ConfidenceLevel, ProvenanceClaim


def claim_from_dict(raw: dict[str, Any] | None) -> ProvenanceClaim:
    data = raw or {}
    level_raw = str(data.get("sourceType") or data.get("confidenceLevel") or "UNKNOWN")
    try:
        level = ConfidenceLevel(level_raw)
    except ValueError:
        level = ConfidenceLevel.UNKNOWN
    return ProvenanceClaim(
        sourceType=level,
        sourceReference=str(data.get("sourceReference") or data.get("url") or ""),
        modelVersion=str(data.get("modelVersion") or ""),
        knowledgePackVersion=str(data.get("knowledgePackVersion") or ""),
        verifiedAt=data.get("verifiedAt"),
        confidence=float(data.get("confidence") or 0.0),
        notes=str(data.get("notes") or ""),
    )


def summarize_pack_provenance(pack: dict[str, Any]) -> list[dict[str, Any]]:
    prov = pack.get("provenance") or {}
    claims = prov.get("claims") or []
    out = []
    for item in claims:
        if isinstance(item, dict):
            out.append(claim_from_dict(item).model_dump())
    return out
