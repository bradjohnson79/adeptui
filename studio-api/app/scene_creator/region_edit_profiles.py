"""Scene Creator region-edit operation profiles and creator-facing gate copy.

Do not lower the Output Gate to let no-ops pass. Change strength via denoise,
mask grow, and compiled prompts instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

MASK_TOO_SMALL_PERCENT = 0.4
MASK_TOO_SMALL_MESSAGE = "Mask too small"

EXPAND_PRESETS: dict[str, int] = {
    "tight": 2,
    "normal": 6,
    "wide": 14,
}

FEATHER_PRESETS: dict[str, int] = {
    "hard": 0,
    "soft": 8,
}

OPERATION_PROFILES: dict[str, dict[str, Any]] = {
    "remove": {
        "denoise": 0.85,
        "grow_mask_by": 6,
        "expand": "normal",
        "feather": "hard",
        "prefix": (
            "Remove the selected object seamlessly. Fill the masked region from the "
            "surrounding context. Do not leave a ghost of the original."
        ),
    },
    "modify": {
        "denoise": 0.82,
        "grow_mask_by": 8,
        "expand": "normal",
        "feather": "soft",
        "prefix": (
            "Change only the masked region as requested. Preserve exact identity, "
            "facial structure, hair, wardrobe, lighting, pose, and camera framing."
        ),
    },
    "add": {
        "denoise": 0.94,
        "grow_mask_by": 12,
        "expand": "wide",
        "feather": "soft",
        "prefix": (
            "Create the described object in the masked region. Do not copy the "
            "existing masked pixels. Match lighting, perspective, and depth."
        ),
    },
    "replace": {
        "denoise": 0.90,
        "grow_mask_by": 8,
        "expand": "normal",
        "feather": "soft",
        "prefix": (
            "Replace the masked object with the described object. The original item "
            "must not remain. Match lighting, perspective, and depth."
        ),
    },
}

OUTPUT_GATE_CREATOR_MESSAGE = (
    "Edit did not change the selected region enough.\n"
    "Try:\n"
    "• expanding the mask\n"
    "• strengthening the prompt\n"
    "• switching to Z-Image / FLUX"
)

GENERATION_FAILED_GATE_MESSAGE = "Generation failed\nOutput did not pass quality gate."


def normalize_expand(preset: str | None, *, operation: str = "") -> str:
    key = (preset or "").strip().lower()
    if key in EXPAND_PRESETS:
        return key
    profile = OPERATION_PROFILES.get((operation or "").strip().lower()) or {}
    return str(profile.get("expand") or "normal")


def normalize_feather(preset: str | None, *, operation: str = "") -> str:
    key = (preset or "").strip().lower()
    if key in FEATHER_PRESETS:
        return key
    profile = OPERATION_PROFILES.get((operation or "").strip().lower()) or {}
    return str(profile.get("feather") or "hard")


def grow_mask_by_for(operation: str, expand: str | None = None) -> int:
    op = (operation or "").strip().lower()
    key = (expand or "").strip().lower()
    if key in EXPAND_PRESETS:
        return int(EXPAND_PRESETS[key])
    profile = OPERATION_PROFILES.get(op) or {}
    return int(profile.get("grow_mask_by") or 6)


def denoise_for(operation: str) -> float:
    profile = OPERATION_PROFILES.get((operation or "").strip().lower()) or {}
    return float(profile.get("denoise") or 0.85)


def compile_operation_prompt(operation: str, prompt: str) -> str:
    text = (prompt or "").strip()
    profile = OPERATION_PROFILES.get((operation or "").strip().lower()) or {}
    prefix = str(profile.get("prefix") or "").strip()
    if prefix and text:
        return f"{prefix} {text}".strip()
    return prefix or text


def operation_profile(operation: str, *, expand: str | None = None, feather: str | None = None) -> dict[str, Any]:
    op = (operation or "").strip().lower()
    expand_key = normalize_expand(expand, operation=op)
    feather_key = normalize_feather(feather, operation=op)
    return {
        "operation": op,
        "denoise": denoise_for(op),
        "grow_mask_by": grow_mask_by_for(op, expand),
        "expand": expand_key,
        "feather": feather_key,
        "featherPx": int(FEATHER_PRESETS[feather_key]),
        "prompt": compile_operation_prompt(op, ""),
    }


def mask_coverage_percent(path: str | Path | None) -> float:
    if not path:
        return 0.0
    p = Path(path)
    if not p.is_file():
        return 0.0
    try:
        from PIL import Image

        with Image.open(p) as im:
            rgba = im.convert("RGBA")
            alpha = rgba.split()[-1]
            pixels = list(alpha.getdata())
        if not pixels:
            return 0.0
        painted = sum(1 for v in pixels if v >= 128)
        return (painted / len(pixels)) * 100.0
    except Exception:
        return 0.0


def assert_mask_large_enough(path: str | Path | None) -> float:
    coverage = mask_coverage_percent(path)
    if coverage < MASK_TOO_SMALL_PERCENT:
        raise ValueError(MASK_TOO_SMALL_MESSAGE)
    return coverage


def creator_facing_job_error(raw: str) -> tuple[str, str]:
    """Return (creator_message, technical_detail)."""
    detail = (raw or "").strip()
    low = detail.lower()
    if "did not change meaningfully" in low or "identical to source" in low:
        return OUTPUT_GATE_CREATOR_MESSAGE, detail
    if "output gate" in low:
        return GENERATION_FAILED_GATE_MESSAGE, detail
    if detail:
        return "Generation failed", detail
    return "Generation failed", ""


def format_take_label(
    *,
    index: int,
    kind: str = "",
    quality_profile: str = "",
    operation: str = "",
) -> str:
    letter = chr(ord("A") + min(max(int(index), 0), 25))
    op = (operation or "").strip().lower()
    op_label = {
        "remove": "Remove",
        "modify": "Modify",
        "add": "Add",
        "replace": "Replace",
    }.get(op, op.title() if op else "")
    quality = (quality_profile or "").strip().lower()
    if (kind or "").strip().lower() == "region_edit":
        prefix = "Final Inpaint" if quality == "final" else "Inpaint"
        return f"{prefix} {letter} — {op_label}".strip(" —")
    if quality in {"draft", "preview"}:
        return f"Preview {letter}"
    return f"Final {letter}"
