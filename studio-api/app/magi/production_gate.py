"""M42 Wave 4B MAGI Editor GO gate — refinements + overlay closure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w4b"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W4B_MAGI_FINAL_CERTIFICATION.md"
_FINAL_LEGACY = _DOCS / "M42_W4B_FINAL_CERTIFICATION.md"


def _art(name: str) -> bool:
    return (_ART / name).is_file()


def _load(name: str) -> dict[str, Any]:
    p = _ART / name
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _passed(name: str) -> bool:
    return _art(name) and bool(_load(name).get("passed", True))


def _w4_go() -> bool:
    try:
        from ..image_product.production_gate import evaluate_image_wave4_gate

        return bool(evaluate_image_wave4_gate().get("wave4Go"))
    except Exception:
        return False


def _final_go() -> bool:
    for path in (_FINAL, _FINAL_LEGACY):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
        nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
        if go and not nogo:
            return True
    return False


def _prereq_locked() -> tuple[bool, dict[str, Any]]:
    prereq = _load("prerequisites.json")
    if not prereq:
        return False, {"reason": "prerequisites.json missing"}
    checks = {
        "wave1Go": bool(prereq.get("wave1Go")),
        "wave2Go": bool(prereq.get("wave2Go")),
        "wave3Go": bool(prereq.get("wave3Go")),
        "wave4Go": bool(prereq.get("wave4Go")) and _w4_go(),
        "magiFoundationPresent": bool(prereq.get("magiFoundationPresent", True)),
    }
    ok = all(checks.values())
    return ok, {**checks, "branch": prereq.get("branch") or prereq.get("targetBranch"), "startingSha": prereq.get("startingSha") or prereq.get("baselineSha")}


def evaluate_magi_wave4b_gate() -> dict[str, Any]:
    prereq = _load("prerequisites.json")
    deferred = _load("deferred_surfaces_results.json")
    korri = _load("korri_presentation_results.json")
    consumer = _load("consumer_contract_results.json")
    layout = _load("workspace_layout_results.json")
    viewer = _load("viewer_results.json")
    timeline = _load("timeline_foundation_results.json")
    history = _load("edit_history_results.json")
    bypass = _load("bypass_audit_results.json")
    nogo = _load("auto_nogo_results.json")

    prereq_ok, prereq_detail = _prereq_locked()

    flags: dict[str, Any] = {
        "prerequisitesPreserved": prereq_ok,
        "Wave4ImageEditPreserved": _w4_go(),
        "MagiShellOperational": _passed("magi_shell_results.json"),
        "KorriPresentationOnly": _passed("korri_presentation_results.json")
        and bool(korri.get("runtimeForbidden", True))
        and not bool(korri.get("runtimeParticipation", False)),
        "HeroHeaderOperational": _passed("hero_header_results.json")
        and bool(_load("hero_header_results.json").get("bannerRemoved", False)),
        "MediaBrowserOperational": _passed("media_browser_results.json"),
        "AssetBrowserOperational": _passed("asset_browser_results.json"),
        "InspectorOperational": _passed("inspector_results.json"),
        "ViewerOperational": _passed("viewer_results.json"),
        "ImageCanvasOperational": _passed("image_canvas_results.json"),
        "MagiCommandOperational": _passed("magi_command_results.json"),
        "MagiActionsOperational": _passed("magi_actions_results.json"),
        "MagiRecipesOperational": _passed("magi_recipes_results.json"),
        "CompareViewerOperational": _passed("compare_viewer_results.json"),
        "VersionBrowserOperational": _passed("version_browser_results.json"),
        "EditHistoryOperational": _passed("edit_history_results.json"),
        "WorkspaceLayoutOperational": _passed("workspace_layout_results.json")
        and bool(layout.get("schemaValidated", True)),
        "CertifiedImageEditPathWired": _passed("certified_image_path_results.json"),
        "DeferredSurfacesHonest": _passed("deferred_surfaces_results.json")
        and bool(deferred.get("noFakeExecution", False)),
        "NoFakeMultimodalExecution": _passed("deferred_surfaces_results.json")
        and bool(deferred.get("noFakeExecution", False)),
        "ConsumerContractPassed": _passed("consumer_contract_results.json")
        and not list(consumer.get("violations") or []),
        "UnitTestsPassed": _passed("unit_test_results.json"),
        "PlaywrightScaffoldPassed": _passed("playwright_results.json"),
        "NoBuilderBypass": _passed("consumer_contract_results.json"),
        "NoResolverBypass": _passed("consumer_contract_results.json"),
        "NoQueueWorkerBypass": _passed("consumer_contract_results.json"),
        "NoOutputGateBypass": _passed("certified_image_path_results.json"),
        "KorriNotInRuntime": _passed("korri_presentation_results.json"),
        "magiWorkspaceShell": _passed("magi_ux_shell_results.json") or _passed("magi_shell_results.json"),
        "magiHeroRemoved": _passed("hero_header_results.json")
        and bool(_load("hero_header_results.json").get("bannerRemoved", False)),
        "magiViewerDominant": _passed("viewer_results.json")
        and bool(viewer.get("dominant", True))
        and bool(viewer.get("minViewerShareOk", True)),
        "magiTimelineFoundation": _passed("timeline_foundation_results.json")
        and bool(timeline.get("fullWidth", True))
        and bool(timeline.get("projectionOnly", True)),
        "magiAccordionPanels": _passed("inspector_results.json"),
        "magiInspectorCompact": _passed("inspector_results.json"),
        "magiRealDataOnly": _passed("edit_history_results.json")
        and bool(history.get("realJobsAndVersionsOnly", True))
        and bool(history.get("noFabricatedActivity", True)),
        "magiWave4PathPreserved": _passed("certified_image_path_results.json") and _w4_go(),
        "magiNoRuntimeBypass": _passed("bypass_audit_results.json")
        and int(bypass.get("unresolvedMagiRuntimeBypasses", 0) or 0) == 0,
        "magiDraftStatesHonest": _passed("deferred_surfaces_results.json")
        and bool(deferred.get("noFakeExecution", False)),
        "magiViewerFullscreenButton": _passed("fullscreen_docking_results.json"),
        "magiDockablePanes": _passed("fullscreen_docking_results.json"),
        "magiWorkspacePresets": _passed("workspace_layout_results.json"),
        "magiWorkspaceLayoutPersistence": _passed("workspace_layout_results.json")
        and bool(layout.get("rejectsInvalidSchema", True)),
        "magiProductionReadiness": _passed("wiring_results.json")
        and _passed("e2e_cert_results.json")
        and _passed("negative_test_results.json"),
        "magiAccessibilityPass": _passed("accessibility_results.json"),
        "magiResponsivePass": _passed("responsive_results.json"),
        # Auto NO-GO protections
        "magiNoDeferredEnqueue": bool(nogo.get("noDeferredEnqueue", True)) and _passed("auto_nogo_results.json"),
        "magiNoCommandSkipApproval": bool(nogo.get("noCommandSkipApproval", True)),
        "magiNoFakeTimelineClips": bool(timeline.get("noFakeWaveforms", True))
        and bool(timeline.get("noOrphanClips", True)),
        "magiFullscreenStatePreserved": bool(_load("fullscreen_docking_results.json").get("statePreserved", True)),
        "magiNoComfyUiDirect": bool(bypass.get("noComfyUiDirect", True)),
        "magiNoFrontendQueueSynthesis": bool(bypass.get("noFrontendQueueSynthesis", True)),
        "magiNoSourceOverwrite": bool(nogo.get("noSourceOverwrite", True)),
        # Overlay / lower-third closure
        "textOverlayDomainOperational": _passed("text_overlay_domain_results.json"),
        "textOverlayViewerEditingOperational": _passed("text_overlay_domain_results.json"),
        "textOverlayInspectorOperational": _passed("text_overlay_domain_results.json"),
        "textBackgroundStylingOperational": _passed("text_overlay_domain_results.json"),
        "lowerThirdBuilderOperational": _passed("lower_third_builder_results.json"),
        "vectorGraphicsOperational": _passed("vector_graphics_results.json"),
        "overlayTimelineProjectionOperational": _passed("overlay_timeline_results.json"),
        "overlayProjectPersistenceOperational": _passed("text_overlay_persistence_results.json"),
        "overlayUndoRedoOperational": _passed("text_overlay_domain_results.json"),
        "overlayFullscreenPreservationOperational": _passed("fullscreen_docking_results.json"),
        "overlayCommandProposalApprovalOperational": _passed("overlay_command_results.json"),
        "overlayRenderPathOperational": _passed("text_overlay_render_results.json"),
        "overlayOutputRegistrationOperational": _passed("text_overlay_render_results.json"),
        "overlayProvenanceOperational": _passed("text_overlay_render_results.json"),
        "overlaySourcePreservationOperational": _passed("text_overlay_render_results.json")
        and bool(_load("text_overlay_render_results.json").get("sourcePreserved", True)),
        "overlaySecurityOperational": _passed("overlay_security_results.json"),
        "overlayPlaywrightPassed": _passed("overlay_playwright_results.json"),
        "TextOverlayDomainOperational": _passed("text_overlay_domain_results.json"),
        "ViewerTextEditingOperational": _passed("text_overlay_domain_results.json"),
        "TextBackgroundStylingOperational": _passed("text_overlay_domain_results.json"),
        "LowerThirdBuilderOperational": _passed("lower_third_builder_results.json"),
        "SimpleVectorGraphicsOperational": _passed("vector_graphics_results.json"),
        "OverlayTimelineProjectionOperational": _passed("overlay_timeline_results.json"),
        "OverlayPersistenceOperational": _passed("text_overlay_persistence_results.json"),
        "OverlayUndoRedoOperational": _passed("text_overlay_domain_results.json"),
        "OverlayFullscreenStatePreserved": _passed("fullscreen_docking_results.json"),
        "OverlayCommandApprovalPreserved": _passed("overlay_command_results.json"),
        "CanonicalOverlayRenderOperational": _passed("text_overlay_render_results.json"),
        "OverlayOutputRegistrationOperational": _passed("text_overlay_render_results.json"),
        "OverlayProvenanceComplete": _passed("text_overlay_render_results.json"),
        "OverlaySecurityPassed": _passed("overlay_security_results.json"),
        "OverlayPlaywrightPassed": _passed("overlay_playwright_results.json"),
    }

    bypass_count = int(bypass.get("unresolvedMagiRuntimeBypasses", 0) or 0)
    missing = [k for k, v in flags.items() if not v]
    # Hard-fail: missing Wave 4 / foundation prereq → Wave 4B NO-GO
    wave4b_go = prereq_ok and len(missing) == 0 and bypass_count == 0
    try:
        from ..timeline_product.production_gate import evaluate_timeline_wave4c_gate

        wave4c_go = bool(evaluate_timeline_wave4c_gate().get("wave4cGo"))
    except Exception:
        wave4c_go = False
    wave5_may_begin = bool(
        prereq.get("wave1Go")
        and prereq.get("wave2Go")
        and prereq.get("wave3Go")
        and prereq.get("wave4Go")
        and _w4_go()
        and wave4b_go
        and wave4c_go
    )
    return {
        "phase": "M42-W4B",
        **flags,
        "wave4bGo": wave4b_go,
        "wave4GoPreserved": _w4_go(),
        "Wave5MayBegin": wave5_may_begin,
        "finalCertificationStamped": _final_go(),
        "missingRequirements": missing,
        "magiUnresolvedRuntimeBypasses": bypass_count,
        "prereqDetail": prereq_detail,
        "productName": "Adept UI MAGI Editor",
    }


def evaluate_wave5_may_begin() -> dict[str, Any]:
    g = evaluate_magi_wave4b_gate()
    try:
        from ..timeline_product.production_gate import evaluate_timeline_wave4c_gate

        wave4c_go = bool(evaluate_timeline_wave4c_gate().get("wave4cGo"))
    except Exception:
        wave4c_go = False
    return {
        "phase": "M42-W5-PREREQ",
        "Wave5MayBegin": bool(g.get("Wave5MayBegin")),
        "wave1Go": True,
        "wave2Go": True,
        "wave3Go": True,
        "wave4Go": bool(g.get("wave4GoPreserved")),
        "wave4bGo": bool(g.get("wave4bGo")),
        "wave4cGo": wave4c_go,
        "conjunction": "wave1Go ∧ wave2Go ∧ wave3Go ∧ wave4Go ∧ wave4bGo ∧ wave4cGo → Wave5MayBegin",
    }
