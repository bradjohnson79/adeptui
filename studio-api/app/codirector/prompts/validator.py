"""Validate prompt front matter at load time."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import PromptFrontMatter, PromptType

KNOWN_PROMPT_TYPES: frozenset[str] = frozenset({"core", "specialist", "playbook", "standard"})
KNOWN_OUTPUT_SCHEMAS: frozenset[str] = frozenset(
    {
        "core-behavior-v1",
        "synthesis-v1",
        "specialist-finding-v1",
        "playbook-v1",
        "standard-v1",
    }
)
KNOWN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "project_overview",
        "story",
        "scene",
        "shot",
        "characters",
        "locations",
        "objects",
        "wardrobe",
        "continuity",
        "visual_language",
        "canon",
        "references",
        "capabilities",
        "production_decisions",
        "previous_shot",
        "next_shot",
        "audio",
        "vfx",
        "production_plan",
        # M2.14 Storyteller / Sound Producer context keys
        "tone",
        "music",
        "dialogue",
    }
)
_REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "version",
    "type",
    "display_name",
    "description",
    "output_schema",
    "allowed_context",
    "may_propose_tools",
    "may_execute_tools",
    "default_priority",
    "enabled",
)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_TYPE_DIRS: dict[str, str] = {
    "core": "core",
    "specialist": "specialists",
    "playbook": "playbooks",
    "standard": "standards",
}


@dataclass(frozen=True)
class PromptValidationIssue:
    path: str
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"path": self.path, "message": self.message, "field": self.field}


def _coerce_bool(value: Any, field: str, path: Path, issues: list[PromptValidationIssue]) -> bool:
    if isinstance(value, bool):
        return value
    issues.append(PromptValidationIssue(str(path), f"{field} must be a boolean.", field))
    return False


def _coerce_int(value: Any, field: str, path: Path, issues: list[PromptValidationIssue]) -> int:
    if isinstance(value, int):
        return value
    issues.append(PromptValidationIssue(str(path), f"{field} must be an integer.", field))
    return 0


def _coerce_context(value: Any, path: Path, issues: list[PromptValidationIssue]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        issues.append(PromptValidationIssue(str(path), "allowed_context must be a list.", "allowed_context"))
        return ()
    out: list[str] = []
    for item in value:
        key = str(item)
        if key not in KNOWN_CONTEXT_KEYS:
            issues.append(
                PromptValidationIssue(str(path), f"Unknown context key '{key}'.", "allowed_context")
            )
        out.append(key)
    return tuple(out)


def validate_front_matter_dict(
    raw: dict[str, Any], *, path: Path, seen_ids: set[str]
) -> tuple[PromptFrontMatter | None, list[PromptValidationIssue]]:
    issues: list[PromptValidationIssue] = []
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            issues.append(PromptValidationIssue(str(path), f"Missing required field '{field}'.", field))

    prompt_id = str(raw.get("id") or "").strip()
    if not prompt_id:
        issues.append(PromptValidationIssue(str(path), "id is required.", "id"))
    elif prompt_id in seen_ids:
        issues.append(PromptValidationIssue(str(path), f"Duplicate prompt id '{prompt_id}'.", "id"))

    version = str(raw.get("version") or "").strip()
    if version and not _SEMVER_RE.match(version):
        issues.append(PromptValidationIssue(str(path), "version must be semantic (x.y.z).", "version"))

    prompt_type = str(raw.get("type") or "").strip()
    if prompt_type not in KNOWN_PROMPT_TYPES:
        issues.append(PromptValidationIssue(str(path), f"Unknown prompt type '{prompt_type}'.", "type"))

    output_schema = str(raw.get("output_schema") or "").strip()
    if output_schema not in KNOWN_OUTPUT_SCHEMAS:
        issues.append(
            PromptValidationIssue(str(path), f"Unknown output schema '{output_schema}'.", "output_schema")
        )

    may_execute = _coerce_bool(raw.get("may_execute_tools"), "may_execute_tools", path, issues)
    if may_execute:
        issues.append(
            PromptValidationIssue(
                str(path),
                "may_execute_tools must be false — specialists never execute tools directly.",
                "may_execute_tools",
            )
        )

    expected_dir = _TYPE_DIRS.get(prompt_type, "")
    if expected_dir and expected_dir not in path.parts:
        issues.append(
            PromptValidationIssue(
                str(path),
                f"Prompt type '{prompt_type}' should live under '{expected_dir}/'.",
                "type",
            )
        )

    if issues:
        return None, issues

    seen_ids.add(prompt_id)
    front = PromptFrontMatter(
        id=prompt_id,
        version=version,
        type=prompt_type,  # type: ignore[arg-type]
        display_name=str(raw.get("display_name") or prompt_id),
        description=str(raw.get("description") or ""),
        output_schema=output_schema,
        allowed_context=_coerce_context(raw.get("allowed_context"), path, issues),
        may_propose_tools=_coerce_bool(raw.get("may_propose_tools"), "may_propose_tools", path, issues),
        may_execute_tools=False,
        default_priority=_coerce_int(raw.get("default_priority"), "default_priority", path, issues),
        enabled=_coerce_bool(raw.get("enabled"), "enabled", path, issues),
    )
    if issues:
        return None, issues
    return front, []
