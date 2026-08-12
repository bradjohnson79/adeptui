"""One-time idempotent migration: rename hero_portrait → hero_identity.

Amendment 2b. Legacy CharacterReferenceAssetRow rows persisted with
reference_role="hero_portrait" (before the full-body casting rename) are
rewritten to reference_role="hero_identity". canonical/approval_status flags
are preserved. The read-time alias in roles.py keeps unmigrated rows
resolvable during the migration window, so this migration is safe to run
once on startup and idempotent (skip if no hero_portrait rows remain).

Audit log: writes a single line to the standard app log recording the
count of rows rewritten (or "skipped: no legacy rows").
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIGRATION_KEY = "hero_identity_rename_v1"
MIGRATION_FLAG_TABLE = "character_traits"


def _migration_already_run(db: Session) -> bool:
    """Idempotency guard: a trait row marks that this migration ran.

    Uses the existing character_traits table on a well-known system profile
    id ("system-migration-state") so we don't introduce a new table.
    """
    try:
        result = db.execute(
            text(
                "SELECT value FROM character_traits "
                "WHERE character_profile_id = :pid AND key = :key LIMIT 1"
            ),
            {"pid": "system-migration-state", "key": MIGRATION_KEY},
        ).fetchone()
        return result is not None
    except Exception:
        # Table missing or unreadable — allow the migration attempt to proceed;
        # the UPDATE itself is idempotent.
        return False


def _mark_migration_run(db: Session, rewritten: int) -> None:
    try:
        db.execute(
            text(
                "INSERT INTO character_traits (id, character_profile_id, category, key, value, importance, canonical, provenance) "
                "VALUES (:id, :pid, :cat, :key, :val, 'optional', 0, 'USER_CONFIRMED')"
            ),
            {
                "id": f"migration-{MIGRATION_KEY}",
                "pid": "system-migration-state",
                "cat": "migration",
                "key": MIGRATION_KEY,
                "val": f'{{"rewritten": {rewritten}}}',
            },
        )
    except Exception:
        # Best-effort marker; the UPDATE itself is idempotent so a missing
        # marker just means we'll re-scan next startup (harmless).
        pass


def run_hero_identity_rename(db: Session) -> dict[str, Any]:
    """Rewrite legacy hero_portrait rows to hero_identity. Idempotent.

    Returns a small audit dict: {rewritten, skipped, already_run}.
    """
    if _migration_already_run(db):
        logger.info("hero_identity_rename: already run; skipping")
        return {"rewritten": 0, "skipped": True, "already_run": True}

    try:
        result = db.execute(
            text(
                "UPDATE character_reference_assets "
                "SET reference_role = 'hero_identity' "
                "WHERE reference_role = 'hero_portrait'"
            )
        )
        rewritten = result.rowcount or 0
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("hero_identity_rename: failed: %s", exc)
        return {"rewritten": 0, "skipped": True, "already_run": False, "error": str(exc)}

    _mark_migration_run(db, rewritten)
    try:
        db.commit()
    except Exception:
        db.rollback()

    logger.info("hero_identity_rename: rewrote %d rows", rewritten)
    return {"rewritten": rewritten, "skipped": False, "already_run": False}


def run_for_all_projects(db: Session) -> dict[str, Any]:
    """Entry point for app startup. Runs the rename once across all projects."""
    return run_hero_identity_rename(db)
