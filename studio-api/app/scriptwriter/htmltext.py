"""HTML <-> plain text helpers for the rich-text Script Writer.

The Script Writer now persists a sanitized HTML document (``contentHtml``).
Legacy structured scripts keep their ``elements[]``. These helpers flatten
either representation into readable plain text for Co-Director context and
for back-compat read paths. No destructive conversion is performed.
"""

from __future__ import annotations

import hashlib
import html as _html
import re
from html.parser import HTMLParser
from typing import Any

from .models import ScriptDocument, ScriptElement

_BLOCK_TAGS = re.compile(r"</?(p|div|h[1-6]|li|blockquote|tr|br)\b[^>]*>", re.IGNORECASE)
_LIST_OPEN = re.compile(r"<(ul|ol)\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")


def html_to_text(html: str | None) -> str:
    """Convert sanitized HTML to readable plain text.

    - ``<p>`` / ``<div>`` / headings / ``<li>`` -> paragraph breaks
    - ``<br>`` -> newline
    - lists -> one line per item with a bullet
    - all other tags stripped
    """
    if not html:
        return ""
    s = html
    s = _LIST_OPEN.sub("\n", s)
    s = _BLOCK_TAGS.sub("\n", s)
    s = _TAG.sub("", s)
    s = _html.unescape(s)
    lines = [_WS.sub(" ", ln).strip() for ln in s.split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln:
            out.append(ln)
    return "\n\n".join(out)


def elements_to_text(elements: list[ScriptElement]) -> str:
    """Flatten legacy structured elements to readable plain text."""
    parts: list[str] = []
    for el in sorted(elements, key=lambda e: e.order):
        text = (el.text or "").strip()
        if not text:
            continue
        if el.type == "scene_heading":
            parts.append(text.upper())
        elif el.type == "character":
            parts.append(text.upper())
        elif el.type == "parenthetical":
            parts.append(f"({text})")
        elif el.type == "transition":
            parts.append(text.upper())
        else:
            parts.append(text)
    return "\n\n".join(parts)


def document_text(doc: ScriptDocument) -> str:
    """Return the readable plain text of a document, preferring HTML content.

    New edits are stored as HTML; legacy structured scripts are flattened from
    their elements. The original elements are never destroyed.
    """
    if doc.contentType == "html" and doc.contentHtml:
        return html_to_text(doc.contentHtml)
    if doc.contentHtml:
        return html_to_text(doc.contentHtml)
    return elements_to_text(doc.elements)


def document_html_for_display(doc: ScriptDocument) -> str:
    """Return an HTML representation of a document for editor hydration.

    Prefers stored ``contentHtml``; otherwise converts legacy elements to HTML
    on the fly without mutating the persisted document.
    """
    if doc.contentHtml:
        return doc.contentHtml
    return elements_to_html(doc.elements)


def elements_to_html(elements: list[ScriptElement]) -> str:
    """Convert legacy structured elements to HTML for display (non-destructive)."""
    if not elements:
        return "<p></p>"
    indent = 40
    parts: list[str] = []
    for el in sorted(elements, key=lambda e: e.order):
        text = _html.escape(el.text or "")
        if el.type == "scene_heading":
            parts.append(f"<h1>{text}</h1>")
        elif el.type == "character":
            parts.append(f'<p style="margin-left: {indent * 6}px; text-transform: uppercase;">{text}</p>')
        elif el.type == "parenthetical":
            parts.append(f'<p style="margin-left: {indent * 7}px; font-style: italic;">{text}</p>')
        elif el.type == "dialogue":
            parts.append(f'<p style="margin-left: {indent * 6}px; margin-right: {indent * 6}px;">{text}</p>')
        elif el.type == "transition":
            parts.append(f'<p style="text-align: right; text-transform: uppercase;">{text}</p>')
        elif el.type == "shot":
            parts.append(f'<p style="text-transform: uppercase; font-weight: 600;">{text}</p>')
        else:
            parts.append(f"<p>{text}</p>")
    return "".join(parts)


def stats_text(doc: ScriptDocument) -> dict[str, Any]:
    """Return lightweight stats derived from the readable text of a document."""
    text = document_text(doc)
    words = len(text.split())
    els = html_scene_elements(doc.contentHtml or "") if html_has_visible_text(doc.contentHtml) else doc.elements
    scenes = sum(1 for e in els if e.type == "scene_heading")
    return {"words": words, "scenes": scenes, "characters": len(text)}


# ── Canonical HTML → element projection (CDX-051) ──────────────────────────


def html_has_visible_text(html: str | None) -> bool:
    """True when the HTML carries any visible text (i.e. is not a blank doc)."""
    if not html:
        return False
    return bool(_TAG.sub("", html).strip())


class _BlockCollector(HTMLParser):
    """Collect block-level (tag, style, indent_px, text) tuples from HTML."""

    _BLOCK_TAGS = {"p", "div", "li", "blockquote", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._cur_tag = "p"
        self._cur_style = ""
        self._cur_indent = 0
        self._cur_text = []

    def _is_block(self, tag: str) -> bool:
        return tag in self._BLOCK_TAGS or (len(tag) == 2 and tag[0] == "h" and tag[1] in "123456")

    def _flush(self) -> None:
        self.blocks.append(
            (self._cur_tag, self._cur_style, self._cur_indent, "".join(self._cur_text).strip())
        )
        self._cur_text = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self._cur_text.append("\n")
            return
        if tag == "hr":
            self._cur_text.append(" ")
            return
        if self._is_block(tag):
            self._flush()
            self._cur_tag = tag
            self._cur_style = ""
            self._cur_indent = 0
            for k, v in attrs or []:
                kl = (k or "").lower()
                if kl == "style":
                    self._cur_style = v or ""
                elif kl == "data-indent":
                    try:
                        self._cur_indent = int(str(v or "0"))
                    except (TypeError, ValueError):
                        self._cur_indent = 0

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._is_block(tag):
            self._flush()
            self._cur_tag = "p"
            self._cur_style = ""
            self._cur_indent = 0

    def handle_data(self, data: str) -> None:
        self._cur_text.append(data)


def html_blocks(html: str | None) -> list[tuple[str, str, int, str]]:
    """Parse sanitized rich-text HTML into (tag, style, indent_px, text) blocks."""
    if not html:
        return []
    parser = _BlockCollector()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    return parser.blocks


def _style_map(style: str) -> dict[str, str]:
    out = {}
    for part in (style or "").split(";"):
        if ":" in part:
            k, _, v = part.partition(":")
            out[k.strip().lower()] = v.strip().lower()
    return out


def _margin_left_px(style: str) -> int:
    low = (style or "").lower()
    idx = low.find("margin-left")
    if idx < 0:
        return 0
    rest = low[idx + len("margin-left") :]
    digits = ""
    for ch in rest:
        if ch.isdigit() or ch == ".":
            digits += ch
        elif digits:
            break
    try:
        return int(float(digits))
    except ValueError:
        return 0


def _is_character_cue(text: str) -> bool:
    """Heuristic: a short ALL-CAPS line is a character cue (screenplay HTML)."""
    t = (text or "").strip()
    if not t or t.startswith("("):
        return False
    if len(t) > 80 or t.endswith((".", "!", "?")):
        return False
    return any(ch.isalpha() for ch in t) and t == t.upper()


def _html_scene_id(heading: str, occurrence: int) -> str:
    digest = hashlib.sha1((heading or "").upper().encode("utf-8")).hexdigest()[:12]
    return f"html-scene-{digest}" if occurrence <= 1 else f"html-scene-{digest}-{occurrence}"


def html_scene_elements(html: str | None) -> list[ScriptElement]:
    """Derive normalized script elements from sanitized rich-text HTML.

    CDX-051: typed HTML is the canonical script content, so element-based
    features (navigator, stats, scene analysis, Timeline-prep, continuity,
    Bible detection) must read the HTML instead of stale/default elements.
    Rich-text HTML carries no element type semantics, so this projection
    uses the editors structural conventions:

    - h1..h6 headings           -> scene heading
    - indented paragraphs       -> parenthetical (starts with "(" or italic),
                                   character cue (short ALL-CAPS), else dialogue
    - right-aligned uppercase   -> transition
    - everything else           -> action

    Scene heading ids are deterministic hashes of the heading text so
    navigator selections survive saves. This function is pure; it never
    writes to any store.
    """
    elements = []
    order = 0
    scene_no = 0
    heading_counts = {}
    for tag, style, indent, raw_text in html_blocks(html):
        text = " ".join((raw_text or "").split()).strip()
        st = _style_map(style)
        if tag.startswith("h"):
            heading = text or "INT. LOCATION - DAY"
            scene_no += 1
            heading_counts[heading] = heading_counts.get(heading, 0) + 1
            elements.append(
                ScriptElement(
                    id=_html_scene_id(heading, heading_counts[heading]),
                    type="scene_heading",
                    text=heading,
                    order=order,
                    sceneNumber=str(scene_no),
                )
            )
            order += 1
            continue
        if st.get("text-align") == "right" and st.get("text-transform") == "uppercase":
            etype = "transition"
        elif max(_margin_left_px(style), indent) >= 200:
            if text.startswith("(") or st.get("font-style") == "italic":
                etype = "parenthetical"
            elif st.get("text-transform") == "uppercase" or _is_character_cue(text):
                etype = "character"
            else:
                etype = "dialogue"
        elif text:
            etype = "action"
        else:
            continue
        if not text:
            continue
        elements.append(
            ScriptElement(
                id=f"html-{etype}-{order}",
                type=etype,  # type: ignore[arg-type]
                text=text,
                order=order,
            )
        )
        order += 1
    current_speaker = None
    for el in elements:
        if el.type == "scene_heading":
            current_speaker = None
        elif el.type == "character":
            current_speaker = el.text
        elif el.type == "dialogue" and current_speaker:
            el.metadata["speaker"] = current_speaker
    return elements
