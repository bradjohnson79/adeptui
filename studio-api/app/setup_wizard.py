from __future__ import annotations

"""Setup Wizard: detect hardware/software + component catalog (approve-before-download)."""

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from .config import settings
from .setup.state import load_state as _load_versioned_state
from .setup.state import save_state as _save_versioned_state
from .vram_profiles import query_gpu_stats


@dataclass
class SetupComponent:
    id: str
    name: str
    description: str
    purpose: str
    required: bool
    download_size_mb: float
    installed_size_mb: float
    min_vram_gb: int
    recommended_vram_gb: int
    modes: list[str]
    source_repo: str
    license: str
    install_kind: str  # detect_only | download | path_link
    category: str = "Core"


CATALOG: list[SetupComponent] = [
    SetupComponent(
        id="comfyui",
        name="ComfyUI",
        description="Local node graph runtime for MiniMax H3 / LTX 2.5 / lip sync.",
        purpose="Powers local video generation in 1 Frame, 3 Frame, and Director.",
        required=True,
        download_size_mb=0,
        installed_size_mb=500,
        min_vram_gb=8,
        recommended_vram_gb=24,
        modes=["1 Frame", "3 Frame", "Director", "Lip Sync", "Character / Angles"],
        source_repo="https://github.com/comfyanonymous/ComfyUI",
        license="GPL-3.0",
        install_kind="detect_only",
    ),
    SetupComponent(
        id="ffmpeg",
        name="FFmpeg",
        description="Media mux, trim, and encode toolkit.",
        purpose="Audio mux, timeline stitch, preview helpers.",
        required=True,
        download_size_mb=80,
        installed_size_mb=100,
        min_vram_gb=0,
        recommended_vram_gb=0,
        modes=["Director", "Generate Timeline", "Export"],
        source_repo="https://ffmpeg.org",
        license="LGPL/GPL",
        install_kind="detect_only",
    ),
    SetupComponent(
        id="python",
        name="Python",
        description="Runtime for studio-api and tooling.",
        purpose="API server and Setup Wizard utilities.",
        required=True,
        download_size_mb=0,
        installed_size_mb=200,
        min_vram_gb=0,
        recommended_vram_gb=0,
        modes=["All"],
        source_repo="https://www.python.org",
        license="PSF",
        install_kind="detect_only",
    ),
    SetupComponent(
        id="ollama",
        name="Ollama",
        description="Local LLM host for the Adept assistant.",
        purpose="Scene setup, timeline propose, creative coaching.",
        required=False,
        download_size_mb=0,
        installed_size_mb=4000,
        min_vram_gb=8,
        recommended_vram_gb=12,
        modes=["Assistant", "Generate Timeline"],
        source_repo="https://ollama.com",
        license="MIT",
        install_kind="detect_only",
    ),
    SetupComponent(
        id="ltx_2_5_checkpoint",
        name="LTX 2.5 Checkpoint",
        description="Required for LTX 2.5 video generation. 25 GB download. Recommended: 16 GB VRAM. Distilled BF16 delivers high quality with fast inference.",
        purpose="LTX 2.5 video generation (Fast / Distilled and Full Quality modes).",
        required=False,
        download_size_mb=25000,
        installed_size_mb=25000,
        min_vram_gb=8,
        recommended_vram_gb=16,
        modes=["Fast / Distilled", "Full Quality"],
        source_repo="https://huggingface.co/Lightricks/LTX-2.5",
        license="Gated model license (Hugging Face)",
        install_kind="path_link",
        category="Video Models",
    ),
    SetupComponent(
        id="ltx_2_5_audio_vae",
        name="LTX 2.5 Audio VAE",
        description="Enables synchronized native audio generation with LTX 2.5 video. 1 GB download.",
        purpose="Synchronized native audio generation with LTX 2.5 video.",
        required=False,
        download_size_mb=1000,
        installed_size_mb=1000,
        min_vram_gb=4,
        recommended_vram_gb=8,
        modes=["Audio ON / OFF"],
        source_repo="https://huggingface.co/Lightricks/LTX-2.5",
        license="Gated model license (Hugging Face)",
        install_kind="path_link",
        category="Video Models",
    ),
    SetupComponent(
        id="fal_key",
        name="fal.ai API Key",
        description="Cloud generation credentials (encrypted locally).",
        purpose="Seedance / Kling / Veo / Runway engines.",
        required=False,
        download_size_mb=0,
        installed_size_mb=0,
        min_vram_gb=0,
        recommended_vram_gb=0,
        modes=["1 Frame", "3 Frame", "Director", "Txt2Vid"],
        source_repo="https://fal.ai/dashboard/keys",
        license="Service ToS",
        install_kind="detect_only",
    ),
]


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _ram_gb() -> Optional[float]:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        try:
            # Windows wmic fallback
            out = subprocess.check_output(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return round(int(line) / (1024**3), 1)
        except Exception:
            return None
    return None


def _disk_free_gb(path: Path) -> Optional[float]:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 1)
    except Exception:
        return None


def detect_environment() -> dict[str, Any]:
    gpu = query_gpu_stats()
    comfy_ok = False
    comfy_msg = ""
    try:
        import httpx

        r = httpx.get(f"{settings.comfy_url.rstrip('/')}/system_stats", timeout=3.0)
        comfy_ok = r.status_code < 400
        comfy_msg = "reachable" if comfy_ok else f"HTTP {r.status_code}"
    except Exception as exc:
        comfy_msg = str(exc)[:200]

    ollama_ok = False
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=3.0)
        ollama_ok = r.status_code < 400
    except Exception:
        ollama_ok = False

    from .secrets_store import secret_status

    fal = secret_status("fal_api_key")

    model_roots = {
        "comfy_models": str(getattr(settings, "comfy_models_dir", "") or ""),
        "data_dir": str(settings.data_dir),
        "comfy_url": settings.comfy_url,
        "ollama_url": settings.ollama_url,
    }

    installed: dict[str, Any] = {}
    state_path = settings.data_dir / "setup_state.json"
    if state_path.exists():
        try:
            installed = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            installed = {}

    return {
        "gpu": gpu,
        "ram_gb": _ram_gb(),
        "disk_free_gb": _disk_free_gb(settings.data_dir),
        "python": {"path": _which("python") or _which("python3"), "version": os.sys.version.split()[0]},
        "ffmpeg": {"path": _which("ffmpeg"), "found": bool(_which("ffmpeg"))},
        "comfyui": {"url": settings.comfy_url, "reachable": comfy_ok, "message": comfy_msg},
        "ollama": {"url": settings.ollama_url, "reachable": ollama_ok},
        "fal_key": fal,
        "paths": model_roots,
        "installed": installed,
        "catalog": [asdict(c) for c in CATALOG],
    }


def load_setup_state() -> dict[str, Any]:
    return _load_versioned_state()


def save_setup_state(state: dict[str, Any]) -> dict[str, Any]:
    return _save_versioned_state(state)


def approve_install(component_id: str, *, action: str, path: str | None = None) -> dict[str, Any]:
    """
    Record an approved install/link action. Does not silently download multi-GB weights.
    For path_link / detect_only: verify path exists and mark installed.
    """
    if action in {"install", "link", "link_existing", "repair", "update", "reinstall"}:
        from .setup.model_license import assert_installation_allowed

        assert_installation_allowed(component_id)
    if component_id in {
        "wan_models",
        "hunyuan_video_15",
        "hunyuan_video_13b",
        "ltx_checkpoint",
        "ltx23_ic_lora_ingredients",
        "comfyui_hunyuan_nodes",
    }:
        raise KeyError(
            f"{component_id} is retired from local video generation and is not installable"
        )
    comp = next((c for c in CATALOG if c.id == component_id), None)
    if not comp:
        raise KeyError(f"Unknown component {component_id}")
    state = load_setup_state()
    comps = state.setdefault("components", {})
    entry = {
        "id": component_id,
        "action": action,
        "path": path or "",
        "approved": True,
        "status": "pending",
        "message": "",
    }
    if component_id in {
        "longcat-video-avatar-1-5-local",
        "infinitetalk-local",
        "musetalk-1-5-local",
        "echomimic-v2-local",
    }:
        # Avatar Studio temporarily retired — refuse install/probe/repair from current flows.
        # Allow remove only (does not delete model weights unless caller uses remove_runtime explicitly).
        if action not in {"remove"}:
            entry["status"] = "retired"
            entry["message"] = (
                "Avatar Studio is not available in this version. "
                "Avatar runtimes (InfiniteTalk / LongCat / MuseTalk / EchoMimic) are retired from "
                "current Adept UI production flows. Model weights were not deleted."
            )
            comps[component_id] = entry
            save_setup_state(state)
            return entry
        from .avatar_runtimes import benchmark_runtime, link_existing_runtime, remove_runtime, verify_runtime

        if action == "remove":
            result = remove_runtime(component_id)
            entry["status"] = "removed"
            entry["message"] = str(result.get("message") or "Removed runtime.")
            state.get("model_locations", {}).pop(component_id, None)
        elif action == "benchmark":
            result = benchmark_runtime(component_id)
            entry["status"] = str(result.get("status") or "benchmark_recorded")
            entry["message"] = str(result.get("message") or "Benchmark hook recorded.")
        elif action == "link_existing":
            if not path:
                raise ValueError("Path is required to link an existing runtime folder.")
            result = link_existing_runtime(component_id, path)
            entry["status"] = "installed"
            entry["message"] = str(result.get("message") or "Linked existing runtime.")
            state.setdefault("model_locations", {})[component_id] = path
        elif action == "verify":
            result = verify_runtime(component_id)
            entry["status"] = "installed" if result.get("runtimeReady") else "failed"
            entry["message"] = str(result.get("message") or "Verification completed.")
        elif action == "update":
            entry["status"] = "update_noted"
            entry["message"] = "Update approved. Use Download and Install from Source Manager to apply the audited pins."
        elif action == "repair":
            entry["status"] = "repair_noted"
            entry["message"] = "Repair approved. Use Source Manager to rerun the isolated install."
        else:
            entry["status"] = "approved"
            entry["message"] = f"{action} approved for Source Manager."
        comps[component_id] = entry
        save_setup_state(state)
        from .setup.orchestrator import diagnose_component

        diagnostic = diagnose_component(component_id)
        entry["verified"] = bool(diagnostic["healthy"])
        entry["verification"] = {
            "checked_at": diagnostic["checked_at"],
            "issue_code": diagnostic["issue_code"],
            "summary": diagnostic["summary"],
            "recommendation": diagnostic["recommendation"],
        }
        latest = load_setup_state()
        latest.setdefault("components", {})[component_id] = entry
        save_setup_state(latest)
        return entry
    if action in ("verify", "repair", "link", "install"):
        if path:
            from .setup.paths import ensure_path_exists, path_selector_mode

            p = Path(path).expanduser()
            try:
                mode = path_selector_mode(component_id)
            except KeyError:
                mode = "directory" if not p.suffix else "file"
            if mode == "directory":
                p = ensure_path_exists(p, mode=mode)
                entry["status"] = "installed"
                entry["message"] = f"Linked/verified at {p}"
                state.setdefault("model_locations", {})[component_id] = str(p)
            elif not p.exists():
                ensure_path_exists(p, mode=mode)
                entry["status"] = "failed"
                entry["message"] = f"Path not found: {path}"
            else:
                entry["status"] = "installed"
                entry["message"] = f"Linked/verified at {p}"
                state.setdefault("model_locations", {})[component_id] = str(p)
        elif action == "verify":
            # soft verify via detect
            env = detect_environment()
            if component_id == "ffmpeg":
                entry["status"] = "installed" if env["ffmpeg"]["found"] else "missing"
            elif component_id == "comfyui":
                entry["status"] = "installed" if env["comfyui"]["reachable"] else "missing"
            elif component_id == "python":
                entry["status"] = "installed" if env["python"]["path"] else "missing"
            elif component_id == "ollama":
                entry["status"] = "installed" if env["ollama"]["reachable"] else "missing"
            elif component_id == "fal_key":
                entry["status"] = "installed" if env["fal_key"].get("configured") else "missing"
            else:
                entry["status"] = "unknown"
                entry["message"] = "Provide a path to link model weights (explicit approval)."
        else:
            entry["status"] = "awaiting_path"
            entry["message"] = "Approved — provide install/link path to complete."
    elif action == "remove":
        entry["status"] = "removed"
        entry["message"] = "Marked removed (files not deleted automatically)."
        state.get("model_locations", {}).pop(component_id, None)
    elif action == "update":
        entry["status"] = "update_noted"
        entry["message"] = "Update flagged — re-link or re-download with approval."
    else:
        entry["status"] = "unknown"
        entry["message"] = f"Unsupported action {action}"

    comps[component_id] = entry
    save_setup_state(state)

    # Legacy action semantics remain intact, but every supported action now
    # finishes with real normalized verification. Approval/path existence alone
    # never promotes the normalized component status to ready.
    from .setup.orchestrator import diagnose_component

    diagnostic = diagnose_component(component_id)
    entry["verified"] = bool(diagnostic["healthy"])
    entry["verification"] = {
        "checked_at": diagnostic["checked_at"],
        "issue_code": diagnostic["issue_code"],
        "summary": diagnostic["summary"],
        "recommendation": diagnostic["recommendation"],
    }
    latest = load_setup_state()
    latest.setdefault("components", {})[component_id] = entry
    save_setup_state(latest)
    return entry
