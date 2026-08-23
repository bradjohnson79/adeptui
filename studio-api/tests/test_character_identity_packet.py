"""G3: provider-neutral Character Identity Packet compiled before any generator call."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity import visual_sheet as visual_sheet_mod
from app.character_identity.crs_schema import (
    ERS_AND_GENERATOR_PACKET_KEYS,
    FOUR_VIEW_REQUIRED_VIEWS,
    LAW_REQUIRED_VIEWS,
    CharacterIdentityPacket,
)
from app.character_identity.crs_service import build_conditioning_packet
from app.character_identity.visual_sheet import (
    QWEN_REF_WORKFLOW_KEY,
    VIEW_ROLE_CANONICAL,
    start_visual_sheet_generation,
)
from app.config import settings
from app.db import Base, Job, Project


def _session(tmp_path, monkeypatch):
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
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()
    return db


def _assert_no_ers_keys(blob: dict) -> None:
    dumped = json.dumps(blob)
    for key in ERS_AND_GENERATOR_PACKET_KEYS:
        assert key not in blob, f"pre-provider packet must not include {key}"
    assert "qwen2512.ref" not in dumped
    assert QWEN_REF_WORKFLOW_KEY not in dumped
    assert "sceneCanvas" not in blob
    assert "environmentEditSource" not in blob


def test_korri_identity_packet_is_crs_generation_without_ers(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    packet = build_conditioning_packet(
        db,
        "proj-sheet",
        profile.id,
        task="CRS_GENERATION",
        character_name=profile.name,
    )
    assert isinstance(packet, CharacterIdentityPacket)
    assert packet.task == "CRS_GENERATION"
    assert list(packet.requiredViews) == list(FOUR_VIEW_REQUIRED_VIEWS)
    assert "three_quarter_full" in LAW_REQUIRED_VIEWS
    assert "three_quarter_full" not in packet.requiredViews
    assert packet.outputType == "character_reference_sheet"
    assert packet.characterId == profile.id
    assert packet.characterName == profile.name
    for inv in (
        "same_face",
        "same_body",
        "same_hair",
        "same_ears",
        "same_clothing",
        "same_special_arm",
    ):
        assert inv in packet.invariants
    blob = packet.model_dump(mode="json")
    _assert_no_ers_keys(blob)
    db.close()


def test_visual_sheet_start_reads_views_from_identity_packet(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
    captured: list[dict] = []
    seen: dict = {}
    real_specs = visual_sheet_mod._candidate_view_specs

    def spy_specs(required_views=None):
        seen["required_views"] = list(required_views or [])
        return real_specs(required_views)

    def fake_enqueue(db, project_id, body, scene_id=None):
        captured.append(dict(body or {}))
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

    monkeypatch.setattr(visual_sheet_mod, "_candidate_view_specs", spy_specs)
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        include_performance=False,
        generator_sources={"local": {"model": "qwen2512"}, "api": None},
    )
    packet = pack.get("identityPacket") or {}
    assert pack.get("taskType") == "CRS_GENERATION"
    assert packet.get("task") == "CRS_GENERATION"
    assert list(packet.get("requiredViews") or []) == ["front_full"]
    _assert_no_ers_keys(packet)
    assert seen.get("required_views") == ["front_full"]
    assert seen.get("required_views") == list(packet.get("requiredViews") or [])

    views = (pack.get("jobs") or {}).get("hero", {}).get("viewJobs") or []
    assert [VIEW_ROLE_CANONICAL[v["role"]] for v in views] == ["front_full"]
    assert len(captured) == 1
    for body in captured:
        assert body.get("taskType") == "CRS_SINGLE_VIEW"
        assert "sceneCanvas" not in body
        assert "environmentEditSource" not in body
        ip = body.get("identityPacket") or {}
        assert ip.get("task") == "CRS_GENERATION"
        assert list(ip.get("requiredViews") or []) == ["front_full"]
        _assert_no_ers_keys(ip)
        assert QWEN_REF_WORKFLOW_KEY not in json.dumps(ip)
    db.close()
