"""Component kinds and primary-action mapping for Setup Wizard cards."""

from __future__ import annotations

from typing import Any

from .catalog import ComponentDefinition

KIND_DOWNLOADABLE_PACK = "downloadable_pack"
KIND_DOWNLOADABLE_MODEL = "downloadable_model"
KIND_DOWNLOADABLE_EXTENSION = "downloadable_extension"
KIND_CREDENTIAL = "credential"
KIND_LOCAL_SERVICE = "local_service"
KIND_EXTERNAL_SERVICE = "external_service"
KIND_CONFIGURATION = "configuration"
KIND_LINKED_RESOURCE = "linked_resource"
KIND_DETECT_ONLY = "detect_only"

# Canonical source / distribution states for downloadable components
SOURCE_READY_TO_DOWNLOAD = "ready_to_download"
SOURCE_NOT_PUBLISHED = "source_not_published"
SOURCE_NOT_CONFIGURED = "source_not_configured"
SOURCE_AUTHENTICATION_REQUIRED = "authentication_required"
SOURCE_UNREACHABLE = "source_unreachable"
SOURCE_RELEASE_NOT_FOUND = "release_not_found"
SOURCE_MATCHING_ASSET_NOT_FOUND = "matching_asset_not_found"
SOURCE_VERIFICATION_FAILED = "verification_failed"
SOURCE_INSTALLABLE_FROM_MANUAL = "installable_from_manual_source"
SOURCE_INSTALLED = "installed"
SOURCE_LINKED = "linked"
SOURCE_FAILED = "failed"


def component_kind(definition: ComponentDefinition) -> str:
    if definition.installer == "credentials" or definition.verifier in ("fal_key", "kie_key", "wavespeed_key"):
        return KIND_CREDENTIAL
    if definition.installer == "asset_pack" or definition.verifier == "asset_pack":
        return KIND_DOWNLOADABLE_PACK
    if definition.installer in (
        "m210b_qwen_voice",
        "huggingface_snapshot",
        "index_tts2",
        "avatar_runtime",
        "realesrgan_ncnn",
    ):
        return KIND_DOWNLOADABLE_MODEL
    if definition.installer == "path_link":
        return KIND_LINKED_RESOURCE
    if definition.verifier in ("comfy_service",):
        return KIND_LOCAL_SERVICE
    if definition.verifier in ("ollama_service",):
        return KIND_LOCAL_SERVICE
    if definition.installer == "detect_only":
        return KIND_DETECT_ONLY
    if definition.installer == "manual":
        return KIND_CONFIGURATION
    return KIND_CONFIGURATION


def primary_action_for_kind(
    kind: str,
    *,
    status: str,
    source_state: str | None = None,
    diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return primary_action dict for a component kind (never Download and Install for credentials)."""
    if status in ("ready", "checking", "installing"):
        return None

    if kind == KIND_CREDENTIAL:
        if status == "ready":
            return None
        return {"action": "configure", "label": "Configure API Key", "disabled": False}

    if kind in (KIND_DOWNLOADABLE_PACK, KIND_DOWNLOADABLE_MODEL):
        if source_state in (SOURCE_NOT_PUBLISHED, SOURCE_NOT_CONFIGURED):
            return {"action": "add_source_url", "label": "Add Source URL", "disabled": False}
        if source_state == SOURCE_RELEASE_NOT_FOUND:
            return {"action": "refresh_source", "label": "Check Again", "disabled": False}
        if source_state == SOURCE_MATCHING_ASSET_NOT_FOUND:
            return {"action": "refresh_source", "label": "Check Again", "disabled": False}
        if source_state in (SOURCE_READY_TO_DOWNLOAD, SOURCE_INSTALLABLE_FROM_MANUAL):
            return {"action": "install", "label": "Download and Install", "disabled": False}
        if status == "not_installed":
            return {"action": "install", "label": "Download and Install", "disabled": False}

    if diagnostic and diagnostic.get("recommendation") not in (None, "none"):
        recommendation = str(diagnostic["recommendation"])
        labels = {
            "install": "Download and Install",
            "configure": "Configure API Key" if kind == KIND_CREDENTIAL else "Configure",
            "repair": "Repair Installation",
            "reinstall": "Reinstall",
            "update": "Update Now",
            "correct_path": "Locate Existing Files",
            "grant_permission": "Grant Permission",
            "manual_help": "View Details",
            "link_existing": "Link Existing Folder",
            "choose_install_location": "Choose Install Location",
            "refresh_source": "Check Again",
            "add_source_url": "Add Source URL",
        }
        return {
            "action": recommendation if recommendation != "configure" or kind == KIND_CREDENTIAL else "configure",
            "label": labels.get(recommendation, "Run Diagnostics"),
            "disabled": False,
        }
    return {"action": "diagnostics", "label": "Run Diagnostics", "disabled": False}
