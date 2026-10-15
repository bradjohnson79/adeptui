"""Opt-in, forward-only database migration foundations."""

from .m001_initial import MIGRATION as M001
from .m002_production_bible import MIGRATION as M002
from .m003_codirector_tools import MIGRATION as M003
from .m004_bible_domain import MIGRATION as M004
from .m005_codirector_intelligence import MIGRATION as M005
from .m006_codirector_vision import MIGRATION as M006
from .m007_timeline_reference_bindings import MIGRATION as M007
from .m008_production_executive import MIGRATION as M008
from .m010_scene_summary import MIGRATION as M010
from .m011_production_context import MIGRATION as M011
from .m012_capability_intelligence import MIGRATION as M012
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003, M004, M005, M006, M007, M008, M010, M011, M012))

__all__ = [
    "ChecksumMismatchError",
    "DEFAULT_REGISTRY",
    "M001",
    "M002",
    "M003",
    "M004",
    "M005",
    "M006",
    "M007",
    "M008",
    "M010",
    "M011",
    "M012",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]