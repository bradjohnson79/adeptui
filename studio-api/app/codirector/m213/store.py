"""Persistence helpers for M2.13 records."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jid() -> str:
    return str(uuid.uuid4())


def _loads(raw: Any, default: Any) -> Any:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


class M213Store:
    @staticmethod
    def ensure() -> None:
        ensure_m213_tables()

    @staticmethod
    def log_capability(
        db: Session,
        *,
        capability_id: str,
        action: str,
        project_id: str | None = None,
        payload: dict | None = None,
        reversible: bool = True,
    ) -> dict[str, Any]:
        M213Store.ensure()
        row_id = _jid()
        db.execute(
            text(
                "INSERT INTO m213_capability_log "
                "(id, project_id, capability_id, action, reversible, payload_json, created_at) "
                "VALUES (:id, :project_id, :capability_id, :action, :reversible, :payload_json, :created_at)"
            ),
            {
                "id": row_id,
                "project_id": project_id,
                "capability_id": capability_id,
                "action": action,
                "reversible": 1 if reversible else 0,
                "payload_json": json.dumps(payload or {}),
                "created_at": _now(),
            },
        )
        db.commit()
        return {"id": row_id, "capabilityId": capability_id, "action": action}

    @staticmethod
    def record_approval(
        db: Session,
        *,
        project_id: str,
        gate: str,
        subject_id: str,
        approved: bool,
        actor: str = "user",
        note: str = "",
    ) -> dict[str, Any]:
        M213Store.ensure()
        row_id = _jid()
        db.execute(
            text(
                "INSERT INTO m213_approvals "
                "(id, project_id, gate, subject_id, approved, actor, note, created_at) "
                "VALUES (:id, :project_id, :gate, :subject_id, :approved, :actor, :note, :created_at)"
            ),
            {
                "id": row_id,
                "project_id": project_id,
                "gate": gate,
                "subject_id": subject_id,
                "approved": 1 if approved else 0,
                "actor": actor,
                "note": note,
                "created_at": _now(),
            },
        )
        db.commit()
        return {
            "id": row_id,
            "gate": gate,
            "subjectId": subject_id,
            "approved": approved,
            "silentAdvance": False,
        }

    @staticmethod
    def latest_approval(db: Session, *, gate: str, subject_id: str) -> Optional[dict[str, Any]]:
        M213Store.ensure()
        row = db.execute(
            text(
                "SELECT id, project_id, gate, subject_id, approved, actor, note, created_at "
                "FROM m213_approvals WHERE gate = :gate AND subject_id = :subject_id "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"gate": gate, "subject_id": subject_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "gate": row["gate"],
            "subjectId": row["subject_id"],
            "approved": bool(row["approved"]),
            "actor": row["actor"],
            "note": row["note"],
            "createdAt": str(row["created_at"]),
        }

    @staticmethod
    def save_version(
        db: Session,
        *,
        project_id: str,
        subject_kind: str,
        subject_id: str,
        version: int,
        snapshot: dict,
    ) -> dict[str, Any]:
        M213Store.ensure()
        row_id = _jid()
        db.execute(
            text(
                "INSERT INTO m213_versions "
                "(id, project_id, subject_kind, subject_id, version, snapshot_json, created_at) "
                "VALUES (:id, :project_id, :subject_kind, :subject_id, :version, :snapshot_json, :created_at)"
            ),
            {
                "id": row_id,
                "project_id": project_id,
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "version": version,
                "snapshot_json": json.dumps(snapshot),
                "created_at": _now(),
            },
        )
        db.commit()
        return {"id": row_id, "version": version, "subjectKind": subject_kind, "subjectId": subject_id}

    @staticmethod
    def get_version(
        db: Session, *, subject_kind: str, subject_id: str, version: int
    ) -> Optional[dict[str, Any]]:
        M213Store.ensure()
        row = db.execute(
            text(
                "SELECT id, project_id, subject_kind, subject_id, version, snapshot_json, created_at "
                "FROM m213_versions WHERE subject_kind = :k AND subject_id = :s AND version = :v"
            ),
            {"k": subject_kind, "s": subject_id, "v": version},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "subjectKind": row["subject_kind"],
            "subjectId": row["subject_id"],
            "version": int(row["version"]),
            "snapshot": _loads(row["snapshot_json"], {}),
            "createdAt": str(row["created_at"]),
        }
