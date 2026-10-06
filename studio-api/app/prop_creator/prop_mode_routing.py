"""Co-Director Prop mode routing sketch (Standard vs Advanced).

Honest heuristics only — creator can override via PropEntity.mode.
Does not silently rewrite primary_prompt / description.
Not yet wired into chat handlers; callable sketch for UX / CD integration.
"""

from __future__ import annotations

from typing import Any, Literal

PropRouteMode = Literal["standard", "advanced", "ambiguous"]

ADVANCED_KEYWORDS = (
    "spacecraft",
    "spaceship",
    "starship",
    "vehicle",
    "car",
    "truck",
    "tank",
    "aircraft",
    "airplane",
    "aeroplane",
    "jet",
    "helicopter",
    "mech",
    "mecha",
    "robot suit",
    "walker",
    "dropship",
    "fighter craft",
)

STANDARD_KEYWORDS = (
    "sword",
    "knife",
    "dagger",
    "mug",
    "cup",
    "keycard",
    "key",
    "book",
    "phone",
    "pistol",
    "gun",
    "ring",
    "necklace",
    "amulet",
    "bottle",
    "lantern",
    "torch",
    "briefcase",
    "bag",
    "hat",
    "helmet",  # simple wearables stay standard unless mech/vehicle context
)


def classify_prop_mode(text: str, *, advanced_type: str | None = None) -> dict[str, Any]:
    """Return mode suggestion. Fail honest when ambiguous — never invent Advanced silently."""
    blob = (text or "").strip().lower()
    if advanced_type:
        at = advanced_type.strip().lower()
        if at in {"spacecraft", "vehicle", "aircraft", "mech"}:
            return {
                "mode": "advanced",
                "confidence": "high",
                "reason": f"advanced_type={at}",
                "suggested_advanced_type": at,
            }
        if at == "other":
            return {
                "mode": "advanced",
                "confidence": "medium",
                "reason": "advanced_type=other",
                "suggested_advanced_type": "other",
            }

    if not blob:
        return {
            "mode": "ambiguous",
            "confidence": "none",
            "reason": "No description to classify. Creator must choose Standard or Advanced.",
            "suggested_advanced_type": None,
        }

    adv_hits = [k for k in ADVANCED_KEYWORDS if k in blob]
    std_hits = [k for k in STANDARD_KEYWORDS if k in blob]

    suggested_type = None
    for key, label in (
        ("spacecraft", "spacecraft"),
        ("spaceship", "spacecraft"),
        ("starship", "spacecraft"),
        ("aircraft", "aircraft"),
        ("airplane", "aircraft"),
        ("helicopter", "aircraft"),
        ("jet", "aircraft"),
        ("vehicle", "vehicle"),
        ("truck", "vehicle"),
        ("tank", "vehicle"),
        ("car", "vehicle"),
        ("mech", "mech"),
        ("mecha", "mech"),
    ):
        if key in blob:
            suggested_type = label
            break

    if adv_hits and not std_hits:
        return {
            "mode": "advanced",
            "confidence": "high" if suggested_type else "medium",
            "reason": f"Matched Advanced class cues: {', '.join(adv_hits[:5])}",
            "suggested_advanced_type": suggested_type or "other",
        }
    if std_hits and not adv_hits:
        return {
            "mode": "standard",
            "confidence": "high",
            "reason": f"Matched Standard prop cues: {', '.join(std_hits[:5])}",
            "suggested_advanced_type": None,
        }
    if adv_hits and std_hits:
        return {
            "mode": "ambiguous",
            "confidence": "low",
            "reason": (
                f"Both Standard ({', '.join(std_hits[:3])}) and Advanced "
                f"({', '.join(adv_hits[:3])}) cues present. Creator must choose."
            ),
            "suggested_advanced_type": suggested_type,
        }
    return {
        "mode": "ambiguous",
        "confidence": "low",
        "reason": "No clear Standard/Advanced cue. Creator must choose; CD will not guess.",
        "suggested_advanced_type": None,
    }


# Explicit product examples from mission brief
EXAMPLES = {
    "sword": classify_prop_mode("ornate steel sword"),
    "spacecraft": classify_prop_mode("scout spacecraft with twin engines"),
}
