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
from .m013_production_suite import MIGRATION as M013
from .m014_production_intelligence import MIGRATION as M014
from .m015_adaptive_learning import MIGRATION as M015
from .m016_virtual_environment_studio import MIGRATION as M016
from .m017_codirector_unified_experience import MIGRATION as M017
from .m018_model_intelligence_experience import MIGRATION as M018
from .m019_language_intelligence import MIGRATION as M019
from .m020_templates_presets_foundation import MIGRATION as M020
from .m021_character_identity import MIGRATION as M021
from .m022_durable_production_plans import MIGRATION as M022
from .m023_continuity_identity import MIGRATION as M023
from .m024_scene_references import MIGRATION as M024
from .m025_character_motion_relationships_prompts import MIGRATION as M025
from .m026_posecraft_persistence import MIGRATION as M026
from .m027_posecraft_custom_poses import MIGRATION as M027
from .m028_codirector_conversation_events import MIGRATION as M028
from .m029_multi_shot import MIGRATION as M029
from .m030_multi_shot_timeline import MIGRATION as M030
from .registry import Migration, MigrationRegistry
from .runner import ChecksumMismatchError, MigrationRun, MigrationRunner

DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003, M004, M005, M006, M007, M008, M010, M011, M012, M013, M014, M015, M016, M017, M018, M019, M020, M021, M022, M023, M024, M025, M026, M027, M028, M029, M030))

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
    "M013",
    "M014",
    "M015",
    "M016",
    "M017",
    "M018",
    "M019",
    "M020",
    "M021",
    "M022",
    "M023",
    "M024",
    "M025",
    "M026",
    "M027",
    "M028",
    "M029",
    "M030",
    "Migration",
    "MigrationRegistry",
    "MigrationRun",
    "MigrationRunner",
]
