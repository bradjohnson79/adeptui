"""Typed project-scoped reference aliases and compile-by-canonical-ID."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project
from app.director_timeline import DirectorTimeline, PromptSegment, TimelineClip, hydrate_prompt_refs, parse_director_timeline
from app.director_timeline_w46.contracts import BatchBlock, DurationState
from app.director_timeline_w46.generation.reference_compile import apply_compiled_references
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.contracts import ExecutionSnapshot
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service
from app.scene_references.aliases import sanitize_alias, unique_alias


@pytest.fixture()
def db():
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
        Asset(
            id="img-1",
            project_id="proj-ref",
            tag="SchnickCounterWide",
            kind="image",
            filename="counter.png",
            path="counter.png",
        )
    )
    session.add(
        Asset(
            id="vid-1",
            project_id="proj-ref",
            tag="KorriPoseVideo",
            kind="video",
            filename="pose.mp4",
            path="pose.mp4",
        )
    )
    session.commit()
    yield session
    session.close()


def test_alias_sanitizes_prefix_and_spaces():
    assert sanitize_alias("@Korri Pose") == "KorriPose"
    assert sanitize_alias("*KorriPoseVideo") == "KorriPoseVideo"
    assert sanitize_alias("#Schnick Counter Wide") == "SchnickCounterWide"


def test_attach_project_scoped_typed_alias(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "usage_modes": ["motion"],
            "alias": "KorriPoseVideo",
            "media_kind": "video",
        },
    )
    assert binding["alias"] == "KorriPoseVideo"
    assert binding["media_kind"] == "video"
    assert binding["display_token"] == "*KorriPoseVideo"
    assert binding["scope_type"] == "project"
    second = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "img-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "usage_modes": ["motion"],
            "alias": "KorriPoseVideo",
            "media_kind": "video",
        },
    )
    assert second["alias"] == "KorriPoseVideo2"
    assert second["alias_adjusted"] is True


def test_remove_then_reattach_reuses_alias(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "usage_modes": ["motion"],
            "alias": "KorriPoseVideo",
            "media_kind": "video",
        },
    )
    service.remove(db, "proj-ref", binding["id"])
    again = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "usage_modes": ["motion"],
            "alias": "KorriPoseVideo",
            "media_kind": "video",
        },
    )
    assert again["id"] == binding["id"]
    assert again["alias"] == "KorriPoseVideo"
    assert again["asset_id"] == "vid-1"


def test_rename_keeps_binding_id_and_asset(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "media_kind": "video",
            "alias": "KorriPoseVideo",
        },
    )
    updated = service.update(db, "proj-ref", binding["id"], {"alias": "KorriDanceMotion"})
    assert updated["id"] == binding["id"]
    assert updated["asset_id"] == "vid-1"
    assert updated["alias"] == "KorriDanceMotion"
    assert updated["display_token"] == "*KorriDanceMotion"


def test_rename_conflict_suggests_suffix(db):
    service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "alias": "KorriDanceMotion",
        },
    )
    other = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "img-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "image",
            "alias": "Other",
        },
    )
    with pytest.raises(HTTPException) as ei:
        service.update(db, "proj-ref", other["id"], {"alias": "KorriDanceMotion"})
    assert ei.value.status_code == 409
    assert ei.value.detail["suggested_alias"] == "KorriDanceMotion2"


def test_compile_uses_canonical_id_not_alias(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "media_kind": "video",
            "alias": "KorriPoseVideo",
        },
    )
    service.update(db, "proj-ref", binding["id"], {"alias": "KorriDanceMotion"})
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(
                start=0,
                length=5,
                text="Korri follows the motion.",
                reference_binding_ids=[binding["id"]],
            )
        ],
        video_reference_clips=[
            TimelineClip(
                id="clip1",
                start=0,
                length=5,
                asset_id="vid-1",
                reference_binding_id=binding["id"],
                label="*KorriDanceMotion",
            )
        ],
    )
    batch = BatchBlock(
        sceneId="scene-1",
        generatorId="seedance-api",
        duration=DurationState(plannedDuration=5),
    )
    apply_compiled_references(batch, timeline, db=db, project_id="proj-ref")
    video_anchor = next(a for a in batch.sourceAnchors if a.kind == "video")
    assert video_anchor.assetId == "vid-1"
    consumed = next(r for r in batch.references if r.get("kind") == "video")
    assert consumed["bindingId"] == binding["id"]
    assert consumed["assetId"] == "vid-1"
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="seedance-api")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert req.videoReferenceAssetId == "vid-1"
    assert "KorriPoseVideo" not in (req.prompt or "")
    assert "KorriDanceMotion" not in (req.prompt or "")


def test_unsupported_video_ref_is_not_consumed(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "vid-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "video",
            "media_kind": "video",
            "alias": "KorriPoseVideo",
        },
    )
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(start=0, length=5, text="", reference_binding_ids=[binding["id"]])
        ],
        video_reference_clips=[
            TimelineClip(id="clip1", asset_id="vid-1", reference_binding_id=binding["id"], length=5)
        ],
    )
    batch = BatchBlock(
        sceneId="scene-1",
        generatorId="ltx-local",
        duration=DurationState(plannedDuration=5),
    )
    warnings = apply_compiled_references(batch, timeline, db=db, project_id="proj-ref")
    assert any(w["code"] == "VIDEO_REFERENCE_UNSUPPORTED" for w in warnings)
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


def test_image_reference_compile_canonical_id(db):
    binding = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "img-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "image",
            "media_kind": "image",
            "alias": "SchnickCounterWide",
        },
    )
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(start=0, length=5, text="", reference_binding_ids=[binding["id"]])
        ],
        image_reference_clips=[
            TimelineClip(id="imgref", asset_id="img-1", reference_binding_id=binding["id"], length=5)
        ],
    )
    batch = BatchBlock(
        sceneId="scene-1",
        generatorId="seedance-api",
        duration=DurationState(plannedDuration=5),
    )
    apply_compiled_references(batch, timeline, db=db, project_id="proj-ref")
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="seedance-api")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert "img-1" in req.referenceAssetIds
    assert "SchnickCounterWide" not in (req.prompt or "")


def test_unique_alias_helper(db):
    unique_alias(db, "proj-ref", "Hello")
    service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "img-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "image",
            "alias": "Hello",
        },
    )
    token, adjusted = unique_alias(db, "proj-ref", "Hello")
    assert token == "Hello2"
    assert adjusted is True
