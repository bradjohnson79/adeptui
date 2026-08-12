"""Image Workflow Registry loader (M42 W2) — domain of unified Workflow Resolver."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REGISTRY = _REPO_ROOT / "config" / "image-workflows" / "certified-registry.json"

VALID_STATUSES = frozenset(
    {"Draft", "Built", "SmokeTested", "Certified", "Deferred", "Blocked", "Retired"}
)
VALID_CATEGORIES = frozenset(
    {
        "Generation",
        "Editing",
        "Reference",
        "Restoration",
        "Utility",
        "Training",
        "Identity",
        "Compositing",
        "Publishing",
    }
)


@dataclass(frozen=True)
class ImageWorkflow:
    workflow_id: str
    workflow_key: str
    workflow_version: str
    modality: str
    category: str
    status: str
    engine: str
    provider_kind: str
    builder: str | None
    builder_path: str | None
    operation: str
    model_family: str = "zimage"
    model_variant: str = ""
    provider: str = "comfyui"
    supported_operations: tuple[str, ...] = ()
    required_runtime: str = "comfy"
    required_nodes: tuple[str, ...] = ()
    required_models: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    # Nodes required only when optional inputs are exercised (e.g. Krea 2
    # reference/LoRA conditioning) — validated at cert time, not per execution.
    optional_nodes: tuple[str, ...] = ()
    supported_outputs: tuple[str, ...] = ()
    cancellation_support: bool = True
    output_validation: bool = True
    limitations: tuple[str, ...] = ()
    api_contract: dict[str, Any] = field(default_factory=dict)
    vram_profile: dict[str, Any] = field(default_factory=dict)
    # Contract-governed runtime extras (e.g. Krea 2 timestep-shift "mu") — merged
    # into CanonicalImageWorkflowContract.runtime_requirements by the resolver.
    runtime_params: dict[str, Any] = field(default_factory=dict)
    fingerprints: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    provenance_policy: dict[str, Any] = field(default_factory=dict)
    certification_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "workflowKey": self.workflow_key,
            "workflowVersion": self.workflow_version,
            "modality": self.modality,
            "category": self.category,
            "status": self.status,
            "modelFamily": self.model_family,
            "modelVariant": self.model_variant,
            "engine": self.engine,
            "providerKind": self.provider_kind,
            "provider": self.provider,
            "builder": self.builder,
            "builderPath": self.builder_path,
            "operation": self.operation,
            "supportedOperations": list(self.supported_operations),
            "requiredRuntime": self.required_runtime,
            "requiredNodes": list(self.required_nodes),
            "requiredModels": list(self.required_models),
            "requiredInputs": list(self.required_inputs),
            "optionalInputs": list(self.optional_inputs),
            "optionalNodes": list(self.optional_nodes),
            "supportedOutputs": list(self.supported_outputs),
            "cancellationSupport": self.cancellation_support,
            "outputValidation": self.output_validation,
            "limitations": list(self.limitations),
            "apiContract": dict(self.api_contract),
            "vramProfile": dict(self.vram_profile),
            "runtimeParams": dict(self.runtime_params),
            "fingerprints": dict(self.fingerprints),
            "capabilities": dict(self.capabilities),
            "provenancePolicy": dict(self.provenance_policy),
            "certificationRecordId": self.certification_record_id,
        }


def _parse_entry(raw: dict[str, Any]) -> ImageWorkflow:
    status = str(raw.get("status") or "Draft")
    if status not in VALID_STATUSES:
        status = "Draft"
    category = str(raw.get("category") or "Generation")
    if category not in VALID_CATEGORIES:
        category = "Generation"
    return ImageWorkflow(
        workflow_id=str(raw.get("workflowId") or raw.get("workflow_id") or ""),
        workflow_key=str(raw.get("workflowKey") or raw.get("workflow_key") or ""),
        workflow_version=str(raw.get("workflowVersion") or raw.get("workflow_version") or "1.0.0"),
        modality=str(raw.get("modality") or "image"),
        category=category,
        status=status,
        engine=str(raw.get("engine") or "zimage"),
        provider_kind=str(raw.get("providerKind") or raw.get("provider_kind") or "local"),
        builder=raw.get("builder"),
        builder_path=raw.get("builderPath") or raw.get("builder_path"),
        operation=str(raw.get("operation") or "image.generate"),
        model_family=str(raw.get("modelFamily") or raw.get("model_family") or raw.get("engine") or "zimage"),
        model_variant=str(raw.get("modelVariant") or raw.get("model_variant") or ""),
        provider=str(raw.get("provider") or raw.get("providerKind") or "comfyui"),
        supported_operations=tuple(raw.get("supportedOperations") or raw.get("supported_operations") or ()),
        required_runtime=str(raw.get("requiredRuntime") or raw.get("required_runtime") or "comfy"),
        required_nodes=tuple(raw.get("requiredNodes") or raw.get("required_nodes") or ()),
        required_models=tuple(raw.get("requiredModels") or raw.get("required_models") or ()),
        required_inputs=tuple(raw.get("requiredInputs") or raw.get("required_inputs") or ()),
        optional_inputs=tuple(raw.get("optionalInputs") or raw.get("optional_inputs") or ()),
        optional_nodes=tuple(raw.get("optionalNodes") or raw.get("optional_nodes") or ()),
        supported_outputs=tuple(raw.get("supportedOutputs") or raw.get("supported_outputs") or ()),
        cancellation_support=bool(raw.get("cancellationSupport", True)),
        output_validation=bool(raw.get("outputValidation", True)),
        limitations=tuple(raw.get("limitations") or ()),
        api_contract=dict(raw.get("apiContract") or raw.get("api_contract") or {}),
        vram_profile=dict(raw.get("vramProfile") or raw.get("vram_profile") or {}),
        runtime_params=dict(raw.get("runtimeParams") or raw.get("runtime_params") or {}),
        fingerprints=dict(raw.get("fingerprints") or {}),
        capabilities=dict(raw.get("capabilities") or {}),
        provenance_policy=dict(raw.get("provenancePolicy") or raw.get("provenance_policy") or {}),
        certification_record_id=raw.get("certificationRecordId") or raw.get("certification_record_id"),
    )


@lru_cache(maxsize=2)
def load_registry(path: str | None = None) -> tuple[ImageWorkflow, ...]:
    reg_path = Path(path) if path else _DEFAULT_REGISTRY
    if not reg_path.is_file():
        return ()
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return ()
    return tuple(_parse_entry(e) for e in entries if isinstance(e, dict))


def reload_registry() -> None:
    load_registry.cache_clear()


def list_workflows(*, category: str | None = None, model_family: str | None = None) -> list[ImageWorkflow]:
    items = list(load_registry())
    if category:
        items = [w for w in items if w.category == category]
    if model_family:
        items = [w for w in items if w.model_family == model_family]
    return items


def get_workflow(key: str) -> Optional[ImageWorkflow]:
    for w in load_registry():
        if w.workflow_key == key or w.workflow_id == key:
            return w
    return None


def draft_keys() -> list[str]:
    return [w.workflow_key for w in load_registry()]


def production_ready_keys() -> list[str]:
    return [w.workflow_key for w in load_registry() if w.status == "Certified"]


def family_keys() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for w in load_registry():
        out.setdefault(w.model_family, []).append(w.workflow_key)
    return out


def assert_executable(key: str, *, allow_non_certified: bool = False) -> ImageWorkflow:
    wf = get_workflow(key)
    if wf is None:
        raise RuntimeError(f"Unknown image workflow: {key}")
    if wf.status in {"Blocked", "Retired"}:
        raise RuntimeError(f"Image workflow blocked/retired: {key}")
    if wf.status == "Deferred":
        raise RuntimeError(f"Image workflow deferred: {key}")
    if not allow_non_certified and wf.status != "Certified":
        raise RuntimeError(f"Image workflow not Certified: {key} status={wf.status}")
    return wf
