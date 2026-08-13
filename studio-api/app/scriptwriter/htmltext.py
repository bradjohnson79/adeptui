"""HTML <-> plain text helpers for the rich-text Script Writer.

The Script Writer now persists a sanitized HTML document (``contentHtml``).
Legacy structured scripts keep their ``elements[]``. These helpers flatten
either representation into readable plain text for Co-Director context and
for back-compat read paths. No destructive conversion is performed.
"""

from __future__ import annotations

import html as _html
import re
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
    scenes = sum(1 for e in doc.elements if e.type == "scene_heading")
    return {"words": words, "scenes": scenes, "characters": len(text)}
