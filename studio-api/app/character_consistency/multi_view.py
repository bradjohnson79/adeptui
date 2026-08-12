"""Contracts for choosing between unified-sheet and anchored sequential views."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .reference_roles import ReferenceRole


class MultiViewMethod(str, Enum):
    METHOD_A_UNIFIED_SHEET = "method_a_unified_sheet"
    METHOD_B_ANCHORED_SEQUENTIAL = "method_b_anchored_sequential"


class MultiViewSelectorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_views: int = Field(..., ge=1)
    approved_anchor_asset_id: str | None = None
    turnaround_required: bool = False
    sheet_workflow_available: bool = True
    sequential_workflow_available: bool = True
    independent_backgrounds_allowed: bool = False
    reference_roles: list[ReferenceRole] = Field(default_factory=list)


class MultiViewSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: MultiViewMethod
    rationale: str
    required_reference_roles: list[ReferenceRole] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


def select_multi_view_method(selector_input: MultiViewSelectorInput) -> MultiViewSelection:
    if selector_input.turnaround_required or (
        selector_input.requested_views >= 4 and selector_input.sheet_workflow_available
    ):
        return MultiViewSelection(
            method=MultiViewMethod.METHOD_A_UNIFIED_SHEET,
            rationale="Use one coordinated sheet when many locked views must agree in a single pass.",
            required_reference_roles=[
                ReferenceRole.IDENTITY,
                ReferenceRole.FACE,
                ReferenceRole.HAIR,
                ReferenceRole.WARDROBE,
                ReferenceRole.BODY_PROPORTIONS,
            ],
            prerequisites=[
                "Sheet workflow must support the requested view layout.",
                "Identity and style references should be approved before production continuity use.",
            ],
        )

    if selector_input.approved_anchor_asset_id and selector_input.sequential_workflow_available:
        return MultiViewSelection(
            method=MultiViewMethod.METHOD_B_ANCHORED_SEQUENTIAL,
            rationale="Use an approved anchor frame when generating one follow-on view at a time.",
            required_reference_roles=[
                ReferenceRole.IDENTITY,
                ReferenceRole.FACE,
                ReferenceRole.HAIR,
            ],
            prerequisites=[
                "Approved anchor asset must stay in the same project library.",
                "Sequential passes should inherit the same seed or reviewed refine seed.",
            ],
        )

    return MultiViewSelection(
        method=MultiViewMethod.METHOD_A_UNIFIED_SHEET,
        rationale="Default to a unified sheet when no approved anchor is available for sequential locking.",
        required_reference_roles=[
            ReferenceRole.IDENTITY,
            ReferenceRole.FACE,
            ReferenceRole.HAIR,
            ReferenceRole.WARDROBE,
        ],
        prerequisites=[
            "If the sheet workflow is unavailable, escalate to a sequential implementation owner.",
        ],
    )
