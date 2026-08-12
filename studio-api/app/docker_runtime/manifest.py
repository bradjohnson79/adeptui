"""Adept Runtime Manifest parse / validate / defaults."""

from __future__ import annotations

from typing import Any

from .contracts import (
    SCHEMA_VERSION,
    AdeptRuntimeManifest,
    RuntimeCapabilityDeclaration,
    RuntimeImageDescriptor,
    RuntimeMountPolicy,
    RuntimeValidationReport,
)
from .security import scan_manifest


def parse_manifest(raw: dict[str, Any]) -> AdeptRuntimeManifest:
    # Accept nested mission-style keys and flat contract keys
    if "runtime" in raw and isinstance(raw["runtime"], dict):
        rt = raw["runtime"]
        container = raw.get("container") or {}
        gpu = raw.get("gpu") or {}
        health = raw.get("health") or {}
        adapter = raw.get("adapter") or {}
        mounts_in = raw.get("mounts") or {}
        mounts = {}
        for k, v in mounts_in.items():
            if isinstance(v, dict):
                mounts[k] = RuntimeMountPolicy(
                    hostClass=v.get("host_class") or v.get("hostClass") or "private",
                    containerPath=v.get("container_path") or v.get("containerPath") or f"/{k}",
                    access=v.get("access") or "read_only",
                )
        caps = []
        for c in raw.get("capabilities") or []:
            if isinstance(c, str):
                caps.append(RuntimeCapabilityDeclaration(id=c, label=c.replace("_", " ").title()))
            elif isinstance(c, dict):
                caps.append(RuntimeCapabilityDeclaration(**c))
        return AdeptRuntimeManifest(
            schemaVersion=int(raw.get("schema_version") or raw.get("schemaVersion") or SCHEMA_VERSION),
            runtimeId=str(rt.get("id") or rt.get("runtimeId")),
            name=str(rt.get("name") or rt.get("id")),
            version=str(rt.get("version") or "1.0.0"),
            classification=rt.get("classification") or "user_added",
            modality=rt.get("modality") or "video",
            engine=rt.get("engine") or "comfyui",
            source=rt.get("source") or "docker",
            image=RuntimeImageDescriptor(image=str(container.get("image") or raw.get("image") or "")),
            internalPort=int(container.get("internal_port") or container.get("internalPort") or 8188),
            restartPolicy=str(container.get("restart_policy") or "unless-stopped"),
            gpu={
                "required": bool(gpu.get("required", True)),
                "minimumVramGb": float(gpu.get("minimum_vram_gb") or gpu.get("minimumVramGb") or 0),
                "cpuFallback": bool(gpu.get("cpu_fallback") or gpu.get("cpuFallback") or False),
            },
            health={
                "type": health.get("type") or "http",
                "endpoint": health.get("endpoint") or "/system_stats",
                "timeoutSeconds": int(health.get("timeout_seconds") or health.get("timeoutSeconds") or 30),
            },
            capabilities=caps,
            mounts=mounts,
            adapter={
                "protocol": adapter.get("protocol") or "comfyui",
                "workflow": adapter.get("workflow"),
            },
        )
    return AdeptRuntimeManifest.model_validate(raw)


def validate_manifest(manifest: AdeptRuntimeManifest) -> RuntimeValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest.runtimeId:
        errors.append("missing_runtime_id")
    if not manifest.name:
        errors.append("missing_name")
    if not manifest.image or not manifest.image.image:
        errors.append("missing_image")
    if manifest.schemaVersion != SCHEMA_VERSION:
        warnings.append(f"schema_version_{manifest.schemaVersion}_migrated_to_{SCHEMA_VERSION}")
    if manifest.gpu.cpuFallback:
        warnings.append("cpu_fallback_declared_disabled_by_default_policy")
    sec = scan_manifest(manifest)
    errors.extend(sec.blocked)
    warnings.extend(sec.warnings)
    return RuntimeValidationReport(ok=not errors, errors=errors, warnings=warnings)


def default_manifest_from_image(
    *,
    runtime_id: str,
    name: str,
    image: str,
    modality: str = "video",
    internal_port: int = 8188,
) -> AdeptRuntimeManifest:
    return AdeptRuntimeManifest(
        runtimeId=runtime_id,
        name=name,
        modality=modality,  # type: ignore[arg-type]
        image=RuntimeImageDescriptor(image=image),
        internalPort=internal_port,
        capabilities=[
            RuntimeCapabilityDeclaration(id="text_to_video", label="Text to Video", modality="video"),
        ],
        mounts={
            "models": RuntimeMountPolicy(hostClass="shared_optional", containerPath="/models", access="read_only"),
            "inputs": RuntimeMountPolicy(hostClass="job_inputs", containerPath="/inputs", access="read_only"),
            "outputs": RuntimeMountPolicy(hostClass="job_outputs", containerPath="/outputs", access="read_write"),
        },
    )
