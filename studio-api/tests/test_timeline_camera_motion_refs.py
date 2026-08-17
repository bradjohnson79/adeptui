"""Camera-clip motion-subject / motion-reference compile. Canonical IDs only."""

from __future__ import annotations

from app.db import Asset, Base, Project
from app.director_timeline import CameraClip, DirectorTimeline, PromptSegment, camera_prompt_hint
from app.director_timeline_w46.contracts import BatchBlock, DurationState, ExecutionSnapshot
from app.director_timeline_w46.generation.reference_compile import apply_compiled_references
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.speech_compile import compile_speech_windows
from app.scene_references import models as _sr_models  # noqa: F401
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
    session.add(Project(id="proj-ref", name="Ref Test"))
    session.add(
        Asset(id="img-k", project_id="proj-ref", tag="Korri", kind="image", filename="korri.png", path="korri.png")
    )
    session.add(
        Asset(id="vid-1", project_id="proj-ref", tag="KorriPoseVideo", kind="video", filename="pose.mp4", path="pose.mp4")
    )
    session.commit()
    return session


def _attach(session, **kwargs):
    return service.attach(session, "proj-ref", kwargs)


def test_legacy_camera_text_only_still_compiles():
    tl = DirectorTimeline(
        duration_sec=5,
        camera_clips=[CameraClip(id="cam-old", start=0, length=2, motion_type="dolly_in", rig="dolly", label="Dolly In")],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="seedance-api", duration=DurationState(plannedDuration=5))
    warnings = apply_compiled_references(batch, tl, db=None, project_id=None)
    assert warnings == []
    assert not any(isinstance(r, dict) and r.get("source") == "camera_clip" for r in batch.references)
    hint = camera_prompt_hint(tl.camera_clips)
    assert "dolly" in hint.lower() or "Dolly" in hint


def test_camera_motion_refs_compile_canonical_ids():
    session = _db()
    korri = _attach(
        session,
        asset_id="img-k",
        scope_type="project",
        scope_id="proj-ref",
        reference_type="character",
        media_kind="entity",
        identity_id="char-korri",
        alias="Korri",
    )
    video = _attach(
        session,
        asset_id="vid-1",
        scope_type="project",
        scope_id="proj-ref",
        reference_type="video",
        media_kind="video",
        alias="KorriPoseVideo",
    )
    tl = DirectorTimeline(
        duration_sec=5,
        camera_clips=[
            CameraClip(
                id="cam-1",
                start=0,
                length=5,
                motion_type="push",
                rig="dolly",
                text="@Korri dancing to *KorriPoseVideo while camera slowly pushes forward.",
                reference_binding_ids=[korri["id"], video["id"]],
            )
        ],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="seedance-api", duration=DurationState(plannedDuration=5))
    warnings = apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
    assert not any(w["code"] == "VIDEO_MOTION_REFERENCE_UNSUPPORTED" for w in warnings)
    subject = next(r for r in batch.references if r.get("role") == "motion_subject")
    motion = next(r for r in batch.references if r.get("role") == "motion_reference")
    assert subject["bindingId"] == korri["id"]
    assert subject["identityId"] == "char-korri"
    assert subject["voiceCoupled"] is False
    assert subject["consumed"] is False
    assert motion["bindingId"] == video["id"]
    assert motion["assetId"] == "vid-1"
    assert motion["consumed"] is True
    assert motion["source"] == "camera_clip"
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="seedance-api")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert req.videoReferenceAssetId == "vid-1"
    assert req.providerOptions["motionSubjectIdentityId"] == "char-korri"
    assert req.providerOptions["motionSubjectBindingId"] == korri["id"]
    assert req.providerOptions["motionReferenceAssetId"] == "vid-1"
    assert req.providerOptions["motionReferenceBindingId"] == video["id"]
    assert "KorriPoseVideo" not in (req.prompt or "")
    windows, errors = compile_speech_windows(tl, db=session, project_id="proj-ref")
    assert errors == []
    assert all(w["speechKind"] == "none" for w in windows)
    session.close()


def test_camera_alias_rename_keeps_canonical_video():
    session = _db()
    video = _attach(
        session,
        asset_id="vid-1",
        scope_type="project",
        scope_id="proj-ref",
        reference_type="video",
        media_kind="video",
        alias="KorriPoseVideo",
    )
    service.update(session, "proj-ref", video["id"], {"alias": "KorriDanceMotion"})
    tl = DirectorTimeline(
        duration_sec=5,
        camera_clips=[
            CameraClip(
                id="cam-1",
                start=0,
                length=5,
                text="follow *KorriDanceMotion",
                reference_binding_ids=[video["id"]],
            )
        ],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="seedance-api", duration=DurationState(plannedDuration=5))
    apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
    motion = next(r for r in batch.references if r.get("role") == "motion_reference")
    assert motion["bindingId"] == video["id"]
    assert motion["assetId"] == "vid-1"
    session.close()


def test_unsupported_camera_video_is_not_dropped():
    session = _db()
    video = _attach(
        session,
        asset_id="vid-1",
        scope_type="project",
        scope_id="proj-ref",
        reference_type="video",
        media_kind="video",
        alias="KorriPoseVideo",
    )
    tl = DirectorTimeline(
        duration_sec=5,
        camera_clips=[
            CameraClip(
                id="cam-1",
                start=0,
                length=5,
                text="@Korri *KorriPoseVideo",
                reference_binding_ids=[video["id"]],
            )
        ],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="ltx-local", duration=DurationState(plannedDuration=5))
    warnings = apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
    assert any(w["code"] == "VIDEO_MOTION_REFERENCE_UNSUPPORTED" for w in warnings)
    assert any("does not support video motion references" in w["message"] for w in warnings)
    motion = next(r for r in batch.references if r.get("role") == "motion_reference")
    assert motion["bindingId"] == video["id"]
    assert motion["consumed"] is False
    assert not any(a.kind == "video" and a.assetId for a in batch.sourceAnchors)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert req.videoReferenceAssetId is None
    assert req.providerOptions["motionReferenceAssetId"] is None
    assert tl.camera_clips[0].reference_binding_ids == [video["id"]]
    session.close()


def test_camera_and_prompt_share_one_video_capacity():
    session = _db()
    video = _attach(
        session,
        asset_id="vid-1",
        scope_type="project",
        scope_id="proj-ref",
        reference_type="video",
        media_kind="video",
        alias="KorriPoseVideo",
    )
    tl = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(id="p1", start=0, length=5, text="dance", reference_binding_ids=[video["id"]])
        ],
        camera_clips=[
            CameraClip(id="cam-1", start=0, length=5, text="follow *KorriPoseVideo", reference_binding_ids=[video["id"]])
        ],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="seedance-api", duration=DurationState(plannedDuration=5))
    apply_compiled_references(batch, tl, db=session, project_id="proj-ref")
    videos = [r for r in batch.references if r.get("kind") == "video"]
    assert len(videos) == 2
    assert all(r["assetId"] == "vid-1" for r in videos)
    assert sum(1 for a in batch.sourceAnchors if a.kind == "video") == 1
    session.close()
