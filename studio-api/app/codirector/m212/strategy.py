"""Versioned strategy JSON packs (not model fine-tuning)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m212_tables
from .safety import AdaptiveLearningSafetyError

DEFAULT_STRATEGY_PACK: dict[str, Any] = {
    "decisionHeuristics": {
        "preferVerifiedSignals": True,
        "boostContinuityLessons": True,
        "requireApprovalForSystem": True,
    },
    "specialistWeightHints": {
        "continuity-analyst": 1.1,
        "qa-reviewer": 1.05,
        "director": 1.0,
    },
    "retrievalBoosts": {
        "activeLessons": 1.2,
        "projectMemory": 1.0,
    },
    "notes": "Default M2.12 strategy pack - structured policy only, no weight updates.",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_pack(
    db: Session,
    *,
    name: str,
    pack: Optional[dict[str, Any]] = None,
    version: int = 1,
) -> dict[str, Any]:
    ensure_m212_tables()
    pid = str(uuid.uuid4())
    body = pack or dict(DEFAULT_STRATEGY_PACK)
    db.execute(
        text(
            """
            INSERT INTO m212_strategy_packs
            (id, name, version, status, pack_json, created_at, activated_at, retired_at)
            VALUES
            (:id, :name, :version, 'candidate', :pack_json, :created_at, NULL, NULL)
            """
        ),
        {
            "id": pid,
            "name": name,
            "version": int(version),
            "pack_json": json.dumps(body, ensure_ascii=False),
            "created_at": _now(),
        },
    )
    db.commit()
    row = get_pack(db, pid)
    assert row is not None
    return row


def get_pack(db: Session, pack_id: str) -> dict[str, Any] | None:
    ensure_m212_tables()
    row = db.execute(
        text("SELECT * FROM m212_strategy_packs WHERE id=:id"),
        {"id": pack_id},
    ).mappings().fetchone()
    return _row(row) if row else None


def list_packs(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    ensure_m212_tables()
    rows = db.execute(
        text(
            """
            SELECT * FROM m212_strategy_packs
            ORDER BY created_at DESC LIMIT :limit
            """
        ),
        {"limit": max(1, min(limit, 200))},
    ).mappings().fetchall()
    return [_row(r) for r in rows]


def get_active_pack(db: Session) -> dict[str, Any] | None:
    ensure_m212_tables()
    row = db.execute(
        text(
            """
            SELECT * FROM m212_strategy_packs
            WHERE status = 'active'
            ORDER BY activated_at DESC
            LIMIT 1
            """
        )
    ).mappings().fetchone()
    return _row(row) if row else None


def activate_pack(db: Session, pack_id: str) -> dict[str, Any]:
    ensure_m212_tables()
    pack = get_pack(db, pack_id)
    if pack is None:
        raise AdaptiveLearningSafetyError("Strategy pack not found")
    # Retire currently active packs (audit via status change; rows retained).
    db.execute(
        text(
            """
            UPDATE m212_strategy_packs
            SET status = 'retired', retired_at = :now
            WHERE status = 'active'
            """
        ),
        {"now": _now()},
    )
    db.execute(
        text(
            """
            UPDATE m212_strategy_packs
            SET status = 'active', activated_at = :now, retired_at = NULL
            WHERE id = :id
            """
        ),
        {"id": pack_id, "now": _now()},
    )
    db.commit()
    updated = get_pack(db, pack_id)
    assert updated is not None
    return updated


def rollback_pack(db: Session, pack_id: str) -> dict[str, Any]:
    """Rollback active pack to retired; optionally re-activate previous candidate/retired."""

    ensure_m212_tables()
    pack = get_pack(db, pack_id)
    if pack is None:
        raise AdaptiveLearningSafetyError("Strategy pack not found")
    db.execute(
        text(
            """
            UPDATE m212_strategy_packs
            SET status = 'retired', retired_at = :now
            WHERE id = :id
            """
        ),
        {"id": pack_id, "now": _now()},
    )
    db.commit()
    # Prefer most recently retired other pack as active fallback.
    prev = db.execute(
        text(
            """
            SELECT * FROM m212_strategy_packs
            WHERE id != :id AND status = 'retired'
            ORDER BY retired_at DESC
            LIMIT 1
            """
        ),
        {"id": pack_id},
    ).mappings().fetchone()
    if prev:
        return activate_pack(db, prev["id"])
    updated = get_pack(db, pack_id)
    assert updated is not None
    return updated


def ensure_default_active(db: Session) -> dict[str, Any]:
    active = get_active_pack(db)
    if active:
        return active
    pack = create_pack(db, name="default-m212", pack=DEFAULT_STRATEGY_PACK, version=1)
    return activate_pack(db, pack["id"])


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "version": int(row["version"]),
        "status": row["status"],
        "pack": json.loads(row["pack_json"] or "{}"),
        "createdAt": row["created_at"],
        "activatedAt": row["activated_at"],
        "retiredAt": row["retired_at"],
    }
