"""Canonical MiniMax H3 resolution-fit guidance (GPU Inspector ladder).

Authority for Timeline → GPU Inspector → MiniMax H3 resolution advice.
Demonstrated on RTX 5090 / ~32 GB: 480p, 720p, 1080p.
2K is not certified. 4K is not native/certified (upscale is separate).

VRAM free-at-the-moment heuristics must NOT label 720p or 1080p as
"Not viable" on a 32 GB-class GPU. Supported ≠ fast.
Never mutates the creator request.
"""

from __future__ import annotations

from typing import Any, Literal

H3ResolutionTier = Literal["480p", "720p", "1080p", "2K", "4K"]

# Physical total GB at/above which 480/720/1080 are certified demonstrated.
H3_DEMONSTRATED_TOTAL_GB = 28.0

H3_RESOLUTION_FIT: dict[str, dict[str, str]] = {
    "480p": {
        "certification": "demonstrated",
        "adviceLabel": "Fastest / Recommended for drafts",
        "adviceDetail": "lowest time; previews/iteration",
        "verdict": "VIABLE",
    },
    "720p": {
        "certification": "demonstrated",
        "adviceLabel": "Viable / Higher Quality",
        "adviceDetail": "supported; more time",
        "verdict": "VIABLE",
    },
    "1080p": {
        "certification": "demonstrated",
        "adviceLabel": "Viable / High Quality",
        "adviceDetail": "supported; substantially longer / heavier GPU",
        "verdict": "VIABLE",
    },
    "2K": {
        "certification": "not_certified",
        "adviceLabel": "Not certified",
        "adviceDetail": "do not claim viability until demonstrated",
        "verdict": "NOT CERTIFIED",
    },
    "4K": {
        "certification": "not_native",
        "adviceLabel": "Not native/certified",
        "adviceDetail": "not demonstrated native H3; upscale separate",
        "verdict": "NOT NATIVE",
    },
}

H3_PRODUCT_IDS = frozenset(
    {
        "minimax-h3",
        "minimax-h3-local",
        "minimax-h3-t2v-local",
        "minimax-h3-i2v-local",
    }
)


def is_minimax_h3_product(product_id: str) -> bool:
    token = str(product_id or "").strip().lower()
    if token in H3_PRODUCT_IDS:
        return True
    return token.startswith("minimax-h3")


def display_product_label(product_id: str) -> str:
    if is_minimax_h3_product(product_id):
        return "MiniMax H3"
    return str(product_id or "").strip() or "generator"


def apply_h3_resolution_fit(
    tier: str,
    *,
    row: dict[str, Any],
    total_gb: float | None,
) -> dict[str, Any]:
    """Overlay canonical H3 resolution-fit advice onto a ladder row.

    Demonstrated tiers (480/720/1080) on a 32 GB-class GPU never emit
    NOT VIABLE. 2K/4K use certification honesty, not a false "Not viable".
    """
    guide = H3_RESOLUTION_FIT.get(str(tier))
    if not guide:
        return row
    out = dict(row)
    out["adviceLabel"] = guide["adviceLabel"]
    out["adviceDetail"] = guide["adviceDetail"]
    out["certification"] = guide["certification"]
    out["honestyLabel"] = f"{guide['adviceLabel']} ({guide['adviceDetail']})"

    cert = guide["certification"]
    if cert == "demonstrated":
        # 32 GB-class: always viable advice for demonstrated tiers.
        # Below that class, keep VRAM estimate but never claim "Not viable"
        # solely from a stale peak heuristic when total is unknown-or-low —
        # still prefer guidance wording; demote NOT VIABLE → MARGINAL.
        if total_gb is not None and total_gb >= H3_DEMONSTRATED_TOTAL_GB:
            out["verdict"] = "VIABLE"
            out["reason"] = (
                f"{guide['adviceLabel']} — {guide['adviceDetail']}. "
                "Supported is not the same as fast; Adept will not change your request."
            )
        else:
            prior = str(out.get("verdict") or "")
            if prior == "NOT VIABLE":
                out["verdict"] = "MARGINAL"
                out["reason"] = (
                    f"{guide['adviceLabel']} — demonstrated on ~32 GB class GPUs; "
                    f"this GPU reports {total_gb} GB total. Adept will not change your request."
                )
            else:
                out["verdict"] = prior or "VIABLE"
                out["reason"] = out.get("reason") or guide["adviceDetail"]
        # Never surface "Not viable" suggestions that contradict demonstrated support.
        out["suggestions"] = [
            s
            for s in (out.get("suggestions") or [])
            if "Try 1080p or 720p" not in str(s)
        ]
    elif cert == "not_certified":
        out["verdict"] = "NOT CERTIFIED"
        out["reason"] = guide["adviceDetail"]
        out["estimatedPeakGb"] = None
        out["suggestions"] = ["480p", "720p", "1080p"]
    else:  # not_native
        out["verdict"] = "NOT NATIVE"
        out["reason"] = guide["adviceDetail"]
        out["estimatedPeakGb"] = None
        out["suggestions"] = ["480p", "720p", "1080p"]
    return out


def decorate_h3_ladder(
    tiers: list[dict[str, Any]],
    *,
    total_gb: float | None,
) -> list[dict[str, Any]]:
    return [apply_h3_resolution_fit(str(t.get("tier") or ""), row=t, total_gb=total_gb) for t in tiers]
