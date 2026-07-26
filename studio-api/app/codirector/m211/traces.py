"""Execution traces for M2.11 orchestration runs."""

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


class ExecutionTraceStore:
    @staticmethod
    def start(
        db: Session,
        *,
        project_id: str,
        scene_id: Optional[str],
        model_used: str,
        specialist_graph: list[dict[str, Any]],
        brief: str,
    ) -> dict[str, Any]:
        ensure_m211_tables()
        tid = str(uuid.uuid4())
        now = _now()
        db.execute(
            text(
                """
                INSERT INTO m211_execution_traces
                (id, project_id, scene_id, model_used, specialist_graph_json, brief, status,
                 durations_json, failures_json, retries_json, approvals_json, stages_json, created_at, updated_at)
                VALUES
                (:id, :project_id, :scene_id, :model_used, :specialist_graph_json, :brief, :status,
                 :durations_json, :failures_json, :retries_json, :approvals_json, :stages_json, :created_at, :updated_at)
                """
            ),
            {
                "id": tid,
                "project_id": project_id,
                "scene_id": scene_id,
                "model_used": model_used,
                "specialist_graph_json": json.dumps(specialist_graph, ensure_ascii=False),
                "brief": brief,
                "status": "running",
                "durations_json": "{}",
                "failures_json": "[]",
                "retries_json": "[]",
                "approvals_json": "[]",
                "stages_json": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
        return ExecutionTraceStore.get(db, project_id, tid)  # type: ignore[return-value]

    @staticmethod
    def update(
        db: Session,
        project_id: str,
        trace_id: str,
        *,
        status: Optional[str] = None,
        durations: Optional[dict[str, Any]] = None,
        failures: Optional[list[dict[str, Any]]] = None,
        retries: Optional[list[dict[str, Any]]] = None,
        approvals: Optional[list[dict[str, Any]]] = None,
        stages: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any] | None:
        ensure_m211_tables()
        current = ExecutionTraceStore.get(db, project_id, trace_id)
        if current is None:
            return None
        db.execute(
            text(
                """
                UPDATE m211_execution_traces
                SET status=:status,
                    durations_json=:durations_json,
                    failures_json=:failures_json,
                    retries_json=:retries_json,
                    approvals_json=:approvals_json,
                    stages_json=:stages_json,
                    updated_at=:updated_at
                WHERE id=:id AND project_id=:project_id
                """
            ),
            {
                "status": status or current["status"],
                "durations_json": json.dumps(durations if durations is not None else current["durations"], ensure_ascii=False),
                "failures_json": json.dumps(failures if failures is not None else current["failures"], ensure_ascii=False),
                "retries_json": json.dumps(retries if retries is not None else current["retries"], ensure_ascii=False),
                "approvals_json": json.dumps(approvals if approvals is not None else current["approvals"], ensure_ascii=False),
                "stages_json": json.dumps(stages if stages is not None else current["stages"], ensure_ascii=False),
                "updated_at": _now(),
                "id": trace_id,
                "project_id": project_id,
            },
        )
        db.commit()
        return ExecutionTraceStore.get(db, project_id, trace_id)

    @staticmethod
    def get(db: Session, project_id: str, trace_id: str) -> dict[str, Any] | None:
        ensure_m211_tables()
        row = db.execute(
            text("SELECT * FROM m211_execution_traces WHERE id=:id AND project_id=:project_id"),
            {"id": trace_id, "project_id": project_id},
        ).mappings().fetchone()
        return ExecutionTraceStore._row(row) if row else None

    @staticmethod
    def list_for_project(db: Session, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        ensure_m211_tables()
        rows = db.execute(
            text(
                """
                SELECT * FROM m211_execution_traces
                WHERE project_id=:project_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"project_id": project_id, "limit": max(1, min(limit, 200))},
        ).mappings().fetchall()
        return [ExecutionTraceStore._row(r) for r in rows]

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "modelUsed": row["model_used"],
            "specialistGraph": json.loads(row["specialist_graph_json"] or "[]"),
            "brief": row["brief"],
            "status": row["status"],
            "durations": json.loads(row["durations_json"] or "{}"),
            "failures": json.loads(row["failures_json"] or "[]"),
            "retries": json.loads(row["retries_json"] or "[]"),
            "approvals": json.loads(row["approvals_json"] or "[]"),
            "stages": json.loads(row["stages_json"] or "[]"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
