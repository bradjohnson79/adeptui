from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..secrets_store import secret_status
from .catalog import ComponentDefinition, get_component
from .paths import ensure_configured_paths
from .state import load_state, update_state


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
        configured = bool(secret_status("fal_api_key").get("configured"))
        if configured:
            return Verification(
                False, False, "credential_unverified",
                "The fal.ai key is configured but has not been verified with the service.",
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
