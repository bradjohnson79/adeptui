"""Provider/runtime resolution — preference order, no silent switch, GPU-first local path."""

from __future__ import annotations

from typing import Any


HOSTED_ORDER = ["kie.ai", "wavespeed.ai", "fal.ai"]


def _probe_sandbox(adapter_cls_name: str, module_path: str, runtime: str, registry_id: str) -> dict[str, Any]:
    row = {
        "runtime": runtime,
        "ready": False,
        "registry_id": registry_id,
        "message": "",
        "stems_supported": False,
        "sandboxOnly": True,
        "productionPath": "audio_studio",
        "cuda": False,
        "accelerator": "unknown",
    }
    try:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, adapter_cls_name)
        adapter = cls()
        health = adapter.health_check() if hasattr(adapter, "health_check") else {}
        ready = bool(health.get("runtimeReady") or (health.get("ok") and health.get("installed")))
        row["ready"] = ready
        cuda = bool(health.get("cuda"))
        accel = str(health.get("accelerator") or ("cuda" if cuda else "cpu"))
        row["cuda"] = cuda
        row["accelerator"] = accel
        row["device"] = health.get("device")
        row["torchVersion"] = health.get("torchVersion")
        if ready and cuda:
            row["message"] = f"ready (CUDA: {health.get('device') or 'gpu'})"
        elif ready:
            row["message"] = (
                "GPU acceleration was requested, but the active worker is using "
                "CPU-only PyTorch. Generation is blocked unless allowCpuFallback=true."
            )
        else:
            row["message"] = str(health.get("message") or f"{runtime} not ready")
        row["health"] = {
            "ok": health.get("ok"),
            "installed": health.get("installed"),
            "runtimeReady": health.get("runtimeReady"),
            "venvPython": health.get("venvPython"),
            "cuda": cuda,
            "accelerator": accel,
            "device": health.get("device"),
            "torchVersion": health.get("torchVersion"),
        }
    except Exception as exc:
        row["message"] = str(exc)
    return row


def local_runtime_status() -> dict[str, Any]:
    ace = _probe_sandbox(
        "AceStepSandboxAdapter",
        "app.codirector.m210b.adapters.ace_step",
        "ACE-Step",
        "m2101-music-045",
    )
    mm = _probe_sandbox(
        "MMAudioSandboxAdapter",
        "app.codirector.m210b.adapters.mmaudio",
        "MMAudio",
        "m2101-sfx-031",
    )
    return {"ACE-Step": ace, "MMAudio": mm}


def hosted_audio_status() -> list[dict[str, Any]]:
    """Hosted generative audio — honest status + stem capability declarations."""
    out: list[dict[str, Any]] = []
    # Map capability matrix ids to display names
    matrix_ids = {"kie.ai": "kie", "wavespeed.ai": "wavespeed", "fal.ai": "fal"}
    try:
        from ..hosted_providers.capabilities import capability_matrix

        matrix = capability_matrix().get("providers") or {}
    except Exception:
        matrix = {}

    for p in HOSTED_ORDER:
        mid = matrix_ids.get(p, p.split(".")[0])
        caps = matrix.get(mid) or {}
        music_status = caps.get("music", "Unsupported")
        audio_status = caps.get("audio", "Unsupported")
        best = music_status if music_status != "Unsupported" else audio_status
        status = "Unavailable" if best == "Unsupported" else str(best)
        out.append(
            {
                "provider": p,
                "status": status,
                "stems_supported": False,  # never claim stems until certified provider returns them
                "modalities": ["audio", "music"] if music_status != "Unsupported" else ["audio"],
                "music": music_status,
                "audio": audio_status,
                "message": (
                    "Hosted audio mapping present; stems not certified."
                    if status != "Unavailable"
                    else "No certified hosted audio adapter for this provider."
                ),
            }
        )
    return out


def resolve_execution(
    kind: str,
    *,
    preferred_provider: str | None = None,
    allow_switch: bool = False,
    allow_cpu_fallback: bool = False,
) -> dict[str, Any]:
    """Resolve where to run. Never silently switches provider or falls back to CPU."""
    local = local_runtime_status()
    hosted = hosted_audio_status()
    if kind == "music":
        runtime = local["ACE-Step"]
        local_key = "ACE-Step"
    else:
        runtime = local["MMAudio"]
        local_key = "MMAudio"

    ready = bool(runtime.get("ready"))
    cuda = bool(runtime.get("cuda"))
    recommendation: dict[str, Any] = {
        "mode": "unavailable",
        "runtime": None,
        "provider": None,
        "reason": runtime.get("message") or "",
        "alternatives": [],
        "requiresApprovalToSwitch": True,
        "requiresApprovalForCpuFallback": True,
        "preferredOrder": ["local_gpu", *HOSTED_ORDER, "local_cpu_explicit"],
        "stems_supported": bool(runtime.get("stems_supported")),
        "cuda": cuda,
        "accelerator": runtime.get("accelerator"),
        "device": runtime.get("device"),
        "torchVersion": runtime.get("torchVersion"),
        "gpuRequired": True,
        "allowCpuFallback": bool(allow_cpu_fallback),
        "cpuFallbackUsed": False,
    }

    if ready and cuda:
        recommendation["mode"] = "local"
        recommendation["runtime"] = local_key
        recommendation["reason"] = f"Local {local_key} is ready on GPU ({runtime.get('device') or 'cuda'})."
    elif ready and not cuda:
        if allow_cpu_fallback:
            recommendation["mode"] = "local"
            recommendation["runtime"] = local_key
            recommendation["cpuFallbackUsed"] = True
            recommendation["reason"] = (
                f"Local {local_key} is CPU-only; explicit allowCpuFallback=true approved. "
                "Expect much slower generation."
            )
        else:
            recommendation["mode"] = "blocked_cpu"
            recommendation["runtime"] = local_key
            recommendation["reason"] = (
                f"GPU acceleration was requested, but {local_key} is using CPU-only PyTorch. "
                "Generation has been blocked to prevent an unexpected CPU execution path. "
                "Repair the CUDA venv, or pass allowCpuFallback=true with explicit user approval."
            )
            alts = [h for h in hosted if h.get("status") not in ("Unsupported", "Unavailable")]
            recommendation["alternatives"] = alts or hosted
    else:
        alts = [h for h in hosted if h.get("status") not in ("Unsupported", "Unavailable")]
        recommendation["alternatives"] = alts or hosted
        recommendation["reason"] = (
            f"Local {local_key} not ready. Hosted alternatives require explicit approval "
            f"(no silent switch). allow_switch={allow_switch} preferred={preferred_provider!r}"
        )
        if preferred_provider and allow_switch:
            recommendation["mode"] = "hosted"
            recommendation["provider"] = preferred_provider
            recommendation["reason"] = f"User-approved switch to {preferred_provider}."

    return {
        "recommendation": recommendation,
        "local": local,
        "hosted": hosted,
        "mock": False,
    }
