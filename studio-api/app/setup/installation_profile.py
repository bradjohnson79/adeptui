"""Installation profile on the existing setup record.

Local, API, and Hybrid are generation strategies for one application.
They are stored on setup_state.json. This module does not open a second database.
"""

from __future__ import annotations

from typing import Any

from .catalog import get_component, public_components
from .state import load_state, update_state

PROFILES = ("local", "api", "hybrid")
SKELETON_IDS = ("python", "ffmpeg")
LOCAL_BASELINE_IDS = (
    "zimage_models",
    "ltx_2_5_checkpoint",
    "ltx_2_5_text_encoder",
    "ltx_2_5_video_vae",
)
LTX_GROUP = (
    "ltx_2_5_checkpoint",
    "ltx_2_5_text_encoder",
    "ltx_2_5_video_vae",
)
PROVIDER_IDS = ("fal", "kie", "wavespeed", "elevenlabs")
PROTECTED_IDS = frozenset({"python", "ffmpeg"})


def active_profile(state: dict[str, Any] | None = None) -> str | None:
    raw = (state if state is not None else load_state()).get("installation_profile")
    value = str(raw or "").strip().lower()
    return value if value in PROFILES else None


def selected_local_models(state: dict[str, Any] | None = None) -> list[str]:
    raw = (state if state is not None else load_state()).get("selected_local_models")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def selected_providers(state: dict[str, Any] | None = None) -> list[str]:
    raw = (state if state is not None else load_state()).get("selected_providers")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item) in PROVIDER_IDS]


def _public_ids() -> set[str]:
    return {item.id for item in public_components()}


def expand_local_selection(selected: list[str]) -> list[str]:
    """Keep catalog dependencies with a chosen model. LTX 2.5 travels as one set."""
    allowed = _public_ids()
    chosen = [item for item in selected if item in allowed]
    if any(item in LTX_GROUP for item in chosen):
        for item in LTX_GROUP:
            if item not in chosen:
                chosen.append(item)
    expanded: list[str] = []
    pending = list(chosen)
    while pending:
        component_id = pending.pop(0)
        if component_id in expanded or component_id not in allowed:
            continue
        expanded.append(component_id)
        try:
            definition = get_component(component_id)
        except KeyError:
            continue
        for dependency in definition.dependencies:
            if dependency not in expanded:
                pending.append(dependency)
    return expanded


def required_ids_for(profile: str, state: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Components that must be ready for this profile. Optional models are not included."""
    if profile == "api":
        return SKELETON_IDS
    if profile == "local":
        return SKELETON_IDS + ("comfyui",) + LOCAL_BASELINE_IDS
    selected = expand_local_selection(selected_local_models(state))
    ordered = list(SKELETON_IDS)
    if selected:
        ordered.append("comfyui")
    for component_id in selected:
        if component_id not in ordered:
            ordered.append(component_id)
    return tuple(ordered)


def profile_required_ids() -> tuple[str, ...]:
    state = load_state()
    profile = active_profile(state)
    if profile is None:
        return ()
    return required_ids_for(profile, state)


def verified_providers() -> list[dict[str, str]]:
    """Names only. The key material stays in the secret store."""
    from ..hosted_providers.registry import PROVIDERS
    from ..secrets_store import secret_status

    found: list[dict[str, str]] = []
    for provider_id in PROVIDER_IDS:
        definition = PROVIDERS.get(provider_id)
        if definition is None:
            continue
        if secret_status(definition.secret_name).get("state") == "verified":
            found.append({"id": provider_id, "name": definition.display_name})
    return found


def save_installation_profile(
    profile: str,
    *,
    selected_models: list[str] | None = None,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    value = str(profile or "").strip().lower()
    if value not in PROFILES:
        raise ValueError("Choose Local, API, or Hybrid.")
    models = expand_local_selection(list(selected_models or []))
    if value == "local":
        models = list(LOCAL_BASELINE_IDS)
    if value == "api":
        models = []
    chosen_providers = [item for item in (providers or []) if item in PROVIDER_IDS]

    def mutate(latest: dict[str, Any]) -> None:
        latest["installation_profile"] = value
        latest["selected_local_models"] = models
        latest["selected_providers"] = chosen_providers

    return update_state(mutate)


def provider_blockers(profile: str, state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    connected = {item["id"] for item in verified_providers()}
    if profile == "api" and not connected:
        return [{
            "id": "provider:validated",
            "name": "Commercial API provider",
            "status": "missing",
        }]
    if profile == "hybrid":
        requested = selected_providers(state)
        missing = [item for item in requested if item not in connected]
        if missing:
            return [{
                "id": "provider:validated",
                "name": "Selected API provider",
                "status": "missing",
            }]
        if not requested and not selected_local_models(state):
            return [{
                "id": "profile:selection",
                "name": "Hybrid selection",
                "status": "missing",
            }]
    return []


COMFY_NOT_DOWNLOADABLE = (
    "Creator Engine is not installed. Adept UI reuses a ComfyUI that is already healthy. "
    "It does not download ComfyUI. Local generation stays incomplete until that engine is healthy."
)


def _job_can_install(job: dict[str, Any]) -> bool:
    """A placeholder confirmation is not an install. Only an active job is queued."""
    if job.get("active"):
        return True
    return str(job.get("state") or "") not in {"", "awaiting_confirmation"}


def apply_saved_profile() -> dict[str, Any]:
    """Queue install jobs only for required components that are not already ready."""
    from .status import build_status, invalidate_status_cache

    state = load_state()
    profile = active_profile(state)
    if profile is None:
        raise ValueError("Choose an installation profile first.")
    invalidate_status_cache()
    status = build_status(persist=False)
    rows = {
        str(item.get("id")): item
        for item in (status.get("components") or [])
        if isinstance(item, dict) and item.get("id")
    }
    needed = [
        component_id
        for component_id in required_ids_for(profile, state)
        if str((rows.get(component_id) or {}).get("status") or "") != "ready"
    ]
    queued: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    from ..source_manager.install_jobs.service import create_or_resume_install

    for component_id in required_ids_for(profile, state):
        if component_id not in needed:
            skipped.append(component_id)
            continue
        try:
            job = create_or_resume_install(
                component_id,
                confirm=True,
                confirm_download_models=True,
            )
            if not _job_can_install(job):
                message = COMFY_NOT_DOWNLOADABLE if component_id == "comfyui" else str(
                    (job.get("error") or {}).get("message") or job.get("message") or "This piece cannot be installed automatically."
                )
                errors.append({"id": component_id, "message": message})
                continue
            queued.append(str(job.get("id") or component_id))
        except Exception as exc:  # noqa: BLE001 — one component must not abort the rest of the plan
            errors.append({"id": component_id, "message": str(exc)})
    invalidate_status_cache()
    return {
        "profile": profile,
        "queued": queued,
        "skipped": skipped,
        "errors": errors,
        "alreadyReady": skipped,
    }
