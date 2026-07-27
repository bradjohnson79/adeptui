"""Generation experience store — never auto-promotes into global pack rules."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .schemas import ExperienceRecord


def ensure_experience_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS m30e_generation_experience (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                model_id VARCHAR(64) NOT NULL,
                model_version VARCHAR(64) NOT NULL DEFAULT '',
                provider_id VARCHAR(64) NOT NULL DEFAULT '',
                knowledge_pack_version VARCHAR(64) NOT NULL DEFAULT '',
                project_id VARCHAR(36),
                scene_id VARCHAR(64),
                shot_id VARCHAR(64),
                request_type VARCHAR(64) NOT NULL DEFAULT '',
                compiled_rule_ids_json TEXT NOT NULL DEFAULT '[]',
                parameter_summary_json TEXT NOT NULL DEFAULT '{}',
                generation_status VARCHAR(64) NOT NULL DEFAULT '',
                user_accepted INTEGER,
                user_rejected INTEGER,
                revision_requested INTEGER,
                vision_score REAL,
                continuity_score REAL,
                failure_codes_json TEXT NOT NULL DEFAULT '[]',
                generation_time_ms INTEGER,
                estimated_cost VARCHAR(128),
                actual_cost VARCHAR(128),
                user_feedback TEXT NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_m30e_exp_model ON m30e_generation_experience (model_id)"
        )
    )
    db.commit()


def _sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (params or {}).items():
        lk = str(k).lower()
        if any(s in lk for s in ("key", "secret", "token", "password", "authorization")):
            continue
        if isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out


def record_experience(
    db: Session,
    *,
    model_id: str,
    model_version: str = "",
    provider_id: str = "",
    knowledge_pack_version: str = "",
    project_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    request_type: str = "",
    compiled_rule_ids: Optional[list[str]] = None,
    parameter_summary: Optional[dict[str, Any]] = None,
    generation_status: str = "",
    failure_codes: Optional[list[str]] = None,
    generation_time_ms: Optional[int] = None,
    estimated_cost: Optional[str] = None,
    user_feedback: str = "",
) -> ExperienceRecord:
    ensure_experience_table(db)
    rid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    db.execute(
        text(
            """
            INSERT INTO m30e_generation_experience (
                id, model_id, model_version, provider_id, knowledge_pack_version,
                project_id, scene_id, shot_id, request_type, compiled_rule_ids_json,
                parameter_summary_json, generation_status, failure_codes_json,
                generation_time_ms, estimated_cost, user_feedback, created_at
            ) VALUES (
                :id, :model_id, :model_version, :provider_id, :kpv,
                :project_id, :scene_id, :shot_id, :request_type, :rules,
                :params, :status, :failures, :elapsed, :cost, :feedback, :created
            )
            """
        ),
        {
            "id": rid,
            "model_id": model_id,
            "model_version": model_version,
            "provider_id": provider_id,
            "kpv": knowledge_pack_version,
            "project_id": project_id,
            "scene_id": scene_id,
            "shot_id": shot_id,
            "request_type": request_type,
            "rules": json.dumps(list(compiled_rule_ids or [])),
            "params": json.dumps(_sanitize_params(parameter_summary or {})),
            "status": generation_status,
            "failures": json.dumps(list(failure_codes or [])),
            "elapsed": generation_time_ms,
            "cost": estimated_cost,
            "feedback": (user_feedback or "")[:2000],
            "created": now,
        },
    )
    db.commit()
    return ExperienceRecord(
        id=rid,
        modelId=model_id,
        modelVersion=model_version,
        providerId=provider_id,
        knowledgePackVersion=knowledge_pack_version,
        projectId=project_id,
        sceneId=scene_id,
        shotId=shot_id,
        requestType=request_type,
        compiledRuleIds=list(compiled_rule_ids or []),
        parameterSummary=_sanitize_params(parameter_summary or {}),
        generationStatus=generation_status,
        failureCodes=list(failure_codes or []),
        generationTimeMs=generation_time_ms,
        estimatedCost=estimated_cost,
        userFeedback=user_feedback,
        createdAt=now,
    )


def maybe_propose_m212_candidate(
    db: Session,
    *,
    project_id: str,
    insight: str,
    model_id: str,
    evidence_count: int = 1,
) -> Optional[dict[str, Any]]:
    """Create an m212 candidate lesson only when threshold met — never auto-activates packs."""
    if evidence_count < 3:
        return {
            "status": "below_threshold",
            "evidenceCount": evidence_count,
            "minimumEvidence": 3,
            "note": "Insight retained as experience only; not promoted",
        }
    try:
        from ..m212.lessons import LessonStore

        lesson = LessonStore.create_candidate(
            db,
            project_id=project_id,
            layer="project",
            title=f"MIL insight: {model_id}",
            text_body=insight[:2000],
            mistake_class="model_intelligence_observation",
            policy={"modelId": model_id, "source": "m30e_experience"},
        )
        return {"status": "candidate_created", "lesson": lesson}
    except Exception as exc:  # noqa: BLE001
        return {"status": "m212_unavailable", "error": str(exc)[:200]}
