"""Prop Creator user-uploaded views — Basic + Advanced, mixed source, Global."""

from __future__ import annotations

import io
import json
import uuid

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.db import Asset, Project, SessionLocal, init_db
from app.prop_creator.service import (
    PropCreatorError,
    approve_candidate,
    create_or_update_prop,
    get_prop,
    upload_identity_from_bytes,
)
from app.prop_creator.view_upload import validate_prop_image_bytes


def _png(size: int = 64, color=(20, 80, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def _session() -> Session:
    init_db()
    return SessionLocal()


def _project(name: str = "Prop Upload") -> str:
    db = _session()
    try:
        pid = str(uuid.uuid4())
        db.add(Project(id=pid, name=name))
        db.commit()
        return pid
    finally:
        db.close()


def test_validate_prop_image_rejects_video_and_tiny():
    with pytest.raises(HTTPException) as video:
        validate_prop_image_bytes(b"\x00\x00\x00\x18ftypmp42", filename="clip.mp4", content_type="video/mp4")
    assert video.value.detail["code"] == "NOT_AN_IMAGE"
    with pytest.raises(HTTPException) as tiny:
        validate_prop_image_bytes(_png(8), filename="tiny.png")
    assert tiny.value.detail["code"] == "IMAGE_TOO_SMALL"
    ok = validate_prop_image_bytes(_png(64), filename="front.png")
    assert ok["width"] == 64


def test_basic_upload_is_candidate_same_prop_library_meta():
    from app.prop_creator.view_upload import PROP_VIEW_ROLE, SOURCE_UPLOADED

    project_id = _project("Basic Upload")
    db = _session()
    try:
        prop = create_or_update_prop(db, project_id, name="Cade Starfighter")
        tag = prop.tag
        uploaded = upload_identity_from_bytes(
            db,
            project_id,
            prop.id,
            data=_png(80, (12, 90, 40)),
            filename="starfighter-front.png",
            content_type="image/png",
        )
        assert uploaded.id == prop.id
        assert uploaded.tag == tag
        assert not (uploaded.approved_asset_id or "").strip()
        cand = uploaded.candidates[-1]
        assert cand.origin == SOURCE_UPLOADED
        assert cand.status == "complete"
        assert cand.asset_id
        asset = db.get(Asset, cand.asset_id)
        assert asset is not None
        meta = json.loads(asset.prompt_meta_json or "{}")
        assert meta["role"] == PROP_VIEW_ROLE
        assert meta["view"] == "primary"
        assert meta["source"] == SOURCE_UPLOADED
        assert meta["propId"] == prop.id
        assert "Starfighter" in (asset.tag or "")
        assert "Primary" in (asset.tag or "")
        approved = approve_candidate(db, project_id, uploaded.id, cand.id)
        assert approved.approved_asset_id == cand.asset_id
        assert approved.id == prop.id
        assert approved.tag == tag
    finally:
        db.close()


def test_advanced_upload_views_mixed_source_same_prop():
    from app.prop_creator import advanced_service as adv
    from app.prop_creator.view_upload import SOURCE_GENERATED, SOURCE_UPLOADED

    project_id = _project("Advanced Upload")
    db = _session()
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            name="Cade Starfighter",
            mode="advanced",
            advanced_type="spacecraft",
            primary_prompt="blue starfighter",
        )
        prop_id = prop.id
        tag = prop.tag
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop_id, data=_png(72, (8, 8, 90)), filename="primary.png"
        )
        cand = prop.candidates[-1]
        prop = adv.approve_primary(db, project_id, prop_id, candidate_id=cand.id)
        assert prop.primary_phase == "approved"
        assert prop.id == prop_id
        assert prop.tag == tag

        for angle, color in (("front", (1, 2, 3)), ("back", (4, 5, 6)), ("right", (7, 8, 9)), ("bottom", (10, 11, 12)), ("hero", (13, 14, 15))):
            prop = adv.upload_angle_from_bytes(
                db, project_id, prop_id, angle, data=_png(70, color), filename=f"{angle}.png"
            )
            slot = prop.angles[angle]
            assert slot.approved is False
            assert slot.source == SOURCE_UPLOADED
            assert slot.asset_id
            asset = db.get(Asset, slot.asset_id)
            meta = json.loads(asset.prompt_meta_json or "{}")
            assert meta["view"] == angle
            assert meta["propId"] == prop_id
            assert meta["source"] == SOURCE_UPLOADED
            assert "%" not in (asset.tag or "")

        # Generated-shaped slots (no live Qwen) still count once approved.
        from app.spatial_map.ers_contracts import PropAngleSlot

        for angle in ("left", "top"):
            aid = str(uuid.uuid4())
            dest = Asset(
                id=aid,
                project_id=project_id,
                tag=f"Cade Starfighter — {angle.title()}",
                kind="image",
                filename=f"{angle}.png",
                path="generated.png",
            )
            db.add(dest)
            db.commit()
            slot = PropAngleSlot(
                key=angle,
                status="complete",
                asset_id=aid,
                approved=False,
                source=SOURCE_GENERATED,
            )
            prop.angles[angle] = slot
        from app.spatial_map.ers_persistence import save_prop_entity

        save_prop_entity(db, project_id, prop)
        for angle in ("front", "back", "left", "right", "top", "bottom"):
            prop = adv.approve_angle(db, project_id, prop_id, angle, approved=True)
        assert prop.angles["front"].source == SOURCE_UPLOADED
        assert prop.angles["left"].source == SOURCE_GENERATED
        assert all(prop.angles[a].approved for a in ("front", "back", "left", "right", "top", "bottom"))
        listed = get_prop(db, project_id, prop_id)
        assert listed.id == prop_id
    finally:
        db.close()


def test_approve_primary_keeps_uploaded_angles():
    from app.prop_creator import advanced_service as adv

    project_id = _project("Keep Uploaded")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Keep Views", mode="advanced", primary_prompt="keep"
        )
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(64, (1, 1, 1)), filename="p1.png"
        )
        first = prop.candidates[-1]
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=first.id)
        prop = adv.upload_angle_from_bytes(
            db, project_id, prop.id, "front", data=_png(64, (2, 2, 2)), filename="f.png"
        )
        front_id = prop.angles["front"].asset_id
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(64, (3, 3, 3)), filename="p2.png"
        )
        second = prop.candidates[-1]
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=second.id)
        assert prop.angles["front"].asset_id == front_id
        assert prop.angles["front"].source == "uploaded"
        assert prop.angles["front"].approved is False
    finally:
        db.close()


def test_prs_readiness_is_source_independent(tmp_path, monkeypatch):
    from app.config import settings
    from app.prop_creator import advanced_service as adv
    from app.prop_creator.view_upload import SOURCE_GENERATED, SOURCE_UPLOADED
    from app.spatial_map.ers_contracts import PropAngleSlot
    from app.spatial_map.ers_persistence import save_prop_entity

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    project_id = _project("PRS Mix")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Mixed PRS", mode="advanced", primary_prompt="mix"
        )
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(80), filename="p.png"
        )
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=prop.candidates[-1].id)
        for angle, src, color in (
            ("front", SOURCE_UPLOADED, (1, 0, 0)),
            ("back", SOURCE_UPLOADED, (0, 1, 0)),
            ("left", SOURCE_GENERATED, (0, 0, 1)),
            ("right", SOURCE_UPLOADED, (1, 1, 0)),
            ("top", SOURCE_GENERATED, (1, 0, 1)),
            ("bottom", SOURCE_UPLOADED, (0, 1, 1)),
        ):
            if src == SOURCE_UPLOADED:
                prop = adv.upload_angle_from_bytes(
                    db, project_id, prop.id, angle, data=_png(80, color), filename=f"{angle}.png"
                )
            else:
                aid = str(uuid.uuid4())
                dest = tmp_path / "assets" / project_id
                dest.mkdir(parents=True, exist_ok=True)
                path = dest / f"{aid}.png"
                path.write_bytes(_png(80, color))
                db.add(
                    Asset(
                        id=aid,
                        project_id=project_id,
                        tag=f"Mixed PRS — {angle}",
                        kind="image",
                        filename=f"{angle}.png",
                        path=str(path),
                    )
                )
                db.commit()
                prop.angles[angle] = PropAngleSlot(
                    key=angle, status="complete", asset_id=aid, approved=False, source=src
                )
                save_prop_entity(db, project_id, prop)
            prop = adv.approve_angle(db, project_id, prop.id, angle, approved=True)
        paths = adv._approved_angle_paths(db, project_id, get_prop(db, project_id, prop.id))
        keys = [k for k, _ in paths]
        assert keys[0] == "primary"
        assert keys[1:7] == ["front", "back", "left", "right", "top", "bottom"]
    finally:
        db.close()


def test_global_prop_view_readable_from_other_project_upload_stays_owned():
    from app.creator_scope.service import ensure_creator_scope_tables, resolve_readable_asset
    from app.prop_creator import advanced_service as adv

    ensure_creator_scope_tables()
    project_a = _project("Global A")
    project_b = _project("Global B")
    db = _session()
    try:
        prop = create_or_update_prop(
            db,
            project_a,
            name="Global Starfighter",
            mode="advanced",
            primary_prompt="global",
            is_global=True,
        )
        prop = adv.upload_primary_from_bytes(
            db, project_a, prop.id, data=_png(64), filename="gp.png"
        )
        prop = adv.approve_primary(db, project_a, prop.id, candidate_id=prop.candidates[-1].id)
        prop = adv.upload_angle_from_bytes(
            db, project_a, prop.id, "front", data=_png(64, (9, 9, 9)), filename="gf.png"
        )
        prop = adv.approve_angle(db, project_a, prop.id, "front", approved=True)
        visible = get_prop(db, project_b, prop.id)
        assert visible.id == prop.id
        front_id = visible.angles["front"].asset_id
        readable = resolve_readable_asset(db, project_b, front_id)
        assert readable is not None
        with pytest.raises(PropCreatorError) as blocked:
            adv.upload_angle_from_bytes(
                db, project_b, prop.id, "back", data=_png(64), filename="nope.png"
            )
        assert blocked.value.status_code == 403
        assert blocked.value.code == "OWNER_REQUIRED"
        from app.prop_creator.service import delete_prop

        delete_prop(db, project_a, prop.id, confirm_cross_project=True)
    finally:
        db.close()


def test_codirector_get_views_matches_store():
    import asyncio

    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import prop_creator as cd
    from app.prop_creator import advanced_service as adv

    project_id = _project("CD Views")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="CD Starfighter", mode="advanced", primary_prompt="cd"
        )
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(64), filename="cdp.png"
        )
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=prop.candidates[-1].id)
        prop = adv.upload_angle_from_bytes(
            db, project_id, prop.id, "top", data=_png(64, (2, 4, 6)), filename="top.png"
        )
        ctx = ToolContext(db=db, project_id=project_id)
        out = asyncio.run(cd.get_views(ctx, {"propName": "CD Starfighter"}))
        assert out["ok"] is True
        assert out["propId"] == prop.id
        assert out["sameStore"] is True
        assert out["angles"]["top"]["source"] == "uploaded"
        assert out["angles"]["top"]["approved"] is False
        adopted = cd.apply_adopt_view(
            ctx,
            {"propId": prop.id, "view": "back", "assetId": prop.angles["top"].asset_id},
        )
        assert adopted["propId"] == prop.id
        assert adopted["view"] == "back"
        assert adopted["approved"] is False
    finally:
        db.close()
