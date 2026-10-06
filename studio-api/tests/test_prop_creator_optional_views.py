"""Owner correction: Primary required, additional views optional."""

from __future__ import annotations

import asyncio
import io
import uuid

from PIL import Image
from sqlalchemy.orm import Session

from app.db import Asset, Project, SessionLocal, init_db
from app.prop_creator import advanced_service as adv
from app.prop_creator.readiness import (
    can_approve_primary,
    identity_ready,
    readiness_payload,
    valid_primary_candidate_asset_id,
    visible_primary_preview_asset_id,
)
from app.prop_creator.service import create_or_update_prop, get_prop


def _png(size: int = 64, color=(20, 80, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def _session() -> Session:
    init_db()
    return SessionLocal()


def _project(name: str) -> str:
    db = _session()
    try:
        pid = str(uuid.uuid4())
        db.add(Project(id=pid, name=name))
        db.commit()
        return pid
    finally:
        db.close()


def test_upload_primary_enables_approve_without_other_views():
    project_id = _project("Upload Enables Approve")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Smoke Ship", mode="advanced", primary_prompt="ship"
        )
        assert can_approve_primary(prop) is False
        assert identity_ready(prop) is False
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(72, (9, 9, 90)), filename="primary.png"
        )
        listed = get_prop(db, project_id, prop.id)
        assert valid_primary_candidate_asset_id(listed)
        assert can_approve_primary(listed) is True
        assert identity_ready(listed) is False
        assert listed.angles
        assert not any(slot.approved for slot in listed.angles.values())
        prop = adv.approve_primary(db, project_id, listed.id, candidate_id=listed.candidates[-1].id)
        assert identity_ready(prop) is True
        assert can_approve_primary(prop) is False
        ready = readiness_payload(prop)
        assert ready["propReady"] is True
        assert ready["missingViewsBlockReadiness"] is False
        assert "front" in ready["missingOptionalViews"]
    finally:
        db.close()


def test_no_primary_candidate_cannot_approve():
    project_id = _project("No Primary")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Empty Ship", mode="advanced", primary_prompt="empty"
        )
        assert can_approve_primary(prop) is False
        assert identity_ready(prop) is False
        from app.prop_creator.service import PropCreatorError

        try:
            adv.approve_primary(db, project_id, prop.id)
            raise AssertionError("approve without candidate must fail")
        except PropCreatorError:
            pass
    finally:
        db.close()


def test_optional_views_alone_do_not_make_identity_valid():
    project_id = _project("Optionals Only")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Hull Only", mode="advanced", primary_prompt="hull"
        )
        prop = adv.upload_angle_from_bytes(
            db, project_id, prop.id, "front", data=_png(64, (1, 2, 3)), filename="front.png"
        )
        prop = adv.approve_angle(db, project_id, prop.id, "front", approved=True)
        assert prop.angles["front"].approved is True
        assert identity_ready(prop) is False
        assert can_approve_primary(prop) is False
    finally:
        db.close()


def test_partial_prs_skips_missing_views(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    project_id = _project("Partial PRS")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Partial Ship", mode="advanced", primary_prompt="partial"
        )
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(80), filename="p.png"
        )
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=prop.candidates[-1].id)
        for angle, color in (("front", (1, 0, 0)), ("back", (0, 1, 0)), ("top", (0, 0, 1))):
            prop = adv.upload_angle_from_bytes(
                db, project_id, prop.id, angle, data=_png(80, color), filename=f"{angle}.png"
            )
            prop = adv.approve_angle(db, project_id, prop.id, angle, approved=True)
        paths = adv._approved_angle_paths(db, project_id, get_prop(db, project_id, prop.id))
        keys = [k for k, _ in paths]
        assert keys == ["primary", "front", "back", "top"]
        assert "right" not in keys
        assert "hero" not in keys
    finally:
        db.close()


def test_mixed_source_approvals_same_prop():
    project_id = _project("Mixed Source")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="Mixed Ship", mode="advanced", primary_prompt="mix"
        )
        prop_id = prop.id
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop_id, data=_png(70, (2, 2, 8)), filename="p.png"
        )
        prop = adv.approve_primary(db, project_id, prop_id, candidate_id=prop.candidates[-1].id)
        prop = adv.upload_angle_from_bytes(
            db, project_id, prop_id, "front", data=_png(70, (8, 2, 2)), filename="f.png"
        )
        prop = adv.approve_angle(db, project_id, prop_id, "front", approved=True)
        from app.spatial_map.ers_contracts import PropAngleSlot
        from app.spatial_map.ers_persistence import save_prop_entity

        aid = str(uuid.uuid4())
        db.add(
            Asset(
                id=aid,
                project_id=project_id,
                tag="Mixed Ship — Left",
                kind="image",
                filename="left.png",
                path="generated.png",
            )
        )
        db.commit()
        prop.angles["left"] = PropAngleSlot(
            key="left", status="complete", asset_id=aid, approved=False, source="generated"
        )
        save_prop_entity(db, project_id, prop)
        prop = adv.approve_angle(db, project_id, prop_id, "left", approved=True)
        assert prop.id == prop_id
        assert prop.angles["front"].source == "uploaded"
        assert prop.angles["left"].source == "generated"
        assert prop.angles["front"].approved and prop.angles["left"].approved
        assert identity_ready(prop) is True
    finally:
        db.close()


def test_codirector_ready_on_primary_only():
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import prop_creator as cd

    project_id = _project("CD Ready")
    db = _session()
    try:
        prop = create_or_update_prop(
            db, project_id, name="CD Ready Ship", mode="advanced", primary_prompt="cd"
        )
        prop = adv.upload_primary_from_bytes(
            db, project_id, prop.id, data=_png(64), filename="cdp.png"
        )
        prop = adv.approve_primary(db, project_id, prop.id, candidate_id=prop.candidates[-1].id)
        prop = adv.upload_angle_from_bytes(
            db, project_id, prop.id, "top", data=_png(64, (2, 4, 6)), filename="top.png"
        )
        prop = adv.approve_angle(db, project_id, prop.id, "top", approved=True)
        ctx = ToolContext(db=db, project_id=project_id)
        out = asyncio.run(cd.get_views(ctx, {"propName": "CD Ready Ship"}))
        assert out["propReady"] is True
        assert out["sheetReady"] is True
        assert out["missingViewsBlockReadiness"] is False
        assert "front" in out["missingOptionalViews"]
        assert "hero" in out["missingOptionalViews"]
        assert "top" not in out["missingOptionalViews"]
    finally:
        db.close()


def test_preview_uses_pending_replacement_not_stale_approved():
    from app.spatial_map.ers_contracts import PropCandidate, PropEntity

    prop = PropEntity(
        id="prop-1",
        project_id="proj-1",
        tag="ship",
        display_label="Ship",
        mode="advanced",
        primary_phase="approved",
        primary_approved_asset_id="old-blue",
        approved_asset_id="old-blue",
        candidates=[
            PropCandidate(id="c1", prop_id="prop-1", index=0, asset_id="old-blue", status="complete"),
            PropCandidate(id="c2", prop_id="prop-1", index=1, asset_id="new-real", status="complete"),
        ],
    )
    assert visible_primary_preview_asset_id(prop) == "new-real"
    ready = readiness_payload(prop)
    assert ready["previewPrimaryAssetId"] == "new-real"
    assert ready["approvedPrimaryAssetId"] == "old-blue"
    assert ready["canApprovePrimary"] is True
