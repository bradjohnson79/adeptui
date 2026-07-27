"""Persistence helpers for M2.14 unified experience."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m214_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _jid(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class M214Store:
    @staticmethod
    def log_capability(
        db: Session,
        *,
        capability_id: str,
        action: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ensure_m214_tables()
        row_id = str(uuid4())
        db.execute(
            text(
                "INSERT INTO m214_capability_invokes "
                "(id, project_id, capability_id, action, payload_json, created_at) "
                "VALUES (:id, :pid, :cid, :action, :payload, :ts)"
            ),
            {
                "id": row_id,
                "pid": project_id,
                "cid": capability_id,
                "action": action,
                "payload": _jid(payload or {}),
                "ts": _now(),
            },
        )
        db.commit()
        return {"id": row_id, "capabilityId": capability_id, "action": action}

    @staticmethod
    def upsert_stage(db: Session, project_id: str, stage: str, extra: Optional[dict] = None) -> dict:
        ensure_m214_tables()
        ts = _now()
        row = db.execute(
            text("SELECT id FROM m214_project_stages WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        payload = {"stage": stage, **(extra or {})}
        if row:
            db.execute(
                text(
                    "UPDATE m214_project_stages SET stage = :stage, stage_json = :j, updated_at = :ts "
                    "WHERE project_id = :pid"
                ),
                {"stage": stage, "j": _jid(payload), "ts": ts, "pid": project_id},
            )
            row_id = row[0]
        else:
            row_id = str(uuid4())
            db.execute(
                text(
                    "INSERT INTO m214_project_stages (id, project_id, stage, stage_json, updated_at) "
                    "VALUES (:id, :pid, :stage, :j, :ts)"
                ),
                {"id": row_id, "pid": project_id, "stage": stage, "j": _jid(payload), "ts": ts},
            )
        db.commit()
        return {"id": row_id, "projectId": project_id, "stage": stage}

    @staticmethod
    def get_stage(db: Session, project_id: str) -> dict[str, Any]:
        ensure_m214_tables()
        row = db.execute(
            text("SELECT id, stage, stage_json FROM m214_project_stages WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if not row:
            return {"projectId": project_id, "stage": "idea", "payload": {}}
        return {
            "id": row[0],
            "projectId": project_id,
            "stage": row[1],
            "payload": json.loads(row[2] or "{}"),
        }

    @staticmethod
    def save_json_row(
        db: Session,
        table: str,
        columns: dict[str, Any],
    ) -> str:
        ensure_m214_tables()
        row_id = columns.get("id") or str(uuid4())
        columns = {**columns, "id": row_id}
        cols = ", ".join(columns.keys())
        binds = ", ".join(f":{k}" for k in columns)
        db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({binds})"), columns)
        db.commit()
        return row_id
