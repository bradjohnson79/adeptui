"""Explicit creator Wiki writes vs model-inferred candidates."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...notes.service import promote_note_to_wiki

_EXPLICIT = re.compile(
    r"\b("
    r"add this to the wiki|put this (in|under|on)|make this canon|"
    r"document this as|remember this as|add this to .+('s)? (wiki )?profile|"
    r"this is canon|belongs in the wiki"
    r")\b",
    re.I,
)


def detect_explicit_wiki_write(message: str) -> bool:
    return bool(_EXPLICIT.search(message or ""))


def promote_explicit_wiki_text(
    db: Session,
    project_id: str,
    *,
    text: str,
    destination: str = "story",
    page_hint: str | None = None,
) -> dict[str, Any]:
    return promote_note_to_wiki(
        db,
        project_id,
        text=text,
        destination=destination,
        authority="USER_EXPLICIT_WIKI_WRITE",
        page_hint=page_hint,
    )
