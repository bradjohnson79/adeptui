"""Character Creator V3 — Front-only generators, Wonder3D multi-view, 21:9 sheet."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image

from app.character_identity.cc_v2 import _active_job_busy, empty_state, generate_view
from app.character_identity.character_sheet_compose import compose_v3_character_sheet
from app.character_identity.wonder3d_runtime import LICENSE_BLOCKER, runtime_status


def test_gpu_probe_rejects_cpu_only(monkeypatch):
    from app.character_identity import multiview_engine

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"devices":[{"name":"cpu","type":"cpu"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: _Resp())
    ready, detail = multiview_engine._gpu_probe()
    assert ready is False
    assert "CUDA" in detail


def test_wonder3d_never_reports_ready():
    status = runtime_status()
    assert status["available"] is False
    assert status["runtimeReady"] is False
    assert status["modelReady"] is False
    assert status["weightsLicense"] == "AGPL-3.0"
    assert LICENSE_BLOCKER in status["blocker"]


def test_generate_back_is_retired(db_v3):
    from app.character_identity import service
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-back", role="fixture"),
    )
    with pytest.raises(HTTPException) as exc:
        generate_view(db_v3, "proj-v3", profile.id, "back")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "BACK_RETIRED"


def test_multiview_generate_requires_front_lock(db_v3):
    from app.character_identity import service
    from app.character_identity.cc_v3_multiview import generate_multiview
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-mv", role="fixture"),
    )
    with pytest.raises(HTTPException) as exc:
        generate_multiview(db_v3, "proj-v3", profile.id)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "FRONT_LOCK_REQUIRED"


def test_multiview_generate_is_honest_when_engine_not_ready(db_v3, monkeypatch):
    from app.character_identity import service
    from app.character_identity.cc_v2 import save_state
    from app.character_identity.cc_v3_multiview import generate_multiview
    from app.character_identity.schemas import CharacterProfileCreate

    monkeypatch.setattr(
        "app.character_identity.multiview_engine.qwen_edit_status",
        lambda: {
            "engine": "qwen_image_edit_2509",
            "available": False,
            "status": "NOT_INSTALLED",
            "code": "MODEL_MISSING",
            "creatorMessage": "Character Angles need Qwen Image Edit 2509 installed in Setup.",
            "installed": False,
            "runtimeReady": False,
            "gpuReady": False,
            "modelReady": False,
            "licenseClear": True,
        },
    )
    monkeypatch.setattr("app.character_identity.multiview_engine._STATUS_CACHE", None)
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-lic", role="fixture"),
    )
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {}}
    save_state(db_v3, profile, state)
    db_v3.commit()
    with pytest.raises(HTTPException) as exc:
        generate_multiview(db_v3, "proj-v3", profile.id)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "MODEL_MISSING"
    assert "Wonder3D" not in str(exc.value.detail)


def test_multiview_generate_enqueues_qwen_edit_not_front_family(db_v3, monkeypatch):
    from app.character_identity import service
    from app.character_identity.cc_v2 import save_state
    from app.character_identity.cc_v3_multiview import generate_multiview
    from app.character_identity.schemas import CharacterProfileCreate

    ready = {
        "engine": "qwen_image_edit_2509",
        "available": True,
        "status": "READY",
        "code": None,
        "creatorMessage": "ready",
        "installed": True,
        "runtimeReady": True,
        "gpuReady": True,
        "modelReady": True,
        "licenseClear": True,
    }
    monkeypatch.setattr("app.character_identity.multiview_engine.qwen_edit_status", lambda: ready)
    monkeypatch.setattr("app.character_identity.multiview_engine._STATUS_CACHE", None)

    captured: list[dict] = []

    class FakeJob:
        def __init__(self, job_id: str):
            self.id = job_id
            self.status = "queued"
            self.comfy_prompt_id = None
            self.message = None

    def fake_enqueue(*_args, **kwargs):
        captured.append(kwargs)
        return FakeJob(f"job-{len(captured)}")

    monkeypatch.setattr("app.character_identity.visual_sheet._enqueue_txt2img", fake_enqueue)
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-enq", role="fixture"),
    )
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {"hair": "dark"}}
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = generate_multiview(db_v3, "proj-v3", profile.id)
    assert len(captured) == 3
    families = {row["model_family_preference"] for row in captured}
    workflows = {row["force_workflow_key"] for row in captured}
    sources = {row["source_asset_id"] for row in captured}
    assert families == {"qwen_edit_2509"}
    assert workflows == {"qwen_edit_2509.edit"}
    assert sources == {"front-asset"}
    assert {row["steps"] for row in captured} == {8}
    assert {row["cfg"] for row in captured} == {1.0}
    assert {row["width"] for row in captured} == {768}
    assert {row["height"] for row in captured} == {768}
    assert out["multiView"]["engine"] == "qwen_image_edit_2509"
    assert out["multiView"]["status"] == "generating"
    for name in ("side", "three_quarter", "back"):
        assert out["multiView"]["angles"][name]["jobId"]
        assert out["multiView"]["angles"][name]["runtime"] == "qwen_image_edit_2509"


def test_reject_unlinks_angle_asset(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import save_state
    from app.character_identity.cc_v3_multiview import set_angle_approval
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset
    from PIL import Image

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-rej", role="fixture"),
    )
    front = tmp_path / "front.png"
    side = tmp_path / "side.png"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(front)
    Image.new("RGB", (32, 32), (20, 20, 20)).save(side)
    db_v3.add(Asset(id="front-asset", project_id="proj-v3", filename="front.png", path=str(front)))
    db_v3.add(Asset(id="side-asset", project_id="proj-v3", filename="side.png", path=str(side)))
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {}}
    state["multiView"]["angles"]["side"].update(
        {"assetId": "side-asset", "approved": True, "status": "approved", "rejected": False}
    )
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = set_angle_approval(db_v3, "proj-v3", profile.id, "side", approved=False)
    slot = out["multiView"]["angles"]["side"]
    assert slot.get("assetId") in {None, ""}
    assert slot.get("approved") is False
    assert db_v3.get(Asset, "side-asset") is None
    assert db_v3.get(Asset, "front-asset") is not None
    assert front.exists()
    assert not side.exists()


def test_wonder3d_engine_stays_license_blocked():
    from app.character_identity.multiview_engine import wonder3d_status
    from app.character_identity.wonder3d_runtime import assert_can_generate

    status = wonder3d_status()
    assert status["available"] is False
    assert status["status"] == "license_blocked"
    with pytest.raises(HTTPException) as exc:
        assert_can_generate()
    assert exc.value.detail["code"] == "WONDER3D_LICENSE_BLOCKED"


def test_legacy_back_ready_does_not_override_active():
    from app.character_identity.cc_v2 import _compute_phase

    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["visualLock"]["status"] = "ok"
    state["views"]["back"]["status"] = "ready"
    assert _compute_phase(state) == "ACTIVE"


def test_gpu_mutex_includes_multiview():
    state = empty_state()
    state["multiView"]["status"] = "generating"
    assert _active_job_busy(state) == "multiview"
    state["multiView"]["status"] = "idle"
    state["multiView"]["angles"]["side"]["upscaleStatus"] = "upscaling"
    assert _active_job_busy(state) == "upscale.side"


def test_v3_express_sheet_layout(tmp_path: Path):
    front = tmp_path / "front.png"
    side = tmp_path / "side.png"
    tq = tmp_path / "tq.png"
    back = tmp_path / "back.png"
    out = tmp_path / "sheet.png"
    Image.new("RGB", (400, 700), (80, 40, 40)).save(front)
    Image.new("RGB", (400, 700), (40, 80, 40)).save(side)
    Image.new("RGB", (400, 700), (40, 40, 80)).save(tq)
    Image.new("RGB", (400, 700), (80, 80, 40)).save(back)
    layout = compose_v3_character_sheet(
        str(front),
        str(side),
        str(tq),
        str(back),
        str(out),
        profile={"name": "Mira Vale", "visual_style": "cinematic"},
    )
    assert layout["layout"] == "v3_21x9_express"
    assert layout["hasCloseup"] is False
    assert layout["width"] == 2560
    assert layout["height"] == 1080
    assert layout["grid"]["cells"]["front"] == {"col": 0, "row": 0}
    assert layout["grid"]["cells"]["side"] == {"col": 1, "row": 0}
    assert layout["grid"]["cells"]["closeup"] is None
    assert layout["grid"]["cells"]["three_quarter"] == {"col": 0, "row": 1}
    assert layout["grid"]["cells"]["back"] == {"col": 1, "row": 1}
    assert layout["grid"]["cells"]["json"] == {"col": 2, "row": 1}
    with Image.open(out) as im:
        assert im.size == (2560, 1080)


def test_setup_character_multiview_engine_is_detect_only():
    from app.setup.catalog import get_component
    from app.setup.component_kinds import KIND_DETECT_ONLY, component_kind

    component = get_component("character_multiview_engine")
    assert component.required is False
    assert component.download_bytes == 0
    assert component_kind(component) == KIND_DETECT_ONLY


def test_setup_wonder3d_never_installs():
    from app.setup.catalog import get_component, is_retired_obsolete_setup_component, public_components
    from app.setup.component_kinds import KIND_DETECT_ONLY, component_kind
    from app.setup.diagnostics import verify_component

    component = get_component("wonder3d_multiview")
    assert component.required is False
    assert component.download_bytes == 0
    assert component_kind(component) == KIND_DETECT_ONLY
    assert is_retired_obsolete_setup_component("wonder3d_multiview")
    assert "wonder3d_multiview" not in {item.id for item in public_components()}
    verification = verify_component("wonder3d_multiview")
    assert verification.healthy is False
    assert verification.issue_code == "license_blocked"
    assert verification.recommendation == "none"


def test_generator_inventory_retires_back():
    from app.character_identity.cc_v2_generators import list_v2_generators

    inventory = list_v2_generators(has_reference=False)
    assert inventory["auto"]["operations"]["back"]["available"] is False
    assert inventory["auto"]["operations"]["back"]["status"] == "retired"
    for row in inventory["generators"]:
        assert row["operations"]["back"]["available"] is False


def test_v3_standard_sheet_places_closeup(tmp_path: Path):
    front = tmp_path / "front.png"
    side = tmp_path / "side.png"
    tq = tmp_path / "tq.png"
    back = tmp_path / "back.png"
    closeup = tmp_path / "close.png"
    out = tmp_path / "sheet.png"
    for path in (front, side, tq, back, closeup):
        Image.new("RGB", (300, 300), (50, 50, 50)).save(path)
    layout = compose_v3_character_sheet(
        str(front),
        str(side),
        str(tq),
        str(back),
        str(out),
        profile={"name": "Mira Vale"},
        closeup_path=str(closeup),
    )
    assert layout["layout"] == "v3_21x9_standard"
    assert layout["hasCloseup"] is True
    assert layout["grid"]["cells"]["closeup"] == {"col": 2, "row": 0}


@pytest.fixture()
def db_v3(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
    from app.character_identity import models as _ci_models  # noqa: F401
    from app.creator_scope.service import CreatorAssetScopeRow as _CreatorScope  # noqa: F401
    from app.config import settings
    from app.db import Base, Project

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
    session.add(Project(id="proj-v3", name="V3 Fixture"))
    session.commit()
    yield session
    session.close()


def _approved_multiview_state(state, *, approve=None):
    approve = set(approve or ("side", "three_quarter", "back"))
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {}}
    for name in ("side", "three_quarter", "back"):
        slot = state["multiView"]["angles"][name]
        slot["assetId"] = f"{name}-asset"
        slot["status"] = "approved" if name in approve else "ready"
        slot["approved"] = name in approve
    state["multiviewEnrichment"]["status"] = "none"
    return state


def test_sheet_gate_ignores_vision_lock():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    state = _approved_multiview_state(empty_state())
    state["visualLock"] = {"status": "failed", "error": "vision failed"}
    gate = sheet_gate(state)
    assert gate["ready"] is True
    assert gate["missing"] == []
    assert gate["nextAction"] == "Character Sheet ready to create."
    assert gate["approvedFrontAssetId"] == "front-asset"
    assert "Co-Director" not in str(gate)
    assert "Wait for Co-Director" not in str(gate)


def test_sheet_gate_mixed_sources_enable_same_button():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    matrices = (
        ("generated", "generated", "generated", "generated"),
        ("uploaded", "uploaded", "uploaded", "uploaded"),
        ("generated", "uploaded", "generated", "uploaded"),
        ("uploaded", "generated", "uploaded", "generated"),
    )
    for front_src, side_src, tq_src, back_src in matrices:
        state = _approved_multiview_state(empty_state())
        state["views"]["front"]["source"] = front_src
        state["visualLock"] = {"status": "none", "facts": {}}
        state["multiView"]["angles"]["side"]["source"] = side_src
        state["multiView"]["angles"]["three_quarter"]["source"] = tq_src
        state["multiView"]["angles"]["back"]["source"] = back_src
        gate = sheet_gate(state)
        assert gate["ready"] is True, (front_src, side_src, tq_src, back_src, gate)
        assert gate["missing"] == []
        assert gate["approvedFrontAssetId"]
        assert gate["approvedSideAssetId"]
        assert gate["approvedThreeQuarterAssetId"]
        assert gate["approvedBackAssetId"]
        joined = " ".join(gate["missing"]).lower()
        assert "qwen" not in joined
        assert "generated" not in joined
        assert "upload" not in joined


def test_sheet_gate_ready_without_enrich():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    gate = sheet_gate(_approved_multiview_state(empty_state()))
    assert gate["ready"] is True
    assert gate["missing"] == []


def test_sheet_gate_missing_front_even_when_angles_approved():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    state = _approved_multiview_state(empty_state())
    state["views"]["front"]["approved"] = False
    gate = sheet_gate(state)
    assert gate["ready"] is False
    assert gate["missing"][0] == "Approve Front"
    assert gate["nextAction"] == "Approve Front"
    assert gate["approvedFrontAssetId"] is None


def test_sheet_gate_one_and_two_approvals():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    one = sheet_gate(_approved_multiview_state(empty_state(), approve=("side",)))
    assert one["ready"] is False
    assert "Approve 3/4" in one["missing"]
    assert "Approve Back" in one["missing"]
    two = sheet_gate(_approved_multiview_state(empty_state(), approve=("side", "three_quarter")))
    assert two["ready"] is False
    assert two["missing"] == ["Approve Back"]


def test_sheet_gate_blocks_live_generation():
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate

    state = _approved_multiview_state(empty_state(), approve=("side", "three_quarter"))
    state["multiView"]["angles"]["back"]["status"] = "generating"
    state["multiView"]["angles"]["back"]["assetId"] = None
    assert sheet_gate(state)["ready"] is False
    assert any("Back" in row for row in sheet_gate(state)["missing"])


def test_reject_clears_only_that_angle_from_gate(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.cc_v3_multiview import set_angle_approval, sheet_gate
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-gate-rej", role="fixture"),
    )
    paths = {}
    for name in ("front", "side", "three_quarter", "back"):
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (16, 16), (10, 10, 10)).save(path)
        paths[name] = path
        db_v3.add(Asset(id=f"{name}-asset", project_id="proj-v3", filename=f"{name}.png", path=str(path)))
    state = _approved_multiview_state(empty_state())
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = set_angle_approval(db_v3, "proj-v3", profile.id, "three_quarter", approved=False)
    gate = sheet_gate(out)
    assert gate["ready"] is False
    assert "Approve 3/4" in gate["missing"] or "Make 3/4" in gate["missing"]
    assert out["multiView"]["angles"]["side"]["approved"] is True
    assert out["multiView"]["angles"]["back"]["approved"] is True
    assert db_v3.get(Asset, "side-asset") is not None


def test_double_approve_is_idempotent(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.cc_v3_multiview import set_angle_approval
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-dbl", role="fixture"),
    )
    other = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Other Vale", slug="other-v3-dbl", role="fixture"),
    )
    side = tmp_path / "side.png"
    Image.new("RGB", (16, 16), (20, 20, 20)).save(side)
    db_v3.add(Asset(id="side-asset", project_id="proj-v3", filename="side.png", path=str(side)))
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {}}
    state["multiView"]["angles"]["side"].update(
        {"assetId": "side-asset", "approved": False, "status": "ready"}
    )
    save_state(db_v3, profile, state)
    other_state = empty_state()
    other_state["multiView"]["angles"]["side"]["approved"] = False
    save_state(db_v3, other, other_state)
    db_v3.commit()
    first = set_angle_approval(db_v3, "proj-v3", profile.id, "side", approved=True)
    second = set_angle_approval(db_v3, "proj-v3", profile.id, "side", approved=True)
    assert first["multiView"]["angles"]["side"]["approved"] is True
    assert second["multiView"]["angles"]["side"]["approved"] is True
    assert second["multiView"]["angles"]["side"]["assetId"] == "side-asset"
    from app.character_identity.cc_v2 import get_status

    other_out = get_status(db_v3, "proj-v3", other.id)
    assert other_out["multiView"]["angles"]["side"]["approved"] is False


def _seed_compose_assets(db, tmp_path, *, include_legacy_back=False):
    from app.db import Asset

    ids = {}
    names = ("front", "side", "three_quarter", "back")
    if include_legacy_back:
        names = names + ("legacy_back",)
    for name in names:
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (32, 48), (30, 30, 30)).save(path)
        aid = f"{name}-asset"
        ids[name] = aid
        db.add(Asset(id=aid, project_id="proj-v3", filename=f"{name}.png", path=str(path)))
    return ids


def test_compose_sheet_is_local_without_enrich(db_v3, tmp_path, monkeypatch):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, save_state
    from app.character_identity.crs_service import load_persisted_crs
    from app.character_identity.schemas import CharacterProfileCreate
    from app.codirector.entity_resolver import resolve_character

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-compose", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path)
    state = _approved_multiview_state(empty_state())
    state["visualLock"]["facts"] = {"hair": "blonde", "wardrobe": "silver"}
    state["multiviewEnrichment"] = {"status": "failed", "facts": {}, "error": "vision_failed"}
    save_state(db_v3, profile, state)
    db_v3.commit()

    async def boom_enrich(*_a, **_k):
        raise AssertionError("enrich_multiview_canon must not run during compose")

    async def boom_vision(*_a, **_k):
        raise AssertionError("chat_vision must not run during compose")

    monkeypatch.setattr("app.character_identity.cc_v3_multiview.enrich_multiview_canon", boom_enrich)
    monkeypatch.setattr("app.codirector.vision.vision_review.chat_vision", boom_vision)
    out = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    assert out["sheetGate"]["ready"] is True
    assert out["multiviewEnrichment"]["status"] == "failed"
    assert out["sheet"]["status"] == "ready"
    assert out["sheet"]["assetId"]
    assert out["sheetAssetId"] == out["sheet"]["assetId"]
    crs = load_persisted_crs(db_v3, profile.id)
    assert crs["approved_sheet_asset_id"] == out["sheetAssetId"]
    assert crs["tag"] == "@Mira Vale"
    resolved = resolve_character(db_v3, "proj-v3", "Mira Vale")
    assert resolved is not None
    assert resolved["approved_sheet_asset_id"] == out["sheetAssetId"]
    assert resolved["at_tag"] == "@Mira Vale"

    again = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    assert again["sheetAssetId"] == out["sheetAssetId"]


def test_compose_sheet_uses_mixed_uploaded_and_generated_ids(db_v3, tmp_path, monkeypatch):
    import asyncio
    import json

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, save_state
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    def boom_generate(*_a, **_k):
        raise AssertionError("Qwen generate_multiview must not run during compose")

    monkeypatch.setattr("app.character_identity.cc_v3_multiview.generate_multiview", boom_generate)
    monkeypatch.setattr("app.character_identity.cc_v3_multiview.regenerate_angle", boom_generate)
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-mixed-compose", role="fixture"),
    )
    colors = {"front": (10, 10, 10), "side": (20, 20, 20), "three_quarter": (30, 30, 30), "back": (40, 40, 40)}
    sources = {"front": "uploaded", "side": "generated", "three_quarter": "uploaded", "back": "generated"}
    for name, color in colors.items():
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (32, 48), color).save(path)
        db_v3.add(
            Asset(
                id=f"{name}-mixed",
                project_id="proj-v3",
                filename=f"{name}.png",
                path=str(path),
                prompt_meta_json=json.dumps({"characterId": profile.id, "source": sources[name]}),
            )
        )
    state = empty_state()
    state["views"]["front"].update(
        {"approved": True, "assetId": "front-mixed", "status": "approved", "source": "uploaded"}
    )
    state["visualLock"] = {"status": "failed", "error": "ignored"}
    for name in ("side", "three_quarter", "back"):
        state["multiView"]["angles"][name].update(
            {
                "approved": True,
                "assetId": f"{name}-mixed",
                "status": "approved",
                "source": sources[name],
            }
        )
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    sheet = db_v3.get(Asset, out["sheetAssetId"])
    meta = json.loads(sheet.prompt_meta_json)
    assert meta["characterId"] == profile.id
    assert set(meta["sourceAssetIds"][:4]) == {"front-mixed", "side-mixed", "three_quarter-mixed", "back-mixed"}
    assert meta["lineage"]["viewAssetIds"] == {
        "front": "front-mixed",
        "side": "side-mixed",
        "three_quarter": "three_quarter-mixed",
        "back": "back-mixed",
    }
    assert out["sheetGate"]["ready"] is True


def test_compose_sheet_uses_angle_back_not_v2_back(db_v3, tmp_path):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, save_state
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-backsrc", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path, include_legacy_back=True)
    state = _approved_multiview_state(empty_state())
    state["views"]["back"]["assetId"] = "legacy_back-asset"
    state["views"]["back"]["approved"] = True
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    sheet = db_v3.get(Asset, out["sheetAssetId"])
    meta = sheet.prompt_meta_json or ""
    assert "back-asset" in meta
    assert "legacy_back-asset" not in meta


def test_compose_sheet_missing_file_does_not_write_sheet(db_v3, tmp_path):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, get_status, save_state
    from app.character_identity.crs_service import load_persisted_crs
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-missing", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path)
    (tmp_path / "back.png").unlink()
    state = _approved_multiview_state(empty_state())
    save_state(db_v3, profile, state)
    db_v3.commit()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "SHEET_SOURCE_MISSING"
    after = get_status(db_v3, "proj-v3", profile.id)
    assert not after.get("sheetAssetId")
    assert not load_persisted_crs(db_v3, profile.id).get("approved_sheet_asset_id")


def test_compose_sheet_active_lock_is_409(db_v3, tmp_path):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import _compose_lock, compose_sheet, empty_state, save_state
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-lock", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path)
    save_state(db_v3, profile, _approved_multiview_state(empty_state()))
    db_v3.commit()
    held = _compose_lock(profile.id)
    assert held.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "SHEET_COMPOSE_ACTIVE"
    finally:
        held.release()


def test_compose_sheet_json_revision_creates_new_sheet(db_v3, tmp_path):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, save_state
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-rev", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path)
    state = _approved_multiview_state(empty_state())
    state["jsonRevision"] = 1
    save_state(db_v3, profile, state)
    db_v3.commit()
    first = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    from app.character_identity.cc_v2 import load_state

    persisted = load_state(db_v3, profile.id)
    persisted["jsonRevision"] = 2
    save_state(db_v3, profile, persisted)
    db_v3.commit()
    second = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    assert second["sheetAssetId"] != first["sheetAssetId"]


def test_compose_sheet_regenerate_writes_new_asset(db_v3, tmp_path):
    import asyncio

    from app.character_identity import service
    from app.character_identity.cc_v2 import compose_sheet, empty_state, save_state
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-regen", role="fixture"),
    )
    _seed_compose_assets(db_v3, tmp_path)
    save_state(db_v3, profile, _approved_multiview_state(empty_state()))
    db_v3.commit()
    first = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    same = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id))
    assert same["sheetAssetId"] == first["sheetAssetId"]
    again = asyncio.run(compose_sheet(db_v3, "proj-v3", profile.id, regenerate=True))
    assert again["sheetAssetId"] != first["sheetAssetId"]
    assert again["sheet"]["progress"]["percent"] == 100


def test_creator_runtime_message_hides_comfy_object_info():
    from app.character_identity.multiview_engine import _creator_runtime_message

    msg = _creator_runtime_message(
        "Comfy object_info unavailable: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>",
        fallback="offline",
    )
    assert "WinError" not in msg
    assert "object_info" not in msg
    assert "offline" in msg.lower() or "runtime" in msg.lower()


def test_remake_clears_only_that_angle_approval(db_v3, tmp_path, monkeypatch):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.cc_v3_multiview import regenerate_angle, sheet_gate
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    ready = {
        "engine": "qwen_image_edit_2509",
        "available": True,
        "status": "READY",
        "code": None,
        "creatorMessage": "ready",
        "installed": True,
        "runtimeReady": True,
        "gpuReady": True,
        "modelReady": True,
        "licenseClear": True,
    }
    monkeypatch.setattr("app.character_identity.multiview_engine.qwen_edit_status", lambda: ready)
    monkeypatch.setattr("app.character_identity.multiview_engine._STATUS_CACHE", None)

    class FakeJob:
        def __init__(self):
            self.id = "job-remake-side"
            self.status = "queued"
            self.comfy_prompt_id = None
            self.message = None

    monkeypatch.setattr(
        "app.character_identity.visual_sheet._enqueue_txt2img",
        lambda *_args, **_kwargs: FakeJob(),
    )
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-remake", role="fixture"),
    )
    for name in ("front", "side", "three_quarter", "back"):
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (16, 16), (12, 12, 12)).save(path)
        db_v3.add(Asset(id=f"{name}-asset", project_id="proj-v3", filename=f"{name}.png", path=str(path)))
    state = _approved_multiview_state(empty_state())
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = regenerate_angle(db_v3, "proj-v3", profile.id, "side")
    assert out["multiView"]["angles"]["side"]["approved"] is False
    assert out["multiView"]["angles"]["three_quarter"]["approved"] is True
    assert out["multiView"]["angles"]["back"]["approved"] is True
    gate = sheet_gate(out)
    assert gate["ready"] is False
    assert any("Side" in row for row in gate["missing"])


def test_character_json_and_resolver_read_cc_v2_multiview(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.crs_service import get_character_json
    from app.character_identity.schemas import CharacterProfileCreate
    from app.codirector.entity_resolver import character_canon_context_block, resolve_character
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Special Agent Fixture", slug="canon-handoff-fixture", role="fixture"),
    )
    ids = {
        "front": "front-canon",
        "side": "side-canon",
        "three_quarter": "tq-canon",
        "back": "back-canon",
        "sheet": "sheet-canon",
    }
    for name, aid in ids.items():
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (16, 16), (20, 20, 20)).save(path)
        db_v3.add(Asset(id=aid, project_id="proj-v3", filename=f"{name}.png", path=str(path)))
    state = _approved_multiview_state(empty_state())
    state["views"]["front"]["assetId"] = ids["front"]
    for name in ("side", "three_quarter", "back"):
        state["multiView"]["angles"][name]["assetId"] = ids[name]
    state["sheetAssetId"] = ids["sheet"]
    state["sheet"] = {"status": "ready", "assetId": ids["sheet"]}
    state["jsonRevision"] = 2
    state["multiviewEnrichment"] = {"status": "ok", "facts": {"notes": "from angles"}}
    save_state(db_v3, profile, state)
    db_v3.commit()

    payload = get_character_json(db_v3, "proj-v3", profile.id)
    assert payload["characterId"] == profile.id
    assert payload["name"] == "Special Agent Fixture"
    assert payload["approvedSheetAssetId"] == ids["sheet"]
    assert payload["views"]["front"]["assetId"] == ids["front"]
    assert payload["views"]["side"]["assetId"] == ids["side"]
    assert payload["views"]["three_quarter"]["assetId"] == ids["three_quarter"]
    assert payload["views"]["back"]["assetId"] == ids["back"]
    assert payload["multiView"]["three_quarter"]["approved"] is True
    assert payload["jsonRevision"] == 2
    assert payload["multiviewEnrichment"]["status"] == "ok"

    resolved = resolve_character(db_v3, "proj-v3", "Special Agent Fixture")
    assert resolved["character_id"] == profile.id
    assert resolved["visual_reference"] == ids["front"]
    assert resolved["side_reference"] == ids["side"]
    assert resolved["three_quarter_reference"] == ids["three_quarter"]
    assert resolved["back_reference"] == ids["back"]
    assert resolved["sheet_asset_id"] == ids["sheet"]
    assert resolved["approved_sheet_asset_id"] == ids["sheet"]

    block = character_canon_context_block(
        db_v3, "proj-v3", "Who is @Special Agent Fixture?"
    )
    assert profile.id in block
    assert ids["front"] in block
    assert ids["side"] in block
    assert ids["three_quarter"] in block
    assert ids["back"] in block
    assert ids["sheet"] in block


def test_hydrator_tolerates_malformed_legacy_slots(db_v3):
    import json

    from app.character_identity import service
    from app.character_identity.cc_v2 import V2_TRAIT_KEY, get_status
    from app.character_identity.models import CharacterTraitRow
    from app.character_identity.schemas import CharacterProfileCreate

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-hydrate", role="fixture"),
    )
    db_v3.add(
        CharacterTraitRow(
            id="legacy-bad",
            character_profile_id=profile.id,
            category="character_creator_v2",
            key=V2_TRAIT_KEY,
            value=json.dumps(
                {
                    "jsonRevision": "nope",
                    "views": {"front": "oops", "back": ["x"], "closeup": None},
                    "multiView": "bad",
                    "multiviewEnrichment": 3,
                }
            ),
        )
    )
    db_v3.commit()
    out = get_status(db_v3, "proj-v3", profile.id)
    assert out["views"]["front"]["status"] == "idle"
    assert out["multiView"]["angles"]["side"]["status"] == "idle"
    assert out["jsonRevision"] == 1
    assert "ready" in out["sheetGate"]


def test_adopt_front_writes_views_front(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import adopt_front_from_asset
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Mira Vale", slug="mira-v3-adopt", role="fixture"),
    )
    path = tmp_path / "front.png"
    Image.new("RGB", (24, 24), (9, 9, 9)).save(path)
    db_v3.add(Asset(id="adopt-front", project_id="proj-v3", filename="front.png", path=str(path)))
    db_v3.commit()
    out = adopt_front_from_asset(db_v3, "proj-v3", profile.id, "adopt-front", source_type="library")
    assert out["views"]["front"]["assetId"] == "adopt-front"
    assert out["views"]["front"]["approved"] is False
    assert out["views"]["front"]["status"] == "ready"


def _png_bytes(size: int = 64, color=(20, 40, 80)) -> bytes:
    import io

    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def test_validate_angle_image_rejects_video_and_tiny():
    from app.character_identity.cc_v3_multiview import validate_angle_image_bytes

    with pytest.raises(HTTPException) as video:
        validate_angle_image_bytes(b"\x00\x00\x00\x18ftypmp42", filename="clip.mp4", content_type="video/mp4")
    assert video.value.detail["code"] == "NOT_AN_IMAGE"
    with pytest.raises(HTTPException) as tiny:
        validate_angle_image_bytes(_png_bytes(8), filename="tiny.png")
    assert tiny.value.detail["code"] == "IMAGE_TOO_SMALL"
    with pytest.raises(HTTPException) as junk:
        validate_angle_image_bytes(b"not-an-image", filename="x.png")
    assert junk.value.detail["code"] == "IMAGE_DECODE_FAILED"
    ok = validate_angle_image_bytes(_png_bytes(64), filename="side.png")
    assert ok["width"] == 64


def test_upload_angle_binds_candidate_and_library_meta(db_v3):
    from app.character_identity import service
    from app.character_identity.cc_v3_multiview import upload_angle_from_bytes
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    before = service.list_profiles(db_v3, "proj-v3")
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-angle-upload", role="fixture"),
    )
    after = service.list_profiles(db_v3, "proj-v3")
    out = upload_angle_from_bytes(
        db_v3,
        "proj-v3",
        profile.id,
        "side",
        data=_png_bytes(80, (12, 90, 40)),
        filename="cade-side.png",
        content_type="image/png",
    )
    slot = out["multiView"]["angles"]["side"]
    assert slot["approved"] is False
    assert slot["status"] == "ready"
    assert slot["source"] == "uploaded"
    assert slot["assetId"]
    assert slot["assetUrl"]
    assert out["characterId"] == profile.id
    assert len(after) == len(before) + 1
    asset = db_v3.get(Asset, slot["assetId"])
    assert asset is not None
    assert asset.project_id == "proj-v3"
    assert "Cade" in (asset.tag or "")
    assert "Side" in (asset.tag or "")
    meta = __import__("json").loads(asset.prompt_meta_json or "{}")
    assert meta["role"] == "character_angle"
    assert meta["angle"] == "side"
    assert meta["source"] == "uploaded"
    assert meta["characterId"] == profile.id
    assert meta["characterName"] == "Cade"
    assert meta["assetType"] == "image"


def test_upload_angle_replaces_generated_candidate_without_deleting(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import save_state, empty_state
    from app.character_identity.cc_v3_multiview import upload_angle_from_bytes
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-angle-replace", role="fixture"),
    )
    prior = tmp_path / "generated-side.png"
    Image.new("RGB", (48, 48), (9, 9, 9)).save(prior)
    db_v3.add(Asset(id="generated-side", project_id="proj-v3", filename="generated-side.png", path=str(prior)))
    state = empty_state()
    state["multiView"]["angles"]["side"].update(
        {"assetId": "generated-side", "status": "ready", "approved": False, "source": "generated"}
    )
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = upload_angle_from_bytes(
        db_v3,
        "proj-v3",
        profile.id,
        "side",
        data=_png_bytes(72, (200, 10, 10)),
        filename="uploaded-side.png",
    )
    slot = out["multiView"]["angles"]["side"]
    assert slot["source"] == "uploaded"
    assert slot["assetId"] != "generated-side"
    assert slot["approved"] is False
    assert db_v3.get(Asset, "generated-side") is not None


def test_generate_multiview_skips_uploaded_candidate(db_v3, monkeypatch):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.cc_v3_multiview import generate_multiview
    from app.character_identity.schemas import CharacterProfileCreate

    ready = {
        "engine": "qwen_image_edit_2509",
        "available": True,
        "status": "READY",
        "code": None,
        "creatorMessage": "ready",
        "installed": True,
        "runtimeReady": True,
        "gpuReady": True,
        "modelReady": True,
        "licenseClear": True,
    }
    monkeypatch.setattr("app.character_identity.multiview_engine.qwen_edit_status", lambda: ready)
    monkeypatch.setattr("app.character_identity.multiview_engine._STATUS_CACHE", None)
    captured: list[str] = []

    class FakeJob:
        def __init__(self, job_id: str):
            self.id = job_id
            self.status = "queued"
            self.comfy_prompt_id = None
            self.message = None

    def fake_enqueue(*_args, **kwargs):
        captured.append(str(kwargs.get("role") or kwargs.get("tag") or ""))
        return FakeJob(f"job-{len(captured)}")

    monkeypatch.setattr("app.character_identity.visual_sheet._enqueue_txt2img", fake_enqueue)
    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-angle-mixed", role="fixture"),
    )
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["views"]["front"]["assetId"] = "front-asset"
    state["visualLock"] = {"status": "ok", "facts": {}}
    state["multiView"]["angles"]["side"].update(
        {"assetId": "uploaded-side", "status": "ready", "approved": False, "source": "uploaded"}
    )
    save_state(db_v3, profile, state)
    db_v3.commit()
    out = generate_multiview(db_v3, "proj-v3", profile.id)
    assert out["multiView"]["angles"]["side"]["source"] == "uploaded"
    assert out["multiView"]["angles"]["side"]["assetId"] == "uploaded-side"
    assert out["multiView"]["angles"]["three_quarter"]["source"] == "generated"
    assert out["multiView"]["angles"]["back"]["source"] == "generated"
    assert len(captured) == 2


def test_approve_uploaded_angle_and_sheet_gate(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, save_state
    from app.character_identity.cc_v3_multiview import set_angle_approval, sheet_gate, upload_angle_from_bytes
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-angle-approve", role="fixture"),
    )
    front = tmp_path / "front.png"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(front)
    db_v3.add(Asset(id="front-ok", project_id="proj-v3", filename="front.png", path=str(front)))
    state = empty_state()
    state["views"]["front"].update({"approved": True, "assetId": "front-ok", "status": "approved"})
    state["visualLock"] = {"status": "ok", "facts": {}}
    save_state(db_v3, profile, state)
    db_v3.commit()
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "side", data=_png_bytes(64, (1, 1, 1)), filename="s.png")
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "three_quarter", data=_png_bytes(64, (2, 2, 2)), filename="t.png")
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "back", data=_png_bytes(64, (3, 3, 3)), filename="b.png")
    for name in ("side", "three_quarter", "back"):
        out = set_angle_approval(db_v3, "proj-v3", profile.id, name, approved=True)
        assert out["multiView"]["angles"][name]["approved"] is True
        assert out["multiView"]["angles"][name]["source"] == "uploaded"
    gate = sheet_gate(out, db=db_v3, character_id=profile.id)
    assert gate["ready"] is True
    assert gate["nextAction"] == "Character Sheet ready to create."
    assert out["characterId"] == profile.id
    assert out["sheetGate"]["ready"] is True


def test_replace_upload_unapproves_and_disables_sheet(db_v3, tmp_path):
    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state, get_status, save_state
    from app.character_identity.cc_v3_multiview import set_angle_approval, sheet_gate, upload_angle_from_bytes
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    profile = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-replace-back", role="fixture"),
    )
    front = tmp_path / "front.png"
    Image.new("RGB", (64, 64), (9, 9, 9)).save(front)
    db_v3.add(Asset(id="front-replace", project_id="proj-v3", filename="front.png", path=str(front)))
    state = empty_state()
    state["views"]["front"].update({"approved": True, "assetId": "front-replace", "status": "approved"})
    save_state(db_v3, profile, state)
    db_v3.commit()
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "side", data=_png_bytes(64, (1, 1, 1)), filename="s.png")
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "three_quarter", data=_png_bytes(64, (2, 2, 2)), filename="t.png")
    upload_angle_from_bytes(db_v3, "proj-v3", profile.id, "back", data=_png_bytes(64, (3, 3, 3)), filename="b.png")
    for name in ("side", "three_quarter", "back"):
        set_angle_approval(db_v3, "proj-v3", profile.id, name, approved=True)
    ready = sheet_gate(get_status(db_v3, "proj-v3", profile.id), db=db_v3, character_id=profile.id)
    assert ready["ready"] is True
    replaced = upload_angle_from_bytes(
        db_v3, "proj-v3", profile.id, "back", data=_png_bytes(64, (8, 8, 8)), filename="b2.png"
    )
    assert replaced["multiView"]["angles"]["back"]["approved"] is False
    gate = sheet_gate(replaced, db=db_v3, character_id=profile.id)
    assert gate["ready"] is False
    assert "Approve Back" in gate["missing"]
    assert gate["approvedBackAssetId"] is None


def test_sheet_gate_rejects_foreign_character_asset(db_v3, tmp_path):
    import json

    from app.character_identity import service
    from app.character_identity.cc_v2 import empty_state
    from app.character_identity.cc_v3_multiview import sheet_gate
    from app.character_identity.schemas import CharacterProfileCreate
    from app.db import Asset

    owner = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Cade", slug="cade-bind-owner", role="fixture"),
    )
    other = service.create_profile(
        db_v3,
        "proj-v3",
        CharacterProfileCreate(name="Other", slug="other-bind", role="fixture"),
    )
    for name in ("front", "side", "three_quarter", "back"):
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (16, 16), (4, 4, 4)).save(path)
        meta = {"characterId": other.id} if name == "side" else {"characterId": owner.id}
        db_v3.add(
            Asset(
                id=f"{name}-bind",
                project_id="proj-v3",
                filename=f"{name}.png",
                path=str(path),
                prompt_meta_json=json.dumps(meta),
            )
        )
    state = empty_state()
    state["characterId"] = owner.id
    state["views"]["front"].update({"approved": True, "assetId": "front-bind"})
    for name in ("side", "three_quarter", "back"):
        state["multiView"]["angles"][name].update(
            {"approved": True, "assetId": f"{name}-bind", "status": "approved", "source": "uploaded"}
        )
    gate = sheet_gate(state, db=db_v3, character_id=owner.id)
    assert gate["ready"] is False
    assert "Side belongs to a different character" in gate["missing"]
    assert gate["approvedSideAssetId"] == "side-bind"
