from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..avatar_runtimes import verify_runtime as verify_avatar_runtime
from ..config import settings
from ..secrets_store import secret_status
from .catalog import ComponentDefinition, get_component
from .paths import ensure_configured_paths
from .state import load_state, update_state

# Short TTL avoids multi-second runtime probes (IndexTTS2 / Qwen voice) on every Setup poll.
_VERIFY_CACHE_TTL_SEC = 45.0
_VERIFY_CACHE: dict[str, tuple[float, "Verification"]] = {}
_CACHE_UNHEALTHY_COMPONENTS = {
    "index_tts2",
    "qwen_voice_design_17b",
    "qwen_voice_clone_17b",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Verification:
    healthy: bool
    absent: bool
    issue_code: str | None
    summary: str
    path: str | None = None
    version: str | None = None
    details: tuple[str, ...] = ()
    recommendation: str = "none"
    requires_user_interaction: bool = False


def _run_version(command: list[str]) -> tuple[bool, str | None, str | None]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip().splitlines()
        if result.returncode == 0 and output:
            return True, output[0][:200], None
        return False, None, f"Process exited with code {result.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, None, str(exc)[:200]


def _configured_location(component_id: str, state: dict[str, Any]) -> str | None:
    location = state.get("model_locations", {}).get(component_id)
    if location:
        return str(location)
    legacy = state.get("components", {}).get(component_id, {})
    if isinstance(legacy, dict) and legacy.get("path"):
        return str(legacy["path"])
    return None


def _candidate_file(location: str | None, filename: str, extra_dirs: tuple[str, ...] = ()) -> Path | None:
    roots: list[Path] = []
    if location:
        configured = Path(location).expanduser()
        if configured.is_file():
            return configured if configured.name.lower() == Path(filename).name.lower() else None
        # An explicit user path is authoritative. Falling through to a globally
        # discovered model would make an invalid link look successfully verified.
        roots.append(configured)
    else:
        models_dir = getattr(settings, "comfy_models_dir", None)
        if models_dir:
            roots.append(Path(models_dir))
        comfy_input_dir = getattr(settings, "comfy_input_dir", None)
        if comfy_input_dir:
            roots.append(Path(comfy_input_dir).parent / "models")
        roots.append(settings.data_dir / "models")
    for root in roots:
        for relative in ("", *extra_dirs):
            candidate = root / relative / filename
            if candidate.is_file():
                return candidate
    return None


def _krea2_roots(location: str | None) -> list[Path]:
    """Krea-scoped search roots: the configured component path, then the Krea 2 model root.

    The ComfyUI shared models dir is deliberately excluded — loose official filenames
    (turbo.safetensors / raw.safetensors) would false-positive on unrelated packs there.
    """
    roots: list[Path] = []
    if location:
        roots.append(Path(location).expanduser())
    model_root = str(getattr(settings, "krea2_model_root", "") or "").strip()
    if model_root:
        roots.append(Path(model_root).expanduser())
    return roots


def _krea2_find(
    roots: list[Path],
    configured: str,
    patterns: tuple[str, ...],
    extra_dirs: tuple[str, ...],
) -> Path | None:
    """Locate one Krea 2 file by configured name (exact) or install-time glob patterns."""
    configured = (configured or "").strip()
    if configured and Path(configured).is_absolute():
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_file() else None
    for root in roots:
        for relative in ("", *extra_dirs):
            base = root / relative if relative else root
            if configured:
                candidate = base / configured
                if candidate.is_file():
                    return candidate
            if not base.is_dir():
                continue
            for pattern in patterns:
                matches = sorted(p for p in base.glob(pattern) if p.is_file())
                if matches:
                    return matches[0]
    return None


def _verify_krea2_files(location: str | None) -> Verification:
    roots = _krea2_roots(location)
    specs = (
        (
            "Turbo checkpoint",
            settings.krea2_turbo_checkpoint,
            ("*turbo*.safetensors",),
            ("checkpoints", "diffusion_models"),
        ),
        (
            "RAW checkpoint",
            settings.krea2_raw_checkpoint,
            ("*raw*.safetensors",),
            ("checkpoints", "diffusion_models"),
        ),
        (
            "Qwen3-VL text encoder",
            settings.krea2_text_encoder,
            ("*qwen3*vl*.safetensors", "*qwen3_vl*.safetensors"),
            ("text_encoders", "clip"),
        ),
        (
            "Qwen Image VAE",
            settings.krea2_vae,
            ("*qwen*image*vae*.safetensors", "*qwen_image_vae*.safetensors"),
            ("vae",),
        ),
    )
    found = [
        _krea2_find(roots, configured, patterns, extra_dirs)
        for _label, configured, patterns, extra_dirs in specs
    ]
    missing = [label for (label, *_rest), path in zip(specs, found) if path is None]
    if not missing and all(path and os.access(path, os.R_OK) for path in found):
        return Verification(
            True,
            False,
            None,
            "Krea 2 Turbo/RAW checkpoints, Qwen3-VL text encoder, and Qwen Image VAE are readable.",
            str(roots[0]) if roots else None,
        )
    details = []
    for (label, configured, patterns, _dirs), path in zip(specs, found):
        if path is None:
            want = configured or " / ".join(patterns)
            details.append(f"Missing: {label} ({want})")
    if not roots:
        details.append("No Krea 2 model root is configured or linked.")
    return Verification(
        False,
        not any(found),
        "required_models_missing",
        "One or more Krea 2 model files are missing.",
        str(roots[0]) if roots else None,
        details=tuple(details),
        recommendation="correct_path" if location else "install",
        requires_user_interaction=True,
    )


def _service(url: str, suffix: str, name: str) -> Verification:
    try:
        import httpx

        response = httpx.get(f"{url.rstrip('/')}{suffix}", timeout=3.0)
        if response.status_code >= 400:
            return Verification(
                False, False, "service_http_error",
                f"{name} responded with HTTP {response.status_code}.",
                details=(f"URL: {url}",), recommendation="repair",
            )
        version = response.headers.get("server")
        return Verification(True, False, None, f"{name} is reachable.", path=url, version=version)
    except Exception as exc:
        return Verification(
            False, True, "service_unreachable", f"{name} is not reachable.",
            path=url, details=(str(exc)[:200],), recommendation="install",
            requires_user_interaction=True,
        )


def verify_component(component_id: str, state: dict[str, Any] | None = None) -> Verification:
    cached = _VERIFY_CACHE.get(component_id)
    if cached and (time.monotonic() - cached[0]) < _VERIFY_CACHE_TTL_SEC:
        return cached[1]
    result = _verify_component_uncached(component_id, state)
    if result.healthy or component_id in _CACHE_UNHEALTHY_COMPONENTS:
        _VERIFY_CACHE[component_id] = (time.monotonic(), result)
    else:
        _VERIFY_CACHE.pop(component_id, None)
    return result


def invalidate_verify_cache(component_id: str | None = None) -> None:
    if component_id:
        _VERIFY_CACHE.pop(component_id, None)
        return
    _VERIFY_CACHE.clear()


def _verify_component_uncached(component_id: str, state: dict[str, Any] | None = None) -> Verification:
    component = get_component(component_id)
    state = state or load_state()
    # Keep in-memory state aligned with Adept-owned defaults so callers that do
    # not go through build_status still see an obvious configured path.
    ensure_configured_paths(state)

    if component.verifier == "python":
        executable = Path(sys.executable)
        ok, version, error = _run_version([str(executable), "--version"])
        if executable.is_file() and ok:
            return Verification(True, False, None, "Python is installed correctly.", str(executable), version)
        return Verification(
            False, not executable.exists(), "executable_unusable", "Python could not be executed.",
            str(executable), details=((error or "Python executable is missing."),),
            recommendation="repair", requires_user_interaction=True,
        )

    if component.id == "ffmpeg":
        executable_name = shutil.which("ffmpeg")
        if not executable_name:
            return Verification(
                False, True, "executable_missing", "FFmpeg is not installed or is not on PATH.",
                recommendation="install", requires_user_interaction=True,
            )
        ok, version, error = _run_version([executable_name, "-version"])
        if ok:
            return Verification(True, False, None, "FFmpeg is installed correctly.", executable_name, version)
        return Verification(
            False, False, "executable_unusable", "FFmpeg exists but could not run.", executable_name,
            details=((error or "Version probe failed."),), recommendation="repair",
            requires_user_interaction=True,
        )

    if component.verifier == "comfy_service":
        return _service(settings.comfy_url, "/system_stats", "ComfyUI")
    if component.verifier == "ollama_service":
        return _service(settings.ollama_url, "/api/tags", "Ollama")

    if component.verifier == "fal_key":
        status = secret_status("fal_api_key")
        state = status.get("state") or "missing"
        message = str(status.get("message") or "")
        if state == "verified":
            return Verification(
                True, False, None,
                "The fal.ai key was accepted by fal.ai.",
                version=str(status.get("verifiedAt") or ""),
                details=((message,) if message else ()),
            )
        if state == "invalid":
            return Verification(
                False, False, "credential_invalid",
                "fal.ai rejected the configured API key.",
                details=((message,) if message else ()),
                recommendation="configure", requires_user_interaction=True,
            )
        if state == "unverified":
            return Verification(
                False, False, "credential_unverified",
                "The fal.ai key is configured but has not been verified with the service.",
                details=((message,) if message else ()),
                recommendation="configure", requires_user_interaction=True,
            )
        return Verification(
            False, True, "credential_missing", "A fal.ai API key is not configured.",
            recommendation="configure", requires_user_interaction=True,
        )

    location = _configured_location(component_id, state)
    if component.verifier == "ltx_file":
        path = _candidate_file(location, settings.ltx_checkpoint, ("checkpoints", "diffusion_models"))
        if path:
            if os.access(path, os.R_OK) and path.stat().st_size > 0:
                return Verification(True, False, None, "The LTX checkpoint is available and readable.", str(path))
            return Verification(
                False, False, "permission_denied", "The LTX checkpoint cannot be read.", str(path),
                recommendation="grant_permission", requires_user_interaction=True,
            )
        return Verification(
            False, True, "required_model_missing", "The required LTX checkpoint was not found.",
            location, details=(f"Expected file: {settings.ltx_checkpoint}",),
            recommendation="correct_path" if location else "install", requires_user_interaction=True,
        )

    if component.verifier == "ltx_2_5_file":
        path = _candidate_file(location, settings.ltx_2_5_checkpoint, ("diffusion_models", "checkpoints"))
        if path:
            if os.access(path, os.R_OK) and path.stat().st_size > 0:
                return Verification(True, False, None, "The LTX 2.5 checkpoint is available and readable.", str(path))
            return Verification(
                False, False, "permission_denied", "The LTX 2.5 checkpoint cannot be read.", str(path),
                recommendation="grant_permission", requires_user_interaction=True,
            )
        return Verification(
            False, True, "required_model_missing", "The required LTX 2.5 checkpoint was not found.",
            location, details=(f"Expected file: {settings.ltx_2_5_checkpoint}",),
            recommendation="correct_path" if location else "install", requires_user_interaction=True,
        )

    if component.verifier == "wan_files":
        names = (settings.wan_high_noise, settings.wan_low_noise, settings.wan_vae, settings.wan_text_encoder)
        found = [_candidate_file(location, name, ("diffusion_models", "vae", "text_encoders")) for name in names]
        missing = [name for name, path in zip(names, found) if path is None]
        if not missing and all(path and os.access(path, os.R_OK) for path in found):
            return Verification(True, False, None, "All required WAN model files are readable.", location)
        return Verification(
            False, not any(found), "required_models_missing", "One or more WAN model files are missing.",
            location, details=tuple(f"Missing: {name}" for name in missing),
            recommendation="correct_path" if location else "install", requires_user_interaction=True,
        )

    if component.verifier == "hunyuan_files":
        from ..video_runtime.hunyuan_providers import PROVIDER_BY_COMPONENT
        from ..video_runtime.hunyuan_install import verify_weights, hardware_preflight

        provider_id = PROVIDER_BY_COMPONENT.get(component_id)
        if not provider_id:
            return Verification(
                False, True, "unknown_component", "Unknown Hunyuan component.",
                recommendation="install", requires_user_interaction=True,
            )
        verify = verify_weights(provider_id)
        if verify.get("ok"):
            return Verification(
                True, False, None, verify.get("message") or "Hunyuan weights verified.",
                verify.get("path"),
            )
        pre = hardware_preflight(provider_id)
        details = tuple(verify.get("missing") or ()) + tuple(pre.get("reasons") or ())
        return Verification(
            False,
            True,
            "required_models_missing",
            verify.get("message") or "Hunyuan weights missing or incomplete.",
            verify.get("path"),
            details=details,
            recommendation="install",
            requires_user_interaction=True,
        )

    if component.verifier == "zimage_files":
        names = (settings.zimage_unet, settings.zimage_clip, settings.zimage_vae)
        extra_dirs = ("diffusion_models", "text_encoders", "vae", "clip", "clip_vision")
        found = [_candidate_file(location, name, extra_dirs) for name in names]
        missing = [name for name, path in zip(names, found) if path is None]
        if not missing and all(path and os.access(path, os.R_OK) for path in found):
            return Verification(
                True, False, None, "Z-Image Turbo UNET, text encoder, and VAE are readable.", location
            )
        return Verification(
            False, not any(found), "required_models_missing",
            "One or more Z-Image still-image model files are missing.",
            location, details=tuple(f"Missing: {name}" for name in missing),
            recommendation="correct_path" if location else "install", requires_user_interaction=True,
        )

    if component.verifier == "qwen_image_2512_files":
        names = (
            settings.qwen_image_2512_unet,
            settings.qwen_image_2512_clip,
            settings.qwen_image_2512_vae,
        )
        extra_dirs = ("diffusion_models", "text_encoders", "vae")
        found = [_candidate_file(location, name, extra_dirs) for name in names]
        missing = [name for name, path in zip(names, found) if path is None]
        if not missing and all(path and os.access(path, os.R_OK) for path in found):
            return Verification(
                True,
                False,
                None,
                "Qwen-Image-2512 UNET, text encoder, and VAE are readable.",
                location,
            )
        return Verification(
            False,
            not any(found),
            "required_models_missing",
            "One or more Qwen-Image-2512 model files are missing.",
            location,
            details=tuple(f"Missing: {name}" for name in missing),
            recommendation="correct_path" if location else "install",
            requires_user_interaction=True,
        )

    if component.verifier == "krea2_files":
        return _verify_krea2_files(location)

    if component.verifier == "linked_files":
        if not location:
            return Verification(
                False, True, "path_not_configured", f"{component.name} has no configured path.",
                recommendation="configure", requires_user_interaction=True,
            )
        path = Path(location).expanduser()
        if not path.exists():
            return Verification(
                False, True, "path_missing", f"The configured {component.name} path does not exist.",
                location, recommendation="correct_path", requires_user_interaction=True,
            )
        if not os.access(path, os.R_OK):
            return Verification(
                False, False, "permission_denied", f"The {component.name} path cannot be read.",
                location, recommendation="grant_permission", requires_user_interaction=True,
            )
        if path.is_dir() and not any(path.iterdir()):
            return Verification(
                False,
                True,
                "required_files_missing",
                f"No pack files were found in the selected directory.",
                location,
                recommendation="install",
                requires_user_interaction=True,
            )
        return Verification(True, False, None, f"{component.name} files are available and readable.", location)

    if component.verifier == "ic_lora_file":
        from ..references.ic_lora_status import ingredients_status
        from ..references.models import INGREDIENTS_FILENAME

        status = ingredients_status(location)
        st = status.get("status")
        if st == "ready":
            return Verification(
                True, False, None,
                status.get("summary") or status.get("message") or "Ingredients IC-LoRA is ready.",
                status.get("path"),
            )
        issue = status.get("issue_code") or "ic_lora_model_missing"
        absent = st in ("missing", "authorization_required")
        recommendation = "configure" if st == "authorization_required" else (
            "correct_path" if location else "install"
        )
        details = [f"Expected file: {INGREDIENTS_FILENAME}"]
        if status.get("hf"):
            details.append(f"HF probe: {status['hf']}")
        return Verification(
            False,
            absent,
            issue,
            status.get("summary") or status.get("message") or "Ingredients IC-LoRA is not ready.",
            status.get("path") or location,
            details=tuple(str(d) for d in details),
            recommendation=recommendation,
            requires_user_interaction=True,
        )

    if component.verifier == "m210b_sandbox":
        from ..codirector.m210b.qwen_voice_install import runtime_ready

        ready, detail = runtime_ready(component_id)
        root = str(detail.get("sandbox") or "")
        if ready:
            return Verification(
                True,
                False,
                "ok",
                f"{component.name} is installed and runtime-ready (venv + weights).",
                root,
                details=(
                    f"source={detail.get('sourceKey')}",
                    f"venv={detail.get('venvPython')}",
                    f"diskBytes={detail.get('diskUsageBytes')}",
                ),
            )
        missing = []
        if not detail.get("modelsPresent"):
            missing.append("weights")
        if not detail.get("venvPython"):
            missing.append("venv")
        if not detail.get("manifestInstalled"):
            missing.append("manifest.installed")
        return Verification(
            False,
            True,
            "not_installed",
            (
                f"{component.name} is not runtime-ready (missing: {', '.join(missing) or 'unknown'}). "
                "Install via Source Manager / Setup Wizard (official HF + isolated venv)."
            ),
            root,
            recommendation="install",
            requires_user_interaction=True,
            details=tuple(f"{k}={v}" for k, v in detail.items() if k != "error"),
        )

    if component.verifier == "index_tts2":
        from ..voice_performance.runtime import get_index_tts2_runtime

        runtime = get_index_tts2_runtime()
        inspection = runtime.inspect_installation()
        last_health = inspection.get("lastHealth") if isinstance(inspection.get("lastHealth"), dict) else {}
        root = str((inspection.get("paths") or {}).get("runtimeRoot") or "")
        state = str(inspection.get("state") or "not_installed")
        if state == "ready":
            return Verification(
                True,
                False,
                None,
                str(last_health.get("message") or inspection.get("message") or "IndexTTS2 is installed and runtime-ready."),
                root,
                version=str(inspection.get("repo", {}).get("revision") or ""),
                details=(
                    f"providerId={inspection.get('providerId')}",
                    f"modelRepository={inspection.get('modelRepository')}",
                    f"venvPython={(inspection.get('paths') or {}).get('venvPython')}",
                    f"device={last_health.get('device')}",
                ),
            )
        issue = {
            "not_installed": "not_installed",
            "compatible": "required_models_missing",
            "installed": "verification_required",
            "checking": "verification_in_progress",
            "verifying": "verification_in_progress",
            "installing": "install_in_progress",
            "update_available": "pinned_revision_mismatch",
            "incompatible": "source_mismatch",
            "repair_required": "repair_required",
            "failed": "runtime_failed",
        }.get(state, str(last_health.get("code") or "runtime_failed"))
        return Verification(
            False,
            state in {"not_installed", "compatible"},
            issue,
            str(last_health.get("message") or inspection.get("message") or "IndexTTS2 is not ready."),
            root,
            version=str(inspection.get("repo", {}).get("revision") or ""),
            details=(
                f"state={state}",
                f"providerId={inspection.get('providerId')}",
                f"modelRepository={inspection.get('modelRepository')}",
            ),
            recommendation="repair" if state in {"repair_required", "failed", "update_available", "incompatible"} else "install",
            requires_user_interaction=True,
        )

    if component.verifier == "audio_sandbox":
        from ..audio_studio.provider_resolver import local_runtime_status

        runtimes = local_runtime_status()
        runtime_name = "ACE-Step" if component_id == "ace_step_local" else "MMAudio"
        runtime = runtimes.get(runtime_name) or {}
        health = runtime.get("health") or {}
        root = str(health.get("venvPython") or "")
        if runtime.get("ready") and runtime.get("cuda"):
            return Verification(
                True,
                False,
                None,
                str(runtime.get("message") or f"{runtime_name} is installed and GPU-ready."),
                root,
                version=str(health.get("torchVersion") or ""),
                details=(
                    f"runtime={runtime_name}",
                    f"accelerator={runtime.get('accelerator')}",
                    f"device={runtime.get('device')}",
                ),
            )
        if runtime.get("ready") and not runtime.get("cuda"):
            return Verification(
                False,
                False,
                "gpu_not_ready",
                str(
                    runtime.get("message")
                    or (
                        f"{runtime_name} is installed but currently CPU-only. "
                        "Repair the CUDA runtime before using production audio generation."
                    )
                ),
                root,
                version=str(health.get("torchVersion") or ""),
                details=(
                    f"runtime={runtime_name}",
                    f"accelerator={runtime.get('accelerator')}",
                    f"device={runtime.get('device')}",
                ),
                recommendation="repair",
                requires_user_interaction=True,
            )
        return Verification(
            False,
            True,
            "not_installed",
            str(runtime.get("message") or f"{runtime_name} is not installed."),
            root,
            details=(f"runtime={runtime_name}",),
            recommendation="manual_help",
            requires_user_interaction=True,
        )

    if component.verifier == "avatar_runtime":
        runtime = verify_avatar_runtime(component_id)
        inspection = runtime.get("inspection") or {}
        if runtime.get("runtimeReady"):
            return Verification(
                True,
                False,
                None,
                str(runtime.get("message") or f"{component.name} is installed."),
                str(inspection.get("runtimeRoot") or ""),
                version=str(inspection.get("codeRevision") or ""),
                details=(
                    f"providerId={inspection.get('providerId')}",
                    f"launchPath={inspection.get('launchPath')}",
                    f"healthState={inspection.get('healthState')}",
                    f"gpu={((inspection.get('gpu') or {}).get('message') or 'unknown')}",
                ),
            )
        issue = "required_models_missing" if inspection.get("installed") else "not_installed"
        recommendation = "update" if inspection.get("updateAvailable") else "repair" if inspection.get("installed") else "install"
        return Verification(
            False,
            not bool(inspection.get("installed")),
            issue,
            str(runtime.get("message") or f"{component.name} is not ready."),
            str(inspection.get("runtimeRoot") or ""),
            version=str(inspection.get("codeRevision") or ""),
            details=tuple(
                [
                    f"providerId={inspection.get('providerId')}",
                    f"healthState={inspection.get('healthState')}",
                    *[f"blocker={item}" for item in (inspection.get("blockers") or [])],
                ]
            ),
            recommendation=recommendation,
            requires_user_interaction=True,
        )

    if component.verifier == "asset_pack":
        from .pack_install import directory_byte_size, required_files_present
        from .pack_manifests import get_pack_manifest
        from .pack_release_cache import get_cached_release
        manifest = get_pack_manifest(component_id)
        cached = get_cached_release(component_id)
        if not location:
            # Cached release (GitHub or fixture_http) means Install is available.
            if cached:
                return Verification(
                    False,
                    True,
                    "not_installed",
                    f"{component.name} is available but not installed.",
                    recommendation="install",
                    requires_user_interaction=True,
                    version=str(cached.get("version") or manifest.version),
                )
            if not manifest.has_valid_source():
                # Unpublished packs without a resolvable source — not a red "broken download".
                # (fixture_http with a base URL makes has_valid_source() True above.)
                if not manifest.is_published():
                    return Verification(
                        False,
                        True,
                        "source_not_published",
                        (
                            f"No official distribution has been published for {component.name} yet. "
                            "Add a Source URL or Link Existing Folder when you have pack files."
                        ),
                        recommendation="add_source_url",
                        requires_user_interaction=True,
                        version=manifest.version,
                        details=(
                            f"distributionStatus={manifest.distribution_status}",
                            "Global ADEPT_PACK_GITHUB_OWNER/REPOSITORY is not used as a universal pack source.",
                        ),
                    )
                return Verification(
                    False,
                    True,
                    "source_not_configured",
                    "This component exists in the catalog, but no installation source has been assigned.",
                    recommendation="add_source_url",
                    requires_user_interaction=True,
                    version=manifest.version,
                )
            # Provider/env configured but Check Again has not cached a release yet.
            if manifest.uses_provider() and not manifest.source_url():
                return Verification(
                    False,
                    True,
                    "pack_release_not_found",
                    "No published release was found for this pack. Use Check Again.",
                    recommendation="refresh_source",
                    requires_user_interaction=True,
                    version=manifest.version,
                )
            return Verification(
                False,
                True,
                "not_installed",
                f"{component.name} is not installed.",
                recommendation="install",
                requires_user_interaction=True,
                version=manifest.version,
            )
        path = Path(location).expanduser()
        if not path.exists():
            if not manifest.has_valid_source():
                issue = (
                    "source_not_published"
                    if not manifest.is_published()
                    else "source_not_configured"
                )
                return Verification(
                    False,
                    True,
                    issue,
                    (
                        f"No official distribution has been published for {component.name} yet."
                        if issue == "source_not_published"
                        else "No official source has been assigned to this component."
                    ),
                    location,
                    recommendation="add_source_url",
                    requires_user_interaction=True,
                    version=manifest.version,
                )
            return Verification(
                False,
                True,
                "path_missing",
                f"The configured {component.name} path does not exist.",
                location,
                recommendation="install",
                requires_user_interaction=True,
                version=manifest.version,
            )
        if not os.access(path, os.R_OK):
            return Verification(
                False, False, "permission_denied", f"The {component.name} path cannot be read.",
                location, recommendation="grant_permission", requires_user_interaction=True,
                version=manifest.version,
            )
        ok, missing = required_files_present(path, manifest.install.required_files)
        if not ok or directory_byte_size(path) <= 0:
            return Verification(
                False,
                True,
                "required_files_missing",
                "No pack files were downloaded."
                if not any(path.iterdir())
                else f"Required pack files are missing: {', '.join(missing)}.",
                location,
                recommendation="install" if manifest.has_valid_source() else "add_source_url",
                requires_user_interaction=True,
                version=manifest.version,
                details=tuple(f"Missing: {item}" for item in missing),
            )
        return Verification(
            True,
            False,
            None,
            f"{component.name} files are available and verified.",
            location,
            version=manifest.version,
        )

    if component.verifier == "comfy_extension_nodes":
        from ..source_manager.install_jobs.comfy_extension_installer import (
            probe_required_nodes,
            resolve_custom_nodes_dir,
            resolve_extension_source,
        )

        try:
            source = resolve_extension_source(component_id)
            target = resolve_custom_nodes_dir() / str(source["packageName"])
        except Exception:
            target = resolve_custom_nodes_dir() / component_id
            source = {}
        if not target.is_dir():
            return Verification(
                False,
                True,
                "not_installed",
                f"{component.name} is not installed in ComfyUI custom_nodes.",
                recommendation="install",
                requires_user_interaction=True,
            )
        probe = probe_required_nodes()
        if probe.get("ok"):
            return Verification(
                True,
                False,
                None,
                f"{component.name} is installed and required nodes are registered.",
                str(target),
                details=(probe.get("message") or "",),
            )
        if not probe.get("available"):
            return Verification(
                False,
                False,
                "restart_required",
                "Extension files are present, but ComfyUI must restart before nodes can be verified.",
                str(target),
                details=(probe.get("message") or "",),
                recommendation="repair",
                requires_user_interaction=True,
            )
        missing = ", ".join(probe.get("missing") or [])
        return Verification(
            False,
            False,
            "nodes_missing",
            f"Extension installed, but required nodes were not registered: {missing}.",
            str(target),
            details=(probe.get("message") or "",),
            recommendation="repair",
            requires_user_interaction=True,
        )

    return Verification(False, False, "unsupported_verifier", "Verification is not supported.", recommendation="manual_help")


def diagnose(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    state = load_state()
    auto_bound = ensure_configured_paths(state)
    if auto_bound:
        update_state(
            lambda latest: latest.setdefault("model_locations", {}).update(auto_bound)
        )
        state = load_state()
    result = verify_component(component_id, state)
    details = list(result.details)

    try:
        usage = shutil.disk_usage(settings.data_dir)
        details.append(f"Available disk bytes: {usage.free}")
        if not result.healthy and component.download_bytes and usage.free < component.download_bytes:
            result = Verification(
                False, result.absent, "insufficient_disk_space",
                f"There is not enough free disk space for {component.name}.",
                result.path, result.version, tuple(details), "manual_help", True,
            )
    except OSError as exc:
        details.append(f"Disk check unavailable: {exc}")

    if result.path:
        target = Path(result.path) if "://" not in result.path else settings.data_dir
        permission_target = target if target.exists() else target.parent
        if permission_target.exists():
            details.append(f"Readable path: {os.access(permission_target, os.R_OK)}")
            details.append(f"Writable path: {os.access(permission_target, os.W_OK)}")

    from .component_kinds import component_kind

    kind = component_kind(component)
    labels = {
        "none": "No Action Required",
        "install": "Download and Install",
        "repair": "Repair Installation",
        "reinstall": "Reinstall",
        "update": "Update Now",
        "correct_path": "Locate Existing Files",
        "grant_permission": "Grant Permission",
        "configure": "Configure API Key" if kind == "credential" else "Configure",
        "manual_help": "View Details",
        "link_existing": "Link Existing Folder",
        "choose_install_location": "Choose Install Location",
        "refresh_source": "Check Again",
        "add_source_url": "Add Source URL",
    }
    recommendation = result.recommendation
    if result.issue_code in (
        "source_not_published",
        "source_not_configured",
        "download_source_missing",
        "pack_provider_not_configured",
    ):
        recommendation = "add_source_url"
    elif result.issue_code == "pack_release_not_found":
        recommendation = "refresh_source"
    return {
        "component_id": component_id,
        "healthy": result.healthy,
        "issue_code": result.issue_code,
        "summary": result.summary,
        "technical_details": details,
        "recommendation": recommendation,
        "recommended_action_label": labels.get(recommendation, "Run Diagnostics"),
        "requires_user_interaction": result.requires_user_interaction,
        "checked_at": utc_now(),
    }
