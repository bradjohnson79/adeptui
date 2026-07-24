"""Opt-in, forward-only database migration foundations."""

from .m001_initial import MIGRATION as M001
from .m002_production_bible import MIGRATION as M002
from .m003_codirector_tools import MIGRATION as M003
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003))

__all__ = [
    "ChecksumMismatchError",
    "DEFAULT_REGISTRY",
    "M001",
    "M002",
    "M003",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]
