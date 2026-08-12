"""M42 W47 Co-Director runtime.* tools — reads + proposal-gated mutators."""

from __future__ import annotations

from typing import Any

from app.docker_runtime import service as dr
from app.docker_runtime.manager import get_manager
from app.docker_runtime.platform import detect_platform
from app.docker_runtime.registry import get_runtime

from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview


def _rid(args: dict[str, Any]) -> str:
    rid = str(args.get("runtimeId") or "").strip()
    if not rid:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "runtimeId is required.",
            details={},
            recoverable=True,
            recommended_action="runtime.list",
        )
    return rid


async def runtime_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rows = dr.list_runtimes()
    return {
        "count": len(rows),
        "runtimes": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "classification": r.get("classification"),
                "executionClass": r.get("executionClass"),
                "readiness": r.get("readiness"),
                "lifecycle": r.get("lifecycle"),
                "uninstallAllowed": r.get("uninstallAllowed"),
                "disabled": r.get("disabled"),
            }
            for r in rows
        ],
        "platform": detect_platform(),
        "_summary": f"{len(rows)} runtime(s) registered.",
    }


async def runtime_inspect(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rid = _rid(args)
    desc = get_runtime(rid)
    if not desc:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "Runtime not found.", details={"runtimeId": rid})
    diag = dr.diagnostics(rid)
    return {
        "runtime": desc.model_dump(mode="json"),
        "diagnostics": diag.model_dump(mode="json") if hasattr(diag, "model_dump") else diag,
        "_summary": f"Runtime {desc.name} ({desc.classification}) lifecycle={desc.lifecycle}.",
    }


async def runtime_test(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rid = _rid(args)
    from app.docker_runtime.gpu_preflight import check_gpu
    from app.docker_runtime.health import check_health
    from app.docker_runtime.manager import get_manager

    start = get_manager().start(rid)
    health = check_health(rid)
    gpu = check_gpu(rid)
    ok = bool(start.get("ok") and health.ok and (gpu.frameworkAccelerator or gpu.cudaAvailable))
    result = {
        "ok": ok,
        "start": start,
        "health": health.model_dump(mode="json"),
        "gpu": gpu.model_dump(mode="json"),
    }
    return {**result, "_summary": f"Test runtime {rid}: {'ok' if ok else 'failed'}."}


async def runtime_open_manager(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "route": "/runtime-manager",
        "hint": "Open Runtime Manager for install/update/repair/uninstall.",
        "_summary": "Deep-link to Runtime Manager.",
    }


def preview_install(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    manifest = args.get("manifest") or {"image": args.get("image"), "name": args.get("name")}
    if isinstance(manifest, str):
        import json

        manifest = json.loads(manifest)
    plan = dr.preview_install(manifest if isinstance(manifest, dict) else {})
    return ToolPreview(
        summary=f"Install Docker runtime {plan.runtimeId} (isolated; never mutates core).",
        lines=plan.steps[:12],
        resourceKind="docker_runtime",
        resourceId=plan.runtimeId,
        warnings=plan.security.blocked + plan.security.warnings,
    )


def apply_install(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    manifest = args.get("manifest") or {"image": args.get("image"), "name": args.get("name"), "runtimeId": args.get("runtimeId")}
    if isinstance(manifest, str):
        import json

        manifest = json.loads(manifest)
    result = dr.install_runtime(manifest if isinstance(manifest, dict) else {})
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)


def preview_update(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    return ToolPreview(
        summary=f"Update Docker runtime {rid} with rollback target.",
        lines=["Pull new image", "Staged recreate", "Health + GPU preflight", "Keep rollback image"],
        resourceKind="docker_runtime",
        resourceId=rid,
    )


def apply_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    image = str(args.get("image") or "").strip()
    if not image:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "image is required for update.", details={})
    return dr.update_runtime(_rid(args), image)


def preview_repair(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    return ToolPreview(
        summary=f"Repair Docker runtime {rid}.",
        lines=["Re-run health", "GPU preflight", "Restart if needed", "Report issues"],
        resourceKind="docker_runtime",
        resourceId=rid,
    )


def apply_repair(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return dr.repair_runtime(_rid(args))


def preview_uninstall(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    option = args.get("option") or "container_image_and_private"
    plan = dr.preview_uninstall(rid, option)
    warnings = []
    if plan.blockedReason:
        warnings.append(plan.blockedReason)
    lines = list(plan.willRemove or []) + [f"preserve:{x}" for x in (plan.willPreserve or [])]
    if not lines:
        lines = ["Remove UI registration", "Stop/remove container", "Preserve shared + project assets"]
    return ToolPreview(
        summary=f"Uninstall Docker runtime {rid} ({option}).",
        lines=lines,
        resourceKind="docker_runtime",
        resourceId=rid,
        warnings=warnings,
    )


def apply_uninstall(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rid = _rid(args)
    option = args.get("option") or "container_image_and_private"
    result = dr.uninstall_runtime(rid, option)
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)


def preview_start(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    return ToolPreview(summary=f"Start Docker runtime {rid}.", lines=["docker start"], resourceKind="docker_runtime", resourceId=rid)


def apply_start(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return get_manager().start(_rid(args))


def preview_stop(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    return ToolPreview(summary=f"Stop Docker runtime {rid}.", lines=["docker stop"], resourceKind="docker_runtime", resourceId=rid)


def apply_stop(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return get_manager().stop(_rid(args))


def preview_restart(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    rid = _rid(args)
    return ToolPreview(summary=f"Restart Docker runtime {rid}.", lines=["docker restart"], resourceKind="docker_runtime", resourceId=rid)


def apply_restart(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return get_manager().restart(_rid(args))
