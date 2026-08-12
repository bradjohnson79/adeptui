"""Character consistency contracts for M42 Qwen-2512 work."""

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
