"""Ensure M3.1a tables exist (migration + runtime safety)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from ..db import engine as default_engine
from ..migrations import DEFAULT_REGISTRY, MigrationRunner
from ..migrations.m020_templates_presets_foundation import apply as apply_m020


def ensure_m31a_tables(eng: Engine | None = None) -> None:
    eng = eng or default_engine
    try:
        MigrationRunner(eng, DEFAULT_REGISTRY).apply_pending()
    except Exception:
        with eng.begin() as conn:
            apply_m020(conn)
