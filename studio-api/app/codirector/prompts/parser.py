"""Parse YAML front matter from Co-Director Markdown prompt files."""

from __future__ import annotations

import re
from typing import Any

_FRONT_MATTER_RE = re.compile(r"^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$", re.MULTILINE)


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _parse_yaml_block(block: str) -> dict[str, Any]:
    """Minimal YAML parser for the predictable front-matter shape in prompt files."""

    root: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] | None = None

    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key is not None and current_list is not None:
            current_list.append(_parse_scalar(line[4:]))
            continue
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if value == "":
            current_key = key
            current_list = []
            root[key] = current_list
            continue
        current_key = None
        current_list = None
        root[key] = _parse_scalar(value)
    return root


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return parsed front matter and Markdown body."""

    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError("Prompt file is missing YAML front matter delimiters.")
    front = _parse_yaml_block(match.group(1))
    body = match.group(2).lstrip("\n")
    return front, body


def parse_markdown_prompt(text: str) -> tuple[dict[str, Any], str]:
    return split_front_matter(text)
