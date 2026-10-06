"""Pane SceneReferenceBinding rows compile into generation refs."""

from __future__ import annotations

from app.db import Asset, Base, Project
from app.director_timeline import DirectorTimeline, PromptSegment
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.reference_compile import apply_compiled_references
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import repository as repo
from app.scene_references import service
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-ref", name="Pane Ref Test"))
    session.add(
        Asset(id="img-1", project_id="proj-ref", tag="Bar", kind="image", filename="bar.png", path="bar.png")
    )
    session.add(
        Asset(id="img-2", project_id="proj-ref", tag="Cup", kind="image", filename="cup.png", path="cup.png")
    )
    session.add(
        Asset(id="aud-k", project_id="proj-ref", tag="Line", kind="audio", filename="line.wav", path="line.wav")
    )
    session.add(
        Asset(id="vid-1", project_id="proj-ref", tag="Walk", kind="video", filename="walk.mp4", path="walk.mp4")
    )
    session.commit()
    return session


def _attach(
    session,
    asset_id: str,
    *,
    scope_type: str = "scene",
    scope_id: str = "scene-1",
    media_kind: str = "image",
    reference_type: str = "image",
    alias: str = "Pane",
):
    return service.attach(
        session,
        "proj-ref",
        {
            "asset_id": asset_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "reference_type": reference_type,
            "media_kind": media_kind,
            "alias": alias,
        },
    )


def _batch(generator_id: str) -> BatchBlock:
    return BatchBlock(
        sceneId="scene-1",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=5.0),
    )


def _req(batch: BatchBlock):
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator=batch.generatorId)
    return build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
        scene_prompt="Scene base",
    )


def test_pane_image_becomes_seedance_reference_asset_ids():
    session = _db()
    try:
        row = _attach(session, "img-1")
        tl = DirectorTimeline(
            duration_sec=5,
            prompt_segments=[PromptSegment(start=0, length=5, text="Korri at the bar.")],
        )
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert "img-1" in (req.referenceAssetIds or [])
        pane = [r for r in batch.references if isinstance(r, dict) and r.get("source") == "pane"]
        assert any(r.get("assetId") == "img-1" and r.get("consumed") for r in pane)
        assert row["id"] in {r.get("bindingId") for r in pane}
    finally:
        session.close()


def test_minimax_t2v_request_has_no_pane_images():
    session = _db()
    try:
        _attach(session, "img-1")
        tl = DirectorTimeline(
            duration_sec=5,
            prompt_segments=[PromptSegment(start=0, length=5, text="Korri at the bar.")],
        )
        batch = _batch("minimax-h3-t2v-local")
        warnings = apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert "img-1" not in (req.referenceAssetIds or [])
        assert req.startImageAssetId is None
        assert any(w.get("code") == "IMAGE_REFERENCE_UNSUPPORTED" for w in warnings)
        pane = [r for r in batch.references if isinstance(r, dict) and r.get("assetId") == "img-1"]
        assert pane
        assert all(r.get("consumed") is False for r in pane)
    finally:
        session.close()


def test_audio_pane_binding_not_in_reference_asset_ids():
    session = _db()
    try:
        repo.create_binding(
            session,
            {
                "project_id": "proj-ref",
                "asset_id": "aud-k",
                "scope_type": "scene",
                "scope_id": "scene-1",
                "reference_type": "other",
                "media_kind": "audio",
                "alias": "Line",
                "enabled": True,
                "order_index": 0,
            },
        )
        session.commit()
        tl = DirectorTimeline(duration_sec=5)
        batch = _batch("seedance-api")
        warnings = apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert "aud-k" not in (req.referenceAssetIds or [])
        assert any(w.get("code") == "AUDIO_REFERENCE_UNSUPPORTED" for w in warnings)
        audio = [r for r in batch.references if isinstance(r, dict) and r.get("kind") == "audio"]
        assert audio
        assert all(r.get("consumed") is False for r in audio)
    finally:
        session.close()


def test_duplicate_clip_and_pane_same_asset_appears_once():
    session = _db()
    try:
        row = _attach(session, "img-1")
        tl = DirectorTimeline(
            duration_sec=5,
            prompt_segments=[
                PromptSegment(
                    start=0,
                    length=5,
                    text="Korri at the bar.",
                    reference_binding_ids=[row["id"]],
                )
            ],
        )
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        ids = list(req.referenceAssetIds or [])
        assert ids.count("img-1") == 1
        compiled = [r for r in batch.references if isinstance(r, dict) and r.get("assetId") == "img-1"]
        assert len(compiled) == 1
        assert compiled[0].get("source") == "prompt_clip"
    finally:
        session.close()


def test_minimax_i2v_pane_fills_empty_start_only():
    session = _db()
    try:
        _attach(session, "img-1")
        tl = DirectorTimeline(duration_sec=5)
        batch = _batch("minimax-h3-i2v-local")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert req.startImageAssetId == "img-1"
        assert "img-1" not in (req.referenceAssetIds or [])
    finally:
        session.close()


def test_minimax_i2v_pane_does_not_override_existing_start():
    session = _db()
    try:
        _attach(session, "img-1")
        tl = DirectorTimeline(duration_sec=5)
        batch = _batch("minimax-h3-i2v-local")
        batch.sourceAnchors = [
            TimelineVisualAnchor(kind="image", assetId="img-2", label="Start")
        ]
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert req.startImageAssetId == "img-2"
        assert "img-1" not in (req.referenceAssetIds or [])
    finally:
        session.close()


def test_library_asset_ids_not_generation_input():
    session = _db()
    try:
        tl = DirectorTimeline(duration_sec=5, library_asset_ids=["img-1", "img-2"])
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert req.referenceAssetIds == []
        assert not any(
            isinstance(r, dict) and r.get("assetId") in {"img-1", "img-2"}
            for r in (batch.references or [])
        )
    finally:
        session.close()


def test_project_scoped_scene_reference_binding_is_generation_input():
    """UX drag/Add writes SceneReferenceBinding scope_type=project.

    That is generation input. DirectorTimeline.library_asset_ids is the
    staging list and is covered by test_library_asset_ids_not_generation_input.
    """
    session = _db()
    try:
        _attach(session, "img-1", scope_type="project", scope_id="proj-ref")
        tl = DirectorTimeline(duration_sec=5)
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref", scene_id="scene-1")
        req = _req(batch)
        assert "img-1" not in (req.referenceAssetIds or [])
        assert not any(
            isinstance(r, dict) and r.get("source") == "pane" and r.get("assetId") == "img-1"
            for r in (batch.references or [])
        )
    finally:
        session.close()

def test_video_pane_only_when_adapter_supports():
    session = _db()
    try:
        _attach(session, "vid-1", media_kind="video", reference_type="video", alias="Walk")
        tl = DirectorTimeline(duration_sec=5)
        seed = _batch("seedance-api")
        apply_compiled_references(seed, tl, db=session, project_id="proj-ref")
        seed_req = _req(seed)
        assert seed_req.videoReferenceAssetId == "vid-1"
        mm = _batch("minimax-h3-t2v-local")
        warnings = apply_compiled_references(mm, tl, db=session, project_id="proj-ref")
        mm_req = _req(mm)
        assert mm_req.videoReferenceAssetId is None
        assert any(w.get("code") == "VIDEO_REFERENCE_UNSUPPORTED" for w in warnings)
    finally:
        session.close()


def test_entity_pane_binding_not_image_slot():
    session = _db()
    try:
        session.add(
            Asset(
                id="ent-1",
                project_id="proj-ref",
                tag="Korri",
                kind="character",
                filename="korri.json",
                path="korri.json",
            )
        )
        session.commit()
        repo.create_binding(
            session,
            {
                "project_id": "proj-ref",
                "asset_id": "ent-1",
                "scope_type": "scene",
                "scope_id": "scene-1",
                "reference_type": "character",
                "media_kind": "entity",
                "alias": "Korri",
                "enabled": True,
                "order_index": 0,
            },
        )
        session.commit()
        tl = DirectorTimeline(duration_sec=5)
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref", scene_id="scene-1")
        req = _req(batch)
        assert "ent-1" not in (req.referenceAssetIds or [])
        assert req.startImageAssetId is None
        ents = [r for r in batch.references if isinstance(r, dict) and r.get("kind") == "entity"]
        assert ents
        assert all(r.get("consumed") is False for r in ents)
    finally:
        session.close()


def test_track_flags_round_trip_dump():
    from app.director_timeline import TrackFlagState, dumps_director_timeline, parse_director_timeline

    tl = DirectorTimeline(
        duration_sec=5.0,
        track_flags={"visual": TrackFlagState(hidden=True, locked=True)},
    )
    parsed = parse_director_timeline(dumps_director_timeline(tl))
    assert parsed.track_flags["visual"].hidden is True
    assert parsed.track_flags["visual"].locked is True
    missing = parse_director_timeline(dumps_director_timeline(DirectorTimeline(duration_sec=5.0)))
    assert missing.track_flags == {}


def test_library_asset_ids_round_trip_dump():
    from app.director_timeline import dumps_director_timeline, parse_director_timeline

    tl = DirectorTimeline(duration_sec=5.0, library_asset_ids=["a", "b"])
    parsed = parse_director_timeline(dumps_director_timeline(tl))
    assert parsed.library_asset_ids == ["a", "b"]
    empty = parse_director_timeline(dumps_director_timeline(DirectorTimeline(duration_sec=5.0, library_asset_ids=[])))
    assert empty.library_asset_ids == []
    missing = parse_director_timeline(dumps_director_timeline(DirectorTimeline(duration_sec=5.0)))
    assert missing.library_asset_ids is None


def test_clip_binding_kept_when_pane_also_present():
    session = _db()
    try:
        pane = _attach(session, "img-2", alias="PaneCup")
        clip = _attach(session, "img-1", alias="ClipBar")
        tl = DirectorTimeline(
            duration_sec=5,
            prompt_segments=[
                PromptSegment(
                    start=0,
                    length=5,
                    text="Korri at the bar.",
                    reference_binding_ids=[clip["id"]],
                )
            ],
        )
        batch = _batch("seedance-api")
        apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
        req = _req(batch)
        assert "img-1" in (req.referenceAssetIds or [])
        assert "img-2" in (req.referenceAssetIds or [])
        sources = {
            r.get("assetId"): r.get("source")
            for r in batch.references
            if isinstance(r, dict) and r.get("assetId")
        }
        assert sources.get("img-1") == "prompt_clip"
        assert sources.get("img-2") == "pane"
        assert pane["id"]
    finally:
        session.close()

