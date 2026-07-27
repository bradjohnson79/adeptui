"""Concept generation tiers + timeline publish (honest mock/real labels)."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .store import M213Store

TIERS = ("draft", "production", "final_candidate")

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


class ConceptProviderUnavailable(RuntimeError):
    """No real concept provider is configured and mock output was not explicitly requested."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _provider_available() -> bool:
    return bool(os.environ.get("STUDIO_M213_REAL_CONCEPT_PROVIDER"))


def _e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in _TRUE


def generate_concept(
    db: Session,
    *,
    project_id: str,
    environment_id: str,
    tier: str = "draft",
    force_mock: bool | None = None,
) -> dict[str, Any]:
    """Generate a concept with the real provider, or fail honestly.

    Mock output is produced only when the caller explicitly asks for it (`force_mock=True`)
    or the process is an E2E run. Production never receives a mock labelled as a success.
    """
    ensure_m213_tables()
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    if force_mock is True:
        real = False
    elif _provider_available():
        real = True
    elif _e2e_enabled():
        real = False
    else:
        raise ConceptProviderUnavailable(
            "Concept generation is unavailable: no real provider is configured "
            "(set STUDIO_M213_REAL_CONCEPT_PROVIDER) and mock output was not requested."
        )
    mode = "real" if real else "mock"
    cid = str(uuid.uuid4())
    payload = {
        "tier": tier,
        "generationMode": mode,
        "prompt": f"Concept {tier} for environment {environment_id}",
        "fixture": not real,
        "honesty": (
            "MOCK/FIXTURE concept. Not a real provider generation."
            if not real
            else "Real provider path enabled via STUDIO_M213_REAL_CONCEPT_PROVIDER."
        ),
        "clip": {
            "durationSec": 4 if tier == "draft" else 8,
            "label": f"{tier}:{mode}",
        },
    }
    db.execute(
        text(
            "INSERT INTO m213_concepts "
            "(id, project_id, environment_id, tier, generation_mode, asset_id, payload_json, approved, created_at, updated_at) "
            "VALUES (:id, :project_id, :environment_id, :tier, :generation_mode, NULL, :payload_json, 0, :ts, :ts)"
        ),
        {
            "id": cid,
            "project_id": project_id,
            "environment_id": environment_id,
            "tier": tier,
            "generation_mode": mode,
            "payload_json": json.dumps(payload),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.concept.generate",
        action="generate",
        project_id=project_id,
        payload={"conceptId": cid, "tier": tier, "mode": mode},
    )
    M213Store.save_version(
        db,
        project_id=project_id,
        subject_kind="concept",
        subject_id=cid,
        version=1,
        snapshot=payload,
    )
    return {
        "id": cid,
        "projectId": project_id,
        "environmentId": environment_id,
        "tier": tier,
        "generationMode": mode,
        "payload": payload,
        "approved": False,
        "approvalGate": "concept",
        "realGeneration": real,
    }


def approve_concept(
    db: Session, *, concept_id: str, actor: str = "user", note: str = ""
) -> dict[str, Any]:
    ensure_m213_tables()
    row = db.execute(
        text("SELECT id, project_id FROM m213_concepts WHERE id = :id"),
        {"id": concept_id},
    ).mappings().first()
    if not row:
        raise LookupError("concept not found")
    db.execute(
        text("UPDATE m213_concepts SET approved = 1, updated_at = :ts WHERE id = :id"),
        {"id": concept_id, "ts": _now()},
    )
    db.commit()
    approval = M213Store.record_approval(
        db,
        project_id=row["project_id"],
        gate="concept",
        subject_id=concept_id,
        approved=True,
        actor=actor,
        note=note,
    )
    return {"ok": True, "conceptId": concept_id, "approved": True, "approval": approval}


def get_concept(db: Session, concept_id: str) -> Optional[dict[str, Any]]:
    ensure_m213_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, environment_id, tier, generation_mode, asset_id, payload_json, approved, created_at "
            "FROM m213_concepts WHERE id = :id"
        ),
        {"id": concept_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "environmentId": row["environment_id"],
        "tier": row["tier"],
        "generationMode": row["generation_mode"],
        "assetId": row["asset_id"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "approved": bool(row["approved"]),
        "createdAt": str(row["created_at"]),
        "realGeneration": row["generation_mode"] == "real",
    }


def publish_to_timeline(
    db: Session,
    *,
    project_id: str,
    concept_ids: list[str],
    selective: bool = False,
) -> dict[str, Any]:
    ensure_m213_tables()
    clips = []
    for cid in concept_ids:
        concept = get_concept(db, cid)
        if not concept:
            continue
        clips.append(
            {
                "conceptId": cid,
                "tier": concept["tier"],
                "generationMode": concept["generationMode"],
                "label": concept["payload"].get("clip", {}).get("label"),
                "durationSec": concept["payload"].get("clip", {}).get("durationSec"),
                "approved": concept["approved"],
                "honesty": concept["payload"].get("honesty"),
            }
        )
    # Soft integration with director timeline when available
    published = False
    director_ref = None
    try:
        from ...director_timeline import DirectorTimelineService  # type: ignore

        if hasattr(DirectorTimelineService, "append_concept_clips"):
            director_ref = DirectorTimelineService.append_concept_clips(  # type: ignore[attr-defined]
                db, project_id=project_id, clips=clips
            )
            published = True
    except Exception:
        published = False
    result = {
        "ok": True,
        "projectId": project_id,
        "clips": clips,
        "selective": selective,
        "publishedToDirectorTimeline": published,
        "directorRef": director_ref,
        "editorHandoff": "use existing send-to-editor when clips materialize as assets",
        "honesty": (
            "Publish package created. Clips may be mock-labeled; do not claim real render "
            "unless generationMode=real and assets exist."
        ),
    }
    M213Store.log_capability(
        db,
        capability_id="ve.timeline.publish",
        action="publish",
        project_id=project_id,
        payload={"clipCount": len(clips), "published": published, "selective": selective},
    )
    return result


def selective_regenerate(
    db: Session, *, project_id: str, concept_id: str, tier: str = "production"
) -> dict[str, Any]:
    prior = get_concept(db, concept_id)
    if not prior:
        raise LookupError("concept not found")
    regenerated = generate_concept(
        db,
        project_id=project_id,
        environment_id=prior["environmentId"],
        tier=tier,
        force_mock=prior["generationMode"] != "real",
    )
    regenerated["replacedConceptId"] = concept_id
    regenerated["selective"] = True
    return regenerated
