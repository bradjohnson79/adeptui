"""DecisionRecord model with explainability for M2.11."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m211_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DecisionRecordStore:
    @staticmethod
    def create(
        db: Session,
        *,
        project_id: str,
        category: str,
        rationale: str,
        confidence: float,
        evidence: Optional[list[dict[str, Any]]] = None,
        bible_refs: Optional[list[str]] = None,
        specialist_id: str,
        approval_required: bool = False,
        approval_status: str = "pending",
        recommendation: str = "",
        scene_id: Optional[str] = None,
        explainability: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ensure_m211_tables()
        did = str(uuid.uuid4())
        now = _now()
        explain = explainability or {
            "summary": rationale,
            "evidence": evidence or [],
            "bibleRefs": bible_refs or [],
            "specialistId": specialist_id,
            "confidence": confidence,
        }
        db.execute(
            text(
                """
                INSERT INTO m211_decision_records
                (id, project_id, scene_id, category, rationale, confidence, evidence_json, bible_refs_json,
                 specialist_id, approval_required, approval_status, recommendation, explainability_json, created_at, updated_at)
                VALUES
                (:id, :project_id, :scene_id, :category, :rationale, :confidence, :evidence_json, :bible_refs_json,
                 :specialist_id, :approval_required, :approval_status, :recommendation, :explainability_json, :created_at, :updated_at)
                """
            ),
            {
                "id": did,
                "project_id": project_id,
                "scene_id": scene_id,
                "category": category,
                "rationale": rationale,
                "confidence": float(confidence),
                "evidence_json": json.dumps(evidence or [], ensure_ascii=False),
                "bible_refs_json": json.dumps(bible_refs or [], ensure_ascii=False),
                "specialist_id": specialist_id,
                "approval_required": 1 if approval_required else 0,
                "approval_status": approval_status,
                "recommendation": recommendation,
                "explainability_json": json.dumps(explain, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
        return DecisionRecordStore.get(db, project_id, did)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, project_id: str, decision_id: str) -> dict[str, Any] | None:
        ensure_m211_tables()
        row = db.execute(
            text("SELECT * FROM m211_decision_records WHERE id=:id AND project_id=:project_id"),
            {"id": decision_id, "project_id": project_id},
        ).mappings().fetchone()
        return DecisionRecordStore._row(row) if row else None

    @staticmethod
    def list_for_project(
        db: Session,
        project_id: str,
        *,
        scene_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ensure_m211_tables()
        clauses = ["project_id = :project_id"]
        params: dict[str, Any] = {"project_id": project_id, "limit": max(1, min(limit, 500))}
        if scene_id:
            clauses.append("scene_id = :scene_id")
            params["scene_id"] = scene_id
        rows = db.execute(
            text(
                f"""
                SELECT * FROM m211_decision_records
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().fetchall()
        return [DecisionRecordStore._row(r) for r in rows]

    @staticmethod
    def set_approval(
        db: Session,
        project_id: str,
        decision_id: str,
        *,
        status: str,
    ) -> dict[str, Any] | None:
        ensure_m211_tables()
        db.execute(
            text(
                """
                UPDATE m211_decision_records
                SET approval_status=:status, updated_at=:updated_at
                WHERE id=:id AND project_id=:project_id
                """
            ),
            {"status": status, "updated_at": _now(), "id": decision_id, "project_id": project_id},
        )
        db.commit()
        return DecisionRecordStore.get(db, project_id, decision_id)

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "category": row["category"],
            "rationale": row["rationale"],
            "confidence": float(row["confidence"]),
            "evidence": json.loads(row["evidence_json"] or "[]"),
            "bibleRefs": json.loads(row["bible_refs_json"] or "[]"),
            "specialistId": row["specialist_id"],
            "approvalRequired": bool(row["approval_required"]),
            "approvalStatus": row["approval_status"],
            "recommendation": row["recommendation"],
            "explainability": json.loads(row["explainability_json"] or "{}"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
