"""Prop Creator generator parity — checked sources x batchCount, no family swap."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.prop_creator import generation as prop_gen
from app.prop_creator.generation import build_prop_candidate_plans


def _families(*rows):
    return list(rows)


def _catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        prop_gen,
        "list_local_generator_families",
        lambda has_reference=False: _families(
            {"id": "zimage", "label": "Z-Image Turbo", "executable": True, "supportsReferences": True},
            {"id": "qwen2512", "label": "Qwen Image 2512", "executable": True, "supportsReferences": False},
            {"id": "illustrious", "label": "Illustrious XL", "executable": True, "supportsReferences": False},
            {"id": "flux", "label": "FLUX.1", "executable": True, "supportsReferences": True},
        ),
    )


def test_local_per_model_expansion(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=1,
        generator_sources={
            "local": [
                {"modelId": "zimage", "enabled": True, "batchCount": 2},
                {"modelId": "illustrious", "enabled": True, "batchCount": 3},
            ],
            "api": None,
        },
    )
    assert [p["family"] for p in plans] == ["zimage", "zimage", "illustrious", "illustrious", "illustrious"]
    assert all(p["source"] == "local" for p in plans)
    assert plans[0]["batch_of"] == 2
    assert plans[2]["batch_of"] == 3


def test_api_per_model_expansion(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=2,
        generator_sources={
            "local": None,
            "api": [
                {"modelId": "nano-banana-kie", "providerId": "kie", "enabled": True, "batchCount": 2},
                {"modelId": "flux-pro", "providerId": "fal", "model": "flux-pro", "enabled": True, "batchCount": 1},
            ],
        },
    )
    assert len(plans) == 3
    assert all(p["source"] == "api" for p in plans)
    assert [p["model_id"] for p in plans] == ["nano-banana-kie", "nano-banana-kie", "flux-pro"]
    assert plans[0]["provider_id"] == "kie"
    assert plans[2]["provider_id"] == "fal"


def test_mixed_local_and_api_expansion(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=3,
        generator_sources={
            "local": [{"modelId": "zimage", "enabled": True, "batchCount": 1}],
            "api": [{"modelId": "imagen-4", "providerId": "google", "enabled": True, "batchCount": 2}],
        },
    )
    assert [p["source"] for p in plans] == ["local", "api", "api"]
    assert plans[0]["family"] == "zimage"
    assert plans[1]["model_id"] == "imagen-4"
    assert plans[2]["model_id"] == "imagen-4"


def test_unchecked_sources_are_omitted(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=4,
        generator_sources={
            "local": [
                {"modelId": "zimage", "enabled": True, "batchCount": 1},
                {"modelId": "qwen2512", "enabled": False, "batchCount": 4},
                {"modelId": "illustrious", "enabled": False, "batchCount": 4},
            ],
            "api": [
                {"modelId": "flux-pro", "enabled": False, "batchCount": 4},
            ],
        },
    )
    assert [p["family"] for p in plans] == ["zimage"]
    assert all(p["family"] != "qwen2512" for p in plans)
    assert all(p["source"] != "api" for p in plans)


def test_all_unchecked_is_zero_jobs(monkeypatch) -> None:
    _catalog(monkeypatch)
    try:
        build_prop_candidate_plans(
            generator_sources={
                "local": [{"modelId": "zimage", "enabled": False, "batchCount": 4}],
                "api": [{"modelId": "flux-pro", "enabled": False, "batchCount": 2}],
            }
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Enable a Local or API generator" in str(exc)


def test_cloud_master_off_is_zero_api_jobs(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=5,
        generator_sources={
            "local": [{"modelId": "zimage", "enabled": True, "batchCount": 1}],
            "api": None,
        },
    )
    assert len(plans) == 1
    assert plans[0]["source"] == "local"


def test_local_master_off_is_zero_local_jobs(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=6,
        generator_sources={
            "local": None,
            "api": [{"modelId": "flux-pro", "enabled": True, "batchCount": 2}],
        },
    )
    assert len(plans) == 2
    assert all(p["source"] == "api" for p in plans)


def test_description_guided_when_no_reference(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        has_reference=False,
        seed=7,
        generator_sources={
            "local": [
                {"modelId": "zimage", "enabled": True, "batchCount": 1},
                {"modelId": "illustrious", "enabled": True, "batchCount": 1},
            ],
            "api": None,
        },
    )
    assert all(p["conditioning"] == "description_guided" for p in plans)
    assert all("Description Guided" in p["provenance_label"] for p in plans)


def test_reference_conditioned_only_when_model_supports_and_mode_allows(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        has_reference=True,
        seed=8,
        generator_sources={
            "local": [
                {"modelId": "zimage", "enabled": True, "batchCount": 1, "generationMode": "Reference Conditioned"},
                {"modelId": "illustrious", "enabled": True, "batchCount": 1, "generationMode": "Description Guided"},
                {"modelId": "qwen2512", "enabled": True, "batchCount": 1},
            ],
            "api": None,
        },
    )
    by = {p["family"]: p for p in plans}
    assert by["zimage"]["conditioning"] == "reference_conditioned"
    assert by["illustrious"]["conditioning"] == "description_guided"
    assert by["qwen2512"]["conditioning"] == "description_guided"


def test_explicit_description_guided_skips_reference_pixels(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        has_reference=True,
        seed=9,
        generator_sources={
            "local": [
                {"modelId": "zimage", "enabled": True, "batchCount": 1, "generationMode": "Description Guided"},
            ],
            "api": None,
        },
    )
    assert plans[0]["conditioning"] == "description_guided"
    assert plans[0]["workflow_key"] == "zimage.txt2img"


def test_no_all_family_fanout_when_only_zimage_checked(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=10,
        candidate_count=4,
        generator_sources={
            "local": [{"modelId": "zimage", "enabled": True, "batchCount": 4}],
            "api": None,
        },
    )
    assert len(plans) == 4
    assert {p["family"] for p in plans} == {"zimage"}
    assert all(p["family"] != "qwen2512" for p in plans)
    assert all(p["family"] != "illustrious" for p in plans)
    assert all(p["family"] != "flux" for p in plans)


def test_legacy_zimage_scalar_does_not_enqueue_qwen(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        local_enabled=True,
        api_enabled=False,
        local_family="zimage",
        candidate_count=4,
        seed=11,
    )
    assert len(plans) == 4
    assert {p["family"] for p in plans} == {"zimage"}
    assert "qwen2512" not in {p["family"] for p in plans}


def test_style_engine_does_not_invent_jobs(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=12,
        generator_sources={
            "local": [{"modelId": "zimage", "enabled": True, "batchCount": 1}],
            "api": None,
            "styleEngine": {"enabled": True, "modelId": "zimage"},
        },
    )
    assert len(plans) == 1
    assert plans[0]["family"] == "zimage"
    assert all(not p.get("style_engine") for p in plans)


def test_generate_zimage_only_does_not_enqueue_qwen(monkeypatch) -> None:
    from app.db import Project, SessionLocal, init_db
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    _catalog(monkeypatch)
    captured: list[dict] = []

    def _enqueue(_db, _project_id, body):
        captured.append(body)
        return SimpleNamespace(id=str(uuid.uuid4()), status="queued", params_json="{}")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Zimage Only"))
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Mug")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": [{"modelId": "zimage", "enabled": True, "batchCount": 3}],
                "api": None,
            },
        )
        assert len(generated.candidates) == 3
        assert {c.family for c in generated.candidates} == {"zimage"}
        assert len(captured) == 3
        assert all(b["modelFamilyPreference"] == "zimage" for b in captured)
        assert all(b.get("forceWorkflowKey") == "zimage.txt2img" for b in captured)
        assert all(b.get("allow_force_workflow_key") is True for b in captured)
        assert all("qwen" not in str(b["modelFamilyPreference"]) for b in captured)
    finally:
        db.close()


def test_api_row_fails_honestly_without_local_substitute(monkeypatch) -> None:
    from app.db import Project, SessionLocal, init_db
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    _catalog(monkeypatch)

    def _enqueue(_db, _project_id, body):
        if body.get("providerPreference") == "cloud":
            raise RuntimeError("no hosted route")
        return SimpleNamespace(id=str(uuid.uuid4()), status="queued", params_json="{}")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="API Honest"))
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Chair")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": [{"modelId": "zimage", "enabled": True, "batchCount": 1}],
                "api": [{"modelId": "flux-pro", "providerId": "fal", "enabled": True, "batchCount": 1}],
            },
        )
        assert len(generated.candidates) == 2
        local = next(c for c in generated.candidates if c.source == "local")
        api = next(c for c in generated.candidates if c.source == "api")
        assert local.status == "queued"
        assert local.family == "zimage"
        assert api.status == "failed"
        assert "No certified API route" in api.error
        assert "flux-pro" in api.error
        assert "Not Available" not in api.error
    finally:
        db.close()


def test_use_as_prop_identity_points_at_existing_asset() -> None:
    from app.db import Asset, Project, SessionLocal, init_db
    from app.prop_creator.service import create_or_update_prop, use_as_prop_identity

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Identity"))
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="ref",
            kind="image",
            filename="mug.png",
            path="mug.png",
            production_approval="none",
        )
        db.add(asset)
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Mug", reference_asset_id=asset.id)
        prop_id = prop.id
        updated = use_as_prop_identity(db, project_id, prop_id, asset_id=asset.id, source_type="upload")
        assert updated.id == prop_id
        assert updated.approved_asset_id == asset.id
        assert updated.library_asset_id == asset.id
        assert updated.reference_asset_id == asset.id
        db.refresh(asset)
        assert asset.production_approval == "approved"
        labels = json.loads(asset.labels_json or "[]")
        assert "approved_prop" in labels
    finally:
        db.close()
