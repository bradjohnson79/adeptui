"""Live Production Readiness is computed from scene bindings, not chat flags."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.codirector.production_lifecycle.live_scene_readiness import compute_live_scene_readiness
from app.codirector.timeline_context.service import build_timeline_context_package
from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.scene_references.models import SceneReferenceBinding
from app.scene_references import repository as repo

PROMPT = (
    "ENVIRONMENT\n#EarthHorizon is the place.\n"
    "SUBJECTS\n%VentureSpaceship — Venture Spaceship.\n"
    "%CadeSStarfighter — Cade's Starfighter.\n"
)


def _bind(db: Session, project_id: str, scene_id: str, *, alias: str, reference_type: str, filename: str) -> SceneReferenceBinding:
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=alias.lower(),
        kind="image",
        filename=filename,
        path=filename,
    )
    db.add(asset)
    db.flush()
    row = SceneReferenceBinding(
        id=str(uuid.uuid4()),
        project_id=project_id,
        asset_id=asset.id,
        scope_type="scene",
        scope_id=scene_id,
        reference_type=reference_type,
        alias=alias,
        enabled=True,
        usage_modes_json="[]",
        reference_roles_json="[]",
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def establishing(db_scene_ready):
    db, pid, sid = db_scene_ready
    earth = _bind(db, pid, sid, alias="EarthHorizon2", reference_type="environment", filename="earth.png")
    venture = _bind(db, pid, sid, alias="VentureSpaceship3", reference_type="prop", filename="venture.png")
    star = _bind(db, pid, sid, alias="CadeSStarfighter3", reference_type="prop", filename="cade.png")
    director = {
        "prompt_segments": [
            {
                "id": "ps_est",
                "start": 0,
                "length": 10,
                "text": PROMPT,
                "reference_binding_ids": [earth.id, venture.id, star.id],
                "reference_name_bindings": [
                    {
                        "bindingId": earth.id,
                        "promptName": "Earth Horizon",
                        "type": "environment",
                        "tag": "#EarthHorizon2",
                    },
                    {
                        "bindingId": venture.id,
                        "promptName": "Venture Spaceship",
                        "type": "prop",
                        "tag": "%VentureSpaceship3",
                    },
                    {
                        "bindingId": star.id,
                        "promptName": "Cade's Starfighter",
                        "type": "prop",
                        "tag": "%CadeSStarfighter3",
                    },
                ],
            }
        ]
    }
    scene = db.get(Scene, sid)
    scene.prompt = PROMPT
    scene.director_json = json.dumps(director)
    db.commit()
    return db, pid, sid, earth, venture, star


@pytest.fixture()
def db_scene_ready():
    Base.metadata.create_all(bind=engine)
    SceneReferenceBinding.__table__.create(bind=engine, checkfirst=True)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Live Readiness", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Establishing",
            prompt=PROMPT,
            duration_sec=10.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _dept(live: dict, category: str) -> dict:
    return next(d for d in live["departments"] if d["category"] == category)


def test_project_timeline_characters_list_on_every_scene(db_scene_ready):
    """Timeline @ tags are stored on the project. Every scene must list them."""
    db, pid, sid = db_scene_ready
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="cadecrs",
        kind="image",
        filename="Cade CRS.png",
        path="Cade CRS.png",
    )
    db.add(asset)
    db.flush()
    db.add(
        SceneReferenceBinding(
            id=str(uuid.uuid4()),
            project_id=pid,
            asset_id=asset.id,
            scope_type="project",
            scope_id=pid,
            reference_type="character",
            alias="CadeCRS",
            enabled=True,
            usage_modes_json="[]",
            reference_roles_json="[]",
        )
    )
    scene = db.get(Scene, sid)
    scene.prompt = ""
    db.commit()
    live = compute_live_scene_readiness(db, pid, sid)
    cast = _dept(live, "cast")
    refs = _dept(live, "references")
    assert cast["status"] == "ready"
    assert any("Cade" in item for item in cast["items"])
    assert refs["status"] == "ready"
    assert any("Cade" in item for item in refs["items"])
    assert _dept(live, "location")["status"] == "not_required"
    assert _dept(live, "voice")["status"] == "not_required"


def test_environment_binding_makes_location_ready(establishing):
    db, pid, sid, *_ = establishing
    live = compute_live_scene_readiness(db, pid, sid)
    location = _dept(live, "location")
    assert location["status"] == "ready"
    assert any("Earth Horizon" in item for item in location["items"])


def test_two_prop_bindings_make_references_ready(establishing):
    db, pid, sid, *_ = establishing
    live = compute_live_scene_readiness(db, pid, sid)
    refs = _dept(live, "references")
    assert refs["status"] == "ready"
    assert refs["resolved"] == 3
    assert refs["required"] == 3
    joined = " ".join(refs["items"])
    assert "Venture Spaceship" in joined
    assert "Cade's Starfighter" in joined
    assert "Earth Horizon" in joined


def test_no_character_requirement_is_not_required(establishing):
    db, pid, sid, *_ = establishing
    live = compute_live_scene_readiness(db, pid, sid)
    assert _dept(live, "cast")["status"] == "not_required"
    assert live["status"] in {"READY", "PARTIAL"}
    assert live["status"] != "BLOCKED"


def test_no_dialogue_requirement_is_not_a_lock(establishing):
    db, pid, sid, *_ = establishing
    live = compute_live_scene_readiness(db, pid, sid)
    voice = _dept(live, "voice")
    assert voice["status"] in {"not_required", "advisory"}
    assert live["status"] != "BLOCKED"


def test_remove_venture_is_advisory_not_lock(establishing):
    db, pid, sid, _earth, venture, _star = establishing
    repo.soft_delete_binding(db, venture, actor="test")
    db.commit()
    live = compute_live_scene_readiness(db, pid, sid)
    refs = _dept(live, "references")
    assert refs["status"] == "advisory"
    assert live["status"] == "PARTIAL"
    assert "Ready with" in live["blockerSummary"]
    assert any("Venture" in name for name in refs["missing"])
    from app.codirector.timeline_context.smart_gates import can_generate_scene, evaluate_smart_gate

    gate = evaluate_smart_gate(db, pid, sid, action_scope="production")
    assert gate["level"] != "PRODUCTION_LOCK"
    assert gate["decision"] != "BLOCK"
    allowed, _reason, _ = can_generate_scene(db, pid, sid, action_scope="production")
    assert allowed is True


def test_restore_venture_returns_references_ready(establishing):
    db, pid, sid, _earth, venture, _star = establishing
    alias = venture.alias
    repo.soft_delete_binding(db, venture, actor="test")
    db.commit()
    repo.restore_binding(db, venture, {"alias": alias, "enabled": True}, actor="test")
    db.commit()
    live = compute_live_scene_readiness(db, pid, sid)
    refs = _dept(live, "references")
    assert refs["status"] == "ready"
    assert live["status"] in {"READY", "PARTIAL"}
    assert live["status"] != "BLOCKED"
    assert any("Venture" in item for item in refs["items"])


def test_context_package_uses_live_compute_without_preflight(establishing):
    db, pid, sid, *_ = establishing
    pkg = build_timeline_context_package(db, pid, sid, action_scope="production")
    assert pkg.get("ok") is True
    readiness = (pkg.get("package") or {}).get("readiness") or {}
    assert readiness.get("liveComputed") is True
    assert readiness.get("status") in {"READY", "PARTIAL"}
    assert readiness.get("status") != "BLOCKED"
    departments = readiness.get("departments") or []
    assert next(d for d in departments if d["category"] == "cast")["status"] == "not_required"
    assert next(d for d in departments if d["category"] == "location")["status"] == "ready"
