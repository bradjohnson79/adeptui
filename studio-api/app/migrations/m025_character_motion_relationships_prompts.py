"""M025: Character Motion Profile, Relationship Graph, Prompt Package columns."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0025"
CHECKSUM_SOURCE = "M025:m42-w43-character-motion-relationships-prompts:v1"

_DDL = [
    "ALTER TABLE character_profiles ADD COLUMN motion_json TEXT DEFAULT '{}'",
    "ALTER TABLE character_profiles ADD COLUMN relationships_json TEXT DEFAULT '[]'",
    "ALTER TABLE character_profiles ADD COLUMN prompt_package_json TEXT DEFAULT '{}'",
    "ALTER TABLE character_profiles ADD COLUMN emotion_json TEXT DEFAULT '{}'",
]


def apply(connection: Connection) -> None:
    # SQLite: ADD COLUMN fails if already present — tolerate for re-runs
    for stmt in _DDL:
        try:
            connection.exec_driver_sql(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg:
                continue
            raise


MIGRATION = Migration(
    revision=REVISION,
    description="M42 W43 Character Motion, Relationships, Emotion, Prompt Package columns",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="SQLite cannot drop columns easily; leave unused columns.",
    reversible=False,
)
