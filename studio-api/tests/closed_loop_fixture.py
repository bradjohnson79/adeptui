"""Deterministic Closed Loop Acceptance Project fixture (Three-Moon Lake Test)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import Asset, Project, Scene
from app.director_references.tags import ensure_tags
from app.director_timeline import DirectorTimeline, ImageClip, dumps_director_timeline


@dataclass
class ClosedLoopFixture:
    project_id: str
    scene_id: str
    image1_id: str
    image2_id: str
    asset_primary_1: str
    asset_primary_2: str
    asset_identity: str
    asset_wardrobe: str
    asset_environment: str
    asset_lighting: str
    asset_continuity: str
    asset_draft: str


def seed_closed_loop_project(db: Session, *, name: str = "Closed Loop Acceptance Project") -> ClosedLoopFixture:
    """Seed @Image1 (no refs) and @Image2 (multi-ref candidates) with local mock assets."""

    pid = f"proj-cl-{uuid.uuid4().hex[:8]}"
    sid = f"scene-cl-{uuid.uuid4().hex[:8]}"
    ids = {k: f"{k}-{uuid.uuid4().hex[:8]}" for k in (
        "p1", "p2", "identity", "wardrobe", "environment", "lighting", "continuity", "draft"
    )}

    db.merge(Project(id=pid, name=name))
    for aid, tag in (
        (ids["p1"], "primary1"),
        (ids["p2"], "primary2"),
        (ids["identity"], "character_identity"),
        (ids["wardrobe"], "wardrobe"),
        (ids["environment"], "environment"),
        (ids["lighting"], "lighting"),
        (ids["continuity"], "continuity"),
        (ids["draft"], "draft_output"),
    ):
        db.merge(
            Asset(
                id=aid,
                project_id=pid,
                tag=tag,
                kind="image",
                filename=f"{tag}.png",
                path=f"{tag}.png",
            )
        )

    tl = DirectorTimeline(
        media_mode="image",
        duration_sec=8.0,
        image_clips=[
            ImageClip(id="clip-image-1", asset_id=ids["p1"], start=0.0, length=3.0, label="Image 1"),
            ImageClip(id="clip-image-2", asset_id=ids["p2"], start=3.0, length=3.0, label="Image 2"),
        ],
    )
    ensure_tags(tl)
    assert tl.image_clips[0].display_tag == "@Image1"
    assert tl.image_clips[1].display_tag == "@Image2"

    db.merge(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Three-Moon Lake Test",
            prompt="Closed-loop acceptance fixture",
            duration_sec=8.0,
            director_json=dumps_director_timeline(tl),
        )
    )
    db.commit()

    return ClosedLoopFixture(
        project_id=pid,
        scene_id=sid,
        image1_id="clip-image-1",
        image2_id="clip-image-2",
        asset_primary_1=ids["p1"],
        asset_primary_2=ids["p2"],
        asset_identity=ids["identity"],
        asset_wardrobe=ids["wardrobe"],
        asset_environment=ids["environment"],
        asset_lighting=ids["lighting"],
        asset_continuity=ids["continuity"],
        asset_draft=ids["draft"],
    )
