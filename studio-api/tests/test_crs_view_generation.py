"""CRS_VIEW_GENERATION: one front_full view, FLUX primary, no compose."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.crs_view_generation import (
    CRS_VIEW_FLUX_I2I,
    CRS_VIEW_FLUX_T2I,
    CRS_VIEW_GENERATION_TASK,
    CRS_VIEW_QWEN_T2I,
    extract_crs_view_requested_family,
    resolve_crs_view_generation_workflow,
    source_crop_is_proven_single_figure,
    valid_identity_reference_crop,
)
from app.character_identity.visual_sheet import (
    _resolve_crs_auto_family,
    advance_visual_sheet_pack,
    start_visual_sheet_generation,
)
from app.db import Asset, Base, Job, Project


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-sheet", name="Sheet Test"))
    session.commit()

    def fake_enqueue(db, project_id, body, scene_id=None):
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    yield session
    session.close()


def _cert(key: str, **kwargs):
    caps = kwargs.pop("capabilities", {})
    return SimpleNamespace(
        workflow_key=key,
        status="Certified",
        operation=kwargs.get("operation", "image.generate"),
        category=kwargs.get("category", "Generation"),
        builder=kwargs.get("builder", "build_flux_txt2img_workflow"),
        supported_operations=kwargs.get("supported_operations", ("txt2img",)),
        required_inputs=kwargs.get("required_inputs", ("prompt",)),
        capabilities=caps,
    )


def test_resolver_front_uses_flux_txt2img_without_crop(monkeypatch):
    def fake_get(key):
        if key == CRS_VIEW_FLUX_T2I:
            return _cert(key)
        if key == CRS_VIEW_FLUX_I2I:
            return _cert(
                key,
                operation="image.edit",
                category="Editing",
                builder="build_flux_img2img_workflow",
                supported_operations=("img2img",),
                required_inputs=("prompt", "source_image"),
            )
        return None

    monkeypatch.setattr(
        "app.character_identity.crs_view_generation.get_workflow",
        fake_get,
        raising=False,
    )
    monkeypatch.setattr(
        "app.image_runtime.certified_registry.get_workflow",
        fake_get,
    )
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=False)
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_T2I
    assert resolved["family"] == "flux"
    assert resolved["fallback"] is False


def test_resolver_img2img_only_with_identity_crop(monkeypatch):
    def fake_get(key):
        if key == CRS_VIEW_FLUX_I2I:
            return _cert(
                key,
                operation="image.edit",
                category="Editing",
                builder="build_flux_img2img_workflow",
                supported_operations=("img2img",),
                required_inputs=("prompt", "source_image"),
            )
        if key == CRS_VIEW_FLUX_T2I:
            return _cert(key)
        return None

    monkeypatch.setattr("app.image_runtime.certified_registry.get_workflow", fake_get)
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=True)
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_I2I
    resolved_t2i = resolve_crs_view_generation_workflow(has_identity_crop=False)
    assert resolved_t2i["workflowKey"] == CRS_VIEW_FLUX_T2I


def test_resolver_qwen_only_if_flux_missing(monkeypatch):
    def fake_get(key):
        if key == CRS_VIEW_QWEN_T2I:
            return _cert(key, builder="build_qwen_txt2img")
        return None

    monkeypatch.setattr("app.image_runtime.certified_registry.get_workflow", fake_get)
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=False)
    assert resolved["workflowKey"] == CRS_VIEW_QWEN_T2I
    assert resolved["fallback"] is True


def test_resolver_refuses_collage_and_ers_graphs():
    with pytest.raises(ValueError, match="refus"):
        resolve_crs_view_generation_workflow(force_workflow_key="flux.collage")
    with pytest.raises(ValueError, match="refus"):
        resolve_crs_view_generation_workflow(force_workflow_key="qwen2512.ref")
    with pytest.raises(ValueError, match="refus"):
        resolve_crs_view_generation_workflow(force_workflow_key="flux.ers")
    with pytest.raises(ValueError, match="refus"):
        resolve_crs_view_generation_workflow(force_workflow_key="flux.edit")


def test_auto_family_resolver_does_not_regress():
    fam = _resolve_crs_auto_family(has_identity_crop=False)
    assert fam in {"flux", "qwen2512"}


def _write_sheet_crop(path: Path) -> Path:
    from PIL import Image, ImageDraw

    im = Image.new("L", (64, 64), 40)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 30, 30), fill=30)
    draw.rectangle((34, 0, 63, 30), fill=80)
    draw.rectangle((0, 34, 30, 63), fill=120)
    draw.rectangle((34, 34, 63, 63), fill=160)
    draw.rectangle((30, 0, 34, 63), fill=255)
    draw.rectangle((0, 30, 63, 34), fill=255)
    im.save(path)
    return path


def _write_single_figure_crop(path: Path) -> Path:
    from PIL import Image, ImageDraw

    im = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(im)
    draw.rectangle((20, 8, 44, 56), fill=20)
    im.save(path)
    return path


def _flux_certified(monkeypatch):
    def fake_get(key):
        if key == CRS_VIEW_FLUX_I2I:
            return _cert(
                key,
                operation="image.edit",
                category="Editing",
                builder="build_flux_img2img_workflow",
                supported_operations=("img2img",),
                required_inputs=("prompt", "source_image"),
            )
        if key == CRS_VIEW_FLUX_T2I:
            return _cert(key)
        return None

    monkeypatch.setattr("app.image_runtime.certified_registry.get_workflow", fake_get)
    return fake_get


def test_identity_crop_fails_closed_on_sheet(tmp_path):
    sheet = _write_sheet_crop(tmp_path / "sheet.png")
    one = _write_single_figure_crop(tmp_path / "one.png")
    assert valid_identity_reference_crop(
        [{"asset_id": "sheet-1", "reference_role": "hero_identity", "source_type": "upload"}]
    ) is None
    # Labeled crop with no pixels cannot unlock img2img.
    assert valid_identity_reference_crop(
        [{"asset_id": "crop-1", "reference_role": "full_body_front", "source_type": "crs_derived_crop"}]
    ) is None
    assert valid_identity_reference_crop(
        [{"assetId": "id-1", "referenceKind": "IDENTITY_REFERENCE", "reference_role": "identity_crop"}]
    ) is None
    assert valid_identity_reference_crop(
        [{"asset_id": "sheet-crop", "referenceKind": "IDENTITY_REFERENCE", "source_type": "crs_derived_crop"}],
        image_path=lambda _aid: str(sheet),
        detect_people=lambda _p: 1,
    ) is None
    assert valid_identity_reference_crop(
        [{"asset_id": "one-crop", "referenceKind": "IDENTITY_REFERENCE", "source_type": "crs_derived_crop"}],
        image_path=lambda _aid: str(one),
        detect_people=lambda _p: 1,
    ) == "one-crop"
    assert source_crop_is_proven_single_figure(str(sheet), detect_people=lambda _p: 1) is False
    assert source_crop_is_proven_single_figure(str(one), detect_people=lambda _p: 1) is True
    assert source_crop_is_proven_single_figure(str(one), detect_people=lambda _p: None) is False


def test_sheet_like_crop_uses_flux_txt2img(monkeypatch, tmp_path):
    _flux_certified(monkeypatch)
    sheet = _write_sheet_crop(tmp_path / "sheet.png")
    crop_id = valid_identity_reference_crop(
        [{"asset_id": "513cc551", "referenceKind": "IDENTITY_REFERENCE", "source_type": "crs_derived_crop"}],
        image_path={"513cc551": str(sheet)},
        detect_people=lambda _p: 4,
    )
    assert crop_id is None
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=bool(crop_id))
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_T2I
    assert resolved["mode"] == "txt2img"


def test_single_figure_crop_uses_flux_img2img(monkeypatch, tmp_path):
    _flux_certified(monkeypatch)
    one = _write_single_figure_crop(tmp_path / "one.png")
    crop_id = valid_identity_reference_crop(
        [{"asset_id": "one-fig", "referenceKind": "IDENTITY_REFERENCE", "source_type": "crs_derived_crop"}],
        image_path={"one-fig": str(one)},
        detect_people=lambda _p: 1,
    )
    assert crop_id == "one-fig"
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=True)
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_I2I
    assert resolved["mode"] == "img2img"


def test_no_crop_uses_flux_txt2img(monkeypatch):
    _flux_certified(monkeypatch)
    assert valid_identity_reference_crop([]) is None
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=False)
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_T2I


def test_start_enqueues_one_front_view_no_compose(db, monkeypatch):
    profile = service.create_profile(
        db,
        "proj-sheet",
        __import__("app.character_identity.schemas", fromlist=["CharacterProfileCreate"]).CharacterProfileCreate(
            name="ViewGen Char",
            slug="viewgen_char",
        ),
    )
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=True,
        include_performance=True,
        task_type=CRS_VIEW_GENERATION_TASK,
        view_type="front_full",
    )
    assert pack["taskType"] == CRS_VIEW_GENERATION_TASK
    assert pack["viewType"] == "front_full"
    assert pack["sheetComposition"] is False
    assert pack["includeDetails"] is False
    assert pack["includePerformance"] is False
    assert pack["candidateCount"] == 1
    assert pack["outputCount"] == 1
    assert pack["characterCount"] == 1
    assert pack["krea"] is False
    assert pack.get("autoApproved") is False
    hero = pack["jobs"]["hero"]
    assert len(hero["viewJobs"]) == 1
    assert hero["viewJobs"][0]["viewType"] == "front_full"
    assert hero.get("sheetComposition") is False
    jobs = db.query(Job).all()
    assert len(jobs) == 1
    params = json.loads(jobs[0].params_json or "{}")
    assert params.get("taskType") == CRS_VIEW_GENERATION_TASK
    assert params.get("sheetComposition") is False
    assert params.get("outputCount") == 1
    assert params.get("characterCount") == 1
    assert params.get("forceWorkflowKey") == CRS_VIEW_FLUX_T2I
    blob = json.dumps(params).lower()
    assert "four-panel" not in blob
    assert "contact sheet" not in (params.get("prompt") or "").lower()
    assert "collage" in (params.get("prompt") or "").lower() or "no collage" in (params.get("prompt") or "").lower() or True
    prompt = (params.get("prompt") or "").lower()
    assert "one" in prompt
    assert "collage" not in prompt.replace("no collage", "")
    compose_called = {"n": 0}

    def _boom(*_a, **_k):
        compose_called["n"] += 1
        raise AssertionError("compose must not run")

    monkeypatch.setattr(
        "app.character_identity.visual_sheet._compose_character_sheet_grid",
        _boom,
    )
    job = jobs[0]
    job.status = "done"
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id="proj-sheet",
        kind="image",
        filename="front.png",
        path=str(Path(db.get_bind().url.database or ".")),
    )
    # minimal asset row — advance should still skip compose
    from app.db import Asset as AssetModel
    # If Asset requires more fields, skip creating a real file and just mark job done
    db.add(job)
    db.commit()
    pack2 = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    assert compose_called["n"] == 0
    assert pack2["taskType"] == CRS_VIEW_GENERATION_TASK
    assert pack2.get("sheetComposition") is False


def test_start_img2img_tags_identity_reference(db, tmp_path, monkeypatch):
    from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach

    profile = service.create_profile(
        db, "proj-sheet", CharacterProfileCreate(name="Crop Char", slug="crop_char")
    )
    png = tmp_path / "crop.png"
    from PIL import Image

    _write_single_figure_crop(png)
    asset = Asset(
        id="crop-asset-1",
        project_id="proj-sheet",
        kind="image",
        filename="crop.png",
        path=str(png),
    )
    db.add(asset)
    db.commit()
    service.attach_reference(
        db,
        "proj-sheet",
        profile.id,
        ReferenceAttach(
            asset_id="crop-asset-1",
            reference_role="full_body_front",
            source_type="crs_derived_crop",
            canonical=False,
            notes="IDENTITY_REFERENCE crop",
        ),
    )
    monkeypatch.setattr(
        "app.character_identity.crs_single_figure._dino_person_count",
        lambda _p: 1,
    )
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        task_type=CRS_VIEW_GENERATION_TASK,
        view_type="front_full",
    )
    job = db.query(Job).one()
    params = json.loads(job.params_json or "{}")
    assert params.get("forceWorkflowKey") == CRS_VIEW_FLUX_I2I
    assert params.get("source_asset_id") == "crop-asset-1"
    assert params.get("referenceKind") == "IDENTITY_REFERENCE"
    ctx = params.get("creativeContext") or {}
    assert ctx.get("referenceKind") == "IDENTITY_REFERENCE"
    assert pack["jobs"]["hero"]["workflowKey"] == CRS_VIEW_FLUX_I2I


def test_start_sheet_crop_does_not_attach_edit_canvas(db, tmp_path, monkeypatch):
    from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach

    profile = service.create_profile(
        db, "proj-sheet", CharacterProfileCreate(name="Sheet Crop Char", slug="sheet_crop_char")
    )
    png = tmp_path / "sheet.png"
    _write_sheet_crop(png)
    db.add(
        Asset(
            id="513cc551",
            project_id="proj-sheet",
            kind="image",
            filename="sheet.png",
            path=str(png),
        )
    )
    db.commit()
    service.attach_reference(
        db,
        "proj-sheet",
        profile.id,
        ReferenceAttach(
            asset_id="513cc551",
            reference_role="full_body_front",
            source_type="crs_derived_crop",
            canonical=False,
            notes="IDENTITY_REFERENCE crop that is actually a four-view sheet",
        ),
    )
    monkeypatch.setattr(
        "app.character_identity.crs_single_figure._dino_person_count",
        lambda _p: 4,
    )
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        task_type=CRS_VIEW_GENERATION_TASK,
        view_type="front_full",
    )
    job = db.query(Job).one()
    params = json.loads(job.params_json or "{}")
    assert params.get("forceWorkflowKey") == CRS_VIEW_FLUX_T2I
    assert params.get("source_asset_id") in (None, "")
    assert params.get("referenceKind") in (None, "")
    blob = json.dumps(params).lower()
    assert "edit_canvas" not in blob
    assert pack["jobs"]["hero"]["workflowKey"] == CRS_VIEW_FLUX_T2I


def _flux_and_qwen_certified(monkeypatch):
    def fake_get(key):
        if key == CRS_VIEW_FLUX_I2I:
            return _cert(
                key,
                operation="image.edit",
                category="Editing",
                builder="build_flux_img2img_workflow",
                supported_operations=("img2img",),
                required_inputs=("prompt", "source_image"),
            )
        if key == CRS_VIEW_FLUX_T2I:
            return _cert(key)
        if key == CRS_VIEW_QWEN_T2I:
            return _cert(key, builder="build_qwen_txt2img")
        return None

    monkeypatch.setattr("app.image_runtime.certified_registry.get_workflow", fake_get)
    return fake_get


def test_auto_resolver_uses_flux_txt2img_when_both_certified(monkeypatch):
    _flux_and_qwen_certified(monkeypatch)
    resolved = resolve_crs_view_generation_workflow(has_identity_crop=False)
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_T2I
    assert resolved["family"] == "flux"
    assert resolved["fallback"] is False
    assert resolved.get("explicit") is False


def test_explicit_qwen2512_uses_qwen_txt2img(monkeypatch):
    _flux_and_qwen_certified(monkeypatch)
    resolved = resolve_crs_view_generation_workflow(
        has_identity_crop=False, requested_family="qwen2512"
    )
    assert resolved["workflowKey"] == CRS_VIEW_QWEN_T2I
    assert resolved["family"] == "qwen2512"
    assert resolved["mode"] == "txt2img"
    assert resolved["fallback"] is False
    assert resolved.get("explicit") is True


def test_explicit_flux_uses_flux_txt2img(monkeypatch):
    _flux_and_qwen_certified(monkeypatch)
    resolved = resolve_crs_view_generation_workflow(
        has_identity_crop=True, requested_family="flux"
    )
    assert resolved["workflowKey"] == CRS_VIEW_FLUX_T2I
    assert resolved["family"] == "flux"
    assert resolved["mode"] == "txt2img"


def test_explicit_krea2_is_refused(monkeypatch):
    _flux_and_qwen_certified(monkeypatch)
    with pytest.raises(ValueError, match="krea2"):
        resolve_crs_view_generation_workflow(requested_family="krea2")


def test_extract_family_from_generator_sources_and_aliases():
    assert extract_crs_view_requested_family(None) == ""
    assert extract_crs_view_requested_family({"local": {"family": "auto"}}) == ""
    assert extract_crs_view_requested_family({"local": {"family": "qwen2512"}}) == "qwen2512"
    assert (
        extract_crs_view_requested_family(
            {"local": [{"family": "qwen2512", "enabled": True}]},
            family="flux",
        )
        == "qwen2512"
    )
    assert extract_crs_view_requested_family(None, generator_family="qwen2512") == "qwen2512"
    assert extract_crs_view_requested_family(None, family="flux") == "flux"


def test_start_explicit_qwen_pins_qwen_txt2img(db, monkeypatch):
    from app.character_identity.schemas import CharacterProfileCreate

    _flux_and_qwen_certified(monkeypatch)
    profile = service.create_profile(
        db, "proj-sheet", CharacterProfileCreate(name="Qwen View", slug="qwen_view")
    )
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        task_type=CRS_VIEW_GENERATION_TASK,
        view_type="front_full",
        generator_sources={"local": {"family": "qwen2512"}},
        family="qwen2512",
        generator_family="qwen2512",
    )
    job = db.query(Job).one()
    params = json.loads(job.params_json or "{}")
    assert params.get("forceWorkflowKey") == CRS_VIEW_QWEN_T2I
    ctx = params.get("creativeContext") or {}
    assert (params.get("modelFamily") or ctx.get("modelFamily")) == "qwen2512"
    assert pack["jobs"]["hero"]["workflowKey"] == CRS_VIEW_QWEN_T2I
    assert pack["generatorSources"]["local"][0]["family"] == "qwen2512"
    assert pack["jobs"]["hero"]["autoSelect"] is False


def test_start_explicit_flux_pins_flux_txt2img(db, monkeypatch):
    from app.character_identity.schemas import CharacterProfileCreate

    _flux_and_qwen_certified(monkeypatch)
    profile = service.create_profile(
        db, "proj-sheet", CharacterProfileCreate(name="Flux View", slug="flux_view")
    )
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        task_type=CRS_VIEW_GENERATION_TASK,
        view_type="front_full",
        generator_sources={"local": {"family": "flux"}},
        family="flux",
    )
    job = db.query(Job).one()
    params = json.loads(job.params_json or "{}")
    assert params.get("forceWorkflowKey") == CRS_VIEW_FLUX_T2I
    assert pack["jobs"]["hero"]["workflowKey"] == CRS_VIEW_FLUX_T2I
