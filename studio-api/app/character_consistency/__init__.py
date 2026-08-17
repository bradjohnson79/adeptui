"""Character consistency contracts for M42 Qwen-2512 work.

DEPRECATED / SUPERSEDED (Phase 8 cleanup, CDX-005)
--------------------------------------------------
This package is SUPERSEDED BY the canonical character identity store in
'app.character_identity/' (role taxonomy: 'app/character_identity/roles.py',
identity rows: CharacterProfileRow). Production code no longer imports these
modules; only the Knowledge Base doc picker ('knowledgebase_api.py'), the
hosted-provider capability label, and legacy tests reference the package name.

The package is quarantined, not deleted: existing tests
('test_character_deviation_report.py', 'test_character_reference_roles.py')
still exercise the contracts, and the Knowledge Base picker lists the package
name as a documentation label. Do not extend it; migrate consumers to
'app.character_identity' before building new features.
"""

from .correction_loop import CharacterCorrectionPlan, CorrectionInstruction, build_correction_plan
from .deviation_report import CharacterDeviationFinding, CharacterDeviationReport, build_deviation_report
from .generation_recipe import (
    GenerationRecipe,
    RecipeLoRA,
    RecipeReferenceAsset,
    RecipeResolution,
    load_generation_recipe,
    save_generation_recipe,
)
from .multi_view import (
    MultiViewMethod,
    MultiViewSelection,
    MultiViewSelectorInput,
    select_multi_view_method,
)
from .reference_roles import REFERENCE_ROLES, REFERENCE_ROLE_DESCRIPTIONS, ReferenceRole, is_valid_role
from .seed_policy import SEED_POLICIES, SeedPolicy, SeedPolicyContract, choose_seed_policy

__all__ = [
    "CharacterCorrectionPlan",
    "CharacterDeviationFinding",
    "CharacterDeviationReport",
    "CorrectionInstruction",
    "GenerationRecipe",
    "MultiViewMethod",
    "MultiViewSelection",
    "MultiViewSelectorInput",
    "REFERENCE_ROLES",
    "REFERENCE_ROLE_DESCRIPTIONS",
    "RecipeLoRA",
    "RecipeReferenceAsset",
    "RecipeResolution",
    "ReferenceRole",
    "SEED_POLICIES",
    "SeedPolicy",
    "SeedPolicyContract",
    "build_correction_plan",
    "build_deviation_report",
    "choose_seed_policy",
    "is_valid_role",
    "load_generation_recipe",
    "save_generation_recipe",
    "select_multi_view_method",
]
