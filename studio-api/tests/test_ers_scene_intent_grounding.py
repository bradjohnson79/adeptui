"""ERS source-lineage grounding: Scene Intent contract, compiler grounding
preamble, Qwen-strip vs GPT Image 2 carve-out, staleness fingerprint, and
semantic-gate verdict parsing (mocked VLM)."""

from __future__ import annotations

import uuid

import pytest

from app.codirector.knowledgebase.ers_compiler import (
    compile_environment_reference_sheet_prompt,
)
from app.codirector.vision.ers_gate import (
    ERS_GATE_CONTEXT,
    ERS_GATE_LAYOUT,
    ERS_GATE_NOT_VERIFIED,
    ERS_GATE_PASS,
    parse_ers_gate_verdict,
)
from app.spatial_map.scene_intent import (
    SceneDescriptionError,
    build_scene_intent,
    coerce_scene_intent,
    environment_intent_summary,
    infer_location_type,
    lineage_fingerprint,
    merge_scene_description_edit,
    scene_intent_from_atlas_meta,
    validate_scene_description,
)
from app.spatial_map.schemas import SpatialMapDocument


SCHNICK_DESCRIPTION = (
    "A warm neighborhood coffee shop — Schnick Coffee — primary location for "
    "our commercial. Cozy café interior with counter, seating, and coffee bar."
)


def _schnick_intent(**overrides):
    kwargs = dict(
        project_name="Schnick Coffee",
        scene_title="Schnick Coffee",
        key_subjects=["Korri"],
        key_props=["coffee cup"],
        environment_traits=["warm", "cozy"],
        source_reference_asset_ids=["4d3062e8-8c30-4230-8376-bc25d1d4f735"],
        originating_prompt="Atlas shot for the Schnick Coffee café (Korri Coffee House.png).",
    )
    kwargs.update(overrides)
    return build_scene_intent(SCHNICK_DESCRIPTION, **kwargs)


# ── Scene Intent builder / validation ─────────────────────────────────────


def test_build_scene_intent_from_description() -> None:
    intent = _schnick_intent()
    assert intent.version == 1
    assert intent.purpose == "spatial_environment"
    assert intent.sceneTitle == "Schnick Coffee"
    assert intent.locationType == "coffee_shop"
    assert intent.summary == SCHNICK_DESCRIPTION
    assert intent.keySubjects == ["Korri"]
    assert intent.keyProps == ["coffee cup"]
    assert intent.sourceReferenceAssetIds == ["4d3062e8-8c30-4230-8376-bc25d1d4f735"]
    assert "café" in intent.sourcePromptSummary


def test_validate_scene_description_rejects_empty_short_generic() -> None:
    for bad in ("", "   ", "room", "test", "scene", "n/a", "too short"):
        with pytest.raises(SceneDescriptionError):
            validate_scene_description(bad)
    ok = validate_scene_description("  A quiet bookstore for our film.  ")
    assert ok == "A quiet bookstore for our film."


def test_infer_location_type_is_deterministic_and_honest() -> None:
    assert infer_location_type("a warm coffee shop with espresso bar") == "coffee_shop"
    assert infer_location_type("downtown office workspace") == "office"
    assert infer_location_type("xyzzy nowhere in particular zzz") == ""


def test_coerce_scene_intent_roundtrip_and_atlas_meta_recovery() -> None:
    intent = _schnick_intent()
    assert coerce_scene_intent(intent.model_dump()) == intent
    assert coerce_scene_intent(None) is None
    assert coerce_scene_intent({"not": "an intent"}) is not None  # permissive schema
    assert coerce_scene_intent(42) is None
    meta = {"sceneIntent": intent.model_dump(), "prompt": "..."}
    assert scene_intent_from_atlas_meta(meta) == intent
    assert scene_intent_from_atlas_meta({"prompt": "no intent"}) is None
    import json as _json

    assert scene_intent_from_atlas_meta(_json.dumps(meta)) == intent


def test_environment_intent_summary_carries_semantics() -> None:
    summary = environment_intent_summary(_schnick_intent())
    assert "Schnick Coffee" in summary
    assert "coffee shop" in summary
    assert "Korri" in summary
    assert "coffee cup" in summary
    assert environment_intent_summary(None) == ""


# ── Staleness fingerprint (W5) ────────────────────────────────────────────


def test_lineage_fingerprint_changes_with_lineage() -> None:
    intent = _schnick_intent()
    base = lineage_fingerprint(
        intent,
        background_asset_id="atlas-1",
        original_reference_asset_id="orig-1",
    )
    assert len(base) == 16
    # Same inputs -> same fingerprint (deterministic).
    assert base == lineage_fingerprint(
        intent, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )
    # Atlas swap -> different fingerprint (ERS must be marked stale).
    assert base != lineage_fingerprint(
        intent, background_asset_id="atlas-2", original_reference_asset_id="orig-1"
    )
    # Original image swap -> different fingerprint.
    assert base != lineage_fingerprint(
        intent, background_asset_id="atlas-1", original_reference_asset_id="orig-2"
    )
    # Description edit -> rebuilt intent -> different fingerprint.
    edited = build_scene_intent(
        "A warm neighborhood coffee shop — Schnick Coffee — now with a patio.",
        project_name="Schnick Coffee",
        scene_title="Schnick Coffee",
        key_subjects=["Korri"],
        key_props=["coffee cup"],
        source_reference_asset_ids=["4d3062e8-8c30-4230-8376-bc25d1d4f735"],
    )
    assert base != lineage_fingerprint(
        edited, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )


def test_scene_description_edit_merges_and_restores_fingerprint() -> None:
    """Regression: Edit Scene Description must preserve the curated snapshot
    (Korri, coffee cup, traits, production intent) so that restoring the
    original text restores the original fingerprint. Pre-fix, the rebuild
    dropped curated fields and the ERS stayed 'Needs Regeneration' forever."""
    original = _schnick_intent()
    fp_original = lineage_fingerprint(
        original, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )

    edited = merge_scene_description_edit(
        original, SCHNICK_DESCRIPTION + " Now with a small patio.", project_name="Schnick Coffee"
    )
    assert edited is not None
    assert edited.summary.endswith("patio.")
    # Curated fields survive the edit.
    assert edited.keySubjects == original.keySubjects
    assert edited.keyProps == original.keyProps
    assert edited.environmentTraits == original.environmentTraits
    assert edited.productionIntent == original.productionIntent
    assert edited.sourceReferenceAssetIds == original.sourceReferenceAssetIds
    fp_edited = lineage_fingerprint(
        edited, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )
    assert fp_edited != fp_original

    restored = merge_scene_description_edit(edited, SCHNICK_DESCRIPTION, project_name="Schnick Coffee")
    assert restored is not None
    fp_restored = lineage_fingerprint(
        restored, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )
    assert fp_restored == fp_original


def test_spatial_map_document_computes_grounding_fingerprint() -> None:
    intent = _schnick_intent()
    doc = SpatialMapDocument(
        projectId="p1",
        id="map-1",
        backgroundAssetId="atlas-1",
        sceneIntent=intent,
        originalEnvironmentReferenceAssetId="orig-1",
    )
    assert doc.groundingFingerprint == lineage_fingerprint(
        intent, background_asset_id="atlas-1", original_reference_asset_id="orig-1"
    )
    doc2 = doc.model_copy(update={"backgroundAssetId": "atlas-2"})
    assert doc2.groundingFingerprint != doc.groundingFingerprint


# ── Compiler grounding preamble (W3) ──────────────────────────────────────


def test_compiler_grounding_preamble_carries_cafe_identity() -> None:
    intent = _schnick_intent()
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Schnick Coffee",
        environment_description=SCHNICK_DESCRIPTION,
        environment_intent=intent.model_dump(),
        spatial_map={"id": "map-1", "backgroundAssetId": "atlas-1"},
    )
    prompt = compiled["prompt"]
    lowered = prompt.lower()
    assert "primary environment identity" in lowered
    assert "schnick coffee" in lowered
    assert "coffee shop" in lowered
    # The living-room failure guard: explicit do-not-replace language.
    assert "do not replace this place with a generic living room" in lowered
    # Exemplar leak guard: structure-only clause present.
    assert "layout structure only" in lowered
    assert "korri" in lowered
    # Scene intent wins over conflicting instructions.
    assert "scene intent wins" in lowered


def test_compiler_without_intent_has_no_grounding_preamble() -> None:
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Helios Research Atrium",
        environment_description="Glass-roofed atrium.",
    )
    assert "PRIMARY ENVIRONMENT IDENTITY" not in compiled["prompt"]


def test_compiler_grounding_preamble_precedes_layout_sections() -> None:
    intent = _schnick_intent()
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Schnick Coffee",
        environment_description=SCHNICK_DESCRIPTION,
        environment_intent=intent.model_dump(),
    )
    prompt = compiled["prompt"].lower()
    preamble_idx = prompt.find("primary environment identity")
    assert preamble_idx != -1
    # Identity authority must come before the directional layout spec.
    layout_idx = prompt.find("n / e / s / w")
    assert layout_idx != -1
    assert preamble_idx < layout_idx


# ── Qwen strip vs GPT Image 2 carve-out (W3 contract) ─────────────────────


def _patched_ers_handle(monkeypatch, captured, *, document):
    """Reuse the established pinning pattern from test_ers_image_product."""
    from app.codirector.capabilities.handlers import ers_generate
    from app.environment_reference_sheet import orchestrator
    from app.environment_reference_sheet.contracts import SpatialMapReference

    sheet = orchestrator.create_sheet(
        project_id=document.projectId,
        name="Schnick Coffee",
        description="Programmatically composed environment reference sheet.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(mapId=document.id, northLockDirection="north")

    class _Job:
        def __init__(self, job_id: str) -> None:
            self.id = job_id

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job("job-ers-grounding")

    monkeypatch.setattr(
        "app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet]
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)
    monkeypatch.setattr(
        ers_generate,
        "_enqueue_ers_image_product",
        lambda db, pid, body, scene_id=None: {
            "jobId": _fake_enqueue(db, pid, body, scene_id).id
        },
    )
    monkeypatch.setattr(
        "app.spatial_map.service.get_document", lambda db, pid, mid: document
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.store.save_sheet", lambda current: None
    )
    return ers_generate


def test_ers_qwen_keeps_honest_t2i_text_grounding(monkeypatch) -> None:
    intent = _schnick_intent()
    project_id = f"proj-{uuid.uuid4()}"
    map_id = f"map-{uuid.uuid4()}"
    document = SpatialMapDocument(
        projectId=project_id,
        id=map_id,
        backgroundAssetId="caa72759-d965-41f9-b1d5-77cdcf9b9614",
        sceneIntent=intent,
        originalEnvironmentReferenceAssetId="4d3062e8-8c30-4230-8376-bc25d1d4f735",
    )
    captured: list[dict] = []
    ers_generate = _patched_ers_handle(monkeypatch, captured, document=document)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=str(uuid.uuid4()),
        spatial_map_id=map_id,
        source="local",
        model="qwen2512",
        model_family_preference="qwen2512",
    )

    assert len(captured) == 1
    body = captured[0]
    # Qwen = text grounding only: no pixel routing, no I2I.
    assert not body.get("input_urls")
    assert not body.get("source_asset_id")
    assert body["creativeContext"]["operationIntent"] == "text_to_image"
    # Lineage rides the body for provenance + prompt grounding.
    ctx = body["creativeContext"]
    assert ctx["sceneIntent"]["sceneTitle"] == "Schnick Coffee"
    assert ctx["sceneIntentVersion"] == 1
    assert ctx["groundingAssetIds"] == [
        "4d3062e8-8c30-4230-8376-bc25d1d4f735",
        "caa72759-d965-41f9-b1d5-77cdcf9b9614",
    ]
    assert ctx["groundingFingerprint"]
    assert "referenceGrounding" not in ctx


def test_ers_gpt_image_2_explicit_carve_out_attaches_pixel_urls(monkeypatch) -> None:
    intent = _schnick_intent()
    project_id = f"proj-{uuid.uuid4()}"
    map_id = f"map-{uuid.uuid4()}"
    document = SpatialMapDocument(
        projectId=project_id,
        id=map_id,
        backgroundAssetId="caa72759-d965-41f9-b1d5-77cdcf9b9614",
        sceneIntent=intent,
        originalEnvironmentReferenceAssetId="4d3062e8-8c30-4230-8376-bc25d1d4f735",
    )
    captured: list[dict] = []
    ers_generate = _patched_ers_handle(monkeypatch, captured, document=document)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=str(uuid.uuid4()),
        spatial_map_id=map_id,
        hosted_model_id="gpt-image-2-kie",
        source="api",
    )

    assert len(captured) == 1
    body = captured[0]
    # GPT Image 2 (explicit creator choice) = pixel grounding via Kie input_urls.
    urls = body.get("input_urls") or []
    assert urls, "explicit GPT Image 2 must receive reference pixel URLs"
    assert any("4d3062e8" in u for u in urls)
    assert any("caa72759" in u for u in urls)
    ctx = body["creativeContext"]
    assert ctx["referenceGrounding"]["mode"] == "pixel"
    assert ctx["referenceGrounding"]["urlCount"] == len(urls)
    # Still honest T2I semantics at the image-product layer (no I2I upgrade).
    assert ctx["operationIntent"] == "text_to_image"
    assert not body.get("source_asset_id")


def test_ers_gpt_image_2_without_public_base_degrades_honestly(monkeypatch) -> None:
    intent = _schnick_intent()
    project_id = f"proj-{uuid.uuid4()}"
    map_id = f"map-{uuid.uuid4()}"
    document = SpatialMapDocument(
        projectId=project_id,
        id=map_id,
        backgroundAssetId="atlas-x",
        sceneIntent=intent,
        originalEnvironmentReferenceAssetId="orig-x",
    )
    captured: list[dict] = []
    ers_generate = _patched_ers_handle(monkeypatch, captured, document=document)
    monkeypatch.setattr("app.config.settings.public_api_base_url", "")

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=str(uuid.uuid4()),
        spatial_map_id=map_id,
        hosted_model_id="gpt-image-2-kie",
        source="api",
    )

    body = captured[0]
    assert not body.get("input_urls")
    grounding = body["creativeContext"]["referenceGrounding"]
    assert grounding["mode"] == "text_only"
    assert "not configured" in grounding["note"]


def test_ers_other_hosted_models_do_not_get_pixel_carve_out(monkeypatch) -> None:
    intent = _schnick_intent()
    project_id = f"proj-{uuid.uuid4()}"
    map_id = f"map-{uuid.uuid4()}"
    document = SpatialMapDocument(
        projectId=project_id,
        id=map_id,
        backgroundAssetId="atlas-x",
        sceneIntent=intent,
        originalEnvironmentReferenceAssetId="orig-x",
    )
    captured: list[dict] = []
    ers_generate = _patched_ers_handle(monkeypatch, captured, document=document)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=str(uuid.uuid4()),
        spatial_map_id=map_id,
        hosted_model_id="nano-banana-kie",
        source="api",
    )

    body = captured[0]
    assert not body.get("input_urls")
    assert "referenceGrounding" not in body["creativeContext"]
    # Lineage still rides creativeContext for provenance.
    assert body["creativeContext"]["groundingAssetIds"] == ["orig-x", "atlas-x"]


# ── Semantic gate verdict parsing (W4, mocked VLM) ────────────────────────


def test_gate_verdict_parsing() -> None:
    assert parse_ers_gate_verdict(
        "VERDICT: PASS\nREASON: Same coffee shop environment."
    ) == {"verdict": ERS_GATE_PASS, "summary": "Same coffee shop environment."}
    assert parse_ers_gate_verdict(
        "VERDICT: ERS_CONTEXT_NONCOMPLIANT\nREASON: This is a living room, not a café."
    )["verdict"] == ERS_GATE_CONTEXT
    assert parse_ers_gate_verdict(
        "VERDICT: ERS_LAYOUT_NONCOMPLIANT\nREASON: Single cinematic still."
    )["verdict"] == ERS_GATE_LAYOUT
    # Unknown / empty output is an honest NOT_VERIFIED — never a fake pass.
    assert parse_ers_gate_verdict("I think it looks nice.")["verdict"] == ERS_GATE_NOT_VERIFIED
    assert parse_ers_gate_verdict("")["verdict"] == ERS_GATE_NOT_VERIFIED


def test_gate_honest_degrade_without_vlm_key(tmp_path) -> None:
    import asyncio

    from app.codirector.vision.ers_gate import run_ers_semantic_gate

    # No kie_api_key configured in the test environment -> NOT_VERIFIED.
    result = asyncio.run(
        run_ers_semantic_gate(
            generated_image_path=str(tmp_path / "missing.png"),
            intent_summary="Schnick Coffee café",
        )
    )
    assert result["verdict"] == ERS_GATE_NOT_VERIFIED
    assert result["advisory"] is True
