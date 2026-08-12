from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import settings
from ...image_runtime.provider_registry import list_providers as list_image_providers
from ...secrets_store import secret_status
from ...source_manager.install_jobs.service import (
    create_or_resume_install,
    get_job,
    jobs_for_component,
    repair as repair_install_job,
)
from ...source_manager.service import save_verified_source_for_component, verify_and_select
from ...vram_profiles import query_gpu_stats
from ..catalog import COMPONENTS, get_component
from ..diagnostics import utc_now, verify_component
from .models import (
    CalibrationProfile,
    CertifiedRecipe,
    InstallPlan,
    MonitorFinding,
    ProviderCertificationRecord,
    ProviderLifecycleState,
    UpdatePlan,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_RECIPES_DIR = _REPO_ROOT / "config" / "setup" / "certified-recipes"
_IMAGE_PROVIDER_KEYS = {
    "fal": "fal_api_key",
    "openai": "openai_api_key",
    "google_imagen": "google_api_key",
    "replicate": "replicate_api_token",
    "ideogram": "ideogram_api_key",
    "recraft": "recraft_api_key",
    "leonardo": "leonardo_api_key",
    "runware": "runware_api_key",
    "together": "together_api_key",
}
_LOCAL_IMAGE_COMPONENTS: dict[str, dict[str, Any]] = {
    "flux1_dev_local": {
        "parameterCount": "12B",
        "downloadSizeLabel": "~23 GB",
        "diskUsageLabel": "~25 GB",
        "vramRecommendationGb": 24,
        "typicalGenerationSpeed": "18-30s at 1024",
        "supportedResolutions": ["1024x1024", "1216x832", "832x1216"],
        "strengths": ["Photoreal detail", "Lighting realism", "Production stills"],
        "weaknesses": ["Slower than preview models", "Needs larger VRAM"],
        "bestFor": ["Photoreal concepts", "Marketing stills", "Character key art"],
        "badges": ["Photoreal", "Production Quality", "Reference Images", "Inpainting"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["photoreal", "cinematic", "marketing"],
    },
    "flux1_schnell_local": {
        "parameterCount": "12B",
        "downloadSizeLabel": "~23 GB",
        "diskUsageLabel": "~25 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "6-12s at 1024",
        "supportedResolutions": ["1024x1024", "1216x832", "832x1216"],
        "strengths": ["Fast preview", "Responsive ideation", "Good lighting"],
        "weaknesses": ["Lower final polish than Dev", "Less dependable typography"],
        "bestFor": ["Rapid mood boards", "Thumbnail exploration", "Fast preview"],
        "badges": ["Fast Preview", "Photoreal", "Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["preview", "speed", "ideation"],
    },
    "flux1_kontext_dev_local": {
        "parameterCount": "12B",
        "downloadSizeLabel": "~24 GB",
        "diskUsageLabel": "~26 GB",
        "vramRecommendationGb": 24,
        "typicalGenerationSpeed": "20-35s at 1024",
        "supportedResolutions": ["1024x1024", "1536x864", "864x1536"],
        "strengths": ["Photoreal characters", "Reference following", "Context-aware edits"],
        "weaknesses": ["Heavy VRAM demand", "Longer setup time"],
        "bestFor": ["Photoreal character work", "Reference matching", "Director notes"],
        "badges": ["Photoreal", "Editing", "Consistency", "Reference Images", "Production Quality"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["photoreal", "character", "reference", "editing"],
    },
    "qwen_image_2512_models": {
        "parameterCount": "8B+",
        "downloadSizeLabel": "~28 GB",
        "diskUsageLabel": "~28 GB",
        "vramRecommendationGb": 12,
        "typicalGenerationSpeed": "12-18s at 1024",
        "supportedResolutions": ["1024x1024", "1328x768", "768x1328"],
        "strengths": ["Balanced realism", "Typography", "Flexible styles"],
        "weaknesses": ["Less context following than Kontext", "Needs tuned steps"],
        "bestFor": ["General stills", "Poster design", "Style exploration"],
        "badges": ["Photoreal", "Illustration", "Text Rendering", "Reference Images"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["general", "text", "illustration", "anime"],
    },
    "zimage_models": {
        "parameterCount": "Turbo",
        "downloadSizeLabel": "~20 GB",
        "diskUsageLabel": "~20 GB",
        "vramRecommendationGb": 8,
        "typicalGenerationSpeed": "5-10s at 1024",
        "supportedResolutions": ["1024x1024", "1344x768", "768x1344"],
        "strengths": ["Speed", "Simple local setup", "Strong fallback"],
        "weaknesses": ["Less detailed than flagship families", "Weak text rendering"],
        "bestFor": ["Fast preview", "Fallback renders", "Low-VRAM stills"],
        "badges": ["Fast Preview", "Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["fallback", "preview", "anime"],
    },
    "sana_15_local": {
        "parameterCount": "4.8B",
        "downloadSizeLabel": "~12 GB",
        "diskUsageLabel": "~14 GB",
        "vramRecommendationGb": 12,
        "typicalGenerationSpeed": "10-16s at 1024",
        "supportedResolutions": ["1024x1024", "1280x720", "720x1280"],
        "strengths": ["Stylized art", "Anime leaning", "Fast composition"],
        "weaknesses": ["Less photoreal", "Lower fidelity small text"],
        "bestFor": ["Anime", "Illustration", "Stylized concept art"],
        "badges": ["Anime", "Illustration", "Fast Preview"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["anime", "illustration", "stylized"],
    },
    "sdxl_local": {
        "parameterCount": "Base+Refiner",
        "downloadSizeLabel": "~13 GB",
        "diskUsageLabel": "~15 GB",
        "vramRecommendationGb": 12,
        "typicalGenerationSpeed": "10-18s at 1024",
        "supportedResolutions": ["1024x1024", "1152x896", "896x1152"],
        "strengths": ["Broad ecosystem", "Editing support", "Mature workflows"],
        "weaknesses": ["Older baseline realism", "Needs workflow tuning"],
        "bestFor": ["General-purpose stills", "LoRA ecosystem", "Inpainting"],
        "badges": ["Photoreal", "Editing", "Inpainting", "Outpainting"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["general", "editing", "ecosystem"],
    },
    "sd35_large_local": {
        "parameterCount": "8B",
        "downloadSizeLabel": "~17 GB",
        "diskUsageLabel": "~18 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-22s at 1024",
        "supportedResolutions": ["1024x1024", "1360x768", "768x1360"],
        "strengths": ["Strong prompt adherence", "Clean compositions", "Modern SD family"],
        "weaknesses": ["Heavier than SDXL", "Less proven than FLUX/Qwen here"],
        "bestFor": ["Prompt-accurate stills", "Illustration", "Layout passes"],
        "badges": ["Illustration", "Photoreal", "Production Quality"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": False,
        "capabilityTags": ["prompt", "layout", "general"],
    },
    "cogview4_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~18 GB",
        "diskUsageLabel": "~20 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-24s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Catalogued for future certification"],
        "weaknesses": ["Not fully certified in this build"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
    "hidream_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~20 GB",
        "diskUsageLabel": "~22 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-24s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Catalogued for future certification"],
        "weaknesses": ["Not installable by recipe yet"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
    "lumina_image_2_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~18 GB",
        "diskUsageLabel": "~20 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-22s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Catalogued for future certification"],
        "weaknesses": ["Not installable by recipe yet"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
    "pixart_sigma_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~12 GB",
        "diskUsageLabel": "~14 GB",
        "vramRecommendationGb": 12,
        "typicalGenerationSpeed": "10-16s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Efficient experimentation"],
        "weaknesses": ["Not certified in this build"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration", "Fast Preview"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
    "kolors_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~13 GB",
        "diskUsageLabel": "~15 GB",
        "vramRecommendationGb": 12,
        "typicalGenerationSpeed": "10-18s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Colorful stylized imagery"],
        "weaknesses": ["Not certified in this build"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
    "omnigen_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~14 GB",
        "diskUsageLabel": "~16 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-22s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Unified multimodal ambitions"],
        "weaknesses": ["Not certified in this build"],
        "bestFor": ["R&D trials"],
        "badges": ["Editing", "Reference Images"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental", "multimodal"],
    },
    "janus_pro_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~14 GB",
        "diskUsageLabel": "~16 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-22s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Multimodal analysis + image creation"],
        "weaknesses": ["Experimental install posture"],
        "bestFor": ["R&D multimodal workflows"],
        "badges": ["Editing", "Reference Images"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental", "multimodal"],
    },
    "hunyuan_image_local": {
        "parameterCount": "Unknown",
        "downloadSizeLabel": "~20 GB",
        "diskUsageLabel": "~22 GB",
        "vramRecommendationGb": 16,
        "typicalGenerationSpeed": "14-24s at 1024",
        "supportedResolutions": ["1024x1024"],
        "strengths": ["Catalogued for future certified image flow"],
        "weaknesses": ["Certified form not landed here yet"],
        "bestFor": ["R&D trials"],
        "badges": ["Illustration", "Photoreal"],
        "group": "Image Generation",
        "subgroup": "Local Models",
        "experimental": True,
        "capabilityTags": ["experimental"],
    },
}

_COMPONENT_METADATA_OVERRIDES: dict[str, dict[str, Any]] = {
    "fal_key": {
        "group": "API Providers",
        "subgroup": "Credentials",
        "surfaceGroups": ["API Providers"],
        "capabilityTags": ["cloud", "credentials", "provider"],
        "badges": ["Credentials", "Cloud"],
        "bestFor": ["Hosted providers", "Cloud render routing", "Commercial image models"],
        "strengths": ["Encrypted local storage", "Shared by setup-aware surfaces"],
        "weaknesses": ["No provider access until verified"],
        "lifecycleActions": {"install": False, "repair": True, "calibrate": False, "certify": False},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
    "ace_step_local": {
        "group": "Music",
        "subgroup": "Local Runtimes",
        "surfaceGroups": ["Music"],
        "capabilityTags": ["music", "audio", "local"],
        "badges": ["Music", "Local GPU"],
        "bestFor": ["Music beds", "Local soundtrack ideation"],
        "strengths": ["Project-local music generation", "GPU-first sandbox"],
        "weaknesses": ["Requires local sandbox install", "CPU-only runtime is blocked"],
        "lifecycleActions": {"install": False, "repair": True, "calibrate": True, "certify": True},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
    "mmaudio_local": {
        "group": "Music",
        "subgroup": "Audio Effects",
        "surfaceGroups": ["Music"],
        "capabilityTags": ["ambience", "sfx", "audio", "local"],
        "badges": ["Ambience", "SFX", "Local GPU"],
        "bestFor": ["Ambience beds", "Sound effects", "Room tone"],
        "strengths": ["Local ambience and SFX runtime", "GPU-first sandbox"],
        "weaknesses": ["Not for music generation", "CPU-only runtime is blocked"],
        "lifecycleActions": {"install": False, "repair": True, "calibrate": True, "certify": True},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
    "ltx_checkpoint": {
        "group": "Video",
        "subgroup": "Local Models",
        "surfaceGroups": ["Video"],
    },
    "wan_models": {
        "group": "Video",
        "subgroup": "Local Models",
        "surfaceGroups": ["Video"],
    },
    "pack_essential_photoreal": {
        "group": "Creative Packs",
        "subgroup": "Essential Packs",
        "surfaceGroups": ["Creative Packs"],
        "capabilityTags": ["pack", "photoreal", "creative"],
        "badges": ["Creative Pack", "Photoreal"],
        "bestFor": ["Photoreal faces", "Lighting presets"],
        "lifecycleActions": {"install": True, "repair": True, "calibrate": False, "certify": False},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
    "pack_essential_anime": {
        "group": "Creative Packs",
        "subgroup": "Essential Packs",
        "surfaceGroups": ["Creative Packs"],
        "capabilityTags": ["pack", "anime", "creative"],
        "badges": ["Creative Pack", "Anime"],
        "bestFor": ["Anime expressions", "Stylized reference packs"],
        "lifecycleActions": {"install": True, "repair": True, "calibrate": False, "certify": False},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
    "pack_essential_cinematic": {
        "group": "Creative Packs",
        "subgroup": "Essential Packs",
        "surfaceGroups": ["Creative Packs"],
        "capabilityTags": ["pack", "cinematic", "creative"],
        "badges": ["Creative Pack", "Cinematic"],
        "bestFor": ["Lighting looks", "Cinematic scene setups"],
        "lifecycleActions": {"install": True, "repair": True, "calibrate": False, "certify": False},
        "surfaceEntryPoints": {"dock": True, "coDirector": True},
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cert_dir() -> Path:
    return Path(settings.data_dir) / "setup" / "lifecycle"


def _cert_path() -> Path:
    return _cert_dir() / "certifications.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def component_metadata(component_id: str) -> dict[str, Any]:
    if component_id in _LOCAL_IMAGE_COMPONENTS:
        meta = dict(_LOCAL_IMAGE_COMPONENTS[component_id])
        if meta.get("group") == "Image Generation":
            meta["group"] = "Image"
        meta.setdefault("surfaceGroups", [meta.get("group") or "Image"])
        return meta
    component = get_component(component_id)
    override = dict(_COMPONENT_METADATA_OVERRIDES.get(component_id) or {})
    group = "Utilities"
    subgroup = "Developer Tools"
    if component.category in {"Still Image Models", "Image Generation"}:
        group = "Image"
        subgroup = "Local Models"
    elif component.category in {"Video Models"}:
        group = "Video"
        subgroup = "Local Models"
    elif component.category in {"Character Voice Models"}:
        group = "Voice"
        subgroup = "Local Models"
    elif component.category in {"Music Runtimes"}:
        group = "Music"
        subgroup = "Local Runtimes"
    elif component.category in {"Avatar Runtimes"}:
        group = "Avatar"
        subgroup = "Local Models"
    elif component.category in {"ComfyUI Extensions"}:
        group = "ComfyUI Extensions"
        subgroup = "Extensions"
    elif component.category in {"API Providers"}:
        group = "API Providers"
        subgroup = "Credentials"
    elif component.category in {"Creative Packs"}:
        group = "Creative Packs"
        subgroup = "Essential Packs"
    elif component.category in {"Core"}:
        group = "Utilities"
        subgroup = "Developer Tools"
    surface_groups = override.pop("surfaceGroups", None)
    if not surface_groups:
        surface_groups = [group]
        if component.category in {"Avatar Runtimes"} and "Motion" not in surface_groups:
            surface_groups.append("Motion")
    payload = {
        "group": group,
        "subgroup": subgroup,
        "surfaceGroups": surface_groups,
        "parameterCount": None,
        "downloadSizeLabel": f"{round((component.download_bytes or 0) / (1024**3), 1)} GB" if component.download_bytes else None,
        "diskUsageLabel": f"{round((component.installed_bytes or 0) / (1024**3), 1)} GB" if component.installed_bytes else None,
        "vramRecommendationGb": None,
        "typicalGenerationSpeed": None,
        "supportedResolutions": [],
        "strengths": [],
        "weaknesses": [],
        "bestFor": [],
        "badges": [],
        "experimental": False,
        "capabilityTags": [],
        "lifecycleActions": {"install": True, "repair": True, "calibrate": True, "certify": True},
        "surfaceEntryPoints": {"dock": False, "coDirector": False},
    }
    payload.update(override)
    if payload.get("group") == "Image Generation":
        payload["group"] = "Image"
    if payload.get("group") == "Video Generation":
        payload["group"] = "Video"
    if not payload.get("surfaceGroups"):
        payload["surfaceGroups"] = [payload.get("group") or "Utilities"]
    return payload


_RECIPES_CACHE: list[CertifiedRecipe] | None = None


def list_certified_recipes() -> list[CertifiedRecipe]:
    global _RECIPES_CACHE
    if _RECIPES_CACHE is not None:
        return list(_RECIPES_CACHE)
    recipes: list[CertifiedRecipe] = []
    for path in sorted(_RECIPES_DIR.glob("*.json")):
        payload = _read_json(path, None)
        if isinstance(payload, dict):
            try:
                recipes.append(CertifiedRecipe.model_validate(payload))
            except Exception:
                continue
    _RECIPES_CACHE = recipes
    return list(recipes)


def get_recipe(recipe_id: str) -> CertifiedRecipe | None:
    for recipe in list_certified_recipes():
        if recipe.recipeId == recipe_id:
            return recipe
    return None


def recipe_for_component(component_id: str) -> CertifiedRecipe | None:
    matches = [item for item in list_certified_recipes() if item.componentId == component_id]
    if not matches:
        return None
    matches.sort(key=lambda item: (item.certifiedDate, item.certifiedVersion), reverse=True)
    return matches[0]


def _load_certifications() -> dict[str, ProviderCertificationRecord]:
    payload = _read_json(_cert_path(), {})
    out: dict[str, ProviderCertificationRecord] = {}
    if isinstance(payload, dict):
        for component_id, item in payload.items():
            if not isinstance(item, dict):
                continue
            try:
                out[component_id] = ProviderCertificationRecord.model_validate(item)
            except Exception:
                continue
    return out


def _save_certifications(records: dict[str, ProviderCertificationRecord]) -> None:
    _write_json(_cert_path(), {key: value.model_dump(mode="json") for key, value in records.items()})


def get_certification(component_id: str) -> ProviderCertificationRecord | None:
    return _load_certifications().get(component_id)


def inspect_hardware() -> dict[str, Any]:
    gpu = query_gpu_stats()
    free_bytes = None
    try:
        free_bytes = os.statvfs(str(settings.data_dir)).f_bavail * os.statvfs(str(settings.data_dir)).f_frsize
    except Exception:
        free_bytes = None
    return {
        "gpu": gpu,
        "dataDir": str(settings.data_dir),
        "freeBytes": free_bytes,
    }


def inspect_dependencies(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    return {
        "componentId": component_id,
        "dependencies": list(component.dependencies),
        "required": component.required,
    }


def inspect_license(component_id: str) -> dict[str, Any]:
    meta = component_metadata(component_id)
    component = get_component(component_id)
    return {
        "componentId": component_id,
        "license": meta.get("license") or component.description,
        "sourceRepo": meta.get("sourceRepo"),
    }


def inspect_source(component_id: str) -> dict[str, Any]:
    from ...source_manager.persistence import get_assignment, get_source

    assignment = get_assignment(component_id)
    source = get_source(str((assignment or {}).get("sourceId") or "")) if assignment else None
    recipe = recipe_for_component(component_id)
    return {
        "componentId": component_id,
        "assigned": assignment,
        "source": source,
        "recipeSource": recipe.source if recipe else None,
    }


def _component_status_label(verification_summary: str, healthy: bool, job: dict[str, Any] | None, archived: bool, update_available: bool) -> tuple[str, str | None, str | None]:
    if archived:
        return "Archived", "archived", None
    if update_available:
        return "Update Available", "update_available", "update"
    if healthy:
        return "Ready", None, "monitor"
    if job and job.get("state") in {"failed", "repair_required"}:
        return "Repair Required", "repair_required", "install"
    lower = verification_summary.lower()
    if "not ready" in lower or "missing" in lower or "not installed" in lower:
        return "Not Installed", None, "discover"
    return "Repair Recommended", "repair_recommended", "repair"


def _monitor_findings(component_id: str, summary: str, healthy: bool, job: dict[str, Any] | None) -> list[MonitorFinding]:
    findings: list[MonitorFinding] = []
    if job and job.get("stallStatus") and job.get("stallStatus") != "none":
        findings.append(
            MonitorFinding(
                code=str(job.get("stallStatus")),
                severity="warning",
                message=str(job.get("stallLabel") or "Install job may need attention."),
                recommendedAction="repair",
            )
        )
    if not healthy:
        findings.append(
            MonitorFinding(
                code="verification_unhealthy",
                severity="warning",
                message=summary,
                recommendedAction="repair",
            )
        )
    return findings


def calibration_defaults_for(component_id: str) -> CalibrationProfile:
    meta = component_metadata(component_id)
    gpu = query_gpu_stats()
    machine = {
        "gpu": gpu.get("gpus", []),
        "dataDir": str(settings.data_dir),
    }
    defaults = recipe_for_component(component_id)
    calibration = dict((defaults.calibrationDefaults if defaults else {}) or {})
    return CalibrationProfile(
        preferredPrecision=str(calibration.get("preferredPrecision") or ("bf16" if meta.get("vramRecommendationGb", 0) and meta.get("vramRecommendationGb", 0) >= 16 else "fp16")),
        nativeResolution=str(calibration.get("nativeResolution") or (meta.get("supportedResolutions") or ["1024x1024"])[0]),
        vramUsageGb=float(calibration.get("vramUsageGb") or meta.get("vramRecommendationGb") or 0) or None,
        safeBatchSize=int(calibration.get("safeBatchSize") or 1),
        maxRecommendedResolution=str(calibration.get("maxRecommendedResolution") or (meta.get("supportedResolutions") or ["1024x1024"])[-1]),
        avgGenerationSeconds=float(calibration.get("avgGenerationSeconds") or 12.0),
        recommendedScheduler=str(calibration.get("recommendedScheduler") or "flow_match_euler"),
        defaultCfg=float(calibration.get("defaultCfg") or 3.5),
        optimalStepCount=int(calibration.get("optimalStepCount") or 28),
        machineProfile=machine,
    )


def lifecycle_state(
    component_id: str,
    verification: Any | None = None,
    job: dict[str, Any] | None = None,
) -> ProviderLifecycleState:
    from ..diagnostics import Verification

    component = get_component(component_id)
    if not isinstance(verification, Verification):
        verification = verify_component(component_id)
    if job is None:
        try:
            jobs = jobs_for_component(component_id)
            job = jobs[-1] if jobs else None
        except Exception:
            job = None
    recipe = recipe_for_component(component_id)
    record = get_certification(component_id)
    update_available = bool(recipe and record and record.certifiedVersion and recipe.certifiedVersion != record.certifiedVersion)
    archived = bool(record and record.status == "archived")
    label, attention, chain = _component_status_label(
        verification.summary,
        verification.healthy,
        job,
        archived,
        update_available,
    )
    findings = _monitor_findings(component_id, verification.summary, verification.healthy, job)
    if record and record.monitorFindings:
        findings.extend(record.monitorFindings)
    recommendations = []
    if label == "Update Available":
        recommendations.append("Use the latest certified recipe from Adept registry.")
    if label in {"Repair Recommended", "Repair Required"}:
        recommendations.append("Repair from the trusted Source Manager flow.")
    if recipe and chain is None and not verification.healthy:
        chain = "discover"
    if record and record.certified and verification.healthy and label == "Ready":
        chain = "ready"
    return ProviderLifecycleState(
        componentId=component_id,
        componentName=component.name,
        chainState=chain,
        attentionState=attention,
        statusLabel=label,
        certified=bool(record and record.certified),
        certifiedRecipeId=record.recipeId if record else recipe.recipeId if recipe else None,
        certifiedVersion=(record.certifiedVersion if record else None) or (recipe.certifiedVersion if recipe else None),
        certifiedDate=(record.certifiedDate if record else None) or (recipe.certifiedDate if recipe else None),
        installJobId=job.get("id") if job else None,
        installState=job.get("state") if job else None,
        verificationHealthy=verification.healthy,
        verificationSummary=verification.summary,
        monitorFindings=findings,
        calibration=(record.calibration if record else None),
        recommendations=recommendations,
    )


def build_install_plan(component_id: str, *, action: str = "install", destination_root: str | None = None) -> InstallPlan:
    component = get_component(component_id)
    recipe = recipe_for_component(component_id)
    verification = verify_component(component_id)
    requires_download_confirmation = bool(component.download_bytes and component.download_bytes >= 10 * 1024 * 1024 * 1024)
    return InstallPlan(
        componentId=component_id,
        componentName=component.name,
        action=action if action in {"install", "update", "repair", "link_existing"} else "install",
        requiresRuntimeConfirmation=True,
        requiresModelDownloadConfirmation=requires_download_confirmation,
        destinationRoot=destination_root,
        estimatedDownloadBytes=component.download_bytes or None,
        estimatedInstalledBytes=component.installed_bytes or None,
        currentVersion=verification.version,
        targetVersion=recipe.certifiedVersion if recipe else verification.version,
        certifiedRecipeId=recipe.recipeId if recipe else None,
        recommendedSource=(recipe.source if recipe else {}),
        steps=[
            "Verify hardware and disk",
            "Verify certified source",
            "Approve runtime install",
            "Approve model download",
            "Run trusted install job",
            "Calibrate runtime",
            "Record certification",
        ],
        warnings=recipe.notes if recipe else [],
        notes=[
            "Co-Director proposes this plan.",
            "Source Manager performs the install.",
        ],
    )


def build_update_plan(component_id: str) -> UpdatePlan:
    plan = build_install_plan(component_id, action="update")
    return UpdatePlan(**plan.model_dump(), updateReason="A newer Adept-certified recipe is available.")


def search_components(query: str = "", *, group: str | None = None) -> dict[str, Any]:
    q = query.strip().lower()
    items = []
    for component in COMPONENTS:
        meta = component_metadata(component.id)
        if group and meta.get("group") != group:
            continue
        haystack = " ".join(
            [
                component.id,
                component.name,
                component.description,
                " ".join(meta.get("capabilityTags") or []),
                " ".join(meta.get("badges") or []),
                " ".join(meta.get("bestFor") or []),
            ]
        ).lower()
        if q and q not in haystack:
            continue
        state = lifecycle_state(component.id)
        items.append(
            {
                "componentId": component.id,
                "name": component.name,
                "statusLabel": state.statusLabel,
                "group": meta.get("group"),
                "subgroup": meta.get("subgroup"),
                "capabilityTags": meta.get("capabilityTags") or [],
                "reason": recommendation_reason(component.id, query),
            }
        )
    return {"count": len(items), "items": items}


def recommendation_reason(component_id: str, intent: str) -> str:
    text = intent.lower()
    if component_id == "flux1_kontext_dev_local" and any(word in text for word in ("photoreal", "character", "reference")):
        return "Best fit for photoreal character work and reference-following edits."
    if component_id in {"sana_15_local", "qwen_image_2512_models", "zimage_models"} and "anime" in text:
        return "Best fit for anime or stylized illustration intent."
    if component_id == "flux1_schnell_local" and any(word in text for word in ("fast", "preview", "quick")):
        return "Best fit for quick preview passes."
    return "Matches the requested capability tags and certified setup posture."


def inspect_component(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    meta = component_metadata(component_id)
    lifecycle = lifecycle_state(component_id)
    recipe = recipe_for_component(component_id)
    return {
        "component": {
            "id": component.id,
            "name": component.name,
            "description": component.description,
            "required": component.required,
            "category": component.category,
            "dependencies": list(component.dependencies),
            "installer": component.installer,
            "verifier": component.verifier,
        },
        "lifecycle": lifecycle.model_dump(mode="json"),
        "metadata": {
            **meta,
            "certifiedRecipeId": recipe.recipeId if recipe else None,
            "certifiedVersion": (lifecycle.certifiedVersion or (recipe.certifiedVersion if recipe else None)),
            "certifiedDate": (lifecycle.certifiedDate or (recipe.certifiedDate if recipe else None)),
        },
        "installPlan": build_install_plan(component_id).model_dump(mode="json"),
        "source": inspect_source(component_id),
    }


def compare_components(component_ids: list[str]) -> dict[str, Any]:
    rows = []
    for component_id in component_ids:
        payload = inspect_component(component_id)
        rows.append(
            {
                "componentId": component_id,
                "name": payload["component"]["name"],
                "statusLabel": payload["lifecycle"]["statusLabel"],
                "vramRecommendationGb": payload["metadata"].get("vramRecommendationGb"),
                "typicalGenerationSpeed": payload["metadata"].get("typicalGenerationSpeed"),
                "bestFor": payload["metadata"].get("bestFor"),
                "badges": payload["metadata"].get("badges"),
            }
        )
    return {"count": len(rows), "items": rows}


def list_repair_options(component_id: str) -> dict[str, Any]:
    lifecycle = lifecycle_state(component_id)
    job = get_job(lifecycle.installJobId) if lifecycle.installJobId else None
    return {
        "componentId": component_id,
        "statusLabel": lifecycle.statusLabel,
        "recoveryActions": list((job or {}).get("recoveryActions") or []),
        "monitorFindings": [item.model_dump(mode="json") for item in lifecycle.monitorFindings],
    }


def diagnose_failure(component_id: str) -> dict[str, Any]:
    lifecycle = lifecycle_state(component_id)
    job = get_job(lifecycle.installJobId) if lifecycle.installJobId else None
    return {
        "componentId": component_id,
        "statusLabel": lifecycle.statusLabel,
        "verificationSummary": lifecycle.verificationSummary,
        "installJob": job,
        "monitorFindings": [item.model_dump(mode="json") for item in lifecycle.monitorFindings],
    }


def approve_source(component_id: str, url: str, *, revision: str | None = None) -> dict[str, Any]:
    verification = verify_and_select(url, component_id=component_id, revision=revision)
    legacy = dict(verification.get("legacy") or {})
    if not legacy.get("ok"):
        raise ValueError(legacy.get("message") or "Source verification failed.")
    saved = save_verified_source_for_component(component_id, legacy)
    return {
        "componentId": component_id,
        "verification": verification,
        "saved": saved,
    }


def create_install_job(component_id: str, *, confirm: bool, confirm_download_models: bool, destination_root: str | None = None) -> dict[str, Any]:
    return create_or_resume_install(
        component_id,
        confirm=confirm,
        confirm_download_models=confirm_download_models,
        install_path=destination_root,
    )


def install_component(component_id: str, *, confirm: bool, confirm_download_models: bool, destination_root: str | None = None) -> dict[str, Any]:
    return create_install_job(
        component_id,
        confirm=confirm,
        confirm_download_models=confirm_download_models,
        destination_root=destination_root,
    )


def install_recipe(recipe_id: str, *, confirm: bool, confirm_download_models: bool) -> dict[str, Any]:
    recipe = get_recipe(recipe_id)
    if recipe is None:
        raise KeyError(recipe_id)
    return install_component(
        recipe.componentId,
        confirm=confirm,
        confirm_download_models=confirm_download_models,
    )


def restart_runtime(component_id: str) -> dict[str, Any]:
    lifecycle = lifecycle_state(component_id)
    if lifecycle.installJobId:
        return repair_install_job(lifecycle.installJobId, "restart_comfyui")
    raise ValueError("No active lifecycle install job is available for restart.")


def verify_component_action(component_id: str) -> dict[str, Any]:
    lifecycle = lifecycle_state(component_id)
    if lifecycle.installJobId:
        return repair_install_job(lifecycle.installJobId, "reverify")
    verification = verify_component(component_id)
    return {
        "componentId": component_id,
        "healthy": verification.healthy,
        "summary": verification.summary,
        "issueCode": verification.issue_code,
    }


def calibrate_component(component_id: str) -> ProviderCertificationRecord:
    records = _load_certifications()
    component = get_component(component_id)
    verification = verify_component(component_id)
    existing = records.get(component_id)
    recipe = recipe_for_component(component_id)
    profile = calibration_defaults_for(component_id)
    record = ProviderCertificationRecord(
        componentId=component_id,
        componentName=component.name,
        status="ready" if verification.healthy else "repair_recommended",
        certified=bool(existing and existing.certified and verification.healthy),
        certifiedVersion=(existing.certifiedVersion if existing else None) or (recipe.certifiedVersion if recipe else verification.version),
        certifiedDate=(existing.certifiedDate if existing else None) or (recipe.certifiedDate if recipe else None),
        recipeId=(existing.recipeId if existing else None) or (recipe.recipeId if recipe else None),
        installJobId=lifecycle_state(component_id).installJobId,
        verificationSummary=verification.summary,
        calibration=profile,
        monitorFindings=_monitor_findings(component_id, verification.summary, verification.healthy, jobs_for_component(component_id)[-1] if jobs_for_component(component_id) else None),
        metadata={"autoCalibrated": True},
        createdAt=existing.createdAt if existing else _now(),
        updatedAt=_now(),
    )
    records[component_id] = record
    _save_certifications(records)
    return record


def certify_component(component_id: str) -> ProviderCertificationRecord:
    verification = verify_component(component_id)
    if not verification.healthy:
        raise ValueError("Component must verify successfully before certification.")
    record = calibrate_component(component_id)
    updated = record.model_copy(
        update={
            "certified": True,
            "status": "ready",
            "certifiedDate": _now(),
            "monitorFindings": [],
            "updatedAt": _now(),
        }
    )
    records = _load_certifications()
    records[component_id] = updated
    _save_certifications(records)
    return updated


def check_updates(component_id: str) -> dict[str, Any]:
    recipe = recipe_for_component(component_id)
    record = get_certification(component_id)
    available = bool(recipe and record and recipe.certifiedVersion != record.certifiedVersion)
    return {
        "componentId": component_id,
        "updateAvailable": available,
        "currentCertifiedVersion": record.certifiedVersion if record else None,
        "latestCertifiedVersion": recipe.certifiedVersion if recipe else None,
        "reason": "Latest Certified recipe from Adept registry." if available else "Already on latest certified recipe.",
    }


def archive_component(component_id: str) -> ProviderCertificationRecord:
    records = _load_certifications()
    existing = records.get(component_id) or calibrate_component(component_id)
    updated = existing.model_copy(update={"status": "archived", "updatedAt": _now()})
    records[component_id] = updated
    _save_certifications(records)
    return updated


def remove_component(component_id: str) -> dict[str, Any]:
    return {
        "componentId": component_id,
        "status": "proposal_only",
        "message": "Removal must remain a reviewed Source Manager action. Installed files are not deleted automatically here.",
    }


def move_installation(component_id: str, destination_root: str) -> dict[str, Any]:
    return {
        "componentId": component_id,
        "destinationRoot": destination_root,
        "status": "proposal_only",
        "message": "Move installation remains review-gated. Use a trusted Source Manager flow before relocating files.",
    }


def get_monitor_status() -> dict[str, Any]:
    items = []
    for component_id in _load_certifications():
        lifecycle = lifecycle_state(component_id)
        if lifecycle.monitorFindings:
            items.append(
                {
                    "componentId": component_id,
                    "statusLabel": lifecycle.statusLabel,
                    "findings": [item.model_dump(mode="json") for item in lifecycle.monitorFindings],
                }
            )
    return {"count": len(items), "items": items}


def list_cloud_providers() -> dict[str, Any]:
    providers = []
    for provider in list_image_providers():
        if provider.get("kind") != "cloud":
            continue
        provider_id = str(provider.get("providerId") or "")
        secret_name = _IMAGE_PROVIDER_KEYS.get(provider_id)
        status = secret_status(secret_name) if secret_name else {"configured": False, "state": "missing"}
        providers.append(
            {
                "providerId": provider_id,
                "displayName": provider.get("displayName"),
                "statusLabel": "Ready" if status.get("state") == "verified" else "Requires Setup",
                "configured": bool(status.get("configured")),
                "state": status.get("state"),
                "operations": list(provider.get("operations") or []),
                "modelFamilies": list(provider.get("supportedModelFamilies") or []),
                "group": "API Providers",
                "subgroup": "Image Providers",
            }
        )
    return {"count": len(providers), "items": providers}

