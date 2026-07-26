"""Versioned, searchable production memory for M2.11."""

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


class ProductionMemoryStore:
    @staticmethod
    def upsert(
        db: Session,
        *,
        project_id: str,
        content: str,
        category: str = "note",
        scene_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> dict[str, Any]:
        ensure_m211_tables()
        mid = memory_id or str(uuid.uuid4())
        now = _now()
        existing = db.execute(
            text("SELECT version FROM m211_memory_items WHERE id = :id"),
            {"id": mid},
        ).fetchone()
        version = int(existing[0]) + 1 if existing else 1
        payload = {
            "id": mid,
            "project_id": project_id,
            "scene_id": scene_id,
            "category": category,
            "content": content,
            "tags_json": json.dumps(tags or [], ensure_ascii=False),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "version": version,
            "created_at": now if not existing else None,
            "updated_at": now,
        }
        if existing:
            db.execute(
                text(
                    """
                    UPDATE m211_memory_items
                    SET scene_id=:scene_id, category=:category, content=:content,
                        tags_json=:tags_json, metadata_json=:metadata_json,
                        version=:version, updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                {k: v for k, v in payload.items() if k != "created_at" and k != "project_id"},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO m211_memory_items
                    (id, project_id, scene_id, category, content, tags_json, metadata_json, version, created_at, updated_at)
                    VALUES
                    (:id, :project_id, :scene_id, :category, :content, :tags_json, :metadata_json, :version, :created_at, :updated_at)
                    """
                ),
                payload,
            )
        db.commit()
        return ProductionMemoryStore.get(db, project_id, mid)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, project_id: str, memory_id: str) -> dict[str, Any] | None:
        ensure_m211_tables()
        row = db.execute(
            text(
                """
                SELECT id, project_id, scene_id, category, content, tags_json, metadata_json, version, created_at, updated_at
                FROM m211_memory_items
                WHERE id=:id AND project_id=:project_id
                """
            ),
            {"id": memory_id, "project_id": project_id},
        ).mappings().fetchone()
        return ProductionMemoryStore._row(row) if row else None

    @staticmethod
    def search(
        db: Session,
        *,
        project_id: str,
        query: str = "",
        scene_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        ensure_m211_tables()
        clauses = ["project_id = :project_id"]
        params: dict[str, Any] = {"project_id": project_id, "limit": max(1, min(limit, 200))}
        if scene_id:
            clauses.append("(scene_id = :scene_id OR scene_id IS NULL)")
            params["scene_id"] = scene_id
        if category:
            clauses.append("category = :category")
            params["category"] = category
        if query.strip():
            clauses.append("(content LIKE :q OR tags_json LIKE :q OR metadata_json LIKE :q)")
            params["q"] = f"%{query.strip()}%"
        sql = f"""
            SELECT id, project_id, scene_id, category, content, tags_json, metadata_json, version, created_at, updated_at
            FROM m211_memory_items
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT :limit
        """
        rows = db.execute(text(sql), params).mappings().fetchall()
        return [ProductionMemoryStore._row(r) for r in rows]

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "category": row["category"],
            "content": row["content"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "version": int(row["version"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
