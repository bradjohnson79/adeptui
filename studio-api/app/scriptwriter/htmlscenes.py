"""Raw-HTML scene surgery for HTML-canonical script documents.

Typed HTML is the canonical Script Writer content (CDX-051). Scene
add/remove/move must therefore operate on that HTML directly: folding the
document through the plain-text element projection and re-serializing would
silently destroy creator formatting (inline bold/italic, alignment) in every
untouched scene.

This module splits the document into RAW top-level blocks (with source
offsets), maps scene spans using the same deterministic heading ids as
``htmltext.html_scene_elements`` (so navigator selections address scenes
directly), and performs insert/delete/move as cut-and-paste over the original
source. Content outside the touched scene span is preserved byte-for-byte.

Pure functions only — never writes to any store.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional

from .htmltext import html_scene_elements

_TOP_LEVEL_TAGS = {
    "p",
    "div",
    "li",
    "blockquote",
    "tr",
    "ul",
    "ol",
    "table",
    "pre",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}
_VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "col", "wbr"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class RawBlock:
    """One top-level block element with raw source offsets."""

    tag: str
    start: int  # offset of the block's opening "<"
    end: int  # offset just past the block's closing ">"


@dataclass
class SceneSpan:
    """A scene = its heading block plus every following block up to (not
    including) the next heading block or end of document."""

    scene_heading_id: str
    heading: str
    scene_number: str
    start: int  # raw offset of the heading block start
    end: int  # raw offset just past the last block of the scene


class _RawSplitter(HTMLParser):
    """Collect raw top-level block spans. Depth-tracked so nested markup
    (lists, inline tags) never splits a block."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self._source = source
        self._line_offsets = self._compute_line_offsets(source)
        self.blocks: list[RawBlock] = []
        self._depth = 0
        self._cur_start: Optional[int] = None
        self._cur_tag = ""

    @staticmethod
    def _compute_line_offsets(source: str) -> list[int]:
        offsets = [0]
        for i, ch in enumerate(source):
            if ch == "\n":
                offsets.append(i + 1)
        return offsets

    def _abs(self) -> int:
        line, col = self.getpos()
        if line - 1 < len(self._line_offsets):
            return self._line_offsets[line - 1] + col
        return len(self._source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._depth == 0 and tag in _TOP_LEVEL_TAGS and self._cur_start is None:
            self._cur_start = self._abs()
            self._cur_tag = tag
        if tag not in _VOID_TAGS:
            self._depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._depth == 0 and tag in _TOP_LEVEL_TAGS:
            start = self._abs()
            end = start + len(self.get_starttag_text() or "")
            self.blocks.append(RawBlock(tag=tag, start=start, end=end))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _VOID_TAGS:
            return
        if self._depth > 0:
            self._depth -= 1
        if self._depth == 0 and self._cur_start is not None and tag == self._cur_tag:
            # getpos() at an end tag points at its "<"; the raw text runs to
            # just past the matching ">".
            start_of_tag = self._abs()
            close = self._source.find(">", start_of_tag)
            end = (close + 1) if close >= 0 else len(self._source)
            self.blocks.append(RawBlock(tag=self._cur_tag, start=self._cur_start, end=end))
            self._cur_start = None
            self._cur_tag = ""

    def close(self) -> None:  # noqa: D102 — guarantee a dangling block is flushed
        super().close()
        if self._cur_start is not None:
            self.blocks.append(RawBlock(tag=self._cur_tag, start=self._cur_start, end=len(self._source)))
            self._cur_start = None
            self._cur_tag = ""


def split_raw_blocks(html: str | None) -> list[RawBlock]:
    """Split sanitized editor HTML into raw top-level blocks."""
    if not html:
        return []
    parser = _RawSplitter(html)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    return parser.blocks


def scene_spans(html: str | None) -> tuple[str, list[SceneSpan]]:
    """Return (preamble_html, scene spans) for an HTML-canonical document.

    Scene heading ids come from the canonical projection
    (``html_scene_elements``) so the ids the navigator displays are the ids
    these spans answer to. The preamble is any markup before the first
    heading block (e.g. a title paragraph); scene ops always preserve it.
    """
    if not html:
        return "", []
    projection = [e for e in html_scene_elements(html) if e.type == "scene_heading"]
    blocks = split_raw_blocks(html)
    heading_blocks = [b for b in blocks if b.tag in _HEADING_TAGS]
    if not heading_blocks or len(heading_blocks) != len(projection):
        # Mismatch between raw structure and the text projection (hand-edited
        # or non-editor HTML). Refuse to guess — callers fall back to the
        # element-fold path.
        return html, []
    spans: list[SceneSpan] = []
    for i, (block, proj) in enumerate(zip(heading_blocks, projection)):
        end = heading_blocks[i + 1].start if i + 1 < len(heading_blocks) else len(html)
        spans.append(
            SceneSpan(
                scene_heading_id=proj.id,
                heading=proj.text or "",
                scene_number=proj.sceneNumber or str(i + 1),
                start=block.start,
                end=end,
            )
        )
    preamble = html[: heading_blocks[0].start]
    return preamble, spans


def _new_scene_html(heading: str) -> str:
    text = _html.escape((heading or "INT. LOCATION - DAY").strip() or "INT. LOCATION - DAY")
    return f"<h1>{text}</h1><p></p>"


def insert_scene_html(html: str | None, heading: str, *, after_scene_id: str | None = None) -> str:
    """Insert a new scene after ``after_scene_id`` (or at the end)."""
    source = html or ""
    preamble, spans = scene_spans(source)
    snippet = _new_scene_html(heading)
    if after_scene_id:
        for span in spans:
            if span.scene_heading_id == after_scene_id:
                return source[: span.end] + snippet + source[span.end :]
    if spans:
        return source[: spans[-1].end] + snippet + source[spans[-1].end :]
    # No scenes yet — append after whatever content exists (usually a title
    # paragraph or an empty doc).
    return source + snippet


def delete_scene_html(html: str | None, scene_heading_id: str) -> str | None:
    """Remove the scene span addressed by ``scene_heading_id``.

    Returns ``None`` when the scene cannot be found (caller raises).
    """
    source = html or ""
    _preamble, spans = scene_spans(source)
    for span in spans:
        if span.scene_heading_id == scene_heading_id:
            return source[: span.start] + source[span.end :]
    return None


def move_scene_html(html: str | None, scene_heading_id: str, to_index: int) -> str | None:
    """Move the addressed scene to scene position ``to_index`` (0-based).

    Returns ``None`` when the scene cannot be found.
    """
    source = html or ""
    _preamble, spans = scene_spans(source)
    idx = next((i for i, s in enumerate(spans) if s.scene_heading_id == scene_heading_id), None)
    if idx is None:
        return None
    span = spans[idx]
    fragment = source[span.start : span.end]
    remainder = source[: span.start] + source[span.end :]
    # Recompute spans on the remainder so insertion offsets are valid.
    _pre2, spans2 = scene_spans(remainder)
    to_index = max(0, min(int(to_index), len(spans2)))
    if to_index >= len(spans2):
        if not spans2:
            return remainder + fragment
        return remainder[: spans2[-1].end] + fragment + remainder[spans2[-1].end :]
    anchor = spans2[to_index].start
    return remainder[:anchor] + fragment + remainder[anchor:]
