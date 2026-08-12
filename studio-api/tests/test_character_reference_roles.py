from __future__ import annotations

from app.character_consistency.multi_view import (
    MultiViewMethod,
    MultiViewSelectorInput,
    select_multi_view_method,
)
from app.character_consistency.reference_roles import (
    REFERENCE_ROLES,
    ReferenceRole,
    identity_roles,
    is_valid_role,
    normalize_roles,
    style_roles,
)


def test_reference_roles_cover_identity_and_style_contracts():
    assert ReferenceRole.IDENTITY.value in REFERENCE_ROLES
    assert ReferenceRole.FACE.value in identity_roles()
    assert ReferenceRole.ART_STYLE.value in style_roles()
    assert ReferenceRole.ENVIRONMENT.value in style_roles()
    assert not set(identity_roles()) & set(style_roles())


def test_normalize_roles_deduplicates_and_drops_unknown_values():
    normalized = normalize_roles(
        [
            "identity",
            "hair",
            "identity",
            "unknown",
            "camera",
        ]
    )

    assert normalized == ["identity", "hair", "camera"]
    assert is_valid_role("markings") is True
    assert is_valid_role("unknown") is False


def test_multi_view_selector_chooses_sheet_for_turnaround():
    selection = select_multi_view_method(
        MultiViewSelectorInput(
            requested_views=6,
            turnaround_required=True,
            reference_roles=[ReferenceRole.IDENTITY, ReferenceRole.FACE, ReferenceRole.HAIR],
        )
    )

    assert selection.method == MultiViewMethod.METHOD_A_UNIFIED_SHEET
    assert ReferenceRole.BODY_PROPORTIONS in selection.required_reference_roles


def test_multi_view_selector_prefers_anchor_for_sequential_refinement():
    selection = select_multi_view_method(
        MultiViewSelectorInput(
            requested_views=2,
            approved_anchor_asset_id="asset-anchor",
            reference_roles=[ReferenceRole.IDENTITY, ReferenceRole.FACE],
        )
    )

    assert selection.method == MultiViewMethod.METHOD_B_ANCHORED_SEQUENTIAL
