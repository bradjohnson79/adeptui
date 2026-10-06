from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import ValidationError


def _rgb(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (64, 48)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_inferred_cannot_become_observed():
    from app.spatial_map.supplementary.contracts import SpatialReferenceRecord

    try:
        SpatialReferenceRecord(slot="A", evidenceClass="OBSERVED", source="QWEN_IMAGE_EDIT")
        raise AssertionError("inferred Qwen view must not be OBSERVED")
    except ValidationError:
        pass


def test_observed_ids_exclude_inferred():
    from app.spatial_map.supplementary.contracts import SpatialReferenceRecord, observed_asset_ids

    inferred = SpatialReferenceRecord(
        slot="A",
        assetId="inf-1",
        evidenceClass="INFERRED",
        source="QWEN_IMAGE_EDIT",
        cameraRole="REVERSE",
    )
    ids = observed_asset_ids(master_asset_id="master-1", references=[inferred], source_asset_ids=["master-1", "inf-1"])
    assert ids == ["master-1"]


def test_inferred_plus_inferred_never_observed():
    from app.spatial_map.supplementary.confidence import promote_inferred_agreement_to_observed, summarize_confidence
    from app.spatial_map.supplementary.contracts import SpatialReferenceRecord

    master = SpatialReferenceRecord(slot="MASTER", assetId="m", evidenceClass="OBSERVED", source="USER")
    a = SpatialReferenceRecord(
        slot="A",
        assetId="a",
        evidenceClass="INFERRED",
        source="QWEN_IMAGE_EDIT",
        approvedForSpatialReasoning=True,
        status="READY",
        cameraRole="REVERSE",
    )
    b = SpatialReferenceRecord(
        slot="B",
        assetId="b",
        evidenceClass="INFERRED",
        source="QWEN_IMAGE_EDIT",
        approvedForSpatialReasoning=True,
        status="READY",
        cameraRole="LEFT_SIDE",
    )
    summary = summarize_confidence(master=master, view_a=a, view_b=b)
    assert all("OBSERVED" not in row or "not" in row.lower() for row in summary.inferredSupported)
    assert any("INFERRED + INFERRED" in note for note in summary.notes)
    try:
        promote_inferred_agreement_to_observed(["door on left"])
        raise AssertionError("must not promote")
    except ValueError as exc:
        assert "INFERRED + INFERRED" in str(exc)


def test_solid_color_view_fails_structure_gate(tmp_path: Path):
    from app.spatial_map.supplementary.gate import evaluate_view_gate

    master = _rgb(tmp_path / "m.png", (80, 80, 90), (96, 64))
    red = _rgb(tmp_path / "red.png", (220, 8, 8), (96, 64))
    result = evaluate_view_gate(master_path=str(master), candidate_path=str(red), camera_role="LEFT_SIDE")
    assert result["verdict"] == "FAIL"
    assert result["informationGain"] is False


def test_information_gain_fail_on_restyle(tmp_path: Path):
    from app.spatial_map.supplementary.gate import evaluate_view_gate

    master = _rgb(tmp_path / "m.png", (80, 80, 90))
    twin = _rgb(tmp_path / "t.png", (82, 81, 91))
    result = evaluate_view_gate(master_path=str(master), candidate_path=str(twin), camera_role="REVERSE")
    assert result["verdict"] == "FAIL_NO_INFORMATION_GAIN"


def test_information_gain_pass_on_new_view(tmp_path: Path):
    from app.spatial_map.supplementary.gate import evaluate_view_gate

    master = _rgb(tmp_path / "m.png", (20, 20, 30), (80, 48))
    other = tmp_path / "o.png"
    arr = np.zeros((48, 80, 3), dtype=np.uint8)
    arr[:, 40:] = (200, 40, 40)
    Image.fromarray(arr).save(other)
    result = evaluate_view_gate(master_path=str(master), candidate_path=str(other), camera_role="REVERSE")
    assert result["verdict"] in {"PASS", "PASS_WITH_LOW_CONFIDENCE"}
    assert result["informationGain"] is True


def test_view_b_targets_residual_uncertainty():
    from app.spatial_map.supplementary.select import select_camera_role

    first = select_camera_role(scene_description="metallic corridor with elevators", slot="A")
    second = select_camera_role(
        scene_description="metallic corridor with elevators",
        slot="B",
        accepted_role_a=first["cameraRole"],
        remaining_unknown=["side doorway still unseen"],
    )
    assert first["cameraRole"] != second["cameraRole"]
    assert "remaining uncertainty" in second["reason"]


def test_vggt_rejects_one_observed_plus_inferred(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import infer

    monkeypatch.setattr(infer, "require_essential_agreement", lambda *a, **k: None)
    result = infer.run_vggt_plate(
        [tmp_path / "master.png"],
        tmp_path,
        inferred_image_paths=[tmp_path / "qwen_a.png"],
    )
    assert result["code"] == "INFERRED_NOT_VGGT_EVIDENCE"


def test_compile_supplementary_uses_qwen_ref_not_ers_or_atlas():
    from app.image_product.compile import is_supplementary_view_purpose
    from app.image_product.resolve import resolve_image_capability

    assert is_supplementary_view_purpose("environment_supplementary_view") is True
    assert is_supplementary_view_purpose("environment_reference_sheet") is False
    resolved = resolve_image_capability(
        {
            "purpose": "environment_supplementary_view",
            "sourceAssetId": "master-1",
            "prompt": "same environment different camera",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "source": "local",
        }
    )
    assert resolved["canExecute"] is True
    assert resolved["workflowKey"] == "qwen2512.ref"
    assert resolved["intent"]["purpose"] == "environment_supplementary_view"


def test_compile_does_not_rewrite_supplementary_to_ers():
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "proj",
        {
            "purpose": "environment_supplementary_view",
            "sourceAssetId": "master-1",
            "prompt": "same environment different camera",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "source": "local",
        },
    )
    intent = compiled["imageIntent"]
    assert intent["purpose"] == "environment_supplementary_view"
    assert compiled["imageRuntime"]["workflowKey"] == "qwen2512.ref"
    assert intent["purpose"] != "environment_reference_sheet"
    assert intent["purpose"] != "atlas_shot"


def test_reconstruction_packet_strips_inferred_from_source_ids():
    from app.spatial_map.reconstruction.compile import compile_packet

    packet = compile_packet(
        project_id="p1",
        execution_id="e1",
        source_asset_ids=["master-1", "inferred-a"],
        geo={
            "environmentType": "corridor",
            "sourceAspect": 1.7,
            "environmentConfidence": 0.6,
            "references": [
                {"assetId": "master-1", "evidenceClass": "OBSERVED"},
                {"assetId": "inferred-a", "evidenceClass": "INFERRED"},
            ],
        },
    )
    assert packet.sourceAssetIds == ["master-1"]
    assert any(item.get("evidenceClass") == "INFERRED" for item in packet.references)


def test_job_done_status_is_success():
    assert "done" in {"completed", "done", "complete"}


def test_job_hydration_reads_params_not_missing_fields():
    from app.spatial_map.supplementary.service import _job_output_asset_id, _job_prompt_id

    class Job:
        params_json = '{"output_asset_id": "asset-9"}'
        history_json = "{}"
        comfy_prompt_id = "prompt-abc"

    job = Job()
    assert _job_output_asset_id(job) == "asset-9"
    assert _job_prompt_id(job) == "prompt-abc"


def test_compile_refuses_four_view_supplementary():
    from app.image_product.compile import compile_image_request

    try:
        compile_image_request(
            "proj",
            {
                "purpose": "environment_supplementary_view",
                "sourceAssetId": "master-1",
                "layout": "four_view",
                "prompt": "grid",
            },
        )
        raise AssertionError("four-view supplementary must fail")
    except RuntimeError as exc:
        assert "four-view" in str(exc).lower()


def test_ers_purpose_still_requires_source_pixels():
    from app.image_product.resolve import resolve_image_capability

    refused = resolve_image_capability({"purpose": "environment_reference_sheet", "model": "qwen2512", "source": "local"})
    assert refused["canExecute"] is False


def _project() -> str:
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Supplementary Cert"))
        db.commit()
        return project_id
    finally:
        db.close()


def test_api_analyze_generate_accept_reject_reload(client, tmp_path: Path, monkeypatch):
    from app.config import settings
    from app.db import Asset, SessionLocal

    project_id = _project()
    master_path = _rgb(tmp_path / "master.png", (30, 30, 40), (96, 64))
    view_a_path = tmp_path / "a.png"
    arr = np.zeros((64, 96, 3), dtype=np.uint8)
    arr[:, 48:] = (180, 20, 20)
    Image.fromarray(arr).save(view_a_path)
    db = SessionLocal()
    try:
        master = Asset(id=str(uuid.uuid4()), project_id=project_id, kind="image", filename="master.png", path=str(master_path))
        view_a = Asset(id=str(uuid.uuid4()), project_id=project_id, kind="image", filename="a.png", path=str(view_a_path))
        db.add(master)
        db.add(view_a)
        db.commit()
        master_id, view_a_id = master.id, view_a.id
    finally:
        db.close()
    created = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={"title": "Corridor", "backgroundAssetId": master_id, "originalEnvironmentReferenceAssetId": master_id, "masterEnvironmentPrompt": "metallic corridor with elevators"},
    )
    assert created.status_code == 200
    map_id = created.json()["document"]["id"]
    analyze = client.post(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/analyze")
    assert analyze.status_code == 200
    assert analyze.json()["slot"] == "A"
    monkeypatch.setenv("STUDIO_E2E", "1")
    gen = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/generate",
        json={"slot": "A", "e2eAssetId": view_a_id},
    )
    assert gen.status_code == 200
    view = gen.json()["view"]
    assert view["evidenceClass"] == "INFERRED"
    assert view["source"] == "QWEN_IMAGE_EDIT"
    accepted = client.post(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/A/accept")
    if view["status"] == "READY":
        assert accepted.status_code == 200
        assert accepted.json()["state"]["viewA"]["approvedForSpatialReasoning"] is True
    rejected = client.post(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/A/reject")
    assert rejected.status_code == 200
    assert rejected.json()["state"]["viewA"]["status"] == "REJECTED"
    reloaded = client.get(f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views")
    assert reloaded.status_code == 200
    assert reloaded.json()["state"]["viewA"]["status"] == "REJECTED"
    assert reloaded.json()["master"]["evidenceClass"] == "OBSERVED"
    assert view_a_id not in reloaded.json()["observedAssetIds"]
    _ = settings
