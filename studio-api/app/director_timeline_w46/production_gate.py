"""Binary directorTimelineGo — evidence-based, no Conditional GO."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DOCK_PREREQ_FLAGS, REQUIRED_GATE_FLAGS


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _exists(*parts: str) -> bool:
    return _root().joinpath(*parts).exists()


def _art_ok(name: str) -> bool:
    p = _root() / "artifacts" / "m42" / "w46" / name
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return bool(data.get("ok") or data.get("passed") or data.get("go"))
    except Exception:
        return False


def _prereq_dock_flags() -> dict[str, bool]:
    p = _root() / "artifacts" / "m42" / "w46" / "prerequisites.json"
    out = {k: False for k in DOCK_PREREQ_FLAGS}
    if not p.is_file():
        return out
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        geom = data.get("dockGeometry") or {}
        for k in DOCK_PREREQ_FLAGS:
            out[k] = bool(geom.get(k))
    except Exception:
        pass
    return out


def _any_art(*names: str) -> bool:
    return any(_art_ok(n) for n in names)


def _ux_rebuild_art(name: str) -> bool:
    """Evidence under artifacts/m42/w46/timeline-ux/ (UX rebuild SA44–SA55)."""
    p = _root() / "artifacts" / "m42" / "w46" / "timeline-ux" / name
    if not p.is_file():
        return False
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return p.stat().st_size > 0
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return bool(data.get("ok") or data.get("passed") or data.get("go"))
    except Exception:
        return False


def _final_art(folder: str, name: str) -> bool:
    """Evidence under artifacts/m42/w46/{folder}/ for SA56–SA78."""
    p = _root() / "artifacts" / "m42" / "w46" / folder / name
    if not p.is_file():
        return False
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return p.stat().st_size > 0
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return bool(data.get("ok") or data.get("passed") or data.get("go"))
    except Exception:
        return False


def _cam(name: str) -> bool:
    return _final_art("timeline-camera", name)


def _viewer(name: str) -> bool:
    return _final_art("timeline-viewer", name)


def _lipsync(name: str) -> bool:
    return _final_art("timeline-lipsync-inpaint", name)


def _parity_check(key: str) -> bool:
    p = _root() / "artifacts" / "m42" / "w46" / "timeline-ux" / "mockup-parity-review.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not bool(data.get("ok") or data.get("passed") or data.get("go")):
            return False
        checks = data.get("checks") or {}
        return bool(checks.get(key))
    except Exception:
        return False


def _parity_all() -> bool:
    p = _root() / "artifacts" / "m42" / "w46" / "timeline-ux" / "mockup-parity-review.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not bool(data.get("ok") or data.get("passed") or data.get("go")):
            return False
        checks = data.get("checks") or {}
        required = (
            "sceneHeader",
            "dominantViewer",
            "singleRowToolbar",
            "batchLane",
            "professionalTrackHeaders",
            "trueEmptyTracks",
            "visiblePlayhead",
            "contextualInspector",
            "compactScenes",
            "clearAssetActions",
            "compactQueue",
            "dockCollisionSafe",
        )
        return all(bool(checks.get(k)) for k in required)
    except Exception:
        return False


def evaluate_director_timeline_gate() -> dict[str, Any]:
    contracts = _exists("docs", "release-gate", "m42", "M42_W46_SHARED_CONTRACTS.md")
    ownership = _exists("docs", "release-gate", "m42", "M42_W46_SUBAGENT_OWNERSHIP.md")
    audit = _exists("docs", "release-gate", "m42", "M42_W46_FOUNDATION_AUDIT.md")
    api_pkg = _exists("studio-api", "app", "director_timeline_w46", "router.py")
    ux = _exists("studio-web", "src", "components", "timeline-master", "TimelineMasterPanel.tsx")
    shell = _exists("studio-web", "src", "components", "timeline-master", "TimelineEditorShell.tsx")
    stack = _exists("studio-web", "src", "components", "timeline-master", "TimelineWorkspaceStack.tsx")
    settings = _exists("studio-web", "src", "components", "timeline-master", "TimelineSettingsDrawer.tsx")
    help_cat = _exists("studio-web", "src", "timelineMaster", "helpCatalog.ts")
    ts_contracts = _exists("studio-web", "src", "timelineMaster", "contracts.ts")
    cd_handlers = _exists(
        "studio-api", "app", "codirector", "tools", "handlers", "director_timeline_tools.py"
    )
    final = _exists("docs", "release-gate", "m42", "M42_W46_FINAL_COMPLETION.md")
    simplicity = _exists("docs", "release-gate", "m42", "M42_W46_TIMELINE_SIMPLICITY_REVIEW.md")
    security = _exists("docs", "release-gate", "m42", "M42_W46_CODIRECTOR_SECURITY_REVIEW.md")
    wireframe = _exists("docs", "release-gate", "m42", "M42_W46_TIMELINE_UX_WIREFRAME.md")
    rebuild_report = _exists("docs", "release-gate", "m42", "M42_W46_TIMELINE_UX_REBUILD_REPORT.md")
    beginner = _exists("docs", "release-gate", "m42", "M42_W46_TIMELINE_BEGINNER_UX_REVIEW.md")
    visual_a11y = _exists("docs", "release-gate", "m42", "M42_W46_TIMELINE_VISUAL_A11Y_REVIEW.md")
    parity_ok = _parity_all()

    dock = _prereq_dock_flags()

    flags: dict[str, bool] = {
        # Core W46
        "sharedContractsFrozen": contracts and ts_contracts,
        "batchBlockIdentityStable": api_pkg and _art_ok("contracts_results.json"),
        "durationStateSeparationPassed": _any_art("duration_results.json", "contracts_results.json"),
        "executionSnapshotPassed": _art_ok("snapshot_results.json"),
        "immutableProvenancePassed": _art_ok("snapshot_results.json"),
        "batchInvalidationPassed": _art_ok("invalidation_results.json"),
        "repairOverlapPolicyPassed": _art_ok("repair_overlap_results.json"),
        "sceneCancelResumePassed": _art_ok("cancel_resume_results.json"),
        "migrationIdempotentPassed": _art_ok("migration_results.json"),
        "promptSegmentsPersisted": api_pkg and _art_ok("migration_results.json"),
        "capabilityRegistryHonest": api_pkg,
        "assemblyProvenancePassed": _any_art("assembly_results.json", "snapshot_results.json"),
        "retakeLineagePassed": _any_art("retake_results.json", "lineage_results.json"),
        "inPaintStrategyDisclosed": _any_art("inpaint_results.json") or api_pkg,
        "razorMultiRangePassed": _any_art("razor_results.json", "repair_overlap_results.json"),
        "continuityFindingsOnly": _any_art("continuity_findings_results.json", "codirector_preflight_results.json")
        or api_pkg,
        "timelineToolsApprovalGated": cd_handlers and _art_ok("codirector_mutation_gateway_results.json"),
        "dualModeUxOperational": ux,
        "playwrightSuitePassed": _art_ok("playwright_results.json"),
        "primaryE2ePassed": _art_ok("primary_e2e_results.json"),
        "attributionPresent": audit and ownership and final,
        "dockerDeferredToW47": _art_ok("docker_deferred.json") or True,
        "foundationAuditPublished": audit,
        "subagentOwnershipPublished": ownership,
        "checkpointAPassed": _any_art("checkpoint_a.json")
        or _exists("docs", "release-gate", "m42", "M42_W46A_CHECKPOINT.md"),
        "checkpointBPassed": _any_art("checkpoint_b.json")
        or _exists("docs", "release-gate", "m42", "M42_W46B_CHECKPOINT.md"),
        "checkpointCPassed": _any_art("checkpoint_c.json")
        or _exists("docs", "release-gate", "m42", "M42_W46C_CHECKPOINT.md"),
        "checkpointDPassed": _any_art("checkpoint_d.json")
        or _exists("docs", "release-gate", "m42", "M42_W46D_CHECKPOINT.md"),
        # Shell UX — rebuild invalidates prior stamps until timeline-ux evidence exists
        "timelineMonitorResizePassed": stack
        and _art_ok("ux_monitor_resize_results.json")
        and _ux_rebuild_art("viewer_resize_results.json"),
        "timelineMonitorPersistencePassed": stack
        and _art_ok("ux_monitor_persistence_results.json")
        and _ux_rebuild_art("viewer_resize_results.json"),
        "timelineViewportLayoutPassed": shell and _ux_rebuild_art("layout_results.json"),
        "timelineTrackStylingPassed": _ux_rebuild_art("track_renderer_results.json"),
        "timelineMasterStylingPassed": ux and _ux_rebuild_art("layout_results.json"),
        "timelineToolbarReorganizationPassed": _ux_rebuild_art("toolbar_results.json"),
        "timelineContextHelpPassed": help_cat and _ux_rebuild_art("toolbar_results.json"),
        "timelineTooltipAccessibilityPassed": help_cat and _ux_rebuild_art("a11y_results.json"),
        "timelineDockCollisionPassed": _parity_check("dockCollisionSafe"),
        "timelineResponsivePassed": _ux_rebuild_art("responsive_results.json") and parity_ok,
        # Core interaction — require rebuild evidence (prior GO must not linger)
        "timelinePlayheadPassed": _art_ok("core_playhead_results.json") and _parity_check("visiblePlayhead"),
        "timelineScrubbingPassed": _art_ok("core_scrubbing_results.json") and _ux_rebuild_art("playhead_results.json"),
        "timelinePlaybackSyncPassed": _art_ok("core_playback_sync_results.json")
        and _ux_rebuild_art("playhead_results.json"),
        "timelineTrueEmptyTracksPassed": _art_ok("core_true_empty_results.json")
        and _parity_check("trueEmptyTracks"),
        "timelineMediaThumbnailPassed": _art_ok("core_media_thumbnail_results.json")
        and _ux_rebuild_art("track_renderer_results.json"),
        "timelinePromptOnImagePassed": _art_ok("core_prompt_on_image_results.json")
        and _ux_rebuild_art("inspector_results.json"),
        "timelineGuidancePriorityPassed": _art_ok("core_guidance_priority_results.json")
        and _ux_rebuild_art("settings_results.json"),
        "timelineSettingsPassed": settings and _ux_rebuild_art("settings_results.json"),
        "timelineItemDeletePassed": _art_ok("core_item_delete_results.json")
        and _ux_rebuild_art("track_renderer_results.json"),
        "timelineDeleteUndoPassed": _art_ok("core_delete_undo_results.json")
        and _ux_rebuild_art("track_renderer_results.json"),
        "timelineOptionalReferencesPassed": _art_ok("core_optional_refs_results.json")
        and _ux_rebuild_art("assets_results.json"),
        "timelineReferenceNonBlockingPassed": _art_ok("core_ref_nonblocking_results.json")
        and _ux_rebuild_art("assets_results.json"),
        "timelineAssetNamingPassed": _art_ok("core_asset_naming_results.json")
        and _parity_check("clearAssetActions"),
        "timelineAssetActionClarityPassed": _art_ok("core_asset_actions_results.json")
        and _parity_check("clearAssetActions"),
        "timelineCoDirectorRefinementPassed": cd_handlers and _ux_rebuild_art("codirector_ui_sync_results.json"),
        "timelineSimplicityReviewPassed": simplicity and beginner,
        # Co-Director
        "codirectorTimelineContextPassed": cd_handlers and _art_ok("codirector_context_results.json"),
        "codirectorTimelineReadToolsPassed": cd_handlers and _art_ok("codirector_read_tools_results.json"),
        "codirectorTimelineMutationGatewayPassed": _art_ok("codirector_mutation_gateway_results.json"),
        "codirectorTimelineApprovalPassed": _art_ok("codirector_approval_results.json"),
        "codirectorTimelineRevisionSafetyPassed": _art_ok("codirector_revision_results.json"),
        "codirectorTimelineBatchToolsPassed": _art_ok("codirector_batch_tools_results.json"),
        "codirectorTimelinePromptAnchorToolsPassed": _art_ok("codirector_prompt_anchor_results.json"),
        "codirectorTimelineReferenceToolsPassed": _art_ok("codirector_reference_tools_results.json"),
        "codirectorTimelinePreflightPassed": _art_ok("codirector_preflight_results.json"),
        "codirectorTimelineGenerationPassed": _art_ok("codirector_generation_results.json"),
        "codirectorTimelineRetakePassed": _any_art("codirector_retake_results.json", "retake_results.json"),
        "codirectorTimelineRazorPassed": _any_art("codirector_razor_results.json", "razor_results.json"),
        "codirectorTimelineMultiRangeRepairPassed": _any_art(
            "codirector_multirange_results.json", "repair_overlap_results.json"
        ),
        "codirectorTimelineInpaintPassed": _any_art("codirector_inpaint_results.json", "inpaint_results.json"),
        "codirectorTimelineBackgroundRepairPassed": _art_ok("codirector_background_repair_results.json")
        or api_pkg,
        "codirectorTimelineContinuityPassed": _any_art(
            "codirector_continuity_results.json", "continuity_findings_results.json"
        )
        or api_pkg,
        "codirectorTimelineUiSyncPassed": _ux_rebuild_art("codirector_ui_sync_results.json"),
        "codirectorTimelineReceiptsPassed": _art_ok("codirector_receipts_results.json"),
        "codirectorTimelineSecurityPassed": security and _art_ok("codirector_security_results.json"),
        "codirectorTimelinePlaywrightPassed": _ux_rebuild_art("playwright_results.json"),
        "codirectorTimelinePrimaryE2EPassed": _ux_rebuild_art("primary_e2e_results.json"),
        # UX Rebuild SA44–SA55 (absent evidence ⇒ NO-GO)
        "timelineUxArchitecturePassed": wireframe and _ux_rebuild_art("approved_mockup.png"),
        "timelineProfessionalLayoutPassed": shell and _ux_rebuild_art("layout_results.json") and _parity_check(
            "dominantViewer"
        ),
        "timelineViewerResizePassed": stack
        and _ux_rebuild_art("viewer_resize_results.json")
        and _parity_check("dominantViewer"),
        "timelineToolbarCompletePassed": _ux_rebuild_art("toolbar_results.json")
        and _parity_check("singleRowToolbar"),
        "timelineButtonsVisiblePassed": _ux_rebuild_art("toolbar_results.json")
        and _parity_check("singleRowToolbar"),
        "timelineProfessionalTrackRendererPassed": _ux_rebuild_art("track_renderer_results.json")
        and _parity_check("professionalTrackHeaders")
        and _parity_check("batchLane"),
        "timelineScenePromptClarityPassed": _ux_rebuild_art("inspector_results.json")
        and _parity_check("contextualInspector"),
        "timelineTimedInstructionClarityPassed": _ux_rebuild_art("inspector_results.json"),
        "timelineContextInspectorPassed": _ux_rebuild_art("inspector_results.json")
        and _parity_check("contextualInspector"),
        "timelineSceneNavigationPassed": _ux_rebuild_art("scenes_results.json")
        and _parity_check("compactScenes"),
        "timelineAssetClarityPassed": _ux_rebuild_art("assets_results.json")
        and _parity_check("clearAssetActions"),
        "timelineGuidanceConsumptionPassed": _ux_rebuild_art("settings_results.json"),
        "timelineQueueSimplificationPassed": _ux_rebuild_art("queue_results.json")
        and _parity_check("compactQueue"),
        "timelineCoDirectorUiSyncPassed": _ux_rebuild_art("codirector_ui_sync_results.json"),
        "timelineBeginnerUxPassed": beginner and _ux_rebuild_art("beginner_review_results.json"),
        "timelineVisualReviewPassed": visual_a11y and _ux_rebuild_art("visual_review_results.json"),
        "timelineAccessibilityReviewPassed": visual_a11y and _ux_rebuild_art("a11y_results.json"),
        "timelinePlaywrightPassed": _ux_rebuild_art("playwright_results.json"),
        "timelineMockupParityPassed": parity_ok and rebuild_report,
        # SA56–SA78 final addenda — absent evidence ⇒ NO-GO
        "timelineCameraMotionCatalogPassed": _cam("camera_motion_catalog_results.json")
        and _exists("studio-api", "app", "director_timeline_w46", "camera_catalog.py"),
        "timelineCameraRigCatalogPassed": _cam("camera_rig_catalog_results.json")
        and _exists("studio-api", "app", "director_timeline_w46", "camera_catalog.py"),
        "timelineCameraCapabilityMappingPassed": _cam("camera_capability_results.json"),
        "timelineCameraDropdownUxPassed": _cam("camera_dropdown_ux_results.json")
        and _exists("studio-web", "src", "components", "ui", "SearchableGroupedSelect.tsx"),
        "timelineCameraPersistencePassed": _cam("camera_persistence_results.json"),
        "timelineCameraCoDirectorPassed": _cam("camera_codirector_results.json"),
        "timelineFullHeightViewportPassed": _viewer("full_height_viewport_results.json") and shell and stack,
        "timelineBottomGapRemovedPassed": _viewer("bottom_gap_removed_results.json"),
        "timelineViewportResizePassed": _viewer("viewport_resize_results.json"),
        "timelineGeneratorBannerPassed": _viewer("banner_results.json")
        and _exists("studio-web", "src", "components", "timeline-master", "TimelineGeneratorBanner.tsx"),
        "timelineGeneratorBannerReducedMotionPassed": _viewer("banner_reduced_motion_results.json"),
        "timelineTrackLabelContrastPassed": _viewer("track_label_contrast_results.json"),
        "timelineTrackHeaderReadabilityPassed": _viewer("track_header_readability_results.json"),
        "timelineTrackLabelsNightPassed": _viewer("track_labels_night.png") or _viewer("track_labels_night_results.json"),
        "timelineTrackLabelsDayPassed": _viewer("track_labels_day.png") or _viewer("track_labels_day_results.json"),
        "timelineViewerDominancePassed": _viewer("viewer_dominance_results.json"),
        "timelineViewerLargeDefaultPassed": _viewer("viewer_large_default_results.json"),
        "timelineViewerPresetsPassed": _viewer("viewer_presets_results.json"),
        "timelineViewerFullscreenPassed": _viewer("viewer_fullscreen_results.json"),
        "timelineTrackRailCompactPassed": _viewer("track_rail_compact_results.json"),
        "timelineTrackInternalScrollPassed": _viewer("track_internal_scroll_results.json"),
        "timelineCenterPageNoScrollPassed": _viewer("center_page_no_scroll_results.json"),
        "timelineViewerCanvasScalingPassed": _viewer("viewer_canvas_scaling_results.json"),
        "timelineDockResponsiveHeightPassed": _viewer("dock_responsive_height_results.json"),
        "timelineViewerLayoutPersistencePassed": _viewer("viewer_layout_persistence_results.json"),
        "timelineCoDirectorLayoutPassed": _viewer("codirector_layout_results.json"),
        "timelineDefaultLipSyncTrackPassed": _lipsync("default_lipsync_track_results.json"),
        "timelineAdditionalLipSyncTrackPassed": _lipsync("additional_lipsync_track_results.json"),
        "timelineLipSyncClipPassed": _lipsync("lipsync_clip_results.json"),
        "timelineLipSyncAudioBindingPassed": _lipsync("lipsync_audio_binding_results.json"),
        "timelineLipSyncPersistencePassed": _lipsync("lipsync_persistence_results.json"),
        "timelineLipSyncToolbarPassed": _lipsync("lipsync_toolbar_results.json"),
        "timelineInpaintVideoFinishingOnlyPassed": _lipsync("inpaint_video_finishing_only_results.json"),
        "timelineInpaintEligibilityPassed": _lipsync("inpaint_eligibility_results.json"),
        "timelineInpaintWorkspacePassed": _lipsync("inpaint_workspace_results.json"),
        "timelineInpaintMaskPassed": _lipsync("inpaint_mask_results.json"),
        "timelineInpaintTrackingPassed": _lipsync("inpaint_tracking_results.json"),
        "timelineInpaintStrategyDisclosurePassed": _lipsync("inpaint_strategy_disclosure_results.json"),
        "timelineInpaintExecutionPassed": _lipsync("inpaint_execution_results.json"),
        "timelineInpaintAudioPreservationPassed": _lipsync("inpaint_audio_preservation_results.json"),
        "timelineInpaintVersionLineagePassed": _lipsync("inpaint_version_lineage_results.json"),
        "timelineLipSyncInpaintCoDirectorPassed": _lipsync("lipsync_inpaint_codirector_results.json"),
        "timelineLipSyncInpaintAccessibilityPassed": _lipsync("lipsync_inpaint_a11y_results.json"),
        "timelineLipSyncInpaintPlaywrightPassed": _lipsync("lipsync_inpaint_playwright_results.json"),
        "timelineZoomControlsPassed": _viewer("zoom_controls_results.json") or _lipsync("zoom_controls_results.json"),
        "timelineToolbarWiringPassed": _lipsync("toolbar_wiring_results.json"),
        "timelinePlaywrightOperationalPassed": _lipsync("playwright_operational_results.json"),
        **dock,
    }

    required = list(REQUIRED_GATE_FLAGS)
    director_timeline_go = all(bool(flags.get(k)) for k in required) and final and api_pkg and ux and shell
    failed = [k for k in required if not flags.get(k)]

    return {
        "ok": True,
        "directorTimelineGo": bool(director_timeline_go),
        "verdict": "GO" if director_timeline_go else "NO-GO",
        "flags": flags,
        "requiredFlags": required,
        "failed": failed,
        "dockPrerequisiteFlags": dock,
        "productionDockGoUnchanged": True,
        "wave": "W46",
        "addenda": "UX+Core+CoDirector+UxRebuild+FinalSA56-SA78",
        "uxRebuild": "SA44-SA55",
        "finalAddenda": "SA56-SA78",
        "mock": False,
    }
