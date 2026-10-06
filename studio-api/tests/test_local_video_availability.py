"""Local video availability — Library hydration + Co-Director mode truth."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.routing.situational_replies import (
    _availability_spoken_from_rows,
    generator_availability_reply,
)
from app.db import Asset, Base, Project
from app.video_runtime.scene_output_library import register_render_output_asset


def test_register_render_output_asset_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(id="proj-v", name="Video"))
    db.commit()
    dest = tmp_path / "scene_ltx.mp4"
    dest.write_bytes(b"fake-mp4")
    first = register_render_output_asset(
        db,
        project_id="proj-v",
        dest=dest,
        tag="ltx",
        prompt_meta={"engine": "ltx", "workflowKey": "ltx.scene"},
    )
    db.commit()
    second = register_render_output_asset(db, project_id="proj-v", dest=dest, tag="ltx")
    assert first.id == second.id
    rows = db.query(Asset).filter(Asset.project_id == "proj-v", Asset.kind == "video").all()
    assert len(rows) == 1
    assert rows[0].path == str(dest)
    db.close()


def test_codirector_lists_local_generators_without_calling_them_offline() -> None:
    spoken = _availability_spoken_from_rows(
        [
            SimpleNamespace(
                id="ltx-2.5-distilled",
                label="LTX 2.5",
                locality="local",
                readiness="Ready",
                executable=True,
                disabledReason="",
                supportsTextToVideo=False,
                supportsImageToVideo=True,
                requiresLastFrame=False,
            ),
            SimpleNamespace(
                id="minimax-h3",
                label="MiniMax H3",
                locality="local",
                readiness="Ready",
                executable=True,
                disabledReason="",
                supportsTextToVideo=True,
                supportsImageToVideo=True,
                requiresLastFrame=False,
            ),
        ]
    )
    low = spoken.lower()
    assert "ltx 2.5" in low
    assert "ready" in low
    assert "minimax h3" in low
    assert "wan" not in low
    assert "hunyuan" not in low
    assert "offline" not in low or "does not always mean offline" in low


def test_codirector_ltx25_shot_and_appropriate_generator() -> None:
    ltx = generator_availability_reply("Can LTX 2.5 create this kind of shot?")
    assert ltx is not None
    assert "start picture" in ltx.spoken.lower()
    assert "text-to-video" in ltx.spoken.lower()
    t2v = generator_availability_reply("Can LTX 2.5 create this kind of Text-to-Video shot?")
    assert t2v is not None
    assert "cannot create a text-to-video" in t2v.spoken.lower()
    pick = generator_availability_reply("Use the appropriate video generator for this shot.")
    assert pick is not None
    assert pick.kind == "appropriate_generator"
    assert "have not started" in pick.spoken.lower()


def test_create_project_video_list_uses_authority_not_wave6() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "codirector" / "routers" / "knowledge.py"
    text = src.read_text(encoding="utf-8")
    assert "timeline_generator_snapshot" in text
    assert "wave6_gate" not in text


def test_availability_reply_calls_timeline_snapshot(monkeypatch) -> None:
    called = {"n": 0}

    def fake_snapshot():
        called["n"] += 1
        return [
            SimpleNamespace(
                id="ltx-2.5-distilled",
                label="LTX 2.5",
                locality="local",
                readiness="Ready",
                executable=True,
                disabledReason="",
                supportsTextToVideo=False,
                supportsImageToVideo=True,
                requiresLastFrame=False,
            ),
            SimpleNamespace(
                id="minimax-h3",
                label="MiniMax H3",
                locality="local",
                readiness="Ready",
                executable=True,
                disabledReason="",
                supportsTextToVideo=True,
                supportsImageToVideo=True,
                requiresLastFrame=False,
            ),
        ]

    monkeypatch.setattr(
        "app.production_control.generator_authority.timeline_generator_snapshot",
        fake_snapshot,
    )
    turn = generator_availability_reply("Which local video generators are available right now?")
    assert called["n"] == 1
    assert turn is not None
    assert turn.kind == "generator_availability"
    low = turn.spoken.lower()
    assert "ltx 2.5" in low
    assert "minimax h3" in low
    assert "ready" in low
    assert "wan" not in low
    assert "does not always mean offline" in low


def test_availability_reply_uses_live_authority_snapshot() -> None:
    from app.production_control.generator_authority import timeline_generator_snapshot

    rows = timeline_generator_snapshot()
    locals_ = [g for g in rows if getattr(g, "locality", "") == "local" and g.id != "optional-wan"]
    assert locals_, "Production Control returned no local video generators"
    by_id = {g.id: g for g in locals_}
    assert "ltx-2.5-distilled" in by_id or any(str(g.id).startswith("ltx-2.5") for g in locals_)
    assert "minimax-h3" in by_id or any(str(g.id).startswith("minimax-h3") for g in locals_)
    turn = generator_availability_reply("Which local video generators are available right now?")
    assert turn is not None
    assert turn.kind == "generator_availability"
    low = turn.spoken.lower()
    assert "ltx 2.5" in low
    assert "minimax" in low or "h3" in low


def test_render_request_accepts_surface_engine() -> None:
    from app.schemas import RenderRequest

    body = RenderRequest(kind="scene", scene_id="scene-1", engine="ltx-2.5", action_scope="exploration")
    assert body.engine == "ltx-2.5"
    assert body.action_scope == "exploration"


def test_frame_modes_generate_sends_scene_engine() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "studio-web" / "src" / "components" / "FrameModes.tsx"
    text = src.read_text(encoding="utf-8")
    assert text.count("engine: scene.engine") >= 2
    assert 'action_scope: "exploration"' in text
    one = text.split("Generate from 1 frame")[0]
    assert "engine: scene.engine" in one


def test_route_a_prepare_on_generate_waits_for_handoff() -> None:
    import inspect

    from app.minimax_h3.service import _ensure_route_a_for_generation
    from app.runtime_manager import service
    from runtime_supervisor.constants import COMFY_READY_TIMEOUT_SEC, ROUTE_A_READY_TIMEOUT_SEC
    from runtime_supervisor.services import _spawn, start_route_a_on_demand

    assert ROUTE_A_READY_TIMEOUT_SEC >= 120
    assert ROUTE_A_READY_TIMEOUT_SEC > COMFY_READY_TIMEOUT_SEC
    start_src = inspect.getsource(service._start_route_a_sync)
    assert "start_route_a_on_demand" in start_src
    spawn_src = inspect.getsource(_spawn)
    assert 'getattr(subprocess, "DETACHED_PROCESS"' not in spawn_src
    assert "start_route_a_on_demand" in inspect.getsource(start_route_a_on_demand)
    ensure_src = inspect.getsource(_ensure_route_a_for_generation)
    assert "150" in ensure_src
