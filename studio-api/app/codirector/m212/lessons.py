"""M2.12 lesson store with versioning and audit history (no silent delete)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m212_tables
from .safety import AdaptiveLearningSafetyError, assert_no_system_auto_activate

LAYERS = ("session", "project", "user", "system")
STATUSES = ("candidate", "active", "retired", "rolled_back")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class LessonStore:
    @staticmethod
    def create_candidate(
        db: Session,
        *,
        layer: str,
        text_body: str,
        title: str = "",
        policy: Optional[dict[str, Any]] = None,
        evidence: Optional[list[dict[str, Any]]] = None,
        confidence: float = 0.0,
        evidence_score: float = 0.0,
        mistake_class: str = "",
        source_signals: Optional[list[dict[str, Any]]] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        regression_suite_id: Optional[str] = None,
        actor: str = "critique",
    ) -> dict[str, Any]:
        ensure_m212_tables()
        if layer not in LAYERS:
            raise AdaptiveLearningSafetyError(f"Invalid lesson layer: {layer}")
        # System candidates are allowed; auto-activate is not.
        assert_no_system_auto_activate(layer, auto=False)
        lid = str(uuid.uuid4())
        now = _now()
        db.execute(
            text(
                """
                INSERT INTO m212_lessons
                (id, layer, status, version, title, text, policy_json, evidence_json,
                 confidence, evidence_score, mistake_class, source_signals_json,
                 regression_suite_id, regression_passed, approval_json,
                 project_id, user_id, session_id, created_at, promoted_at, retired_at, updated_at)
                VALUES
                (:id, :layer, 'candidate', 1, :title, :text, :policy_json, :evidence_json,
                 :confidence, :evidence_score, :mistake_class, :source_signals_json,
                 :regression_suite_id, 0, :approval_json,
                 :project_id, :user_id, :session_id, :created_at, NULL, NULL, :updated_at)
                """
            ),
            {
                "id": lid,
                "layer": layer,
                "title": title or (text_body[:80] if text_body else "lesson"),
                "text": text_body,
                "policy_json": json.dumps(policy or {}, ensure_ascii=False),
                "evidence_json": json.dumps(evidence or [], ensure_ascii=False),
                "confidence": float(confidence),
                "evidence_score": float(evidence_score),
                "mistake_class": mistake_class or "",
                "source_signals_json": json.dumps(source_signals or [], ensure_ascii=False),
                "regression_suite_id": regression_suite_id,
                "approval_json": json.dumps({}, ensure_ascii=False),
                "project_id": project_id,
                "user_id": user_id,
                "session_id": session_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
        row = LessonStore.get(db, lid)
        assert row is not None
        LessonStore._record_version(db, row, action="create", actor=actor, note="candidate created")
        return row

    @staticmethod
    def get(db: Session, lesson_id: str) -> dict[str, Any] | None:
        ensure_m212_tables()
        row = db.execute(
            text("SELECT * FROM m212_lessons WHERE id=:id"),
            {"id": lesson_id},
        ).mappings().fetchone()
        return LessonStore._row(row) if row else None

    @staticmethod
    def list_lessons(
        db: Session,
        *,
        project_id: Optional[str] = None,
        layer: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ensure_m212_tables()
        clauses = ["1=1"]
        params: dict[str, Any] = {"limit": max(1, min(limit, 500))}
        if project_id:
            clauses.append("(project_id = :project_id OR layer = 'system' OR layer = 'user')")
            params["project_id"] = project_id
        if layer:
            clauses.append("layer = :layer")
            params["layer"] = layer
        if status:
            clauses.append("status = :status")
            params["status"] = status
        rows = db.execute(
            text(
                f"""
                SELECT * FROM m212_lessons
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().fetchall()
        return [LessonStore._row(r) for r in rows]

    @staticmethod
    def list_active_for_context(
        db: Session,
        *,
        project_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        ensure_m212_tables()
        rows = db.execute(
            text(
                """
                SELECT * FROM m212_lessons
                WHERE status = 'active'
                  AND (
                    (layer = 'project' AND project_id = :project_id)
                    OR (layer = 'session' AND project_id = :project_id
                        AND (:session_id IS NULL OR session_id = :session_id))
                    OR (layer = 'user' AND (:user_id IS NULL OR user_id = :user_id OR user_id IS NULL))
                    OR layer = 'system'
                  )
                ORDER BY layer ASC, promoted_at DESC
                LIMIT :limit
                """
            ),
            {
                "project_id": project_id,
                "session_id": session_id,
                "user_id": user_id,
                "limit": max(1, min(limit, 100)),
            },
        ).mappings().fetchall()
        return [LessonStore._row(r) for r in rows]

    @staticmethod
    def update_fields(
        db: Session,
        lesson_id: str,
        *,
        fields: dict[str, Any],
        actor: str = "system",
        action: str = "update",
        note: str = "",
        bump_version: bool = False,
    ) -> dict[str, Any] | None:
        ensure_m212_tables()
        row = LessonStore.get(db, lesson_id)
        if row is None:
            return None
        allowed = {
            "status",
            "title",
            "text",
            "policy",
            "evidence",
            "confidence",
            "evidenceScore",
            "mistakeClass",
            "sourceSignals",
            "regressionSuiteId",
            "regressionPassed",
            "approval",
            "promotedAt",
            "retiredAt",
        }
        col_map = {
            "status": "status",
            "title": "title",
            "text": "text",
            "policy": "policy_json",
            "evidence": "evidence_json",
            "confidence": "confidence",
            "evidenceScore": "evidence_score",
            "mistakeClass": "mistake_class",
            "sourceSignals": "source_signals_json",
            "regressionSuiteId": "regression_suite_id",
            "regressionPassed": "regression_passed",
            "approval": "approval_json",
            "promotedAt": "promoted_at",
            "retiredAt": "retired_at",
        }
        sets = ["updated_at = :updated_at"]
        params: dict[str, Any] = {"id": lesson_id, "updated_at": _now()}
        version = int(row["version"])
        if bump_version:
            version += 1
            sets.append("version = :version")
            params["version"] = version
        for key, value in fields.items():
            if key not in allowed:
                continue
            col = col_map[key]
            if col.endswith("_json"):
                params[col] = json.dumps(value if value is not None else {}, ensure_ascii=False) if not isinstance(value, str) else value
                if col in ("evidence_json", "source_signals_json") and not isinstance(value, str):
                    params[col] = json.dumps(value if value is not None else [], ensure_ascii=False)
            elif col == "regression_passed":
                params[col] = 1 if value else 0
            else:
                params[col] = value
            sets.append(f"{col} = :{col}")
        db.execute(
            text(f"UPDATE m212_lessons SET {', '.join(sets)} WHERE id = :id"),
            params,
        )
        db.commit()
        updated = LessonStore.get(db, lesson_id)
        assert updated is not None
        LessonStore._record_version(db, updated, action=action, actor=actor, note=note)
        return updated

    @staticmethod
    def versions(db: Session, lesson_id: str, limit: int = 50) -> list[dict[str, Any]]:
        ensure_m212_tables()
        rows = db.execute(
            text(
                """
                SELECT * FROM m212_lesson_versions
                WHERE lesson_id = :lesson_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"lesson_id": lesson_id, "limit": max(1, min(limit, 200))},
        ).mappings().fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "lessonId": r["lesson_id"],
                    "version": r["version"],
                    "action": r["action"],
                    "actor": r["actor"],
                    "snapshot": json.loads(r["snapshot_json"] or "{}"),
                    "note": r["note"],
                    "createdAt": r["created_at"],
                }
            )
        return out

    @staticmethod
    def _record_version(
        db: Session,
        lesson: dict[str, Any],
        *,
        action: str,
        actor: str,
        note: str = "",
    ) -> None:
        ensure_m212_tables()
        db.execute(
            text(
                """
                INSERT INTO m212_lesson_versions
                (id, lesson_id, version, action, actor, snapshot_json, note, created_at)
                VALUES
                (:id, :lesson_id, :version, :action, :actor, :snapshot_json, :note, :created_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "lesson_id": lesson["id"],
                "version": int(lesson["version"]),
                "action": action,
                "actor": actor,
                "snapshot_json": json.dumps(lesson, ensure_ascii=False),
                "note": note or "",
                "created_at": _now(),
            },
        )
        db.commit()

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "layer": row["layer"],
            "status": row["status"],
            "version": int(row["version"]),
            "title": row["title"],
            "text": row["text"],
            "policy": json.loads(row["policy_json"] or "{}"),
            "evidence": json.loads(row["evidence_json"] or "[]"),
            "confidence": float(row["confidence"] or 0.0),
            "evidenceScore": float(row["evidence_score"] or 0.0),
            "mistakeClass": row["mistake_class"] or "",
            "sourceSignals": json.loads(row["source_signals_json"] or "[]"),
            "regressionSuiteId": row["regression_suite_id"],
            "regressionPassed": bool(row["regression_passed"]),
            "approval": json.loads(row["approval_json"] or "{}"),
            "projectId": row["project_id"],
            "userId": row["user_id"],
            "sessionId": row["session_id"],
            "createdAt": row["created_at"],
            "promotedAt": row["promoted_at"],
            "retiredAt": row["retired_at"],
            "updatedAt": row["updated_at"],
        }
