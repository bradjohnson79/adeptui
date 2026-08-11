"""M031: Character Profile visual_description + visual_style columns.

Adds first-class fields for the embedded Character Creator:
- visual_description: long-form physical/visual appearance text (distinct from
  bio/personality, which lives in `description`).
- visual_style: creator-facing style key (Live Action / Anime / 3D / etc.),
  resolved against style_intelligence.registry.STYLE_REGISTRY at generation.

Backward compatible: existing rows default to blank strings.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0031"
CHECKSUM_SOURCE = "M031:character-visual-description-style:v1"

_DDL = [
    "ALTER TABLE character_profiles ADD COLUMN visual_description TEXT DEFAULT ''",
    "ALTER TABLE character_profiles ADD COLUMN visual_style TEXT DEFAULT ''",
]


def apply(connection: Connection) -> None:
    # SQLite: ADD COLUMN fails if already present — tolerate for re-runs.
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
    description="Character Profile visual_description + visual_style columns",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="SQLite cannot drop columns easily; leave unused columns.",
    reversible=False,
)
