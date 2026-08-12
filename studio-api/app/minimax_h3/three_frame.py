"""Three-frame planning helpers for MiniMax H3."""

from __future__ import annotations

from .contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment, H3ThreeFrameInterval, H3ThreeFramePlan


def creator_disclosure() -> str:
    return (
        "MiniMax H3 does not take three timed keyframes natively. "
        "Adept plans this as two guided beats: Start to Middle, then Middle to End."
    )


def validate_three_distinct_asset_roles(assignments: list[H3ReferenceAssignment]) -> dict[str, H3ReferenceAssignment]:
    required = ("start", "middle", "end")
    role_map = {item.role: item for item in assignments if item.role in required}
    missing = [role for role in required if role not in role_map]
    if missing:
        raise ValueError(f"Three-frame planning needs a {', '.join(missing)} frame.")
    asset_ids = [role_map[role].assetId for role in required]
    if len(set(asset_ids)) != 3:
        raise ValueError("Use three different frames for Start, Middle, and End.")
    return {role: role_map[role] for role in required}


def build_segmented_plan(request: AdeptMiniMaxH3Request) -> H3ThreeFramePlan:
    roles = validate_three_distinct_asset_roles(request.referenceAssignments)
    return H3ThreeFramePlan(
        strategy="segmented-a",
        nativeSupported=False,
        disclosureText=creator_disclosure(),
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
                creatorGoal="Carry the midpoint beat into the final frame without claiming a native three-keyframe run.",
            ),
        ],
        assemblyNotes=[
            "Interval one covers Start to Middle.",
            "Interval two covers Middle to End.",
            "Adept assembles the two intervals on the timeline after both passes are reviewed.",
        ],
    )
