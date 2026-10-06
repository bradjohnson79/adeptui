"""Timeline reference eligibility. Server owns the union. Classification does not bind a shot."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.film_timeline.orchestrator import attach_reference, new_shot
from app.film_timeline.store import load_film
from app.scene_references.reference_eligibility import (
    creator_roles_for_project,
    resolve_reference_role,
    set_explicit_reference_role,
    stamp_aligned_role,
)


def _ready(db: Session) -> tuple[str, str]:
    Base.metadata.create_all(bind=engine)
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Reference Taxonomy"))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="",
            engine="minimax-h3",
            duration_sec=10,
            director_json=json.dumps({"timelineMaster": {"version": 1, "batchBlocks": []}}),
        )
    )
    db.commit()
    return pid, sid


def _image(db: Session, project_id: str, filename: str, approved_as: str | None = None) -> Asset:
    meta: dict[str, str] = {}
    if approved_as is not None:
        meta["approvedAs"] = approved_as
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="image",
        tag="",
        filename=filename,
        path=f"library/{filename}",
        prompt_meta_json=json.dumps(meta),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _saved_character(db: Session, project_id: str, asset_id: str, *, role: str = "hero_identity") -> None:
    profile_id = str(uuid.uuid4())
    db.add(CharacterProfileRow(id=profile_id, project_id=project_id, name="Renkoka"))
    db.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=profile_id,
            asset_id=asset_id,
            reference_role=role,
            approval_status="approved",
            canonical=True,
        )
    )
    db.commit()


def _resolved(db: Session, project_id: str, asset: Asset) -> dict:
    return resolve_reference_role(
        kind=asset.kind,
        prompt_meta=asset.prompt_meta_json,
        creator_role=creator_roles_for_project(db, project_id).get(asset.id),
    )


def test_a_generic_image_has_no_image_tab():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "seg_01_head.png")
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] is None
        assert resolved["referenceRoleSource"] == "none"
    finally:
        db.close()


def test_b_explicit_character_is_character_only():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "plate.png", "character")
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] == "character"
        assert resolved["referenceRoleSource"] == "explicit"
    finally:
        db.close()


def test_c_saved_character_without_approved_as_is_character():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "Renkoka Front.png")
        _saved_character(db, pid, asset.id)
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] == "character"
        assert resolved["referenceRoleSource"] == "creator"
        assert resolved["creatorReferenceRole"] == "character"
    finally:
        db.close()


def test_d_saved_character_overridden_to_prop_is_prop_only():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "Renkoka Front.png", "prop")
        _saved_character(db, pid, asset.id)
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] == "prop"
        assert resolved["referenceRoleSource"] == "override"
        assert resolved["creatorReferenceRole"] == "character"
    finally:
        db.close()


def test_e_clearing_override_returns_the_saved_character():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "Renkoka Front.png", "prop")
        _saved_character(db, pid, asset.id)
        cleared = set_explicit_reference_role(db, pid, asset.id, None)
        assert cleared["effectiveReferenceRole"] == "character"
        assert cleared["referenceRoleSource"] == "creator"
        db.refresh(asset)
        assert "approvedAs" not in json.loads(asset.prompt_meta_json)
    finally:
        db.close()


def test_h_scene_frame_is_not_an_image_reference_role():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "tail-500.png", "scene_frame")
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] is None
        assert resolved["referenceRoleSource"] == "none"
    finally:
        db.close()


def test_sheet_tile_and_filename_do_not_become_a_character():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "character_sheet_front.png")
        _saved_character(db, pid, asset.id, role="closeup_front")
        resolved = _resolved(db, pid, asset)
        assert resolved["effectiveReferenceRole"] is None
    finally:
        db.close()


def test_i_and_j_classification_does_not_rewrite_the_shot_or_create_a_character():
    db = SessionLocal()
    try:
        pid, sid = _ready(db)
        asset = _image(db, pid, "Renkoka.png", "character")
        profiles_before = db.query(CharacterProfileRow).count()
        bindings_before = db.query(CharacterReferenceAssetRow).count()
        created = new_shot(db, pid, sid, name="Shot 4")
        shot_id = created["shot"]["id"]
        attach_reference(
            db,
            pid,
            sid,
            shot_id,
            asset_id=asset.id,
            ref_type="character",
            label="Renkoka",
            tag="Renkoka",
        )
        before = json.loads(db.get(Scene, sid).director_json)
        master_before = before.get("timelineMaster")
        shots_before = before["filmTimeline"]["shots"]
        bound_before = [
            ref
            for shot in shots_before
            for ref in (shot.get("state") or {}).get("references") or []
            if ref.get("assetId") == asset.id
        ]
        assert len(bound_before) == 1
        assert bound_before[0]["type"] == "character"

        classified = set_explicit_reference_role(db, pid, asset.id, "prop")
        assert classified["effectiveReferenceRole"] == "prop"
        assert classified["referenceRoleSource"] == "explicit"

        db.expire_all()
        after = json.loads(db.get(Scene, sid).director_json)
        assert after.get("timelineMaster") == master_before
        bound_after = [
            ref
            for shot in after["filmTimeline"]["shots"]
            for ref in (shot.get("state") or {}).get("references") or []
            if ref.get("assetId") == asset.id
        ]
        assert bound_after == bound_before
        reloaded = load_film(db, pid, sid)
        assert reloaded["ok"] is True
        live = [
            ref
            for shot in reloaded["film"].shots
            for ref in shot.state.references
            if ref.assetId == asset.id
        ]
        assert len(live) == 1
        assert live[0].type == "character"
        assert db.query(CharacterProfileRow).count() == profiles_before
        assert db.query(CharacterReferenceAssetRow).count() == bindings_before
    finally:
        db.close()


def test_g_remove_reference_clears_a_manual_role():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        asset = _image(db, pid, "generic.png")
        classified = set_explicit_reference_role(db, pid, asset.id, "character")
        assert classified["effectiveReferenceRole"] == "character"
        assert classified["referenceRoleSource"] == "explicit"
        cleared = set_explicit_reference_role(db, pid, asset.id, None)
        assert cleared["effectiveReferenceRole"] is None
        assert cleared["referenceRoleSource"] == "none"
    finally:
        db.close()


def test_stamp_does_not_clobber_an_override_and_scene_frame_is_not_protected():
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        overridden = _image(db, pid, "hero.png", "prop")
        assert stamp_aligned_role(overridden, "character") is False
        assert json.loads(overridden.prompt_meta_json)["approvedAs"] == "prop"
        frame = _image(db, pid, "frame.png", "scene_frame")
        assert stamp_aligned_role(frame, "character") is True
        assert json.loads(frame.prompt_meta_json)["approvedAs"] == "character"
    finally:
        db.close()


def test_route_rejects_scene_frame_and_video(client):
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        image = _image(db, pid, "still.png")
        video = Asset(
            id=str(uuid.uuid4()),
            project_id=pid,
            kind="video",
            tag="",
            filename="plate.mp4",
            path="library/plate.mp4",
        )
        db.add(video)
        db.commit()
        video_id = video.id
        image_id = image.id
    finally:
        db.close()

    rejected = client.put(
        f"/api/projects/{pid}/assets/{image_id}/reference-classification",
        json={"approvedAs": "scene_frame"},
    )
    assert rejected.status_code == 400
    media = client.put(
        f"/api/projects/{pid}/assets/{video_id}/reference-classification",
        json={"approvedAs": "character"},
    )
    assert media.status_code == 400
    saved = client.put(
        f"/api/projects/{pid}/assets/{image_id}/reference-classification",
        json={"approvedAs": "environment"},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["effectiveReferenceRole"] == "environment"
    assert body["referenceRoleSource"] == "explicit"


def test_library_ids_returns_a_classified_asset_outside_the_first_page(client):
    db = SessionLocal()
    try:
        pid, _sid = _ready(db)
        older = _image(db, pid, "Renkoka sample.png")
        older.tag = "Renkoka-sample"
        db.commit()
        asset_id = older.id
    finally:
        db.close()

    saved = client.put(
        f"/api/projects/{pid}/assets/{asset_id}/reference-classification",
        json={"approvedAs": "character"},
    )
    assert saved.status_code == 200, saved.text
    looked_up = client.get(f"/api/projects/{pid}/library?scope=project&ids={asset_id}")
    assert looked_up.status_code == 200, looked_up.text
    rows = looked_up.json()["items"]
    assert [row["id"] for row in rows] == [asset_id]
    assert rows[0]["effectiveReferenceRole"] == "character"
    assert rows[0]["referenceRoleSource"] == "explicit"
