"""Official Tencent HunyuanVideo install / remove / repair / verify / health."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .hunyuan_providers import (
    HUNYUAN_13B,
    HUNYUAN_15,
    OFFICIAL_SOURCES,
    PROVIDER_BY_COMPONENT,
    load_install_status,
    provider_dir,
    save_install_status,
)

ProgressCb = Callable[[str, float, str], None]
CancelCheck = Callable[[], bool]


@dataclass
class InstallResult:
    ok: bool
    message: str
    evidence: dict[str, Any]


# Marker files/dirs that prove an official snapshot landed (not exhaustive weights).
# HunyuanVideo-1.5 has no root transformer/config.json — variants live under transformer/<profile>/.
_REQUIRED_MARKERS: dict[str, tuple[str, ...]] = {
    HUNYUAN_15: (
        "README.md",
        "config.json",
        "vae",
        "transformer",
    ),
    HUNYUAN_13B: (
        "README.md",
        "hunyuan-video-t2v-720p",
    ),
}

# Profile-scoped HF allow_patterns — full multi-variant snapshot is 100GB+ and fails mid-download.
_ALLOW_PATTERNS: dict[str, dict[str, list[str]]] = {
    HUNYUAN_15: {
        "consumer": [
            "README.md",
            "README_CN.md",
            "LICENSE",
            "NOTICE",
            ".gitattributes",
            "config.json",
            "scheduler/*",
            "vae/*",
            "transformer/480p_i2v/*",
            "transformer/720p_i2v/*",
        ],
        "quality": [
            "README.md",
            "README_CN.md",
            "LICENSE",
            "NOTICE",
            ".gitattributes",
            "config.json",
            "scheduler/*",
            "vae/*",
            "transformer/480p_i2v/*",
            "transformer/480p_t2v/*",
            "transformer/720p_i2v/*",
            "transformer/720p_t2v/*",
        ],
    },
    HUNYUAN_13B: {
        "fp8_production": [
            "README.md",
            "LICENSE*",
            "hunyuan-video-t2v-720p/*",
            "hunyuan-video-i2v-720p/*",
            "ckpts/*",
        ],
        "full": [
            "README.md",
            "LICENSE*",
            "hunyuan-video-t2v-720p/*",
            "hunyuan-video-i2v-720p/*",
            "hunyuan-video-t2v-720p-fp8/*",
            "ckpts/*",
        ],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hardware_preflight(provider_id: str) -> dict[str, Any]:
    meta = OFFICIAL_SOURCES[provider_id]
    vram_gb: float | None = None
    gpu_name = None
    cuda = False
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        if cuda:
            props = torch.cuda.get_device_properties(0)
            vram_gb = float(props.total_memory) / (1024**3)
            gpu_name = props.name
    except Exception:
        pass

    root = provider_dir(provider_id)
    root.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(str(root))
    free_gb = disk.free / (1024**3)
    need_gb = float(meta["diskGb"])
    min_vram = float(meta["minVramGb"])
    rec_vram = float(meta["recommendedVramGb"])

    profile = str(meta["defaultProfile"])
    if provider_id == HUNYUAN_13B and vram_gb is not None and vram_gb >= 30:
        profile = "fp8_production"
    elif provider_id == HUNYUAN_15 and vram_gb is not None and vram_gb >= 22:
        profile = "quality"

    reasons: list[str] = []
    ok = True
    if free_gb < need_gb * 0.9:
        ok = False
        reasons.append(f"Need ~{need_gb:.0f} GB free disk; have {free_gb:.1f} GB.")
    if vram_gb is not None and vram_gb < min_vram:
        ok = False
        reasons.append(f"Need ≥{min_vram:.0f} GB VRAM; detected {vram_gb:.1f} GB.")
    if not cuda and vram_gb is None:
        # Soft warning — download may proceed; generation will fail health until CUDA present.
        reasons.append("CUDA GPU not detected; install may proceed but generation health will fail.")

    return {
        "ok": ok,
        "providerId": provider_id,
        "gpuName": gpu_name,
        "cuda": cuda,
        "vramGb": vram_gb,
        "freeDiskGb": round(free_gb, 2),
        "requiredDiskGb": need_gb,
        "minVramGb": min_vram,
        "recommendedVramGb": rec_vram,
        "recommendedProfile": profile,
        "compatible": ok,
        "message": "; ".join(reasons) if reasons else f"Hardware suitable for {meta['label']}.",
        "reasons": reasons,
    }


def verify_weights(provider_id: str) -> dict[str, Any]:
    root = provider_dir(provider_id)
    markers = _REQUIRED_MARKERS[provider_id]
    missing: list[str] = []
    found: list[str] = []
    for marker in markers:
        path = root / marker
        # Accept README_CN.md as soft substitute when README.md not yet fetched
        if marker == "README.md" and not path.exists() and (root / "README_CN.md").exists():
            found.append("README_CN.md")
            continue
        if path.exists():
            found.append(marker)
        else:
            missing.append(marker)
    # Real weights (ignore tiny cache/metadata)
    weight_files = [
        p
        for p in list(root.rglob("*.safetensors")) + list(root.rglob("*.pt"))
        if p.is_file() and p.stat().st_size > 1_000_000
    ]
    healthy = not missing and len(weight_files) >= 1
    if not missing and not weight_files:
        total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and ".cache" not in p.parts)
        healthy = total > 500_000_000  # >500MB indicates real weights, not stub docs
    return {
        "ok": healthy,
        "providerId": provider_id,
        "path": str(root),
        "missing": missing,
        "found": found,
        "weightFileCount": len(weight_files),
        "message": "Weights verified." if healthy else f"Missing or incomplete: {', '.join(missing) or 'weights'}",
    }


def health_check(provider_id: str) -> dict[str, Any]:
    verify = verify_weights(provider_id)
    pre = hardware_preflight(provider_id)
    status = load_install_status(provider_id)
    healthy = bool(verify.get("ok")) and bool(status.get("installed"))
    # Generation readiness needs CUDA for local Comfy path
    generation_ready = healthy and (pre.get("cuda") or pre.get("vramGb") is not None)
    payload = {
        "ok": healthy,
        "providerId": provider_id,
        "installed": bool(status.get("installed")),
        "healthy": healthy,
        "generationReady": generation_ready,
        "verify": verify,
        "hardware": pre,
        "profile": status.get("profile") or pre.get("recommendedProfile"),
        "version": status.get("version"),
        "checkedAt": _now(),
    }
    if status.get("installed"):
        save_install_status(
            provider_id,
            {
                **status,
                "healthy": healthy,
                "generationReady": generation_ready,
                "lastHealthAt": _now(),
            },
        )
    return payload


def remove_provider(provider_id: str) -> InstallResult:
    root = provider_dir(provider_id)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    save_install_status(
        provider_id,
        {
            "installed": False,
            "healthy": False,
            "version": None,
            "profile": None,
            "removedAt": _now(),
        },
    )
    return InstallResult(True, f"Removed {provider_id} weights and status.", {"path": str(root)})


def install_component(
    component_id: str,
    *,
    on_progress: ProgressCb | None = None,
    cancel_check: CancelCheck | None = None,
    force: bool = False,
) -> InstallResult:
    provider_id = PROVIDER_BY_COMPONENT.get(component_id)
    if not provider_id:
        return InstallResult(False, f"Unknown Hunyuan component {component_id}", {})

    meta = OFFICIAL_SOURCES[provider_id]
    pre = hardware_preflight(provider_id)
    if not pre.get("compatible") and not force:
        return InstallResult(
            False,
            pre.get("message") or "Hardware incompatible for install.",
            {"preflight": pre, "fakeSuccess": False},
        )

    root = provider_dir(provider_id)
    root.mkdir(parents=True, exist_ok=True)
    profile = str(pre.get("recommendedProfile") or meta["defaultProfile"])

    def progress(phase: str, frac: float, message: str) -> None:
        if on_progress:
            on_progress(phase, frac, message)

    progress("preflight", 0.02, pre.get("message") or "Preflight OK")
    if cancel_check and cancel_check():
        return InstallResult(False, "Cancelled", {"phase": "cancelled"})

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return InstallResult(False, "huggingface_hub is required for Hunyuan install.", {})

    repo = str(meta["hfRepo"])
    patterns = (_ALLOW_PATTERNS.get(provider_id) or {}).get(profile)
    progress(
        "downloading",
        0.05,
        f"Downloading official {repo} profile={profile} (resume-safe"
        + (f", {len(patterns)} patterns)" if patterns else ", full snapshot)"),
    )

    local = None
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        if cancel_check and cancel_check():
            return InstallResult(False, "Cancelled", {"phase": "cancelled"})
        try:
            kwargs: dict[str, Any] = {
                "repo_id": repo,
                "local_dir": str(root),
                "local_dir_use_symlinks": False,
                "max_workers": 4,
            }
            if patterns:
                kwargs["allow_patterns"] = patterns
            try:
                local = snapshot_download(**kwargs, resume_download=True)
            except TypeError:
                # Newer huggingface_hub may drop resume_download / local_dir_use_symlinks
                kwargs.pop("local_dir_use_symlinks", None)
                local = snapshot_download(**kwargs)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            progress("downloading", 0.05 + attempt * 0.02, f"Retry {attempt}/3 after: {exc}")
    if last_exc is not None or local is None:
        save_install_status(
            provider_id,
            {
                "installed": False,
                "healthy": False,
                "version": None,
                "profile": profile,
                "lastError": f"Official download failed: {last_exc}",
                "updatedAt": _now(),
            },
        )
        return InstallResult(
            False,
            f"Official download failed: {last_exc}",
            {"repo": repo, "path": str(root), "preflight": pre, "profile": profile},
        )

    if cancel_check and cancel_check():
        return InstallResult(False, "Cancelled after download", {"phase": "cancelled"})

    progress("verifying", 0.9, "Verifying official weights")
    verify = verify_weights(provider_id)
    if not verify.get("ok"):
        save_install_status(
            provider_id,
            {
                "installed": False,
                "healthy": False,
                "version": None,
                "profile": pre.get("recommendedProfile"),
                "lastError": verify.get("message"),
                "updatedAt": _now(),
            },
        )
        return InstallResult(False, verify.get("message") or "Verify failed", {"verify": verify})

    version = "1.5" if provider_id == HUNYUAN_15 else "13b"
    status = {
        "installed": True,
        "healthy": True,
        "version": version,
        "profile": pre.get("recommendedProfile"),
        "hfRepo": repo,
        "localDir": local,
        "componentId": component_id,
        "installedAt": _now(),
        "updatedAt": _now(),
    }
    save_install_status(provider_id, status)
    progress("completed", 1.0, f"{meta['label']} installed")
    return InstallResult(
        True,
        f"{meta['label']} installed from official {repo}.",
        {"status": status, "verify": verify, "preflight": pre, "weights": {"diskUsageBytes": _dir_size(root)}},
    )


def repair_component(component_id: str, *, on_progress: ProgressCb | None = None) -> InstallResult:
    provider_id = PROVIDER_BY_COMPONENT.get(component_id)
    if not provider_id:
        return InstallResult(False, f"Unknown component {component_id}", {})
    verify = verify_weights(provider_id)
    if verify.get("ok"):
        health = health_check(provider_id)
        return InstallResult(True, "Already healthy; re-checked.", {"verify": verify, "health": health})
    return install_component(component_id, on_progress=on_progress, force=False)


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def active_download_for(component_id: str) -> dict[str, Any] | None:
    """Latest non-terminal (or recent failed) download op for a Hunyuan component."""
    try:
        from ..source_manager.downloads.queue import get_queue_manager

        qm = get_queue_manager()
        active = qm.active_for_component(component_id)
        if active:
            return active
        ops = qm.list({"componentId": component_id}) or []
    except Exception:
        return None
    if not ops:
        return None
    ops.sort(key=lambda o: str(o.get("updatedAt") or ""), reverse=True)
    return ops[0]


def enqueue_install(component_id: str) -> dict[str, Any]:
    """Enqueue a single Hunyuan install job (never auto-queues both models)."""
    from ..setup.catalog import get_component
    from ..source_manager.downloads.models import create_install_plan
    from ..source_manager.downloads.queue import get_queue_manager

    provider_id = PROVIDER_BY_COMPONENT[component_id]
    meta = OFFICIAL_SOURCES[provider_id]

    # Avoid stacking duplicate active installs for the same component
    existing = active_download_for(component_id)
    if existing and not existing.get("terminal"):
        phase = str(existing.get("phase") or "queued")
        pct = (existing.get("progress") or {}).get("percent")
        return {
            "ok": True,
            "alreadyQueued": True,
            "message": f"Install already {phase}"
            + (f" ({pct:.0f}%)" if isinstance(pct, (int, float)) else "")
            + " — track progress in Source Manager Active Downloads.",
            "operation": existing,
            "operationId": existing.get("id"),
            "componentId": component_id,
            "providerId": provider_id,
        }

    component = get_component(component_id)
    dest = str(provider_dir(provider_id))
    plan = create_install_plan(
        component_id=component_id,
        source_id=str(meta["hfRepo"]),
        provider_id="huggingface_snapshot",
        artifacts=[
            {
                "remotePath": str(meta["hfRepo"]),
                "destinationRelativePath": ".",
                "downloadUrl": f"https://huggingface.co/{meta['hfRepo']}",
            }
        ],
        destination_root=dest,
        estimated_download_bytes=component.download_bytes,
        estimated_extracted_bytes=component.installed_bytes,
        metadata={
            "componentId": component_id,
            "providerId": provider_id,
            "engine": meta["engine"],
            "officialOnly": True,
            "hunyuan": True,
        },
    )
    op = get_queue_manager().enqueue(plan, priority=40)
    return {
        "ok": True,
        "alreadyQueued": False,
        "message": "Install queued — track progress in Source Manager Active Downloads.",
        "operation": op,
        "operationId": op.get("id") if isinstance(op, dict) else getattr(op, "id", None),
        "componentId": component_id,
        "providerId": provider_id,
    }
