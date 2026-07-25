"""Prompt library datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PromptType = Literal["core", "specialist", "playbook", "standard"]


@dataclass(frozen=True)
class PromptFrontMatter:
    id: str
    version: str
    type: PromptType
    display_name: str
    description: str
    output_schema: str
    allowed_context: tuple[str, ...] = ()
    may_propose_tools: bool = False
    may_execute_tools: bool = False
    default_priority: int = 50
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "version": self.version,
            "type": self.type,
            "displayName": self.display_name,
            "description": self.description,
            "outputSchema": self.output_schema,
            "allowedContext": list(self.allowed_context),
            "mayProposeTools": self.may_propose_tools,
            "mayExecuteTools": self.may_execute_tools,
            "defaultPriority": self.default_priority,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class PromptRecord:
    front_matter: PromptFrontMatter
    body: str
    source_path: Path
    checksum: str
    load_order: int = 0

    @property
    def id(self) -> str:
        return self.front_matter.id

    @property
    def prompt_type(self) -> PromptType:
        return self.front_matter.type

    def version_tag(self) -> str:
        return f"{self.front_matter.id}@{self.front_matter.version}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self.front_matter.to_dict(),
            "checksum": self.checksum,
            "sourcePath": str(self.source_path),
            "loadOrder": self.load_order,
            "bodyLength": len(self.body),
        }
