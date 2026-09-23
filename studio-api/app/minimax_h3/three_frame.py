"""Three-frame planning helpers for MiniMax H3."""

from __future__ import annotations

from .contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment, H3ThreeFrameInterval, H3ThreeFramePlan


def creator_disclosure() -> str:
    return (
        "Local MiniMax H3 runs First + Last on one Route A graph "
        "(MiniMaxH3ImageToVideo). When Middle is set, Adept anchors it with "
        "MiniMaxH3AddGuide at mid length. Empty Middle keeps the same first+last "
        "graph with no guide node — never a fake middle from first/last."
    )


def validate_three_distinct_asset_roles(assignments: list[H3ReferenceAssignment]) -> dict[str, H3ReferenceAssignment]:
    """Legacy segmented-a validator (requires three distinct roles). Prefer optional-middle helper for CREATE."""
    required = ("start", "middle", "end")
    role_map = {item.role: item for item in assignments if item.role in required}
    missing = [role for role in required if role not in role_map]
    if missing:
        raise ValueError(f"Three-frame planning needs a {', '.join(missing)} frame.")
    asset_ids = [role_map[role].assetId for role in required]
    if len(set(asset_ids)) != 3:
        raise ValueError("Use three different frames for Start, Middle, and End.")
    return {role: role_map[role] for role in required}


def validate_first_last_optional_middle(
    assignments: list[H3ReferenceAssignment],
) -> dict[str, H3ReferenceAssignment | None]:
    """CREATE 3 Frame contract: First+Last required; Middle optional and distinct when set."""
    role_map = {item.role: item for item in assignments if item.role in {"start", "middle", "end"}}
    if "start" not in role_map or not str(role_map["start"].assetId or "").strip():
        raise ValueError("Add a First Frame before MiniMax H3 3 Frame.")
    if "end" not in role_map or not str(role_map["end"].assetId or "").strip():
        raise ValueError("Add a Last Frame before MiniMax H3 3 Frame.")
    middle = role_map.get("middle")
    if middle and not str(middle.assetId or "").strip():
        middle = None
    start_id = role_map["start"].assetId
    end_id = role_map["end"].assetId
    if start_id == end_id:
        raise ValueError("First and Last frames must be different stills.")
    if middle:
        mid_id = middle.assetId
        if mid_id in {start_id, end_id}:
            raise ValueError("Middle Frame must be a different still than First and Last.")
    return {"start": role_map["start"], "middle": middle, "end": role_map["end"]}


def build_add_guide_plan(request: AdeptMiniMaxH3Request) -> H3ThreeFramePlan:
    """Native local CREATE plan: one Route A FLF run ± optional AddGuide."""
    roles = validate_first_last_optional_middle(request.referenceAssignments)
    middle = roles["middle"]
    notes = [
        "First and Last stills bind MiniMaxH3ImageToVideo.first_frame / last_frame.",
        "Empty Middle omits MiniMaxH3AddGuide and the third LoadImage (same as proven local 2-frame).",
        "Partner Hailuo FLF is not used for Adept 3 Frame middle.",
    ]
    if middle:
        notes.insert(
            1,
            "Middle still binds MiniMaxH3AddGuide at frame_idx = length // 2; guider consumes AddGuide.",
        )
    return H3ThreeFramePlan(
        strategy="middle-guidance-b",
        nativeSupported=True,
        disclosureText=creator_disclosure(),
        intervals=[],
        assemblyNotes=notes,
    )


def build_segmented_plan(request: AdeptMiniMaxH3Request) -> H3ThreeFramePlan:
    """Legacy two-pass assembly — not the CREATE 3 Frame execute path."""
    roles = validate_three_distinct_asset_roles(request.referenceAssignments)
    return H3ThreeFramePlan(
        strategy="segmented-a",
        nativeSupported=False,
        disclosureText=(
            "Legacy segmented assembly: Start to Middle, then Middle to End. "
            "CREATE 3 Frame uses native AddGuide instead."
        ),
        intervals=[
            H3ThreeFrameInterval(
                label="Start-Middle",
                startRole="start",
                endRole="middle",
                startAssetId=roles["start"].assetId,
                endAssetId=roles["middle"].assetId,
                creatorGoal="Guide the motion from the opening frame into the midpoint beat.",
            ),
            H3ThreeFrameInterval(
                label="Middle-End",
                startRole="middle",
                endRole="end",
                startAssetId=roles["middle"].assetId,
                endAssetId=roles["end"].assetId,
                creatorGoal="Carry the midpoint beat into the final frame.",
            ),
        ],
        assemblyNotes=[
            "Interval one covers Start to Middle.",
            "Interval two covers Middle to End.",
            "Not used for CREATE 3 Frame execute — prefer build_add_guide_plan.",
        ],
    )
