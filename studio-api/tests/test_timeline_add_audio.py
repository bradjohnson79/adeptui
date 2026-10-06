from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers.timeline_add_audio import (
    _DUCK_UNDER_DIALOGUE_RE,
    looks_like_footstep_placement,
    plan_walk_footsteps,
)
from app.codirector.capabilities.registry import HandlerKind, get_capability
from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.director_timeline import parse_director_timeline


def test_timeline_add_audio_capability_is_the_place_handler() -> None:
    cap = get_capability("timeline.add_audio")
    assert cap is not None
    assert cap.handler_kind == HandlerKind.CAPABILITY_HANDLER
    assert cap.tool_ids == ("audio.place",)


def test_walk_plan_keeps_independent_character_lanes() -> None:
    hits = plan_walk_footsteps(["Korri", "Anadriya"], duration_sec=8.0, cadence_sec=0.55)
    korri = [h for h in hits if h.character_name == "Korri"]
    ana = [h for h in hits if h.character_name == "Anadriya"]
    assert korri and ana
    assert korri[0].start_sec == 0.0
    assert ana[0].start_sec == 0.22
    assert {round(h.start_sec, 2) for h in korri}.isdisjoint({round(h.start_sec, 2) for h in ana})
    assert all(h.volume < 0.5 for h in hits)
    assert looks_like_footstep_placement("Add footsteps for Korri and Anadriya and time them to their walking.")


def test_duck_under_dialogue_matches_creator_phrasing() -> None:
    assert _DUCK_UNDER_DIALOGUE_RE.search("Add subtle music that stays under the dialogue.")
    assert _DUCK_UNDER_DIALOGUE_RE.search("duck under dialogue")
    assert not _DUCK_UNDER_DIALOGUE_RE.search("add music to the scene")


def test_handler_places_timed_sfx_on_director_timeline(tmp_path) -> None:
    from app.character_identity.models import CharacterProfileRow
    from app.codirector.capabilities.handlers.timeline_add_audio import handle
    from app.codirector.m29.db import ensure_m29_tables
    from tests.test_m30_audio_timeline import make_wav_bytes

    init_db()
    ensure_m29_tables()
    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"
    asset_id = str(uuid.uuid4())
    wav_path = tmp_path / "metal-grate-step.wav"
    wav_path.write_bytes(make_wav_bytes(seconds=1.0))

    session = SessionLocal()
    try:
        session.merge(Project(id=project_id, name="Footstep Place"))
        session.merge(
            Scene(
                id=scene_id,
                project_id=project_id,
                index=0,
                name="Venture Corridor Walk",
                prompt="@Korri and @Anadriya walk the corridor",
                duration_sec=8.0,
            )
        )
        session.merge(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag="metal-grate-step",
                kind="audio",
                filename="metal-grate-step.wav",
                path=str(wav_path),
            )
        )
        session.merge(
            CharacterProfileRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                name="Korri",
                slug="korri",
            )
        )
        session.merge(
            CharacterProfileRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                name="Anadriya",
                slug="anadriya",
            )
        )
        session.commit()

        result = handle(
            session,
            project_id,
            "exec-footsteps",
            prompt="Add footsteps for Korri and Anadriya and time them to their walking.",
            scene_id=scene_id,
            attachment_asset_ids=[asset_id],
        )
        assert result.get("error") in (None, "")
        jobs = result.get("child_jobs") or []
        assert len(jobs) >= 4
        assert {job["label"] for job in jobs} >= {"Korri footsteps", "Anadriya footsteps"}
        assert all(job["status"] == "completed" for job in jobs)

        scene = session.get(Scene, scene_id)
        assert scene is not None
        timeline = parse_director_timeline(scene.director_json, fallback_duration=8.0)
        labels = {clip.label for clip in timeline.sfx_clips}
        korri_starts = sorted(
            round(float(clip.start), 2)
            for clip in timeline.sfx_clips
            if clip.label == "Korri footsteps"
        )
        ana_starts = sorted(
            round(float(clip.start), 2)
            for clip in timeline.sfx_clips
            if clip.label == "Anadriya footsteps"
        )
        assert "Korri footsteps" in labels
        assert "Anadriya footsteps" in labels
        assert korri_starts[0] == 0.0
        assert ana_starts[0] == 0.22
        assert len(timeline.sfx_clips) == len(jobs)
    finally:
        session.close()


def test_handler_ignores_image_attachments_and_uses_approved_audio(tmp_path) -> None:
    from app.codirector.capabilities.handlers.timeline_add_audio import handle
    from app.codirector.m29.db import ensure_m29_tables
    from tests.test_m30_audio_timeline import make_wav_bytes

    init_db()
    ensure_m29_tables()
    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"
    image_id = str(uuid.uuid4())
    audio_id = str(uuid.uuid4())
    wav_path = tmp_path / "approved-footsteps.wav"
    wav_path.write_bytes(make_wav_bytes(seconds=1.0))

    session = SessionLocal()
    try:
        session.merge(Project(id=project_id, name="Footstep Guard"))
        session.merge(
            Scene(
                id=scene_id,
                project_id=project_id,
                index=0,
                name="Venture Corridor Dialogue",
                prompt="Corridor walk",
                duration_sec=4.0,
            )
        )
        session.merge(
            Asset(
                id=image_id,
                project_id=project_id,
                tag="codirector_image_generate",
                kind="image",
                filename="corridor.png",
                path=str(tmp_path / "corridor.png"),
            )
        )
        session.merge(
            Asset(
                id=audio_id,
                project_id=project_id,
                tag="sfx_gen",
                kind="audio",
                filename="approved-footsteps.wav",
                path=str(wav_path),
                production_approval="approved",
                prompt_meta_json='{"prompt": "Distinct human boot footsteps on steel grating"}',
            )
        )
        session.commit()

        result = handle(
            session,
            project_id,
            "exec-ignore-image",
            prompt="Add the approved footsteps to this scene.",
            scene_id=scene_id,
            attachment_asset_ids=[image_id],
        )
        assert result.get("error") in (None, "")
        scene = session.get(Scene, scene_id)
        timeline = parse_director_timeline(scene.director_json, fallback_duration=4.0)
        assert timeline.sfx_clips
        assert {clip.asset_id for clip in timeline.sfx_clips} == {audio_id}
    finally:
        session.close()


def test_contact_first_beats_default_cadence(tmp_path) -> None:
    """When a Media Intelligence packet has contactEvents, footstep hits must be
    placed at the visible contact times, not the generic 0.55s walking cadence."""
    from app.codirector.capabilities.handlers.timeline_add_audio import handle
    from app.codirector.m29.db import ensure_m29_tables
    from app.codirector.video_intelligence import media_persist
    from app.codirector.video_intelligence.media_packet import (
        ContactEvent,
        MediaFacts,
        MediaIntelligencePacket,
    )
    from tests.test_m30_audio_timeline import make_wav_bytes

    init_db()
    ensure_m29_tables()
    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"
    audio_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())

    wav_path = tmp_path / "footsteps.wav"
    wav_path.write_bytes(make_wav_bytes(seconds=1.0))
    video_path = tmp_path / "scene.mp4"
    video_path.write_bytes(b"not-a-real-mp4")

    session = SessionLocal()
    try:
        session.merge(Project(id=project_id, name="Contact First"))
        session.merge(
            Scene(
                id=scene_id,
                project_id=project_id,
                index=0,
                name="Contact Walk",
                prompt="Korri walks across steel plating",
                duration_sec=2.0,
                director_json='{"timelineMaster": {"sceneStitch": {"assetId": "' + video_id + '"}}}',
            )
        )
        session.merge(
            Asset(
                id=audio_id,
                project_id=project_id,
                tag="metal-grate-step",
                kind="audio",
                filename="footsteps.wav",
                path=str(wav_path),
                production_approval="approved",
                prompt_meta_json='{"prompt": "Distinct human boot footsteps on steel grating"}',
            )
        )
        session.merge(
            Asset(
                id=video_id,
                project_id=project_id,
                tag="scene_stitch",
                kind="video",
                filename="scene.mp4",
                path=str(video_path),
            )
        )
        session.commit()

        # Persist a Media Intelligence packet with visible contact events.
        packet = MediaIntelligencePacket(
            projectId=project_id,
            assetId=video_id,
            mode="full",
            media=MediaFacts(durationSec=2.0, hasAudio=False),
            summary="Korri walks across a steel corridor with three visible foot contacts.",
            contactEvents=[
                ContactEvent(startTime=0.12, endTime=0.12, characterLabel="Korri", foot="right", timingSource="visible_contact"),
                ContactEvent(startTime=0.65, endTime=0.65, characterLabel="Korri", foot="left", timingSource="visible_contact"),
                ContactEvent(startTime=1.18, endTime=1.18, characterLabel="Korri", foot="right", timingSource="visible_contact"),
            ],
            availability="ready",
        )
        media_persist.save_packet(session, project_id, packet)

        result = handle(
            session,
            project_id,
            "exec-contact-first",
            prompt="Add footstep hits timed to Korri's walking in this scene.",
            scene_id=scene_id,
            attachment_asset_ids=[audio_id],
        )
        assert result.get("error") in (None, "")
        assert result["status"] == "completed"
        assert "visible foot contacts" in result["creatorAck"].lower()

        jobs = result.get("child_jobs") or []
        assert len(jobs) == 3
        starts = sorted(job["metadata"]["startSec"] for job in jobs)
        assert starts == [0.12, 0.65, 1.18]
        assert all(job["metadata"]["timingSource"] == "visible_contact" for job in jobs)

        # The cadence fallback would have placed at 0.0, 0.55, 1.10 — prove it did not.
        assert 0.0 not in starts
        assert 0.55 not in starts

        scene = session.get(Scene, scene_id)
        timeline = parse_director_timeline(scene.director_json, fallback_duration=2.0)
        sfx_starts = sorted(round(float(clip.start), 2) for clip in timeline.sfx_clips)
        assert 0.12 in sfx_starts
        assert 0.65 in sfx_starts
        assert 1.18 in sfx_starts
    finally:
        session.close()
