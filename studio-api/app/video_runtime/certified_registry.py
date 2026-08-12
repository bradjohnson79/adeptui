"""Certified Workflow Registry — single authority for video workflows (M41 4.1B)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from .job_model import ProviderKindVideo

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REGISTRY = _REPO_ROOT / "config" / "video-workflows" / "certified-registry.json"

VALID_STATUSES = frozenset(
    {"Draft", "Built", "SmokeTested", "Certified", "Deferred", "Blocked", "Retired"}
)


@dataclass(frozen=True)
class VramProfile:
    minimum_gb: float = 0
    recommended_gb: float = 0
    heavy_gb: float = 0
    peak_gb: float = 0
    safe_concurrency: int = 1
    recommended_gpu: str = "n/a"
    state: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimumGb": self.minimum_gb,
            "recommendedGb": self.recommended_gb,
            "heavyGb": self.heavy_gb,
            "peakGb": self.peak_gb,
            "safeConcurrency": self.safe_concurrency,
            "recommendedGpu": self.recommended_gpu,
            "state": self.state,
        }


@dataclass(frozen=True)
class Fingerprints:
    graph_hash: str | None = None
    builder_hash: str | None = None
    node_inventory_hash: str | None = None
    model_inventory_hash: str | None = None
    topology_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "graphHash": self.graph_hash,
            "builderHash": self.builder_hash,
            "nodeInventoryHash": self.node_inventory_hash,
            "modelInventoryHash": self.model_inventory_hash,
            "topologyHash": self.topology_hash,
        }


@dataclass(frozen=True)
class CertificationRecord:
    workflow_id: str
    workflow_key: str
    workflow_version: str
    status: str
    certified_at: str | None = None
    certified_by: str | None = None
    evidence: Mapping[str, str] = field(default_factory=dict)
    comfy_version: str | None = None
    node_inventory: str | None = None
    model_inventory: str | None = None
    fingerprints: Fingerprints = field(default_factory=Fingerprints)
    artifact_refs: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "workflowKey": self.workflow_key,
            "workflowVersion": self.workflow_version,
            "status": self.status,
            "certifiedAt": self.certified_at,
            "certifiedBy": self.certified_by,
            "evidence": dict(self.evidence),
            "comfyVersion": self.comfy_version,
            "nodeInventory": self.node_inventory,
            "modelInventory": self.model_inventory,
            "fingerprints": self.fingerprints.to_dict(),
            "artifactRefs": list(self.artifact_refs),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CertifiedWorkflow:
    workflow_id: str
    workflow_key: str
    workflow_version: str
    modality: str
    engine: str
    generation_mode: str
    status: str
    model_family: str
    builder: str | None
    builder_path: str | None
    required_nodes: tuple[str, ...]
    required_models: tuple[str, ...]
    required_extensions: tuple[str, ...]
    supported_inputs: tuple[str, ...]
    unsupported_inputs: tuple[str, ...]
    supported_outputs: tuple[str, ...]
    limitations: tuple[str, ...]
    vram_profile: VramProfile
    cancellation_support: bool
    output_validation: bool
    playback_validation: bool
    api_contract: Mapping[str, Any]
    fingerprints: Fingerprints
    certification_record: CertificationRecord | None
    provider_kind: ProviderKindVideo
    capability_id: str
    orchestration: bool = False
    node_alias_groups: tuple[frozenset[str], ...] = ()
    certification_record_id: str | None = None

    @property
    def versioned_key(self) -> str:
        return f"{self.workflow_key}@{self.workflow_version}"

    @property
    def is_production_ready(self) -> bool:
        """Certified only with a Certification Record pointer or full record."""
        if self.status != "Certified":
            return False
        return bool(self.certification_record_id or self.certification_record)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "workflowKey": self.workflow_key,
            "workflowVersion": self.workflow_version,
            "versionedKey": self.versioned_key,
            "modality": self.modality,
            "engine": self.engine,
            "generationMode": self.generation_mode,
            "status": self.status,
            "modelFamily": self.model_family,
            "builder": self.builder,
            "builderPath": self.builder_path,
            "requiredNodes": list(self.required_nodes),
            "requiredModels": list(self.required_models),
            "requiredExtensions": list(self.required_extensions),
            "supportedInputs": list(self.supported_inputs),
            "unsupportedInputs": list(self.unsupported_inputs),
            "supportedOutputs": list(self.supported_outputs),
            "limitations": list(self.limitations),
            "vramProfile": self.vram_profile.to_dict(),
            "cancellationSupport": self.cancellation_support,
            "outputValidation": self.output_validation,
            "playbackValidation": self.playback_validation,
            "apiContract": dict(self.api_contract),
            "fingerprints": self.fingerprints.to_dict(),
            "certificationRecordId": self.certification_record_id,
            "certificationRecord": (
                self.certification_record.to_dict() if self.certification_record else None
            ),
            "providerKind": self.provider_kind.value,
            "capabilityId": self.capability_id,
            "orchestration": self.orchestration,
            "nodeAliasGroups": [sorted(g) for g in self.node_alias_groups],
            "productionReady": self.is_production_ready,
        }


def _parse_vram(raw: Mapping[str, Any] | None) -> VramProfile:
    raw = raw or {}
    return VramProfile(
        minimum_gb=float(raw.get("minimumGb") or 0),
        recommended_gb=float(raw.get("recommendedGb") or 0),
        heavy_gb=float(raw.get("heavyGb") or 0),
        peak_gb=float(raw.get("peakGb") or 0),
        safe_concurrency=int(raw.get("safeConcurrency") or 1),
        recommended_gpu=str(raw.get("recommendedGpu") or "n/a"),
        state=str(raw.get("state") or "UNKNOWN"),
    )


def _parse_fingerprints(raw: Mapping[str, Any] | None) -> Fingerprints:
    raw = raw or {}
    return Fingerprints(
        graph_hash=raw.get("graphHash"),
        builder_hash=raw.get("builderHash"),
        node_inventory_hash=raw.get("nodeInventoryHash"),
        model_inventory_hash=raw.get("modelInventoryHash"),
        topology_hash=raw.get("topologyHash"),
    )


def _parse_cert(raw: Mapping[str, Any] | None) -> CertificationRecord | None:
    if not raw or not isinstance(raw, Mapping):
        return None
    return CertificationRecord(
        workflow_id=str(raw.get("workflowId") or ""),
        workflow_key=str(raw.get("workflowKey") or ""),
        workflow_version=str(raw.get("workflowVersion") or ""),
        status=str(raw.get("status") or ""),
        certified_at=raw.get("certifiedAt"),
        certified_by=raw.get("certifiedBy"),
        evidence=dict(raw.get("evidence") or {}),
        comfy_version=raw.get("comfyVersion"),
        node_inventory=raw.get("nodeInventory"),
        model_inventory=raw.get("modelInventory"),
        fingerprints=_parse_fingerprints(raw.get("fingerprints")),
        artifact_refs=tuple(str(x) for x in (raw.get("artifactRefs") or [])),
        notes=str(raw.get("notes") or ""),
    )


def _parse_entry(raw: Mapping[str, Any]) -> CertifiedWorkflow:
    status = str(raw.get("status") or "Draft")
    if status not in VALID_STATUSES:
        status = "Draft"
    pk = str(raw.get("providerKind") or "local")
    try:
        provider = ProviderKindVideo(pk)
    except ValueError:
        provider = ProviderKindVideo.LOCAL
    alias_groups = tuple(
        frozenset(str(x) for x in group)
        for group in (raw.get("nodeAliasGroups") or [])
        if isinstance(group, list)
    )
    cert = _parse_cert(raw.get("certificationRecord"))
    cert_id = raw.get("certificationRecordId")
    if cert is not None and not cert_id:
        # Thin pointer may embed id
        cert_id = (raw.get("certificationRecord") or {}).get("certificationRecordId")
    # Bare CERTIFIED without record or pointer is invalid → Blocked
    if status == "Certified" and cert is None and not cert_id:
        status = "Blocked"
    return CertifiedWorkflow(
        workflow_id=str(raw.get("workflowId") or ""),
        workflow_key=str(raw.get("workflowKey") or ""),
        workflow_version=str(raw.get("workflowVersion") or "0.0.0"),
        modality=str(raw.get("modality") or "video"),
        engine=str(raw.get("engine") or ""),
        generation_mode=str(raw.get("generationMode") or "comfy"),
        status=status,
        model_family=str(raw.get("modelFamily") or ""),
        builder=raw.get("builder"),
        builder_path=raw.get("builderPath"),
        required_nodes=tuple(str(x) for x in (raw.get("requiredNodes") or [])),
        required_models=tuple(str(x) for x in (raw.get("requiredModels") or [])),
        required_extensions=tuple(str(x) for x in (raw.get("requiredExtensions") or [])),
        supported_inputs=tuple(str(x) for x in (raw.get("supportedInputs") or [])),
        unsupported_inputs=tuple(str(x) for x in (raw.get("unsupportedInputs") or [])),
        supported_outputs=tuple(str(x) for x in (raw.get("supportedOutputs") or [])),
        limitations=tuple(str(x) for x in (raw.get("limitations") or [])),
        vram_profile=_parse_vram(raw.get("vramProfile")),
        cancellation_support=bool(raw.get("cancellationSupport")),
        output_validation=bool(raw.get("outputValidation", True)),
        playback_validation=bool(raw.get("playbackValidation", True)),
        api_contract=dict(raw.get("apiContract") or {}),
        fingerprints=_parse_fingerprints(raw.get("fingerprints")),
        certification_record=cert,
        provider_kind=provider,
        capability_id=str(raw.get("capabilityId") or raw.get("workflowKey") or ""),
        orchestration=bool(raw.get("orchestration")),
        node_alias_groups=alias_groups,
        certification_record_id=str(cert_id) if cert_id else None,
    )


@lru_cache(maxsize=4)
def load_registry(path: str | None = None) -> tuple[CertifiedWorkflow, ...]:
    registry_path = Path(path) if path else _DEFAULT_REGISTRY
    if not registry_path.is_file():
        return ()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return ()
    return tuple(_parse_entry(item) for item in entries if isinstance(item, Mapping))


def reload_registry() -> None:
    load_registry.cache_clear()


def list_workflows(*, modality: str | None = "video") -> list[CertifiedWorkflow]:
    items = list(load_registry())
    if modality:
        items = [w for w in items if w.modality == modality]
    return items


def get_workflow(workflow_key: str) -> CertifiedWorkflow | None:
    for entry in load_registry():
        if entry.workflow_key == workflow_key:
            return entry
    return None


def get_by_id(workflow_id: str) -> CertifiedWorkflow | None:
    for entry in load_registry():
        if entry.workflow_id == workflow_id:
            return entry
    return None


def assert_executable(workflow_key: str, *, allow_non_certified: bool = True) -> CertifiedWorkflow:
    """Return workflow or raise. Deferred always blocked. Certified preferred for production."""
    wf = get_workflow(workflow_key)
    if not wf:
        raise RuntimeError(f"Unknown workflowKey: {workflow_key}")
    if wf.status == "Deferred":
        raise RuntimeError(f"workflow_deferred:{workflow_key}")
    if wf.status == "Retired":
        raise RuntimeError(f"workflow_retired:{workflow_key}")
    if not allow_non_certified and wf.status != "Certified":
        raise RuntimeError(f"workflow_not_certified:{workflow_key}:{wf.status}")
    return wf


def production_ready_keys() -> list[str]:
    return [w.workflow_key for w in list_workflows() if w.is_production_ready]


def registry_as_dict() -> list[dict[str, Any]]:
    return [w.to_dict() for w in list_workflows(modality=None)]


def compatibility_projection() -> list[dict[str, Any]]:
    """Project certified registry into the 4.1A compatibility catalog shape."""
    out: list[dict[str, Any]] = []
    for w in list_workflows(modality=None):
        # Map certification status → capabilityState honesty
        if w.status == "Certified":
            cap_state = "production_ready"
        elif w.status == "Deferred":
            cap_state = "deferred"
        elif w.status in {"Blocked", "Draft", "Built", "SmokeTested"}:
            # Honesty: not Production Ready until Certified
            cap_state = "blocked" if w.status == "Blocked" else "pending_certification"
        else:
            cap_state = "retired"
        out.append(
            {
                "modelFamily": w.model_family,
                "workflowKey": w.workflow_key,
                "workflowVersion": w.workflow_version,
                "workflowId": w.workflow_id,
                "requiredNodes": list(w.required_nodes),
                "requiredModels": list(w.required_models),
                "requiredExtensions": list(w.required_extensions),
                "minVramGb": w.vram_profile.minimum_gb,
                "recommendedVramGb": w.vram_profile.recommended_gb,
                "supportedInputs": list(w.supported_inputs),
                "unsupportedInputs": list(w.unsupported_inputs),
                "supportedOutputs": list(w.supported_outputs),
                "knownLimitations": list(w.limitations),
                "capabilityState": cap_state,
                "providerKind": w.provider_kind.value,
                "capabilityId": w.capability_id,
                "nodeAliasGroups": [sorted(g) for g in w.node_alias_groups],
                "status": w.status,
                "productionReady": w.is_production_ready,
                "fingerprints": w.fingerprints.to_dict(),
            }
        )
    return out
