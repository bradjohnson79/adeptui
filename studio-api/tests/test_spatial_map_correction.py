"""Spatial Map correction - unit truth (zimage.inpaint unlocked; no Mess Hall GO)."""

from __future__ import annotations

from app.spatial_map.correction import (
    CERTIFIED_WORKFLOW,
    ENGINE,
    ENGINE_CERT_ID,
    ENGINE_FAMILY,
    ENGINE_HOLD,
    ENGINE_STATUS_READY,
    LEGACY_ENGINE_HOLD,
    LEGACY_ENGINE_STATUS_BLOCKED,
    PREFERRED_FAL_MODEL,
    PRESERVATION_TEMPLATE,
    build_gpt_mask_edit_arguments,
    compose_frozen_prompt,
    engine_status,
    get_correction_state,
    reconcile_dimensions,
)


def test_engine_unlocked_zimage_certified(monkeypatch):
    monkeypatch.delenv("ADEPT_SPATIAL_MAP_GPT_MASK_ENGINE", raising=False)
    status = engine_status()
    assert status["engine"] == ENGINE == "zimage.inpaint"
    assert status["engineStatus"] == ENGINE_STATUS_READY == "ZIMAGE_INPAINT_CERTIFIED"
    assert status["engineHold"] is None
    assert status["executable"] is True
    assert status["providerCalled"] is False
    assert status["zimageWired"] is True
    assert status["preferredModel"] == CERTIFIED_WORKFLOW == "zimage.inpaint"
    assert status["workflowKey"] == CERTIFIED_WORKFLOW
    assert status["certificationId"] == ENGINE_CERT_ID == "IMG-ZIMAGE-INPAINT-001"
    assert status["family"] == ENGINE_FAMILY == "zimage"
    assert status["certified"] is True
    assert status["atlasErsGeneration"] == "gpt-image-2"
    assert status.get("atlasGenerationUnchanged") is True
    assert LEGACY_ENGINE_STATUS_BLOCKED in status["legacyHoldsRemoved"]
    assert LEGACY_ENGINE_HOLD in status["legacyHoldsRemoved"]
    # ENGINE_HOLD constant may keep legacy label for imports; live payload clears hold.
    assert ENGINE_HOLD == LEGACY_ENGINE_HOLD
    assert "Brad" in status["reason"] or "unlock" in status["reason"].lower()


def test_gpt_env_flip_does_not_change_zimage_correct_area_engine(monkeypatch):
    monkeypatch.setenv("ADEPT_SPATIAL_MAP_GPT_MASK_ENGINE", "1")
    status = engine_status()
    assert status["allowEnv"] is True
    assert status["executable"] is True
    assert status["engineStatus"] == "ZIMAGE_INPAINT_CERTIFIED"
    assert status["engineHold"] is None
    assert status["zimageWired"] is True
    assert status["preferredModel"] == CERTIFIED_WORKFLOW


def test_get_correction_state_accepts_db_kwarg():
    """Router passes db=db; must not TypeError (REVIEW NO-GO #1)."""
    import inspect

    sig = inspect.signature(get_correction_state)
    assert "db" in sig.parameters
    out = get_correction_state("proj-test-missing", "doc-test-missing", db=None)
    assert out["documentId"] == "doc-test-missing"
    assert out["engine"] == "zimage.inpaint"
    assert "activeSession" in out


def test_compose_frozen_prompt_edit_only_masked_region():
    frozen = compose_frozen_prompt("  Move the crate left  ")
    assert frozen["creatorPrompt"] == "Move the crate left"
    assert frozen["preservationTemplate"] == PRESERVATION_TEMPLATE
    assert "EDIT ONLY MASKED REGION" in PRESERVATION_TEMPLATE
    assert frozen["creatorPrompt"] in frozen["composedPrompt"]
    assert PRESERVATION_TEMPLATE in frozen["composedPrompt"]
    assert "Co-Director" not in frozen["composedPrompt"]
    assert frozen["preserveStyle"] == "true"


def test_compose_frozen_prompt_requires_text():
    try:
        compose_frozen_prompt("   ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "required" in str(exc).lower()


def test_build_gpt_mask_edit_arguments_draft_only_includes_mask():
    args = build_gpt_mask_edit_arguments(
        source_image_url="https://example.test/map.png",
        mask_url="https://example.test/mask.png",
        composed_prompt="fix crate\n\n" + PRESERVATION_TEMPLATE,
        width=2048,
        height=1024,
    )
    assert args["image_urls"] == ["https://example.test/map.png"]
    assert args["mask_image_url"] == "https://example.test/mask.png"
    assert args["mask_url"] == "https://example.test/mask.png"
    assert args["image_size"] == {"width": 2048, "height": 1024}
    assert "prompt" in args


def test_reconcile_dimensions_match():
    out = reconcile_dimensions(source_width=1024, source_height=512, output_width=1024, output_height=512)
    assert out["ok"] is True
    assert out["matched"] is True
    assert out["resized"] is False


def test_reconcile_dimensions_mismatch_refuses_without_silent_resize():
    out = reconcile_dimensions(source_width=1024, source_height=512, output_width=800, output_height=400)
    assert out["ok"] is False
    assert out["matched"] is False
    assert out["resized"] is False
    err = out.get("error") or ""
    assert "Silent resize is forbidden" in err


def test_reconcile_dimensions_never_uses_lanczos():
    import inspect
    import app.spatial_map.correction as mod

    src = inspect.getsource(mod.reconcile_dimensions)
    assert "Resampling.LANCZOS" not in src
    assert "im.resize" not in src


def test_correction_module_wires_image_core_and_job_bridge():
    import inspect
    import app.spatial_map.correction as mod

    src = inspect.getsource(mod)
    assert "fal_adapter.submit" not in src
    assert "submit_kie_image_task" not in src
    assert "from ..image_core.generate import generate" in src
    assert "zimage.inpaint" in src
    assert "_sync_provider_jobs" in src
    assert "preview_ready" in src
    assert "queueJobId" in src
    assert PREFERRED_FAL_MODEL in src


def test_accept_path_never_calls_create_document():
    import inspect
    import app.spatial_map.correction as mod

    src = inspect.getsource(mod)
    assert "create_document(" not in src
    assert "createMap(" not in src
    assert "SpatialMapUpdateBody(backgroundAssetId=" in src
    assert src.count("update_document(") >= 3
    assert "stamp_cameras_on_ers_image" not in src


def test_accept_uses_background_only_update_body():
    import inspect
    from app.spatial_map.correction import accept_correction, reset_correction, undo_correction

    for fn in (accept_correction, undo_correction, reset_correction):
        src = inspect.getsource(fn)
        assert "SpatialMapUpdateBody(backgroundAssetId=" in src


def test_accept_enforces_dimension_match():
    import inspect
    from app.spatial_map.correction import accept_correction

    src = inspect.getsource(accept_correction)
    assert "reconcile_dimensions(" in src
    assert "_sync_provider_jobs" in src

def test_certified_workflow_import_path_is_honest():
    """Collection/import must resolve CERTIFIED_WORKFLOW and registry without fallback."""
    import inspect
    import app.spatial_map.correction as mod
    from app.image_runtime.certified_registry import get_workflow

    assert CERTIFIED_WORKFLOW == "zimage.inpaint"
    assert mod.CERTIFIED_WORKFLOW == CERTIFIED_WORKFLOW
    src = inspect.getsource(mod._zimage_inpaint_certified)
    assert "except Exception" not in src
    assert "get_workflow(CERTIFIED_WORKFLOW)" in src
    wf = get_workflow(CERTIFIED_WORKFLOW)
    assert wf is not None
    assert str(wf.status) == "Certified"
    assert str(wf.workflow_id) == "IMG-ZIMAGE-INPAINT-001"


def test_get_correction_state_exposes_preview_bridge_fields():
    out = get_correction_state("proj-test-missing", "doc-test-missing", db=None)
    assert "resultAssetId" in out
    assert "previewUrl" in out
    assert "previewReady" in out
    assert out["previewReady"] is False
    assert out["resultAssetId"] is None
    assert "acceptToken" in out
    assert "queueJobId" in out


def test_sync_provider_jobs_does_not_fail_missing_queue_row():
    import inspect
    from app.spatial_map.correction import _sync_provider_jobs

    src = inspect.getsource(_sync_provider_jobs)
    assert "Provider job missing." not in src
    assert "leave queued" in src
    assert "preview_ready" in src
    assert "dimension_mismatch" in src
    assert "rejectedAssetId" in src
