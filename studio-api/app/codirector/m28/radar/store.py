"""Persistence for M2.8 model radar entries and watchlist."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RadarStore:
    @staticmethod
    def upsert_entry(
        db: Session,
        *,
        source: str,
        source_key: str,
        display_name: str,
        classification: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_m28_tables()
        existing = db.execute(
            text(
                "SELECT id, source, source_key, display_name, classification, metadata_json, created_at "
                "FROM m28_model_entries WHERE source = :source AND source_key = :source_key"
            ),
            {"source": source, "source_key": source_key},
        ).mappings().first()
        if existing:
            db.execute(
                text(
                    "UPDATE m28_model_entries SET display_name = :display_name, "
                    "classification = :classification, metadata_json = :metadata_json "
                    "WHERE id = :id"
                ),
                {
                    "id": existing["id"],
                    "display_name": display_name,
                    "classification": classification,
                    "metadata_json": json.dumps(metadata or {}),
                },
            )
            db.commit()
            return RadarStore.get_entry(db, existing["id"])  # type: ignore[return-value]

        entry_id = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_model_entries "
                "(id, source, source_key, display_name, classification, metadata_json, created_at) "
                "VALUES (:id, :source, :source_key, :display_name, :classification, :metadata_json, :created_at)"
            ),
            {
                "id": entry_id,
                "source": source,
                "source_key": source_key,
                "display_name": display_name,
                "classification": classification,
                "metadata_json": json.dumps(metadata or {}),
                "created_at": _now(),
            },
        )
        db.commit()
        return RadarStore.get_entry(db, entry_id)  # type: ignore[return-value]

    @staticmethod
    def get_entry(db: Session, entry_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, source, source_key, display_name, classification, metadata_json, created_at "
                "FROM m28_model_entries WHERE id = :id"
            ),
            {"id": entry_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "source": row["source"],
            "sourceKey": row["source_key"],
            "displayName": row["display_name"],
            "classification": row["classification"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "createdAt": str(row["created_at"]),
            "installAction": None
            if row["classification"] == "announcement_only"
            else "plan_install",
        }

    @staticmethod
    def list_entries(db: Session) -> list[dict[str, Any]]:
        ensure_m28_tables()
        rows = db.execute(
            text(
                "SELECT id FROM m28_model_entries ORDER BY created_at DESC"
            )
        ).fetchall()
        out: list[dict[str, Any]] = []
        for (entry_id,) in rows:
            item = RadarStore.get_entry(db, entry_id)
            if item:
                out.append(item)
        return out

    @staticmethod
    def add_watchlist(
        db: Session, *, entry_id: str, project_id: str | None = None
    ) -> dict[str, Any]:
        ensure_m28_tables()
        wid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_watchlist (id, entry_id, project_id, created_at) "
                "VALUES (:id, :entry_id, :project_id, :created_at)"
            ),
            {
                "id": wid,
                "entry_id": entry_id,
                "project_id": project_id,
                "created_at": _now(),
            },
        )
        db.commit()
        return {"id": wid, "entryId": entry_id, "projectId": project_id}

    @staticmethod
    def list_watchlist(db: Session, project_id: str | None = None) -> list[dict[str, Any]]:
        ensure_m28_tables()
        if project_id:
            rows = db.execute(
                text(
                    "SELECT id, entry_id, project_id, created_at FROM m28_watchlist "
                    "WHERE project_id = :project_id ORDER BY created_at DESC"
                ),
                {"project_id": project_id},
            ).mappings().all()
        else:
            rows = db.execute(
                text(
                    "SELECT id, entry_id, project_id, created_at FROM m28_watchlist "
                    "ORDER BY created_at DESC"
                )
            ).mappings().all()
        return [
            {
                "id": r["id"],
                "entryId": r["entry_id"],
                "projectId": r["project_id"],
                "createdAt": str(r["created_at"]),
            }
            for r in rows
        ]
