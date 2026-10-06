"""Versioned ERS collage template contracts.

Panel 9 geometry is bound to a named template. The 3x3 gallery region is
only valid for the gallery template. Missing or mismatched contracts fail
closed — they never fall back to the gallery box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SENSENOVA_INTEGRATION_LAB_ERS_V1 = "sensenova-integration-lab-ers-v1"
ORIGINAL_ERS_V1 = "ers.original.v1"
GALLERY_3X3_V1 = "gallery-3x3-v1"

SENSENOVA_TEMPLATE_ASSET_ID = "32cfec5b-5110-43bc-bd0f-96e089f287d0"

# Certified content rectangle on the original 1672x941 collage.
# Title "9. CONTEXTUAL PRODUCTION (OCCUPIED SCALE)" is outside this box.
_SENSENOVA_PANEL9_PIXELS = (1048, 496, 1660, 632)
_SENSENOVA_SIZE = (1672, 941)

_STRIP_TOLERANCE_PX = 16


def visual_ers_canvas_size(width: int, height: int) -> tuple[int, int]:
    """Return the clean 16:9 visual canvas. Never include the 780px strip chrome."""
    core_h = int(round(int(width) * 9 / 16))
    if int(height) > core_h + _STRIP_TOLERANCE_PX:
        return int(width), core_h
    return int(width), int(height)


def canonical_panel9_box(size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Canonical Occupied rectangle on a clean 16:9 sheet.

    Template pixels (1048, 496, 1660, 632) on 1672x941, scaled proportionally
    onto other 16:9 canvases including 2560x1440. Never computed against 2220 chrome.
    """
    vis_w, vis_h = visual_ers_canvas_size(int(size[0]), int(size[1]))
    tw, th = _SENSENOVA_SIZE
    x0, y0, x1, y1 = _SENSENOVA_PANEL9_PIXELS
    box = (
        int(round(x0 * vis_w / tw)),
        int(round(y0 * vis_h / th)),
        int(round(x1 * vis_w / tw)),
        int(round(y1 * vis_h / th)),
    )
    box = (
        max(0, min(vis_w, box[0])),
        max(0, min(vis_h, box[1])),
        max(0, min(vis_w, box[2])),
        max(0, min(vis_h, box[3])),
    )
    return box


@dataclass(frozen=True)
class ErsCollageTemplateContract:
    template_id: str
    template_asset_id: str
    contract_version: int
    template_size: tuple[int, int]
    panel9_pixels: tuple[int, int, int, int]  # x0, y0, x1, y1 exclusive
    # Optional named content rectangles in original-template pixels (exclusive).
    panel_pixels: dict[str, tuple[int, int, int, int]] | None = None
    allow_scaled: bool = False

    @property
    def panel9_content(self) -> dict[str, float]:
        return self.panel_content("occupied") or _pixels_to_frac(self.panel9_pixels, self.template_size)

    def panel_content(self, panel: str) -> dict[str, float] | None:
        rects = dict(self.panel_pixels or {})
        key = str(panel or "").strip().lower()
        aliases = {
            "panel9": "occupied",
            "occupied": "occupied",
            "hero": "hero",
            "panel1": "hero",
            "master": "hero",
            "spatial": "spatial",
            "spatial_map": "spatial",
            "legend": "legend",
            "three_d": "three_d",
            "structuring": "three_d",
            "structural": "three_d",
            "north": "north",
            "east": "east",
            "south": "south",
            "west": "west",
        }
        mapped = aliases.get(key, key)
        if mapped == "occupied" and mapped not in rects:
            return _pixels_to_frac(self.panel9_pixels, self.template_size)
        raw = rects.get(mapped)
        if not raw:
            return None
        return _pixels_to_frac(raw, self.template_size)


def _pixels_to_frac(
    pixels: tuple[int, int, int, int],
    size: tuple[int, int],
) -> dict[str, float]:
    w, h = size
    x0, y0, x1, y1 = pixels
    return {
        "left": x0 / w,
        "top": y0 / h,
        "width": (x1 - x0) / w,
        "height": (y1 - y0) / h,
    }


# 4:3 master the Edit/Inpaint legend layout is designed against.
ERS_SHEET_MASTER = (2048, 1536)

# Middle row on the original 1672×941 sheet, same 42% / 16% / 42% split
# the editor paints on a 2048×1536 master (top 28%, height 42%).
_MIDDLE_TOP = 0.28
_MIDDLE_HEIGHT = 0.42
_MIDDLE_Y0 = int(round(_SENSENOVA_SIZE[1] * _MIDDLE_TOP))
_MIDDLE_Y1 = int(round(_SENSENOVA_SIZE[1] * (_MIDDLE_TOP + _MIDDLE_HEIGHT)))
_MIDDLE_X0 = 16
_MIDDLE_X1 = _SENSENOVA_SIZE[0] - 16
_MIDDLE_SPAN = _MIDDLE_X1 - _MIDDLE_X0
_SPATIAL_W = int(round(_MIDDLE_SPAN * 0.42))
_LEGEND_W = int(round(_MIDDLE_SPAN * 0.16))


_ORIGINAL_PANEL_PIXELS = {
    # Hero is the large left production still on the certified original sheet.
    "hero": (24, 40, 820, 470),
    "occupied": _SENSENOVA_PANEL9_PIXELS,
    "spatial": (_MIDDLE_X0, _MIDDLE_Y0, _MIDDLE_X0 + _SPATIAL_W, _MIDDLE_Y1),
    "legend": (
        _MIDDLE_X0 + _SPATIAL_W,
        _MIDDLE_Y0,
        _MIDDLE_X0 + _SPATIAL_W + _LEGEND_W,
        _MIDDLE_Y1,
    ),
    "three_d": (
        _MIDDLE_X0 + _SPATIAL_W + _LEGEND_W,
        _MIDDLE_Y0,
        _MIDDLE_X1,
        _MIDDLE_Y1,
    ),
}


_ORIGINAL_CONTRACT = ErsCollageTemplateContract(
    template_id=ORIGINAL_ERS_V1,
    template_asset_id=SENSENOVA_TEMPLATE_ASSET_ID,
    contract_version=1,
    template_size=_SENSENOVA_SIZE,
    panel9_pixels=_SENSENOVA_PANEL9_PIXELS,
    panel_pixels=_ORIGINAL_PANEL_PIXELS,
    allow_scaled=True,
)


COLLAGE_TEMPLATES: dict[str, ErsCollageTemplateContract] = {
    SENSENOVA_INTEGRATION_LAB_ERS_V1: ErsCollageTemplateContract(
        template_id=SENSENOVA_INTEGRATION_LAB_ERS_V1,
        template_asset_id=SENSENOVA_TEMPLATE_ASSET_ID,
        contract_version=1,
        template_size=_SENSENOVA_SIZE,
        panel9_pixels=_SENSENOVA_PANEL9_PIXELS,
        panel_pixels={"occupied": _SENSENOVA_PANEL9_PIXELS},
    ),
    ORIGINAL_ERS_V1: _ORIGINAL_CONTRACT,
}

_ASSET_TO_TEMPLATE = {
    SENSENOVA_TEMPLATE_ASSET_ID: SENSENOVA_INTEGRATION_LAB_ERS_V1,
}


class ErsCollageTemplateError(RuntimeError):
    """Fail-closed: cannot compose occupied into an unbound or mismatched template."""


def lookup_collage_template(
    *,
    collage_asset_id: str = "",
    template_id: str = "",
) -> ErsCollageTemplateContract | None:
    tid = str(template_id or "").strip()
    if tid == GALLERY_3X3_V1:
        return None
    if tid in {ORIGINAL_ERS_V1, "full_sheet", "full_sheet_api"}:
        return COLLAGE_TEMPLATES[ORIGINAL_ERS_V1]
    if tid and tid in COLLAGE_TEMPLATES:
        return COLLAGE_TEMPLATES[tid]
    aid = str(collage_asset_id or "").strip()
    mapped = _ASSET_TO_TEMPLATE.get(aid)
    if mapped:
        return COLLAGE_TEMPLATES[mapped]
    return None


def resolve_occupied_region(
    collage_size: tuple[int, int],
    *,
    collage_asset_id: str = "",
    template_id: str = "",
    gallery_region: dict[str, float] | None = None,
) -> dict[str, float]:
    tid = str(template_id or "").strip()
    aid = str(collage_asset_id or "").strip()
    if tid == GALLERY_3X3_V1:
        if gallery_region is None:
            raise ErsCollageTemplateError("Gallery 3x3 template requires an explicit gallery region.")
        return dict(gallery_region)
    contract = lookup_collage_template(collage_asset_id=aid, template_id=tid)
    if contract is None:
        raise ErsCollageTemplateError(
            "ERS collage template contract is missing. Occupied cannot be pasted "
            "into a 3x3 gallery region by default."
        )
    if tuple(collage_size) != contract.template_size and not contract.allow_scaled:
        raise ErsCollageTemplateError(
            f"ERS collage size {collage_size} does not match template "
            f"{contract.template_id} size {contract.template_size}."
        )
    vis_w, vis_h = visual_ers_canvas_size(int(collage_size[0]), int(collage_size[1]))
    x0, y0, x1, y1 = canonical_panel9_box((vis_w, vis_h))
    return {
        "left": x0 / vis_w,
        "top": y0 / vis_h,
        "width": (x1 - x0) / vis_w,
        "height": (y1 - y0) / vis_h,
        "pixels": (x0, y0, x1, y1),
        "canvas": (vis_w, vis_h),
    }


def stamp_template_on_package(package: Any, contract: ErsCollageTemplateContract) -> None:
    meta = dict(getattr(package, "metadata", None) or {})
    if not str(meta.get("collageAssetId") or "").strip():
        meta["collageAssetId"] = contract.template_asset_id
    meta["ersCollageTemplateId"] = contract.template_id
    meta["ersCollageContractVersion"] = contract.contract_version
    meta["occupiedCollageRegion"] = contract.panel9_content
    package.metadata = meta
