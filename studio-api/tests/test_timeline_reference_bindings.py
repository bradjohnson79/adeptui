"""Director M2.6 timeline reference bindings — tags, COW, package, flag gate."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.director_references.package import ReferencePackageBuilder
from app.director_references.service import TimelineReferenceService
from app.director_references.tags import allocate_display_tag, ensure_tags
from app.director_timeline import DirectorTimeline, ImageClip, dumps_director_timeline
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M007


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    pid = f"proj-ref-{uuid.uuid4().hex[:8]}"
    sid = f"scene-ref-{uuid.uuid4().hex[:8]}"
    aid_a = f"asset-a-{uuid.uuid4().hex[:8]}"
    aid_b = f"asset-b-{uuid.uuid4().hex[:8]}"
    session.merge(Project(id=pid, name="Ref Binding Project"))
    session.merge(
        Asset(id=aid_a, project_id=pid, tag="hero", kind="image", filename="a.png", path="a.png")
    )
    session.merge(
        Asset(id=aid_b, project_id=pid, tag="style", kind="image", filename="b.png", path="b.png")
    )
    tl = DirectorTimeline(
        media_mode="image",
        duration_sec=5.0,
        image_clips=[
            ImageClip(id="clip-1", asset_id=aid_a, start=0.0, length=2.0),
            ImageClip(id="clip-2", asset_id=aid_b, start=2.0, length=2.0),
        ],
    )
    ensure_tags(tl)
    session.merge(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="test",
            duration_sec=5.0,
            director_json=dumps_director_timeline(tl),
        )
    )
    session.commit()
    session.info["pid"] = pid
    session.info["sid"] = sid
    session.info["aid_a"] = aid_a
    session.info["aid_b"] = aid_b
    try:
        yield session
    finally:
        session.close()


def _ids(db: Session):
    return db.info["pid"], db.info["sid"], db.info["aid_a"], db.info["aid_b"]


def _enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_FEATURE_TIMELINE_REFERENCES_V1", "1")
    import app.director_references.package as pkg_mod
    import app.director_references.service as svc_mod
    import app.feature_flags as ff

    fresh = FeatureFlags.from_env(os.environ)
    monkeypatch.setattr(ff, "feature_flags", fresh)
    monkeypatch.setattr(svc_mod, "feature_flags", fresh)
    monkeypatch.setattr(pkg_mod, "feature_flags", fresh)


def test_feature_flag_defaults_off():
    flags = FeatureFlags.from_env({})
    assert flags.timeline_references_v1 is False


def test_m007_registered_and_neighbors_untouched():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M007" in revs
    assert "M006" in revs
    assert "M010" in revs
    assert M007.revision == "M007"
    assert revs.index("M006") < revs.index("M007") < revs.index("M010")


def test_stable_tags_allocate_and_never_renumber():
    tl = DirectorTimeline(image_clips=[ImageClip(id="a"), ImageClip(id="b")])
    ensure_tags(tl)
    assert tl.image_clips[0].display_tag == "@Image1"
    assert tl.image_clips[1].display_tag == "@Image2"
    tl.image_clips = [tl.image_clips[1]]
    ensure_tags(tl)
    assert tl.image_clips[0].display_tag == "@Image2"
    tl.image_clips.append(ImageClip(id="c"))
    ensure_tags(tl)
    assert tl.image_clips[-1].display_tag == "@Image3"
    assert allocate_display_tag(tl) == "@Image4"


def test_flag_off_blocks_service(db: Session, monkeypatch: pytest.MonkeyPatch):
    import app.director_references.service as svc_mod
    import app.feature_flags as ff

    off = FeatureFlags.from_env({})
    monkeypatch.setattr(ff, "feature_flags", off)
    monkeypatch.setattr(svc_mod, "feature_flags", off)
    pid, sid, _, _ = _ids(db)
    with pytest.raises(Exception) as exc:
        TimelineReferenceService(db).get_references(pid, sid, "clip-1")
    assert getattr(exc.value, "code", "") == "feature_disabled"


def test_cow_versions_and_empty_set(db: Session, monkeypatch: pytest.MonkeyPatch):
    _enable_flag(monkeypatch)
    pid, sid, aid_a, aid_b = _ids(db)
    svc = TimelineReferenceService(db)
    empty = svc.get_references(pid, sid, "clip-1")
    assert empty["count"] == 0
    assert empty["bindings"] == []
    assert empty["displayTag"]

    v1 = svc.add_binding(pid, sid, "clip-1", reference_asset_id=aid_b, role="style", influence="moderate")
    assert v1["activeVersion"] == 1
    assert v1["count"] == 1

    v2 = svc.add_binding(
        pid, sid, "clip-1", reference_asset_id=aid_a, role="character_identity", influence="strong"
    )
    assert v2["activeVersion"] == 2
    assert v2["count"] == 2
    # Use active-version binding id (COW remints row ids each version).
    style_id = next(b["bindingId"] for b in v2["bindings"] if b["role"] == "style")

    v3 = svc.delete_binding(pid, sid, "clip-1", style_id)
    assert v3["activeVersion"] == 3
    assert v3["count"] == 1

    restored = svc.restore_version(pid, sid, "clip-1", 1)
    assert restored["activeVersion"] == 4
    assert restored["count"] == 1
    assert restored["bindings"][0]["role"] == "style"


def test_cycle_detection(db: Session, monkeypatch: pytest.MonkeyPatch):
    _enable_flag(monkeypatch)
    pid, sid, aid_a, aid_b = _ids(db)
    svc = TimelineReferenceService(db)
    svc.add_binding(
        pid,
        sid,
        "clip-1",
        reference_asset_id=aid_b,
        role="continuity",
        source="timeline_image",
        source_timeline_item_id="clip-2",
    )
    with pytest.raises(Exception) as exc:
        svc.add_binding(
            pid,
            sid,
            "clip-2",
            reference_asset_id=aid_a,
            role="continuity",
            source="timeline_image",
            source_timeline_item_id="clip-1",
        )
    assert getattr(exc.value, "code", "") == "reference_cycle_detected"


def test_package_shape_empty_and_populated(db: Session, monkeypatch: pytest.MonkeyPatch):
    _enable_flag(monkeypatch)
    pid, sid, _, aid_b = _ids(db)
    builder = ReferencePackageBuilder(db)
    empty = builder.build(pid, sid, "clip-1")
    assert empty["primaryFrame"]["role"] == "primary_frame"
    assert empty["primaryFrame"]["timelineItemId"] == "clip-1"
    assert empty["referenceSet"] is None
    assert empty["support"]["status"] == "ready"

    TimelineReferenceService(db).add_binding(pid, sid, "clip-1", reference_asset_id=aid_b, role="style")
    pkg = builder.build(pid, sid, "clip-1")
    assert pkg["referenceSet"] is not None
    assert pkg["referenceSet"]["bindings"]
    assert pkg["support"]["status"] in ("ready", "degraded")
    check = builder.validate_package(pid, sid, "clip-1")
    assert check["blocksRun"] is False


def test_api_flag_gate_and_crud(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    created = client.post("/api/projects", json={"name": "HTTP Refs"})
    assert created.status_code == 200
    project_id = created.json()["id"]
    scenes = client.get(f"/api/projects/{project_id}/scenes")
    assert scenes.status_code == 200
    scene_list = scenes.json()
    if isinstance(scene_list, dict):
        scene_id = (scene_list.get("scenes") or scene_list.get("items") or [scene_list])[0]["id"]
    else:
        scene_id = scene_list[0]["id"]

    director = client.get(f"/api/projects/{project_id}/scenes/{scene_id}/director")
    assert director.status_code == 200
    body = director.json()
    body["image_clips"] = [
        {
            "id": "http-clip-1",
            "asset_id": None,
            "start": 0,
            "length": 2,
            "role": "guide",
            "label": "Image 1",
        }
    ]
    put = client.put(f"/api/projects/{project_id}/scenes/{scene_id}/director", json=body)
    assert put.status_code == 200
    tagged = put.json()["image_clips"][0]
    tag = tagged.get("display_tag") or tagged.get("displayTag") or ""
    assert str(tag).startswith("@Image"), tagged
    item_id = tagged["id"]

    import app.director_references.service as svc_mod
    import app.feature_flags as ff

    off = FeatureFlags.from_env({})
    monkeypatch.setattr(ff, "feature_flags", off)
    monkeypatch.setattr(svc_mod, "feature_flags", off)
    denied = client.get(
        f"/api/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references"
    )
    assert denied.status_code == 404

    _enable_flag(monkeypatch)
    db = SessionLocal()
    try:
        db.merge(
            Asset(
                id="http-asset-1",
                project_id=project_id,
                tag="ref",
                kind="image",
                filename="r.png",
                path="r.png",
            )
        )
        db.commit()
    finally:
        db.close()

    listed = client.get(
        f"/api/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references"
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 0

    added = client.post(
        f"/api/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references",
        json={"referenceAssetId": "http-asset-1", "role": "style", "influence": "loose"},
    )
    assert added.status_code == 200
    assert added.json()["count"] == 1

    pkg = client.get(
        f"/api/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/reference-package"
    )
    assert pkg.status_code == 200
    assert pkg.json()["primaryFrame"]["displayTag"]
    assert pkg.json()["referenceSet"] is not None
