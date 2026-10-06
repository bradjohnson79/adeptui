"""Board-level storyboard aspect. One mapping for 16:9 and 9:16.

Panel pixels come from the image-product size resolver. The 2K sheet uses the
existing 2560×1440 landscape canvas, and the portrait sheet is that canvas
turned upright.
"""

from __future__ import annotations

import re

StoryboardAspect = str

STORYBOARD_ASPECTS = ("16:9", "9:16")
LANDSCAPE_SHEET = (2560, 1440)
PORTRAIT_SHEET = (1440, 2560)


def normalize_storyboard_aspect(value: str | None) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    if text in {"9:16", "9/16", "portrait", "vertical"}:
        return "9:16"
    return "16:9"


def sheet_canvas(aspect: str | None) -> tuple[int, int]:
    if normalize_storyboard_aspect(aspect) == "9:16":
        return PORTRAIT_SHEET
    return LANDSCAPE_SHEET


def generation_dimensions(aspect: str | None, resolution: str = "1080p") -> tuple[int, int]:
    """Legal panel size from the image-product dimension owner."""
    from ..image_product.compile import _size

    return _size(normalize_storyboard_aspect(aspect), resolution)


def storyboard_board_intent(text: str | None) -> tuple[str | None, int | None]:
    """Read an explicit board ratio and 6/9/12 count from creator language.

    Returns (None, None) when the text does not name either, so a later save
    does not reset a board that already has a ratio.
    """
    raw = (text or "").lower()
    marks: list[tuple[int, str]] = []
    for token, aspect in (
        ("9:16", "9:16"),
        ("9/16", "9:16"),
        ("vertical", "9:16"),
        ("portrait", "9:16"),
        ("16:9", "16:9"),
        ("16/9", "16:9"),
        ("landscape", "16:9"),
        ("widescreen", "16:9"),
    ):
        idx = raw.find(token)
        if idx >= 0:
            marks.append((idx, aspect))
    aspect = sorted(marks)[-1][1] if marks else None
    page: int | None = None
    for count in (12, 9, 6):
        if re.search(rf"\b{count}\s*-?\s*panels?\b", raw):
            page = count
            break
    return aspect, page


def board_aspect_of(project_id: str) -> str:
    from .documents import list_documents

    docs = list_documents(project_id)
    if not docs:
        return "16:9"
    return normalize_storyboard_aspect(getattr(docs[0], "aspectRatio", None))


def apply_storyboard_board(project_id: str, aspect: str | None, page_size: int | None) -> None:
    """Persist an explicit ratio or page count on the existing storyboard document."""
    from .documents import ensure_document, set_aspect_ratio, set_page_size

    if aspect is None and page_size not in (6, 9, 12):
        return
    doc = ensure_document(project_id, page_size=page_size if page_size in (6, 9, 12) else 9)
    if aspect is not None:
        updated = set_aspect_ratio(project_id, doc.id, aspect)
        if updated is not None:
            doc = updated
    if page_size in (6, 9, 12) and int(doc.pageSize) != int(page_size):
        set_page_size(project_id, doc.id, page_size)  # type: ignore[arg-type]
