"""Character Sheet four-view product law.

A Character Sheet is always four views. A single reference image is identity
conditioning only and must not collapse the request into one standalone portrait.
Adapters must read structured intent, not prompt text alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_VIEWS: tuple[str, ...] = (
    "full_body_front",
    "full_body_side",
    "full_body_back",
    "head_shoulders_closeup",
)

# Per-view tile roles used by the compose-4-then-grid pipeline.
# These jobs are one camera each; do NOT rewrite them into a four-panel prompt.
TILE_VIEW_ROLES: frozenset[str] = frozenset(
    {
        "hero_identity",
        "full_body_front",
        "full_body_side",
        "full_body_side_left",
        "full_body_back",
        "closeup_front",
        "head_shoulders_closeup",
        "front",
        "side",
        "side_left",
        "back",
        "closeup",
        "front_closeup",
    }
)

FOUR_VIEW_SHEET_PROMPT = (
    "Create a professional four-panel character turnaround sheet using the supplied "
    "reference only to preserve identity, face, hair, wardrobe, body proportions, "
    "accessories, and distinctive markings. The final output must contain exactly "
    "four distinct views of the same character: full-body front view, full-body side "
    "profile, full-body back view, and a head-and-shoulders close-up portrait. "
    "Do not generate a single standalone character image. Do not crop or omit any required view."
)

# Compiler sheet_request for a single four-panel output (hosted API / Co-Director).
FOUR_VIEW_SHEET_REQUEST: dict[str, Any] = {
    "enabled": True,
    "layout": "four_view",
    "views": ["front", "side_left", "back", "front_closeup"],
}

# Tall portraits are treated as a single pose. Square/landscape is compatible
# with a 2x2 sheet but is NOT verified without a vision model.
_SINGLE_POSE_ASPECT_MIN = 1.25


def four_view_sheet_intent(*, reference_mode: str = "identity_preservation") -> dict[str, Any]:
    return {
        "purpose": "character_sheet",
        "layout": "four_view",
        "requiredViews": list(REQUIRED_VIEWS),
        "referenceMode": reference_mode,
    }


def attach_four_view_sheet_intent(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Stamp structured four-view intent onto a compile/enqueue payload."""
    body = payload if isinstance(payload, dict) else {}
    intent = four_view_sheet_intent()
    body["purpose"] = "character_sheet"
    body["layout"] = "four_view"
    body["requiredViews"] = list(REQUIRED_VIEWS)
    body["referenceMode"] = "identity_preservation"
    body["characterSheetIntent"] = intent
    body["fourViewSingleOutput"] = True
    ctx = body.get("creativeContext")
    if isinstance(ctx, dict):
        ctx = dict(ctx)
        ctx.update(intent)
        body["creativeContext"] = ctx
    return body


def _intent_blob(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    blob: dict[str, Any] = dict(params)
    for key in ("characterSheetIntent", "creativeContext", "imageIntent"):
        nested = params.get(key)
        if isinstance(nested, dict):
            blob.update(nested)
    return blob


def sheet_tile_role(params: Any) -> str | None:
    """Return the per-view tile role if this job is one camera of a 4-view compose."""
    if not isinstance(params, dict):
        return None
    blob = _intent_blob(params)
    for key in ("viewRole", "role"):
        raw = str(blob.get(key) or "").strip()
        if raw in TILE_VIEW_ROLES:
            return raw
    return None


def is_sheet_tile_request(params: Any) -> bool:
    if is_four_view_sheet_request(params):
        return False
    return sheet_tile_role(params) is not None


def is_four_view_sheet_request(params: Any) -> bool:
    blob = _intent_blob(params)
    layout = str(blob.get("layout") or "").strip().lower()
    if layout == "four_view":
        return True
    if blob.get("fourViewSingleOutput") is True:
        return True
    intent = params.get("characterSheetIntent") if isinstance(params, dict) else None
    if isinstance(intent, dict) and str(intent.get("layout") or "").strip().lower() == "four_view":
        return True
    return False


def is_single_image_four_view(params: Any) -> bool:
    """True when the *output* must be one four-panel image (not a compose tile)."""
    if is_four_view_sheet_request(params):
        return True
    if is_sheet_tile_request(params):
        return False
    blob = _intent_blob(params)
    purpose = str(blob.get("purpose") or blob.get("objective") or "").strip()
    preset = str(blob.get("presetId") or "").strip()
    if purpose == "character_sheet" or preset == "builtin-character-sheet":
        return True
    return False


def strengthen_four_view_prompt(prompt: str | None) -> str:
    text = str(prompt or "").strip()
    marker = "professional four-panel character turnaround sheet"
    if marker in text.lower():
        return text
    if text:
        return f"{FOUR_VIEW_SHEET_PROMPT}\n\n{text}"
    return FOUR_VIEW_SHEET_PROMPT


def public_job_error(message: str | None) -> str:
    """Surface the honest job summary only. Never a raw traceback."""
    text = str(message or "")
    cut = text.lower().find("--- details ---")
    if cut >= 0:
        text = text[:cut]
    tb = "Traceback (most recent call last)"
    if tb in text:
        text = text.split(tb)[0]
    return text.strip().splitlines()[0][:400] if text.strip() else ""


def assess_four_view_layout(
    path: str | Path | None = None,
    *,
    view_count: int | None = None,
    composed: bool = False,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Honest layout check. Does not invent a vision model.

    - 4 composed tiles → verified compliant
    - view_count != 4 → layout-noncompliant
    - Clearly tall portrait → layout-noncompliant (single pose)
    - Otherwise → layout not verified (do not fake-pass)
    """
    out: dict[str, Any] = {
        "ok": True,
        "compliant": None,
        "verified": False,
        "layoutNoncompliant": False,
        "note": "layout not verified / does not look like a four-view sheet",
        "width": None,
        "height": None,
        "aspect": None,
        "viewCount": view_count,
        "composed": composed,
    }
    if composed and view_count == 4:
        out["compliant"] = True
        out["verified"] = True
        out["layoutNoncompliant"] = False
        out["note"] = "verified_composed: four views assembled into one sheet"
        return out
    if view_count is not None and view_count != 4:
        out["ok"] = False
        out["compliant"] = False
        out["verified"] = True
        out["layoutNoncompliant"] = True
        if view_count == 1:
            out["note"] = "layout-noncompliant: single pose / not a four-view sheet"
        else:
            out["note"] = f"layout-noncompliant: expected 4 views, got {view_count}"
        return out
    if not path and not (width and height):
        out["ok"] = False
        out["layoutNoncompliant"] = False
        out["note"] = "layout not verified / does not look like a four-view sheet"
        return out
    w = int(width) if width else None
    h = int(height) if height else None
    if path:
        pth = Path(path)
        if pth.is_file():
            try:
                from PIL import Image

                with Image.open(pth) as im:
                    w, h = int(im.size[0]), int(im.size[1])
            except Exception as exc:  # noqa: BLE001
                if not w or not h:
                    out["ok"] = False
                    out["layoutNoncompliant"] = False
                    out["note"] = (
                        "layout not verified / does not look like a four-view sheet "
                        f"({type(exc).__name__})"
                    )
                    return out
    if not w or not h:
        out["ok"] = False
        out["layoutNoncompliant"] = False
        out["note"] = "layout not verified / does not look like a four-view sheet"
        return out
    out["width"] = int(w)
    out["height"] = int(h)
    if w <= 0 or h <= 0:
        out["ok"] = False
        out["layoutNoncompliant"] = False
        out["note"] = "layout not verified / does not look like a four-view sheet"
        return out
    aspect = float(h) / float(w)
    out["aspect"] = round(aspect, 4)
    if aspect >= _SINGLE_POSE_ASPECT_MIN:
        out["ok"] = False
        out["compliant"] = False
        out["verified"] = True
        out["layoutNoncompliant"] = True
        out["note"] = (
            "layout-noncompliant: image is a tall single-pose portrait, "
            "not a four-view character sheet"
        )
        return out
    # Square or landscape four_view output is a sheet candidate.
    # Compatible aspect is not proof of a 2x2 sheet. Do not fake-verify.
    # Do NOT stamp layoutNoncompliant; Use This Look is gated on that flag only.
    out["ok"] = True
    out["compliant"] = None
    out["verified"] = False
    out["layoutNoncompliant"] = False
    out["note"] = "layout not verified / does not look like a four-view sheet"
    return out


def strengthen_local_character_sheet_prompt(prompt: str, *, family: str | None = None) -> str:
    """Qwen-Image-2512 / Z-Image / Illustrious four-panel strengthen."""
    return strengthen_four_view_prompt(prompt)


def apply_layout_assessment_to_candidate(
    candidate: dict[str, Any] | None,
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    """Stamp FE-facing layout flags onto a pack candidate. Honest if heuristic-only."""
    body = candidate if isinstance(candidate, dict) else {}
    assess = assessment if isinstance(assessment, dict) else {}
    flag = bool(assess.get("layoutNoncompliant"))
    body["layoutAssessment"] = assess
    body["characterSheetLayout"] = assess
    body["layoutVerified"] = bool(assess.get("verified"))
    body["layoutNote"] = assess.get("note")
    body["layoutNoncompliant"] = flag
    body["layout_noncompliant"] = flag
    if assess.get("width") is not None:
        body["width"] = assess.get("width")
    if assess.get("height") is not None:
        body["height"] = assess.get("height")
    if assess.get("aspect") is not None:
        body["aspect"] = assess.get("aspect")
    return body


def _aspect_from_candidate(item: dict[str, Any]) -> float | None:
    blobs: list[Any] = [
        item.get("layoutAssessment"),
        item.get("characterSheetLayout"),
        item,
    ]
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        w, h = blob.get("width"), blob.get("height")
        try:
            ww = float(w) if w is not None else 0.0
            hh = float(h) if h is not None else 0.0
        except (TypeError, ValueError):
            continue
        if ww > 0 and hh > 0:
            return hh / ww
    return None


def candidate_layout_noncompliant(item: dict[str, Any] | None) -> bool:
    """Resolve the FE flag. Never force-clear on done+assetId / sheetAssetId.

    In-flight jobs are not assessable — do not show the FE flag or Retry yet.
    """
    if not isinstance(item, dict):
        return False
    aspect = _aspect_from_candidate(item)
    if aspect is not None:
        return aspect >= _SINGLE_POSE_ASPECT_MIN
    if item.get("layoutNoncompliant") is True or item.get("layout_noncompliant") is True:
        return True
    if item.get("layoutNoncompliant") is False or item.get("layout_noncompliant") is False:
        return False
    status = str(item.get("status") or "").strip().lower()
    has_asset = bool(item.get("sheetAssetId") or item.get("assetId"))
    if status not in {"done", "complete", "completed"} and not has_asset:
        return False
    return False

def can_use_this_look(candidate: dict[str, Any] | None) -> bool:
    """Use This Look is gated on layoutNoncompliant only, not layoutVerified."""
    if not isinstance(candidate, dict):
        return False
    if candidate_layout_noncompliant(candidate):
        return False
    return bool(candidate.get("sheetAssetId") or candidate.get("assetId"))
