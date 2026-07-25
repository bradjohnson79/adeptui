"""Opt-in, forward-only database migration foundations."""

from .m001_initial import MIGRATION as M001
from .m002_production_bible import MIGRATION as M002
from .m003_codirector_tools import MIGRATION as M003
from .m004_bible_domain import MIGRATION as M004
from .m005_codirector_intelligence import MIGRATION as M005
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003, M004, M005))

__all__ = [
    "ChecksumMismatchError",
    "DEFAULT_REGISTRY",
    "M001",
    "M002",
    "M003",
    "M004",
    "M005",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]
