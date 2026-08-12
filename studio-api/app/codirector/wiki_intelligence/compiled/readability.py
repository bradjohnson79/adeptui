"""Human-readability gates for compiled Wiki pages."""

from __future__ import annotations

import re
from typing import Any

# Generic fragment titles only — canonical roots (Project Overview, Story, …) are allowed.
_BAD_TITLE = re.compile(
    r"^(theme|emerging theme|character/person|character note|project title)\s*$",
    re.I,
)
_RAW_PREFIX = re.compile(r"^(EXTRACTED|INFERRED|PROPOSED|RAW|JSON|DEBUG)\s*[:\-]", re.I)
_PAYLOADISH = re.compile(r"^\s*[\{\[]|knowledgeEntries|reloadKey|specialist_id", re.I)


def assert_wiki_readability(pages: list[dict[str, Any]], toc: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    titles: list[str] = []
    for page in pages:
        title = str(page.get("title") or "").strip()
        titles.append(title)
        if _BAD_TITLE.match(title):
            issues.append(f"generic_title:{title}")
        if _RAW_PREFIX.search(title) or _PAYLOADISH.search(title):
            issues.append(f"raw_title:{title}")
        for sec in page.get("sections") or []:
            for bullet in sec.get("bullets") or []:
                if _BAD_TITLE.match(str(bullet).strip()):
                    issues.append(f"generic_bullet:{bullet}")
                if _RAW_PREFIX.search(str(bullet)):
                    issues.append(f"raw_bullet:{bullet}")
    # Repeated Theme headings in TOC children
    child_labels: list[str] = []
    for node in toc:
        for child in node.get("children") or []:
            child_labels.append(str(child.get("label") or "").strip().lower())
    if child_labels.count("theme") >= 2:
        issues.append("repeated_theme_toc")
    # Character pollution
    for node in toc:
        if str(node.get("key")) != "characters":
            continue
        for child in node.get("children") or []:
            label = str(child.get("label") or "")
            if re.search(r"project type|aspect ratio|theme|16:9|minimax", label, re.I):
                issues.append(f"character_pollution:{label}")
    return issues
