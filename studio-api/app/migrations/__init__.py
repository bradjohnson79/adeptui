"""Opt-in, forward-only database migration foundations."""

from .m001_initial import MIGRATION as M001
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001,))

__all__ = [
    "ChecksumMismatchError",
    "DEFAULT_REGISTRY",
    "M001",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]
