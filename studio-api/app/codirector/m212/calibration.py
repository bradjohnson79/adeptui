"""Confidence calibration store (separate from Gemma weights)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m212_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_sample(
    db: Session,
    *,
    predicted_confidence: float,
    observed_outcome: str,
    project_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m212_tables()
    outcome = str(observed_outcome or "").lower()
    if outcome not in ("success", "failure", "partial"):
        outcome = "partial"
    pred = max(0.0, min(1.0, float(predicted_confidence)))
    # Simple calibration nudge: shrink overconfidence on failures, boost on success.
    if outcome == "success":
        calibrated = min(1.0, pred + 0.05)
    elif outcome == "failure":
        calibrated = max(0.0, pred * 0.7)
    else:
        calibrated = pred * 0.9
    sid = str(uuid.uuid4())
    db.execute(
        text(
            """
            INSERT INTO m212_confidence_calibration
            (id, project_id, predicted_confidence, observed_outcome, calibrated_confidence, context_json, created_at)
            VALUES
            (:id, :project_id, :predicted, :observed, :calibrated, :context_json, :created_at)
            """
        ),
        {
            "id": sid,
            "project_id": project_id,
            "predicted": pred,
            "observed": outcome,
            "calibrated": calibrated,
            "context_json": json.dumps(context or {}, ensure_ascii=False),
            "created_at": _now(),
        },
    )
    db.commit()
    return {
        "id": sid,
        "projectId": project_id,
        "predictedConfidence": pred,
        "observedOutcome": outcome,
        "calibratedConfidence": calibrated,
        "context": context or {},
        "createdAt": _now(),
    }


def list_samples(db: Session, project_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_m212_tables()
    if project_id:
        rows = db.execute(
            text(
                """
                SELECT * FROM m212_confidence_calibration
                WHERE project_id = :project_id
                ORDER BY created_at DESC LIMIT :limit
                """
            ),
            {"project_id": project_id, "limit": max(1, min(limit, 200))},
        ).mappings().fetchall()
    else:
        rows = db.execute(
            text(
                """
                SELECT * FROM m212_confidence_calibration
                ORDER BY created_at DESC LIMIT :limit
                """
            ),
            {"limit": max(1, min(limit, 200))},
        ).mappings().fetchall()
    return [
        {
            "id": r["id"],
            "projectId": r["project_id"],
            "predictedConfidence": float(r["predicted_confidence"]),
            "observedOutcome": r["observed_outcome"],
            "calibratedConfidence": float(r["calibrated_confidence"]) if r["calibrated_confidence"] is not None else None,
            "context": json.loads(r["context_json"] or "{}"),
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


def calibration_health(db: Session, project_id: Optional[str] = None) -> dict[str, Any]:
    samples = list_samples(db, project_id=project_id, limit=200)
    if not samples:
        return {
            "sampleCount": 0,
            "meanPredicted": None,
            "meanCalibrated": None,
            "failureRate": None,
            "status": "no_data",
        }
    preds = [s["predictedConfidence"] for s in samples]
    cals = [s["calibratedConfidence"] for s in samples if s["calibratedConfidence"] is not None]
    failures = sum(1 for s in samples if s["observedOutcome"] == "failure")
    return {
        "sampleCount": len(samples),
        "meanPredicted": sum(preds) / len(preds),
        "meanCalibrated": (sum(cals) / len(cals)) if cals else None,
        "failureRate": failures / len(samples),
        "status": "ok",
    }
