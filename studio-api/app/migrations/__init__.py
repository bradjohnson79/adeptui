"""Opt-in, forward-only database migration foundations."""

from .m001_initial import MIGRATION as M001
from .m002_production_bible import MIGRATION as M002
from .m010_scene_summary import MIGRATION as M010
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M010))

__all__ = [
    "ChecksumMismatchError",
    "DEFAULT_REGISTRY",
    "M001",
    "M002",
    "M010",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]
