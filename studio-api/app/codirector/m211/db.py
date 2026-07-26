"""Ensure M2.11 tables exist (migration + runtime safety)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from ...db import engine as default_engine
from ...migrations import DEFAULT_REGISTRY, MigrationRunner
from ...migrations.m014_production_intelligence import _DDL

__all__ = ["ensure_m211_tables", "_DDL"]


def ensure_m211_tables(eng: Engine | None = None) -> None:
    eng = eng or default_engine
    try:
        MigrationRunner(eng, DEFAULT_REGISTRY).apply_pending()
    except Exception:
        with eng.begin() as conn:
            for stmt in _DDL:
                conn.exec_driver_sql(stmt)
