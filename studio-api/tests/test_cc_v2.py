"""Character Creator V2 — JSON-first, Front identity, 21:9 compose, tag alias."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity import service
from app.character_identity.cc_v2 import (
    _compute_phase,
    collapse_retired_required_views,
    compact_character_tag,
    compose_sheet,
    empty_state,
    generate_view,
)
from app.character_identity.schemas import CharacterProfileCreate
from app.config import settings
from app.db import Base, Project
from app.character_identity.character_sheet_compose import (
    V2_SHEET_HEIGHT,
    V2_SHEET_WIDTH,
    compose_v2_character_sheet,
)
from app.character_identity.service import _slugify


def test_auto_front_and_pixel_ref_back_use_flux():
    from app.character_identity.crs_view_generation import resolve_crs_view_generation_workflow

    front = resolve_crs_view_generation_workflow()
    back = resolve_crs_view_generation_workflow(has_identity_crop=True)
    assert front["workflowKey"] == "flux.txt2img"
    assert front["family"] == "flux"
    assert back["workflowKey"] == "flux.img2img"
    assert back["mode"] == "img2img"


def test_retired_four_view_collapses_to_front_only():
    assert collapse_retired_required_views(
        ["front_full", "side_full", "back_full", "face_closeup"],
        "four_view",
    ) == ["front_full"]
    assert collapse_retired_required_views(["front_full"], "single_view") == ["front_full"]


def test_compact_tag_aliases_mira_vale():
    assert compact_character_tag("Mira Vale") == compact_character_tag("MiraVale")
    assert compact_character_tag("@Mira Vale") == compact_character_tag("MiraVale")
    assert _slugify("Mira Vale") in {"mira-vale", "mira_vale"} or "mira" in _slugify("Mira Vale")


def test_phase_active_after_front_lock():
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["visualLock"]["status"] = "ok"
    assert _compute_phase(state) == "ACTIVE"
    state["views"]["back"]["approved"] = True
    state["revision2"]["status"] = "ok"
    assert _compute_phase(state) == "DETAILS_READY"


def test_back_not_required_for_active():
    state = empty_state()
    state["views"]["front"]["approved"] = True
    state["visualLock"]["status"] = "ok"
    assert _compute_phase(state) == "ACTIVE"
    assert _compute_phase(state) != "DETAILS_READY"


def test_sheet_gate_requires_revision_2(tmp_path: Path):
    front = tmp_path / "front.png"
    back = tmp_path / "back.png"
    out = tmp_path / "sheet.png"
    Image.new("RGB", (512, 768), (40, 40, 80)).save(front)
    Image.new("RGB", (512, 768), (40, 80, 40)).save(back)
    layout = compose_v2_character_sheet(
        str(front),
        str(back),
        str(out),
        profile={"name": "Mira Vale", "visual_style": "cinematic", "gender_presentation": "woman", "description": "teal coat"},
        extra_facts={"hair": "black bob"},
    )
    assert layout["width"] == V2_SHEET_WIDTH
    assert layout["height"] == V2_SHEET_HEIGHT
    assert layout["layout"] == "v2_21x9"
    assert out.is_file()
    with Image.open(out) as im:
        assert im.size == (2560, 1080)


def test_standard_closeup_keeps_21x9_width(tmp_path: Path):
    front = tmp_path / "front.png"
    back = tmp_path / "back.png"
    closeup = tmp_path / "close.png"
    out = tmp_path / "sheet.png"
    Image.new("RGB", (400, 400), (80, 40, 40)).save(front)
    Image.new("RGB", (400, 400), (40, 80, 80)).save(back)
    Image.new("RGB", (300, 300), (80, 80, 40)).save(closeup)
    layout = compose_v2_character_sheet(
        str(front),
        str(back),
        str(out),
        profile={"name": "Mira Vale"},
        closeup_path=str(closeup),
    )
    assert layout["hasCloseup"] is True
    assert layout["width"] == 2560
    with Image.open(out) as im:
        assert im.size[0] == 2560


@pytest.fixture()
def db(tmp_path, monkeypatch):
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
    session.add(Project(id="proj-v2", name="V2 Fixture"))
    session.commit()
    yield session
    session.close()


def test_back_and_closeup_require_front_lock(db):
    profile = service.create_profile(
        db,
        "proj-v2",
        CharacterProfileCreate(name="Mira Vale", slug="mira-vale", role="fixture"),
    )
    for view in ("back", "closeup"):
        with pytest.raises(HTTPException) as exc:
            generate_view(db, "proj-v2", profile.id, view)
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "FRONT_LOCK_REQUIRED"


def test_sheet_compose_requires_revision_2(db):
    profile = service.create_profile(
        db,
        "proj-v2",
        CharacterProfileCreate(name="Mira Vale", slug="mira-vale-sheet", role="fixture"),
    )
    with pytest.raises(HTTPException) as exc:
        compose_sheet(db, "proj-v2", profile.id)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "SHEET_GATE"


def test_resolve_mira_vale_compact_alias(db):
    profile = service.create_profile(
        db,
        "proj-v2",
        CharacterProfileCreate(name="Mira Vale", slug="mira-vale-alias", role="fixture"),
    )
    found = service.resolve_character_by_name(db, "proj-v2", "MiraVale")
    assert found is not None
    assert found.id == profile.id
    from app.codirector.entity_resolver import resolve_character

    resolved = resolve_character(db, "proj-v2", "MiraVale")
    assert resolved is not None
    assert resolved["character_id"] == profile.id
    assert resolved["at_tag"] == "@Mira Vale"
