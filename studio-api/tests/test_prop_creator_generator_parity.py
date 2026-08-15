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



def test_discovered_hosted_image_models_uses_all_keyed(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _dock(modality, scope=None):
        seen["modality"] = modality
        seen["scope"] = scope
        return {
            "scope": "all_keyed",
            "models": [
                {"id": "nano-banana-kie", "providerId": "kie", "modality": "image"},
                {"id": "flux-fal", "providerId": "fal", "modality": "image"},
            ],
        }

    monkeypatch.setattr("app.hosted_providers.discovery.dock_api_models", _dock)
    rows = prop_gen.discovered_hosted_image_models()
    assert seen["modality"] == "image"
    assert [r["id"] for r in rows] == ["nano-banana-kie", "flux-fal"]
    assert all(r["providerId"] != "wavespeed" for r in rows)


def test_api_kie_plan_family_is_kie_not_imagen(monkeypatch) -> None:
    _catalog(monkeypatch)
    plans = build_prop_candidate_plans(
        seed=21,
        generator_sources={
            "local": None,
            "api": [
                {"modelId": "nano-banana-kie", "providerId": "kie", "enabled": True, "batchCount": 1},
                {"modelId": "flux-kie", "providerId": "kie", "enabled": True, "batchCount": 1},
            ],
        },
    )
    assert [p["family"] for p in plans] == ["kie", "kie"]
    assert plans[0]["hosted_model_id"] == "nano-banana-kie"
    assert plans[1]["hosted_model_id"] == "flux-kie"
    assert plans[0].get("kie_image_model_id") in (None, "")
    assert plans[1].get("kie_image_model_id") in (None, "")


def test_enqueue_kie_pins_official_id(monkeypatch) -> None:
    from app.db import Job, Project, SessionLocal, init_db
    from app.image_product.compile import compile_image_request
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    _catalog(monkeypatch)
    captured: list[dict] = []

    def _enqueue(_db, _project_id, body):
        captured.append(dict(body))
        compiled = compile_image_request(_project_id, body)
        runtime = compiled.get("imageRuntime") or {}
        job = Job(
            id=str(uuid.uuid4()),
            project_id=_project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(
                {
                    "cloudPaid": runtime.get("provider") == "kie",
                    "kieImageModelId": compiled.get("kieImageModelId") or runtime.get("kieImageModelId"),
                    "hostedModelId": body.get("hostedModelId") or compiled.get("hostedModelId"),
                    "officialModelId": runtime.get("officialModelId"),
                    "imageRuntime": runtime,
                }
            ),
        )
        _db.add(job)
        _db.commit()
        _db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr("app.secrets_store.get_secret", lambda _name: "test-kie-key")
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Kie Pin"))
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Mug")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": None,
                "api": [
                    {"modelId": "nano-banana-kie", "providerId": "kie", "enabled": True, "batchCount": 2},
                ],
            },
        )
        assert len(generated.candidates) == 2
        assert all(c.status == "queued" for c in generated.candidates)
        assert len(captured) == 2
        for body in captured:
            assert body.get("hostedModelId") == "nano-banana-kie"
            assert body.get("source") == "api"
            assert body.get("kieImageModelId") in (None, "")
            assert body.get("providerPreference") == "cloud"
        job = db.get(Job, generated.candidates[0].job_id)
        params = json.loads(job.params_json or "{}")
        runtime = params.get("imageRuntime") or {}
        assert params.get("kieImageModelId") == "nano-banana-2"
        assert params.get("cloudPaid") is True
        assert runtime.get("workflowKey") == "kie:nano-banana-2"
        assert runtime.get("provider") == "kie"
        assert runtime.get("adapter") == "kie"
        assert runtime.get("officialModelId") == "nano-banana-2"
    finally:
        db.close()


def test_enqueue_fal_does_not_false_pin_kie_via_flux_family(monkeypatch) -> None:
    from app.db import Job, Project, SessionLocal, init_db
    from app.image_product.compile import compile_image_request
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    _catalog(monkeypatch)
    captured: list[dict] = []

    def _enqueue(_db, _project_id, body):
        captured.append(dict(body))
        compiled = compile_image_request(_project_id, body)
        runtime = compiled.get("imageRuntime") or {}
        job = Job(
            id=str(uuid.uuid4()),
            project_id=_project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(
                {
                    "cloudPaid": runtime.get("provider") == "fal",
                    "hostedModelId": body.get("hostedModelId") or compiled.get("hostedModelId"),
                    "falImageModelId": compiled.get("falImageModelId") or runtime.get("falImageModelId"),
                    "kieImageModelId": compiled.get("kieImageModelId") or runtime.get("kieImageModelId"),
                    "officialModelId": runtime.get("officialModelId"),
                    "imageRuntime": runtime,
                }
            ),
        )
        _db.add(job)
        _db.commit()
        _db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    monkeypatch.setattr(
        "app.fal_catalog.fal_image_model_id_for_dock",
        lambda mid: "fal-ai/flux/dev" if mid == "flux-fal" else None,
    )
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Fal Pin"))
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Chair")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": None,
                "api": [
                    {"modelId": "flux-fal", "providerId": "fal", "enabled": True, "batchCount": 1},
                ],
            },
        )
        assert len(generated.candidates) == 1
        assert generated.candidates[0].status == "queued"
        assert len(captured) == 1
        body = captured[0]
        assert body.get("hostedModelId") == "flux-fal"
        assert body.get("source") == "api"
        assert body.get("kieImageModelId") in (None, "")
        job = db.get(Job, generated.candidates[0].job_id)
        params = json.loads(job.params_json or "{}")
        runtime = params.get("imageRuntime") or {}
        assert params.get("falImageModelId") == "fal-ai/flux/dev"
        assert params.get("kieImageModelId") in (None, "")
        assert params.get("cloudPaid") is True
        assert runtime.get("provider") == "fal"
        assert runtime.get("adapter") == "fal"
        assert runtime.get("officialModelId") == "fal-ai/flux/dev"
        assert runtime.get("workflowKey") == "fal:fal-ai/flux/dev"
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


def test_prop_local_flux_job_does_not_call_imagegen_kie(monkeypatch) -> None:
    """Local flux Prop jobs must not alias to flux-kie or enter _imagegen_kie."""
    from app.db import Job, Project, SessionLocal, init_db
    from app.hosted_providers.adapters.kie_adapter import kie_image_model_id_for_dock
    from app.image_product.compile import compile_image_request
    from app.prop_creator.service import create_or_update_prop, generate_candidates

    assert kie_image_model_id_for_dock("flux") is None
    assert kie_image_model_id_for_dock("flux-kie") == "flux"

    _catalog(monkeypatch)
    compiled_params: list[dict] = []

    def _enqueue(_db, _project_id, body):
        compiled = compile_image_request(_project_id, body)
        runtime = compiled.get("imageRuntime") or {}
        params = {
            "kieImageModelId": compiled.get("kieImageModelId") or runtime.get("kieImageModelId"),
            "imageRuntime": runtime,
            "imageIntent": compiled.get("imageIntent"),
        }
        compiled_params.append(params)
        job = Job(
            id=str(uuid.uuid4()),
            project_id=_project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(params),
        )
        _db.add(job)
        _db.commit()
        _db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name="Local Flux Isolation"))
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Mug")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": [{"modelId": "flux", "enabled": True, "batchCount": 1}],
                "api": None,
            },
        )
        assert len(generated.candidates) == 1
        cand = generated.candidates[0]
        assert cand.source == "local"
        assert cand.family == "flux"
        assert cand.status == "queued"
        assert compiled_params
        params = compiled_params[0]
        kie_image_model = str(params.get("kieImageModelId") or "").strip()
        assert kie_image_model == ""
        runtime = params.get("imageRuntime") or {}
        assert not str(runtime.get("workflowKey") or "").startswith("kie:")
        assert runtime.get("provider") != "kie"
        assert runtime.get("engine") != "kie"
        # queue_worker._imagegen calls _imagegen_kie only when kieImageModelId is set.
        called: list[str] = []
        if kie_image_model:
            called.append("_imagegen_kie")
        assert called == []
    finally:
        db.close()

def test_local_flux_compile_is_not_kie_route() -> None:
    from app.hosted_providers.adapters.kie_adapter import kie_image_model_id_for_dock
    from app.image_product.compile import _kie_image_route, compile_image_request

    assert kie_image_model_id_for_dock("flux") is None
    assert kie_image_model_id_for_dock("flux-kie") == "flux"

    local_body = {
        "prompt": "a brass mug on a table",
        "purpose": "project_prop",
        "modelFamilyPreference": "flux",
        "model": "flux",
        "lockModelFamily": True,
        "source": "local",
        "forceWorkflowKey": "flux.txt2img",
        "allow_force_workflow_key": True,
        "creativeContext": {"objective": "project_prop", "providerKind": "local"},
    }
    assert _kie_image_route(local_body) is None
    assert _kie_image_route({"modelFamilyPreference": "flux", "model": "flux"}) is None
    hosted = _kie_image_route({"hostedModelId": "flux-kie", "prompt": "a mug"})
    assert hosted == {"dock": "flux-kie", "official": "flux"}
    pinned = _kie_image_route({"kieImageModelId": "flux", "hostedModelId": "flux-kie"})
    assert pinned == {"dock": "flux-kie", "official": "flux"}

    try:
        compiled = compile_image_request("proj-local-flux", local_body)
    except RuntimeError as exc:
        msg = str(exc)
        assert "kie:" not in msg.lower()
        assert "createtask" not in msg.lower()
        assert "flux" in msg.lower() or "not installed" in msg.lower()
        return
    assert compiled.get("kieImageModelId") in (None, "")
    wk = str((compiled.get("imageRuntime") or {}).get("workflowKey") or "")
    assert not wk.startswith("kie:")
    assert compiled.get("hostedModelId") in (None, "", "flux")


def test_local_flux_prop_does_not_call_imagegen_kie(monkeypatch) -> None:
    """UI-selected local FLUX must not alias to flux-kie or call createTask."""
    import asyncio
    import json
    import uuid

    from app.db import Job, Project, SessionLocal, init_db
    from app.image_product.compile import _kie_image_route
    from app.prop_creator.service import create_or_update_prop, generate_candidates
    from app.queue_worker import JobQueue

    _catalog(monkeypatch)
    kie_calls: list[str] = []

    async def _spy_kie(self, db, job, project, params, model_id, edit_op="generate"):
        kie_calls.append(str(model_id))
        raise AssertionError("local flux must not call _imagegen_kie")

    async def _spy_fal(self, db, job, project, params, model_id, edit_op="generate"):
        raise AssertionError("local flux must not call _imagegen_fal")

    monkeypatch.setattr(JobQueue, "_imagegen_kie", _spy_kie)
    monkeypatch.setattr(JobQueue, "_imagegen_fal", _spy_fal)

    captured: list[dict] = []

    def _enqueue(_db, _project_id, body):
        captured.append(dict(body))
        assert _kie_image_route(body) is None
        assert body.get("kieImageModelId") in (None, "")
        assert body.get("forceWorkflowKey") == "flux.txt2img"
        assert body.get("source") == "local"
        job = Job(
            id=str(uuid.uuid4()),
            project_id=_project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(
                {
                    "prompt": body.get("prompt"),
                    "model": "flux",
                    "source": "local",
                    "providerPreference": "local",
                    "forceWorkflowKey": "flux.txt2img",
                    "imageRuntime": {"workflowKey": "flux.txt2img", "modelFamily": "flux"},
                    "imageIntent": {
                        "projectId": _project_id,
                        "prompt": body.get("prompt"),
                        "enginePreference": "flux",
                        "providerPreference": "local",
                        "operation": "image.generate",
                        "purpose": "project_prop",
                        "width": 1024,
                        "height": 1024,
                        "metadata": {},
                    },
                }
            ),
        )
        _db.add(job)
        _db.commit()
        _db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        project = Project(id=project_id, name="Local Flux")
        db.add(project)
        db.commit()
        prop = create_or_update_prop(db, project_id, name="Mug")
        generated = generate_candidates(
            db,
            project_id,
            prop.id,
            generator_sources={
                "local": [{"modelId": "flux", "enabled": True, "batchCount": 1}],
                "api": None,
            },
        )
        assert len(generated.candidates) == 1
        cand = generated.candidates[0]
        assert cand.source == "local"
        assert cand.family == "flux"
        assert "LOCAL" in (cand.provenance_label or "")
        assert len(captured) == 1
        body = captured[0]
        assert body.get("modelFamilyPreference") == "flux"
        assert body.get("forceWorkflowKey") == "flux.txt2img"
        assert body.get("source") == "local"
        assert body.get("kieImageModelId") in (None, "")
        assert body.get("hostedModelId") in (None, "")
        assert _kie_image_route(body) is None

        job = db.get(Job, cand.job_id)
        assert job is not None
        params = json.loads(job.params_json or "{}")
        assert params.get("kieImageModelId") in (None, "")

        def _stop_local(*_a, **_k):
            raise RuntimeError("LOCAL_PATH_REACHED")

        monkeypatch.setattr(
            "app.image_runtime.contract.resolve_image_workflow",
            _stop_local,
        )
        worker = JobQueue()

        async def _run():
            await worker._imagegen(db, job, project)

        try:
            asyncio.run(_run())
        except RuntimeError as exc:
            assert "LOCAL_PATH_REACHED" in str(exc)
        except Exception as exc:
            assert "local flux must not call" not in str(exc)
            raise
        assert kie_calls == []
    finally:
        db.close()

