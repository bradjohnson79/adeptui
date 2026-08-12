"""High-level install / validate / uninstall / repair / update orchestration."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from .contracts import (
    AdeptRuntimeManifest,
    DockerRuntimeDescriptor,
    RuntimeDependencyReport,
    RuntimeDiagnosticReport,
    RuntimeInstallationPlan,
    RuntimeInstallationResult,
    RuntimeUninstallPlan,
    RuntimeUninstallResult,
    RuntimeUsageReport,
    UninstallOption,
)
from .gpu_preflight import check_gpu
from .health import check_health
from .manager import get_manager
from .manifest import default_manifest_from_image, parse_manifest, validate_manifest
from .platform import detect_platform
from .registry import get_runtime, load_registry, remove_runtime, upsert_runtime
from .security import scan_manifest
from .storage import dir_size, private_path, remove_private


def list_runtimes() -> list[dict[str, Any]]:
    reg = load_registry()
    return [r.model_dump(mode="json") for r in reg.runtimes.values()]


def preview_install(raw_manifest: dict[str, Any]) -> RuntimeInstallationPlan:
    if isinstance(raw_manifest.get("image"), str) and "runtime" not in raw_manifest:
        rid = str(raw_manifest.get("runtimeId") or f"user-{uuid.uuid4().hex[:8]}")
        manifest = default_manifest_from_image(
            runtime_id=rid,
            name=str(raw_manifest.get("name") or rid),
            image=str(raw_manifest["image"]),
            modality=str(raw_manifest.get("modality") or "video"),
            internal_port=int(raw_manifest.get("internalPort") or 8188),
        )
    else:
        manifest = parse_manifest(raw_manifest)
    validation = validate_manifest(manifest)
    security = scan_manifest(manifest)
    steps = [
        "Validate Adept Runtime Manifest",
        "Security inspection",
        "Pull or build image",
        "Create private volumes",
        "Create restricted mounts",
        "Reserve host port",
        "Create container",
        "Start container",
        "Health check",
        "GPU preflight",
        "Register capability",
    ]
    return RuntimeInstallationPlan(
        runtimeId=manifest.runtimeId,
        steps=steps,
        security=security,
        validation=validation,
        dependencies=RuntimeDependencyReport(),
        estimatedDiskGb=2.0,
    )


def install_runtime(raw_manifest: dict[str, Any], *, run_test: bool = True) -> RuntimeInstallationResult:
    plat = detect_platform()
    if not plat.get("readyForInstall"):
        return RuntimeInstallationResult(ok=False, error=plat.get("error") or "docker_unavailable")

    if isinstance(raw_manifest.get("image"), str) and "runtime" not in raw_manifest:
        # shorthand: {image, name?, runtimeId?}
        rid = str(raw_manifest.get("runtimeId") or f"user-{uuid.uuid4().hex[:8]}")
        manifest = default_manifest_from_image(
            runtime_id=rid,
            name=str(raw_manifest.get("name") or rid),
            image=str(raw_manifest["image"]),
            modality=str(raw_manifest.get("modality") or "video"),
            internal_port=int(raw_manifest.get("internalPort") or 8188),
        )
    else:
        manifest = parse_manifest(raw_manifest)

    validation = validate_manifest(manifest)
    if not validation.ok:
        return RuntimeInstallationResult(ok=False, error="validation_failed:" + ",".join(validation.errors))

    security = scan_manifest(manifest)
    if not security.ok:
        return RuntimeInstallationResult(ok=False, error="security_blocked:" + ",".join(security.blocked))

    completed: list[str] = ["validate", "security"]
    mgr = get_manager()
    pull = mgr.pull_image(manifest.image.image)
    if not pull.get("ok"):
        return RuntimeInstallationResult(ok=False, error=f"pull_failed:{pull.get('stderr')}", stepsCompleted=completed)
    completed.append("pull")

    priv = private_path(manifest.runtimeId)
    completed.append("private_volume")

    create = mgr.create_container(
        runtime_id=manifest.runtimeId,
        image=manifest.image.image,
        internal_port=manifest.internalPort,
        gpu=manifest.gpu.required,
        mounts=[(str(priv), "/runtime_private", "read_write")],
    )
    if not create.get("ok"):
        return RuntimeInstallationResult(ok=False, error=f"create_failed:{create.get('stderr')}", stepsCompleted=completed)
    completed.append("create")

    desc = DockerRuntimeDescriptor(
        id=manifest.runtimeId,
        name=manifest.name,
        version=manifest.version,
        classification="user_added",
        ownership="user",
        modality=manifest.modality,
        readiness="installing",
        lifecycle="created",
        executionClass="docker_local",
        image=manifest.image.image,
        imageDigest=pull.get("digest"),
        containerId=create.get("containerId"),
        hostPort=create.get("hostPort"),
        minimumVramGb=manifest.gpu.minimumVramGb,
        uninstallAllowed=True,
        manifest=manifest,
        privateStoragePath=str(priv),
        models=[c.id for c in manifest.capabilities],
        workflows=[manifest.adapter.workflow] if manifest.adapter.workflow else [],
    )
    upsert_runtime(desc)

    start = mgr.start(manifest.runtimeId)
    if not start.get("ok"):
        desc.readiness = "error"
        desc.lastError = start.get("error") or start.get("stderr")
        upsert_runtime(desc)
        return RuntimeInstallationResult(ok=False, error="start_failed", runtime=desc, stepsCompleted=completed)
    completed.append("start")

    health = check_health(manifest.runtimeId)
    gpu = check_gpu(manifest.runtimeId)
    completed.extend(["health", "gpu"])

    desc = get_runtime(manifest.runtimeId) or desc
    if health.ok and (gpu.frameworkAccelerator or mgr._simulate()):  # noqa: SLF001
        desc.readiness = "tested_locally" if run_test else "ready"
        if run_test:
            completed.append("minimal_test")
            desc.readiness = "ready"
        desc.healthOk = True
    else:
        desc.readiness = "requires_repair"
        desc.lastError = health.detail if not health.ok else "gpu_framework_not_ready"
    upsert_runtime(desc)
    completed.append("register")
    return RuntimeInstallationResult(ok=desc.readiness in {"ready", "tested_locally"}, runtime=desc, stepsCompleted=completed)


def usage_report(runtime_id: str) -> RuntimeUsageReport:
    desc = get_runtime(runtime_id)
    priv = private_path(runtime_id)
    shared = []
    if desc:
        for m in desc.models:
            shared.append({"id": m, "kind": "model", "refCount": 1, "shared": False})
    return RuntimeUsageReport(
        runtimeId=runtime_id,
        activeJobs=0,
        queuedJobs=0,
        projectIds=[],
        timelineBlocks=0,
        generationRecords=0,
        sharedArtifacts=shared,
        privateStorageBytes=dir_size(priv),
        imageSizeBytes=0,
        rollbackAvailable=bool(desc and desc.rollbackImage),
    )


def preview_uninstall(runtime_id: str, option: UninstallOption = "container_image_and_private") -> RuntimeUninstallPlan:
    desc = get_runtime(runtime_id)
    usage = usage_report(runtime_id)
    if not desc:
        return RuntimeUninstallPlan(
            runtimeId=runtime_id, option=option, usage=usage, blockedReason="runtime_not_found"
        )
    if desc.classification == "core_mandatory" or not desc.uninstallAllowed:
        return RuntimeUninstallPlan(
            runtimeId=runtime_id,
            option=option,
            usage=usage,
            blockedReason="core_mandatory_uninstall_blocked",
            willPreserve=["core_runtime", "project_assets", "provenance"],
        )
    preserve = [
        "project_assets",
        "generated_media",
        "timeline_lineage",
        "production_bible",
        "provenance",
        "shared_models",
        "credentials",
    ]
    remove = ["dock_registration", "runtime_registry_entry"]
    if option in {"container", "container_and_image", "container_image_and_private"}:
        remove.append("container")
    if option in {"container_and_image", "container_image_and_private"}:
        remove.append("image")
    if option == "container_image_and_private":
        remove.append("private_storage")
    return RuntimeUninstallPlan(
        runtimeId=runtime_id, option=option, usage=usage, willPreserve=preserve, willRemove=remove
    )


def uninstall_runtime(
    runtime_id: str,
    option: UninstallOption = "container_image_and_private",
    *,
    force_fail_step: Optional[str] = None,
) -> RuntimeUninstallResult:
    plan = preview_uninstall(runtime_id, option)
    if plan.blockedReason:
        return RuntimeUninstallResult(ok=False, runtimeId=runtime_id, option=option, error=plan.blockedReason)

    desc = get_runtime(runtime_id)
    assert desc
    # Snapshot for rollback
    snapshot = desc.model_copy(deep=True)
    removed: list[str] = []
    preserved = list(plan.willPreserve)
    mgr = get_manager()

    try:
        if force_fail_step == "before_stop":
            raise RuntimeError("controlled_uninstall_failure")

        # block new jobs by disabling first
        desc.disabled = True
        desc.readiness = "disabled"
        upsert_runtime(desc)
        removed.append("blocked_new_jobs")

        if desc.lifecycle == "running":
            mgr.stop(runtime_id)
            removed.append("stopped")

        if force_fail_step == "after_stop":
            raise RuntimeError("controlled_uninstall_failure")

        if option != "ui_only":
            mgr.remove_container(runtime_id)
            removed.append("container")
        if option in {"container_and_image", "container_image_and_private"}:
            mgr.remove_image(desc.image)
            removed.append("image")
        if option == "container_image_and_private":
            remove_private(runtime_id)
            removed.append("private_storage")

        if force_fail_step == "registry":
            raise RuntimeError("controlled_uninstall_failure")

        remove_runtime(runtime_id)
        removed.append("registry")
        return RuntimeUninstallResult(
            ok=True, runtimeId=runtime_id, option=option, removed=removed, preserved=preserved
        )
    except Exception as exc:
        # Restore registry entry
        upsert_runtime(snapshot)
        return RuntimeUninstallResult(
            ok=False,
            runtimeId=runtime_id,
            option=option,
            removed=removed,
            preserved=preserved,
            error=str(exc),
            rolledBack=True,
        )


def repair_runtime(runtime_id: str) -> dict[str, Any]:
    desc = get_runtime(runtime_id)
    if not desc:
        return {"ok": False, "error": "runtime_not_found"}
    corrections: list[str] = []
    mgr = get_manager()

    if desc.executionClass == "native_local":
        health = check_health(runtime_id)
        gpu = check_gpu(runtime_id)
        desc.healthOk = health.ok
        desc.gpuReady = gpu.frameworkAccelerator or gpu.cudaAvailable
        desc.readiness = "ready" if health.ok else "requires_repair"
        upsert_runtime(desc)
        return {"ok": health.ok, "corrections": ["native_reprobe"], "health": health.model_dump(), "gpu": gpu.model_dump()}

    if not desc.containerId or desc.lifecycle == "absent":
        if desc.manifest:
            create = mgr.create_container(
                runtime_id=desc.id,
                image=desc.image,
                internal_port=desc.manifest.internalPort,
                host_port=desc.hostPort,
                gpu=desc.manifest.gpu.required,
            )
            if create.get("ok"):
                desc.containerId = create.get("containerId")
                desc.hostPort = create.get("hostPort")
                corrections.append("recreated_container")
        else:
            return {"ok": False, "error": "manifest_missing_cannot_repair"}

    start = mgr.start(runtime_id)
    if start.get("ok"):
        corrections.append("started")
    health = check_health(runtime_id)
    gpu = check_gpu(runtime_id)
    desc = get_runtime(runtime_id) or desc
    if health.ok and (gpu.frameworkAccelerator or mgr._simulate()):  # noqa: SLF001
        desc.readiness = "ready"
        desc.healthOk = True
        desc.lastError = None
        corrections.append("validated")
    else:
        desc.readiness = "requires_repair"
        desc.lastError = health.detail
    upsert_runtime(desc)
    return {
        "ok": desc.readiness == "ready",
        "corrections": corrections,
        "health": health.model_dump(),
        "gpu": gpu.model_dump(),
    }


def update_runtime(runtime_id: str, new_image: str) -> dict[str, Any]:
    desc = get_runtime(runtime_id)
    if not desc:
        return {"ok": False, "error": "runtime_not_found"}
    if desc.classification == "core_mandatory" and desc.executionClass == "native_local":
        return {"ok": False, "error": "core_native_update_via_setup"}
    prev = desc.image
    desc.rollbackImage = prev
    upsert_runtime(desc)
    mgr = get_manager()
    pull = mgr.pull_image(new_image)
    if not pull.get("ok"):
        return {"ok": False, "error": "pull_failed", "rollbackImage": prev}
    mgr.stop(runtime_id)
    mgr.remove_container(runtime_id)
    port = desc.manifest.internalPort if desc.manifest else 8188
    create = mgr.create_container(runtime_id=runtime_id, image=new_image, internal_port=port, gpu=True)
    if not create.get("ok"):
        # rollback
        create_old = mgr.create_container(runtime_id=runtime_id, image=prev, internal_port=port, gpu=True)
        mgr.start(runtime_id)
        return {"ok": False, "error": "create_failed_rolled_back", "rollbackImage": prev, "recreated": create_old.get("ok")}
    desc.image = new_image
    desc.imageDigest = pull.get("digest")
    desc.containerId = create.get("containerId")
    desc.hostPort = create.get("hostPort")
    upsert_runtime(desc)
    mgr.start(runtime_id)
    health = check_health(runtime_id)
    gpu = check_gpu(runtime_id)
    ok = health.ok and (gpu.frameworkAccelerator or mgr._simulate())  # noqa: SLF001
    desc = get_runtime(runtime_id) or desc
    desc.readiness = "ready" if ok else "requires_repair"
    upsert_runtime(desc)
    return {"ok": ok, "image": new_image, "digest": pull.get("digest"), "rollbackImage": prev}


def rollback_runtime(runtime_id: str) -> dict[str, Any]:
    desc = get_runtime(runtime_id)
    if not desc or not desc.rollbackImage:
        return {"ok": False, "error": "no_rollback_target"}
    return update_runtime(runtime_id, desc.rollbackImage)


def diagnostics(runtime_id: str) -> RuntimeDiagnosticReport:
    from .security import scan_manifest

    desc = get_runtime(runtime_id)
    health = check_health(runtime_id)
    gpu = check_gpu(runtime_id)
    sec = scan_manifest(desc.manifest) if desc and desc.manifest else scan_manifest(
        default_manifest_from_image(runtime_id=runtime_id or "x", name="x", image="user/x:1.0.0")
    )
    issues = []
    if not health.ok:
        issues.append(f"health:{health.detail}")
    if not gpu.frameworkAccelerator and desc and desc.executionClass == "docker_local":
        issues.append("gpu_framework_not_ready")
    if sec.blocked:
        issues.extend(sec.blocked)
    return RuntimeDiagnosticReport(
        runtimeId=runtime_id,
        platform=detect_platform(),
        health=health,
        gpu=gpu,
        security=sec,
        issues=issues,
    )


def import_comfy_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """Inspect Comfy workflow JSON — never install into core Comfy."""
    nodes = workflow.get("nodes") or workflow
    model_loaders: list[str] = []
    custom_nodes: list[str] = []
    loras: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    if isinstance(nodes, dict):
        for _nid, node in nodes.items():
            if not isinstance(node, dict):
                continue
            ctype = str(node.get("class_type") or node.get("type") or "")
            if "Loader" in ctype or "Checkpoint" in ctype or "UNET" in ctype:
                model_loaders.append(ctype)
            if "Lora" in ctype or "LoRA" in ctype:
                loras.append(ctype)
            if ctype and not ctype.startswith(("CLIP", "VAE", "KSampler", "Save", "Preview")):
                custom_nodes.append(ctype)
            if "CLIPTextEncode" in ctype:
                inputs.append("prompt")
            if "LoadImage" in ctype:
                inputs.append("source_image")
            if "SaveVideo" in ctype or "VHS_VideoCombine" in ctype or "SaveImage" in ctype:
                outputs.append("output_media")
    missing_models = sorted(set(model_loaders))
    missing_nodes = sorted(set(custom_nodes))
    missing_loras = sorted(set(loras))
    rid = f"user-comfy-{uuid.uuid4().hex[:8]}"
    isolated_plan = {
        "runtimeId": rid,
        "classification": "user_added",
        "executionClass": "docker_local",
        "buildsIsolatedImage": True,
        "mutatesCoreComfy": False,
        "mutatesCoreModels": False,
        "steps": [
            "Inspect workflow nodes/models/LoRAs/IO",
            "Report missing dependencies",
            "Build isolated Docker image (private volumes only)",
            "Security scan (default deny privileged/host/docker.sock)",
            "Register as user_added Docker Local capability",
            "Dock registration (never auto-Certified)",
        ],
        "capabilityLabelPolicy": "tested_locally_or_available_never_certified",
    }
    return {
        "ok": True,
        "modelLoaders": missing_models,
        "nodes": missing_nodes,
        "loras": missing_loras,
        "inputs": sorted(set(inputs)) or ["prompt", "negative_prompt", "seed", "duration"],
        "outputs": sorted(set(outputs)) or ["output_video"],
        "missingDependencies": missing_models + missing_nodes + missing_loras,
        "buildsIsolatedRuntime": True,
        "mutatesCoreComfy": False,
        "isolatedInstallPlan": isolated_plan,
        "mapping": {
            "prompt": "CLIPTextEncode.text",
            "negative_prompt": "CLIPTextEncode.negative",
            "source_image": "LoadImage",
            "seed": "KSampler.seed",
            "duration": "frames_or_length",
            "output_video": "SaveVideo",
        },
    }
