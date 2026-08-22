"""Hard one-figure gate for CRS single-view tiles.

A tile passes only when exactly one person is proven. Multi-figure and collage
fail. Unverified (no detector, no collage hit) is not a pass and does not
trigger fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

FAILURE_MULTI = "CRS_SINGLE_VIEW_MULTI_FIGURE"
FAILURE_COLLAGE = "CRS_SINGLE_VIEW_COLLAGE"

_PERSON_LABELS = frozenset({"person", "people", "human", "man", "woman", "girl", "boy", "character"})


@dataclass(frozen=True)
class CrsSingleFigureResult:
    single_figure_pass: bool | None
    detected_figures: int | None
    failure_code: str | None
    view_angle_pass: None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_crs_single_view_job(params: Any) -> bool:
    if not isinstance(params, dict):
        return False
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    task = str(params.get("taskType") or ctx.get("taskType") or "").strip().upper()
    if task == "CRS_SINGLE_VIEW":
        return True
    if params.get("fourViewSingleOutput") is True or ctx.get("fourViewSingleOutput") is True:
        return False
    layout = str(
        params.get("layout") or params.get("sheet_layout") or ctx.get("layout") or ""
    ).strip().lower()
    return layout in {"crs_view", "law_views"}


def _count_person_entities(entities: Sequence[Mapping[str, Any]] | None) -> int | None:
    if entities is None:
        return None
    n = 0
    for item in entities:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("kindHint") or "").strip().lower()
        if label in _PERSON_LABELS or label == "character":
            n += 1
    return n


def detect_collage_layout(path: str | Path) -> bool:
    """Cheap PIL grid/contact-sheet detector. No vision model."""
    try:
        from PIL import Image
    except Exception:
        return False
    pth = Path(path)
    if not pth.is_file():
        return False
    try:
        with Image.open(pth) as im:
            gray = im.convert("L")
            w, h = gray.size
            if w < 8 or h < 8:
                return False
            pix = gray.load()
            mid_x = w // 2
            mid_y = h // 3
            # Bright gutter through the center (2x2 / contact sheet).
            col = [pix[mid_x, y] for y in range(h)]
            row = [pix[x, h // 2] for x in range(w)]
            col_bright = sum(1 for v in col if v >= 200) / max(1, len(col))
            row_bright = sum(1 for v in row if v >= 200) / max(1, len(row))
            # Quadrant means differ from the gutter (four panels).
            def _mean(x0: int, y0: int, x1: int, y1: int) -> float:
                total = 0
                n = 0
                for y in range(y0, y1, max(1, (y1 - y0) // 8)):
                    for x in range(x0, x1, max(1, (x1 - x0) // 8)):
                        total += pix[x, y]
                        n += 1
                return total / max(1, n)

            q = [
                _mean(0, 0, w // 2, h // 2),
                _mean(w // 2, 0, w, h // 2),
                _mean(0, h // 2, w // 2, h),
                _mean(w // 2, h // 2, w, h),
            ]
            quadrant_spread = max(q) - min(q)
            if col_bright >= 0.55 and row_bright >= 0.55 and quadrant_spread >= 20:
                return True
            # Inset: a small dark rectangle in a corner plus a large body.
            _ = mid_y
            return False
    except Exception:
        return False


def _dino_person_count(path: str) -> int | None:
    try:
        from ..codirector.perception.paths import geometry_models_present
        from ..codirector.perception.worker_client import _run_worker
    except Exception:
        return None
    try:
        if not geometry_models_present():
            return None
        parsed = _run_worker({"imagePath": path}, timeout=90)
    except Exception:
        return None
    if not parsed.get("ok"):
        return None
    return _count_person_entities(parsed.get("entities"))


def validate_crs_single_figure(
    path: str | Path,
    *,
    detect_people: Callable[[str], int | None] | None = None,
    detect_collage: Callable[[str], bool] | None = None,
) -> CrsSingleFigureResult:
    image_path = str(path)
    collage_fn = detect_collage or (lambda p: detect_collage_layout(p))
    if collage_fn(image_path):
        return CrsSingleFigureResult(
            single_figure_pass=False,
            detected_figures=None,
            failure_code=FAILURE_COLLAGE,
            note="collage or contact-sheet layout",
        )
    counter = detect_people or _dino_person_count
    count = counter(image_path)
    if count is None:
        return CrsSingleFigureResult(
            single_figure_pass=None,
            detected_figures=None,
            failure_code=None,
            note="unverified: no person detector",
        )
    if count == 1:
        return CrsSingleFigureResult(
            single_figure_pass=True,
            detected_figures=1,
            failure_code=None,
            note="one figure",
        )
    return CrsSingleFigureResult(
        single_figure_pass=False,
        detected_figures=count,
        failure_code=FAILURE_MULTI,
        note=f"detected_figures={count}",
    )


def should_fallback_to_qwen(params: dict[str, Any] | None, result: CrsSingleFigureResult) -> bool:
    """AUTO FLUX tile failed the hard gate → one Qwen retry. Never retry FLUX."""
    if result.single_figure_pass is not False:
        return False
    if not isinstance(params, dict):
        return False
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    if params.get("crsSingleFigureFallback") or ctx.get("crsSingleFigureFallback"):
        return False
    family = str(
        params.get("modelFamilyPreference")
        or params.get("modelFamily")
        or ctx.get("modelFamily")
        or ctx.get("modelFamilyPreference")
        or ""
    ).strip().lower()
    if family != "flux":
        return False
    auto = params.get("autoSelect")
    if auto is None:
        auto = ctx.get("autoSelect")
    return bool(auto)
