"""Specialist registry built from prompt front matter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..prompts.loader import PromptLibrary, get_prompt_library
from ..prompts.types import PromptRecord
from .contracts import CONTRACTS, SpecialistContract, get_contract, resolve_role


@dataclass(frozen=True)
class SpecialistDefinition:
    id: str
    prompt_id: str
    display_name: str
    description: str
    enabled: bool
    allowed_context: tuple[str, ...]
    output_schema_id: str
    may_propose_tools: bool
    may_execute_tools: bool
    default_priority: int
    prompt_version: str
    timeout_ms: int = 30_000
    max_retries: int = 0

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "promptId": self.prompt_id,
            "displayName": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "allowedContext": list(self.allowed_context),
            "outputSchemaId": self.output_schema_id,
            "mayProposeTools": self.may_propose_tools,
            "mayExecuteTools": self.may_execute_tools,
            "defaultPriority": self.default_priority,
            "promptVersion": self.prompt_version,
            "timeoutMs": self.timeout_ms,
            "maxRetries": self.max_retries,
        }
        contract = get_contract(self.id)
        if contract is not None:
            payload["contract"] = contract.to_dict()
            payload["productRole"] = contract.product_role
            payload["approvalRequired"] = contract.approval_required
            payload["escalationPath"] = contract.escalation_path
        return payload


class SpecialistRegistry:
    def __init__(self, library: PromptLibrary | None = None) -> None:
        self._library = library or get_prompt_library()
        self._definitions: dict[str, SpecialistDefinition] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        self._definitions.clear()
        for record in self._library.by_type("specialist"):
            definition = self._from_prompt(record)
            if definition.enabled:
                self._definitions[definition.id] = definition

    def _from_prompt(self, record: PromptRecord) -> SpecialistDefinition:
        front = record.front_matter
        if front.may_execute_tools:
            raise ValueError(f"Specialist '{front.id}' declares may_execute_tools=true — forbidden.")
        return SpecialistDefinition(
            id=front.id,
            prompt_id=front.id,
            display_name=front.display_name,
            description=front.description,
            enabled=front.enabled,
            allowed_context=front.allowed_context,
            output_schema_id=front.output_schema,
            may_propose_tools=front.may_propose_tools,
            may_execute_tools=False,
            default_priority=front.default_priority,
            prompt_version=front.version,
        )

    def get(self, specialist_id: str) -> SpecialistDefinition | None:
        return self._definitions.get(specialist_id)

    def all(self) -> list[SpecialistDefinition]:
        return list(self._definitions.values())

    def require(self, specialist_id: str) -> SpecialistDefinition:
        definition = self.get(specialist_id)
        if definition is None:
            raise KeyError(specialist_id)
        return definition

    def all_enabled(self) -> tuple[SpecialistDefinition, ...]:
        return tuple(
            sorted(self._definitions.values(), key=lambda d: (-d.default_priority, d.id))
        )

    def ids(self) -> frozenset[str]:
        return frozenset(self._definitions.keys())

    def validate_ids(self, specialist_ids: Iterable[str]) -> list[str]:
        unknown = [sid for sid in specialist_ids if sid not in self._definitions]
        return unknown

    def contract(self, specialist_id: str) -> SpecialistContract | None:
        return get_contract(specialist_id)

    def resolve(self, role_or_id: str) -> SpecialistDefinition | None:
        sid = resolve_role(role_or_id) or role_or_id
        return self.get(sid)

    def inventory(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for definition in self.all_enabled():
            row = definition.to_dict()
            if "contract" not in row and definition.id in CONTRACTS:
                row["contract"] = CONTRACTS[definition.id].to_dict()
            rows.append(row)
        return rows
