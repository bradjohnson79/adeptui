"""Model Compatibility Registry — projection over Certified Workflow Registry (4.1B)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from .job_model import ProviderKindVideo

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CATALOG = _REPO_ROOT / "config" / "video-runtime" / "compatibility-catalog.json"
_CERTIFIED = _REPO_ROOT / "config" / "video-workflows" / "certified-registry.json"


@dataclass(frozen=True)
class CompatibilityEntry:
    model_family: str
    workflow_key: str
    workflow_version: str
    required_nodes: tuple[str, ...]
    required_models: tuple[str, ...]
    required_extensions: tuple[str, ...]
    min_vram_gb: float
    recommended_vram_gb: float
    supported_inputs: tuple[str, ...]
    unsupported_inputs: tuple[str, ...]
    supported_outputs: tuple[str, ...]
    known_limitations: tuple[str, ...]
    capability_state: str
    provider_kind: ProviderKindVideo
    capability_id: str
    node_alias_groups: tuple[frozenset[str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "modelFamily": self.model_family,
            "workflowKey": self.workflow_key,
            "workflowVersion": self.workflow_version,
            "requiredNodes": list(self.required_nodes),
            "requiredModels": list(self.required_models),
            "requiredExtensions": list(self.required_extensions),
            "minVramGb": self.min_vram_gb,
            "recommendedVramGb": self.recommended_vram_gb,
            "supportedInputs": list(self.supported_inputs),
            "unsupportedInputs": list(self.unsupported_inputs),
            "supportedOutputs": list(self.supported_outputs),
            "knownLimitations": list(self.known_limitations),
            "capabilityState": self.capability_state,
            "providerKind": self.provider_kind.value,
            "capabilityId": self.capability_id,
            "nodeAliasGroups": [sorted(g) for g in self.node_alias_groups],
        }


def _parse_entry(raw: Mapping[str, Any]) -> CompatibilityEntry:
    alias_groups = tuple(
        frozenset(str(x) for x in group)
        for group in (raw.get("nodeAliasGroups") or [])
        if isinstance(group, list)
    )
    pk = str(raw.get("providerKind") or "local")
    try:
        provider = ProviderKindVideo(pk)
    except ValueError:
        provider = ProviderKindVideo.LOCAL
    return CompatibilityEntry(
        model_family=str(raw.get("modelFamily") or ""),
        workflow_key=str(raw.get("workflowKey") or ""),
        workflow_version=str(raw.get("workflowVersion") or ""),
        required_nodes=tuple(str(x) for x in (raw.get("requiredNodes") or [])),
        required_models=tuple(str(x) for x in (raw.get("requiredModels") or [])),
        required_extensions=tuple(str(x) for x in (raw.get("requiredExtensions") or [])),
        min_vram_gb=float(raw.get("minVramGb") or 0),
        recommended_vram_gb=float(raw.get("recommendedVramGb") or 0),
        supported_inputs=tuple(str(x) for x in (raw.get("supportedInputs") or [])),
        unsupported_inputs=tuple(str(x) for x in (raw.get("unsupportedInputs") or [])),
        supported_outputs=tuple(str(x) for x in (raw.get("supportedOutputs") or [])),
        known_limitations=tuple(str(x) for x in (raw.get("knownLimitations") or [])),
        capability_state=str(raw.get("capabilityState") or "deferred"),
        provider_kind=provider,
        capability_id=str(raw.get("capabilityId") or raw.get("workflowKey") or ""),
        node_alias_groups=alias_groups,
    )


def _from_certified() -> tuple[CompatibilityEntry, ...] | None:
    """Prefer Certified Workflow Registry when present (single authority)."""
    if not _CERTIFIED.is_file():
        return None
    try:
        from .certified_registry import compatibility_projection, reload_registry

        reload_registry()
        projected = compatibility_projection()
        if not projected:
            return None
        return tuple(_parse_entry(item) for item in projected)
    except Exception:
        return None


@lru_cache(maxsize=4)
def load_catalog(path: str | None = None) -> tuple[CompatibilityEntry, ...]:
    if path is None:
        certified = _from_certified()
        if certified is not None:
            return certified
    catalog_path = Path(path) if path else _DEFAULT_CATALOG
    if not catalog_path.is_file():
        return ()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return ()
    return tuple(_parse_entry(item) for item in entries if isinstance(item, Mapping))


def reload_catalog() -> None:
    load_catalog.cache_clear()
    try:
        from .certified_registry import reload_registry

        reload_registry()
    except Exception:
        pass


def list_entries() -> list[CompatibilityEntry]:
    return list(load_catalog())


def get_entry(workflow_key: str) -> CompatibilityEntry | None:
    for entry in load_catalog():
        if entry.workflow_key == workflow_key:
            return entry
    return None


def missing_nodes(entry: CompatibilityEntry, node_types: set[str] | None) -> list[str] | None:
    if node_types is None:
        return None
    missing = {n for n in entry.required_nodes if n not in node_types}
    for group in entry.node_alias_groups:
        if missing & group and (node_types & group):
            missing -= group
    # Default LatentSync alias if catalog omitted groups
    if entry.workflow_key == "lipsync.latentsync":
        alt = frozenset({"D_LatentSyncNode", "LatentSyncNode"})
        if missing & alt and (node_types & alt):
            missing -= alt
    return sorted(missing)


def validate_inputs(
    entry: CompatibilityEntry,
    present_inputs: Iterable[str],
) -> list[str]:
    """Return unsupported input names that were supplied."""
    present = {str(x) for x in present_inputs}
    blocked = set(entry.unsupported_inputs)
    if "*" in blocked and present:
        return sorted(present)
    return sorted(present & blocked)


def assert_not_deferred(entry: CompatibilityEntry) -> None:
    if entry.capability_state in {"deferred", "retired"}:
        from ..capabilities.errors import CapabilityError

        raise CapabilityError(
            code="CAPABILITY_DEFERRED",
            message=(
                f"{entry.workflow_key} is deferred and cannot execute. "
                f"{(entry.known_limitations[0] if entry.known_limitations else '')}"
            ).strip(),
            details={"workflowKey": entry.workflow_key, "capabilityId": entry.capability_id},
            recoverable=False,
            recommended_action="use_supported_workflow",
        )


def catalog_as_dict() -> list[dict[str, Any]]:
    return [e.to_dict() for e in list_entries()]
