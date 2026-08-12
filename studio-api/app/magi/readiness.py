"""MAGI Editor surface readiness — Production Ready vs honest Draft/Deferred/Blocked."""

from __future__ import annotations

from typing import Any


def production_surfaces() -> list[dict[str, Any]]:
    """Wave 4B Production Ready product surfaces (image path only)."""
    return [
        {"id": "magi_shell", "name": "MAGI Editor application shell", "status": "Certified"},
        {"id": "korri_branding", "name": "Korri branding (presentation only)", "status": "Certified"},
        {"id": "media_browser", "name": "Media Browser", "status": "Certified"},
        {"id": "asset_browser", "name": "Asset Browser", "status": "Certified"},
        {"id": "inspector", "name": "Inspector", "status": "Certified"},
        {"id": "viewer", "name": "Viewer", "status": "Certified"},
        {"id": "image_canvas", "name": "Image Canvas", "status": "Certified"},
        {"id": "magi_command", "name": "MAGI Command", "status": "Certified"},
        {"id": "magi_actions", "name": "MAGI Actions", "status": "Certified"},
        {"id": "magi_recipes", "name": "MAGI Recipes", "status": "Certified"},
        {"id": "compare_viewer", "name": "Compare Viewer", "status": "Certified"},
        {"id": "version_browser", "name": "Version Browser", "status": "Certified"},
        {"id": "edit_history", "name": "Edit History", "status": "Certified"},
        {"id": "workspace_layout", "name": "Workspace Layout", "status": "Certified"},
        {
            "id": "certified_image_edit_path",
            "name": "Certified Wave 4 image-edit pipeline",
            "status": "Certified",
            "path": (
                "CreativeContext → ImageEditIntent → Unified Resolver → pinned Runtime "
                "→ QueueWorker → Output Gate → Provenance → Version Graph"
            ),
        },
    ]


def deferred_surfaces() -> list[dict[str, Any]]:
    """Visible multimodal/timeline surfaces that must not fake-execute."""
    return [
        {
            "id": "timeline",
            "name": "Timeline",
            "status": "Draft",
            "executable": False,
            "reason": "AI-native multimodal timeline not dual-stage certified for MAGI production.",
        },
        {
            "id": "video_tracks",
            "name": "Video tracks",
            "status": "Draft",
            "executable": False,
            "reason": "Video track editing in MAGI is foundation UI only.",
        },
        {
            "id": "audio_tracks",
            "name": "Audio tracks",
            "status": "Deferred",
            "executable": False,
            "reason": "Audio track mix/edit deferred pending certified audio edit workflows.",
        },
        {
            "id": "ai_timeline_actions",
            "name": "AI Timeline Actions",
            "status": "Blocked",
            "executable": False,
            "reason": "No certified MAGI timeline action workflows.",
        },
        {
            "id": "smart_reframe",
            "name": "Smart Reframe",
            "status": "Deferred",
            "executable": False,
            "reason": "Smart reframe requires certified video spatial workflows.",
        },
        {
            "id": "video_inpainting",
            "name": "Video Inpainting",
            "status": "Blocked",
            "executable": False,
            "reason": "Video inpaint not in certified production path.",
        },
        {
            "id": "video_outpainting",
            "name": "Video Outpainting",
            "status": "Blocked",
            "executable": False,
            "reason": "Video outpaint not in certified production path.",
        },
        {
            "id": "ai_transitions",
            "name": "AI Transitions",
            "status": "Deferred",
            "executable": False,
            "reason": "AI transitions deferred until certified transition workflows exist.",
        },
        {
            "id": "audio_cleanup",
            "name": "Audio Cleanup",
            "status": "Deferred",
            "executable": False,
            "reason": "Audio cleanup not certified for MAGI production execute.",
        },
        {
            "id": "dialogue_cleanup",
            "name": "Dialogue Cleanup",
            "status": "Deferred",
            "executable": False,
            "reason": "Dialogue cleanup not certified for MAGI production execute.",
        },
        {
            "id": "multimodal_recipes",
            "name": "Multimodal Recipes",
            "status": "Draft",
            "executable": False,
            "reason": "Only image editing recipes are Production Ready in Wave 4B.",
        },
    ]


def korri_policy() -> dict[str, Any]:
    return {
        "role": "presentation-only",
        "allowed": [
            "splash",
            "hero_banner",
            "onboarding",
            "empty_workspace",
            "tutorials",
            "marketing",
            "optional_tips",
        ],
        "forbidden": [
            "workflow_routing",
            "QueueWorker",
            "UnifiedResolver",
            "OutputGate",
            "certification",
            "runtime_orchestration",
            "ProductionBible_enforcement",
            "scheduling",
            "project_decisions",
        ],
        "notCoDirector": True,
        "notRuntimeAgent": True,
    }


def magi_actions_catalog() -> list[dict[str, Any]]:
    """Image MAGI Actions — execute only via ImageEditIntent / certified keys."""
    return [
        {"id": "inpaint", "label": "Inpaint", "operation": "image.inpaint", "status": "Certified"},
        {
            "id": "object_remove",
            "label": "Remove Object",
            "operation": "image.object_remove",
            "status": "Certified",
        },
        {
            "id": "object_replace",
            "label": "Replace Object",
            "operation": "image.object_replace",
            "status": "Certified",
        },
        {"id": "outpaint", "label": "Outpaint", "operation": "image.outpaint", "status": "Certified"},
        {"id": "upscale", "label": "Upscale", "operation": "image.upscale", "status": "Certified"},
        {
            "id": "reference_edit",
            "label": "Reference Edit",
            "operation": "image.reference_edit",
            "status": "Certified",
        },
        {
            "id": "face_restore",
            "label": "Repair Face",
            "operation": "image.face_restore",
            "status": "Certified",
        },
        {"id": "relight", "label": "Relight", "operation": "image.relight", "status": "Certified"},
        {
            "id": "bg_remove",
            "label": "Remove Background",
            "operation": "image.background_remove",
            "status": "Certified",
        },
        {
            "id": "smart_reframe",
            "label": "Smart Reframe",
            "operation": None,
            "status": "Deferred",
            "executable": False,
        },
        {
            "id": "video_inpaint",
            "label": "Video Inpaint",
            "operation": None,
            "status": "Blocked",
            "executable": False,
        },
        {
            "id": "ai_transition",
            "label": "AI Transition",
            "operation": None,
            "status": "Deferred",
            "executable": False,
        },
        {
            "id": "audio_cleanup",
            "label": "Audio Cleanup",
            "operation": None,
            "status": "Deferred",
            "executable": False,
        },
    ]


def readiness_payload() -> dict[str, Any]:
    deferred = deferred_surfaces()
    return {
        "phase": "M42-W4B",
        "productName": "Adept UI MAGI Editor",
        "tagline": "Cut. Change. Create. All Types. All Takes.",
        "productionSurfaces": production_surfaces(),
        "deferredSurfaces": deferred,
        "magiActions": magi_actions_catalog(),
        "korri": korri_policy(),
        "honestNonExecutableCount": sum(1 for s in deferred if not s.get("executable", False)),
        "noFakeExecution": True,
    }
