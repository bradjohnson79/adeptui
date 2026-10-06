"""Global Character / Prop / Environment wiring contract — no hardcoded production UUIDs."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate
from app.character_identity.service import (
    create_profile,
    get_profile,
    list_profiles,
    update_profile,
)
from app.creator_scope.contract import is_ephemeral_creator_fixture, strip_machine_notes
from app.creator_scope.service import ensure_creator_scope_tables, resolve_readable_asset
from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def db(monkeypatch: pytest.MonkeyPatch) -> Session:
    _apply_flags(monkeypatch)
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    ensure_creator_scope_tables()
    session = SessionLocal()
    yield session
    session.close()


def _project(db: Session, name: str) -> str:
    pid = f"wire-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _image(db: Session, project_id: str, filename: str = "ref.png") -> Asset:
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag="character_reference",
        kind="image",
        filename=filename,
        path=filename,
    )
    db.add(asset)
    db.commit()
    return asset


def test_character_promote_keeps_id_tag_description(db: Session):
    owner = _project(db, "Owner")
    viewer = _project(db, "Viewer")
    created = create_profile(
        db,
        owner,
        CharacterProfileCreate(name=f"KorriWire{uuid.uuid4().hex[:8]}", slug=f"korriwire{uuid.uuid4().hex[:6]}", description="Sun sprite"),
    )
    updated = update_profile(db, owner, created.id, CharacterProfileUpdate(is_global=True))
    assert updated.id == created.id
    assert updated.slug == created.slug
    assert updated.description == "Sun sprite"
    assert updated.is_global is True
    visible = get_profile(db, viewer, created.id)
    assert visible.id == created.id
    assert visible.slug == created.slug
    reloaded = get_profile(db, owner, created.id)
    assert reloaded.id == created.id
    assert reloaded.is_global is True


def test_placeholder_new_character_never_overwrites_existing(db: Session):
    owner = _project(db, "Owner")
    created = create_profile(db, owner, CharacterProfileCreate(name=f"KorriWire{uuid.uuid4().hex[:8]}", slug=f"korri{uuid.uuid4().hex[:6]}"))
    updated = update_profile(
        db,
        owner,
        created.id,
        CharacterProfileUpdate(name="New Character", is_global=True),
    )
    assert updated.name == created.name
    assert updated.slug == created.slug
    assert updated.is_global is True
    row = db.get(CharacterProfileRow, created.id)
    assert row is not None
    assert row.name == created.name
    assert row.slug == created.slug


def test_placeholder_slug_repairs_on_owned_get(db: Session):
    owner = _project(db, "Owner")
    token = uuid.uuid4().hex[:8]
    created = create_profile(db, owner, CharacterProfileCreate(name=f"KorriWire{token}", slug=f"korriwire{token}"))
    row = db.get(CharacterProfileRow, created.id)
    assert row is not None
    row.slug = "new-character"
    db.commit()
    repaired = get_profile(db, owner, created.id)
    assert repaired.slug == f"korriwire{token}"
    assert repaired.name == f"KorriWire{token}"


def test_prop_save_does_not_uniquify_existing_tag(db: Session):
    from app.prop_creator.service import create_or_update_prop, get_prop

    owner = _project(db, "Owner")
    first = create_or_update_prop(db, owner, name=f"Venture Wire {uuid.uuid4().hex[:6]}")
    first.tag = "VentureSpaceshipWire"
    from app.spatial_map.ers_persistence import save_prop_entity

    save_prop_entity(db, owner, first)
    saved = create_or_update_prop(
        db,
        owner,
        prop_id=first.id,
        name=first.display_label,
        description="Orbital carrier",
        is_global=True,
    )
    assert saved.id == first.id
    assert saved.tag == "VentureSpaceshipWire"
    assert saved.description == "Orbital carrier"
    assert "prsAssetId" not in saved.description
    reloaded = get_prop(db, owner, first.id)
    assert reloaded.tag == "VentureSpaceshipWire"
    assert reloaded.description == "Orbital carrier"


def test_description_does_not_absorb_prs_markers(db: Session):
    from app.prop_creator.service import create_or_update_prop, get_prop

    owner = _project(db, "Owner")
    prop = create_or_update_prop(db, owner, name=f"Marker Ship {uuid.uuid4().hex[:6]}")
    leaked = "prsAssetId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee adeptWorkingProp=1 universalAdeptProp=1"
    dirty = create_or_update_prop(db, owner, prop_id=prop.id, name=prop.display_label, description=leaked)
    assert dirty.description == ""
    assert "prsAssetId" not in (dirty.notes or "")
    reloaded = get_prop(db, owner, prop.id)
    assert reloaded.description == ""
    assert strip_machine_notes(leaked) == ""


def test_foreign_global_prop_mutates_only_from_owner(db: Session):
    from app.prop_creator.service import PropCreatorError, create_or_update_prop, get_prop

    owner = _project(db, "Owner")
    viewer = _project(db, "Viewer")
    prop = create_or_update_prop(db, owner, name=f"Shared Ship {uuid.uuid4().hex[:6]}", is_global=True)
    viewed = get_prop(db, viewer, prop.id)
    assert viewed.id == prop.id
    with pytest.raises(PropCreatorError) as exc:
        create_or_update_prop(db, viewer, prop_id=prop.id, name=prop.display_label, is_global=True)
    assert exc.value.status_code == 403
    assert exc.value.code == "OWNER_REQUIRED"
    from app.prop_creator.service import approve_candidate, generate_candidates, retry_candidate, use_as_prop_identity

    with pytest.raises(PropCreatorError) as gen_exc:
        generate_candidates(db, viewer, prop.id)
    assert gen_exc.value.status_code == 403
    assert gen_exc.value.code == "OWNER_REQUIRED"
    with pytest.raises(PropCreatorError) as retry_exc:
        retry_candidate(db, viewer, prop.id, "missing")
    assert retry_exc.value.status_code == 403
    with pytest.raises(PropCreatorError) as ident_exc:
        use_as_prop_identity(db, viewer, prop.id, asset_id="missing")
    assert ident_exc.value.status_code == 403
    with pytest.raises(PropCreatorError) as approve_exc:
        approve_candidate(db, viewer, prop.id, "missing")
    assert approve_exc.value.status_code == 403


def test_standard_and_advanced_remove_are_detach_only(db: Session):
    from app.prop_creator import advanced_service as adv
    from app.prop_creator.service import create_or_update_prop, get_prop
    from app.spatial_map.ers_contracts import PropAngleSlot

    owner = _project(db, "Owner")
    asset = _image(db, owner, "primary.png")
    angle_asset = _image(db, owner, "front.png")
    prop = create_or_update_prop(
        db,
        owner,
        name=f"Detach Ship {uuid.uuid4().hex[:6]}",
        mode="advanced",
        reference_asset_id=asset.id,
    )
    prop.approved_asset_id = asset.id
    prop.library_asset_id = asset.id
    prop.angles["front"] = PropAngleSlot(key="front", status="approved", asset_id=angle_asset.id, approved=True)
    from app.spatial_map.ers_persistence import save_prop_entity

    save_prop_entity(db, owner, prop)

    detached = create_or_update_prop(
        db,
        owner,
        prop_id=prop.id,
        name=prop.display_label,
        clear_reference=True,
    )
    assert detached.reference_asset_id in {None, ""}
    assert detached.id == prop.id
    assert db.get(Asset, asset.id) is not None
    reloaded = get_prop(db, owner, prop.id)
    assert reloaded.reference_asset_id in {None, ""}

    removed = adv.approve_angle(db, owner, prop.id, "front", approved=False)
    assert removed.angles["front"].asset_id in {None, ""}
    assert removed.angles["front"].approved is False
    again = get_prop(db, owner, prop.id)
    assert again.angles["front"].asset_id in {None, ""}
    assert db.get(Asset, angle_asset.id) is not None


def test_global_selector_excludes_wiring_smoke_names(db: Session):
    from app.prop_creator.service import create_or_update_prop, list_props

    owner = _project(db, "Owner")
    viewer = _project(db, "Viewer")
    create_profile(db, owner, CharacterProfileCreate(name=f"WiringSmoke {uuid.uuid4().hex[:6]} Character", is_global=True))
    create_profile(db, owner, CharacterProfileCreate(name=f"CharacterGlobalTest{uuid.uuid4().hex[:6]}", is_global=True))
    keep = create_profile(db, owner, CharacterProfileCreate(name=f"KeepWireChar{uuid.uuid4().hex[:6]}", is_global=True))
    create_or_update_prop(db, owner, name="WiringSmoke Prop", is_global=True)
    keep_prop = create_or_update_prop(db, owner, name=f"KeepWireProp{uuid.uuid4().hex[:6]}", is_global=True)
    names = {p.name for p in list_profiles(db, viewer)}
    assert keep.name in names
    assert not any(is_ephemeral_creator_fixture(n) for n in names)
    prop_names = {p.display_label for p in list_props(db, viewer)}
    assert keep_prop.display_label in prop_names
    assert "WiringSmoke Prop" not in prop_names


def test_cade_reconnects_from_library_assets_without_new_id(db: Session):
    owner = _project(db, "Cade Scenes")
    cid = str(uuid.uuid4())
    meta = json.dumps(
        {
            "characterId": cid,
            "characterName": "Cade O'Connor",
            "library": {"characterId": cid},
        }
    )
    db.add(
        Asset(
            id=str(uuid.uuid4()),
            project_id=owner,
            tag="character_reference",
            kind="image",
            filename="Cade CRS.png",
            path="cade-crs.png",
            prompt_meta_json=meta,
        )
    )
    db.commit()
    assert db.get(CharacterProfileRow, cid) is None
    listed = list_profiles(db, owner)
    assert any(p.id == cid for p in listed)
    healed = get_profile(db, owner, cid)
    assert healed.id == cid
    assert healed.name == "Cade O'Connor"
    again = list_profiles(db, owner)
    assert sum(1 for p in again if p.id == cid) == 1


def test_deleted_character_does_not_resurrect_from_library_assets(db: Session):
    from app.character_identity.service import delete_profile

    owner = _project(db, "Owner")
    created = create_profile(
        db,
        owner,
        CharacterProfileCreate(name=f"KeepWireGone{uuid.uuid4().hex[:6]}"),
    )
    db.add(
        Asset(
            id=str(uuid.uuid4()),
            project_id=owner,
            tag="character_reference",
            kind="image",
            filename="gone-crs.png",
            path="gone-crs.png",
            prompt_meta_json=json.dumps({"characterId": created.id, "characterName": created.name}),
        )
    )
    db.commit()
    delete_profile(db, owner, created.id)
    listed = list_profiles(db, owner)
    assert not any(p.id == created.id for p in listed)
    assert db.get(CharacterProfileRow, created.id) is None


def test_delete_global_prop_unlinks_foreign_bindings(db: Session):
    from app.db import engine
    from app.prop_creator.service import create_or_update_prop, delete_prop
    from app.scene_references.models import SceneReferenceBinding

    SceneReferenceBinding.__table__.create(bind=engine, checkfirst=True)
    owner = _project(db, "Owner")
    viewer = _project(db, "Viewer")
    prop = create_or_update_prop(db, owner, name=f"Shared Ship {uuid.uuid4().hex[:6]}", is_global=True)
    asset = _image(db, viewer, "bound.png")
    bind_id = str(uuid.uuid4())
    db.add(
        SceneReferenceBinding(
            id=bind_id,
            project_id=viewer,
            asset_id=asset.id,
            scope_type="scene",
            scope_id="shot-1",
            reference_type="prop",
            identity_id=prop.id,
            enabled=True,
        )
    )
    db.commit()
    delete_prop(db, owner, prop.id, confirm_cross_project=True)
    row = db.get(SceneReferenceBinding, bind_id)
    assert row is not None
    assert row.identity_id is None
    assert row.enabled is False


def test_global_prop_visual_resolves_from_other_project(db: Session):
    from app.prop_creator.service import create_or_update_prop

    owner = _project(db, "Owner")
    viewer = _project(db, "Viewer")
    asset = _image(db, owner, "venture-prs.png")
    prop = create_or_update_prop(
        db,
        owner,
        name=f"Venture Wire {uuid.uuid4().hex[:6]}",
        is_global=True,
        reference_asset_id=asset.id,
    )
    prop.advanced_sheet_asset_id = asset.id
    prop.advanced_sheet_status = "complete"
    from app.spatial_map.ers_persistence import save_prop_entity
    from app.prop_creator.service import _sync_prop_scope

    save_prop_entity(db, owner, prop)
    _sync_prop_scope(db, prop)
    readable = resolve_readable_asset(db, viewer, asset.id)
    assert readable is not None
    assert readable.id == asset.id


def test_environment_identity_does_not_reset_composite(db: Session, tmp_path, monkeypatch):
    from app.config import settings
    from app.environment_reference_sheet.api import ErsIdentityBody, api_patch_sheet_identity
    from app.environment_reference_sheet.orchestrator import create_sheet
    from app.environment_reference_sheet.store import save_sheet, sync_environment_scope

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    owner = _project(db, "Owner")
    sheet = create_sheet(project_id=owner, name=f"Earth Horizon Wire {uuid.uuid4().hex[:6]}", description="orbit")
    sheet.ers_composite_asset_id = "composite-keep"
    save_sheet(sheet)
    sync_environment_scope(db, sheet)
    patched = api_patch_sheet_identity(
        owner,
        sheet.sheetId,
        ErsIdentityBody(isGlobal=True, name=sheet.name),
        db,
    )
    assert patched["sheet"]["isGlobal"] is True
    assert patched["sheet"]["ers_composite_asset_id"] == "composite-keep"
    assert patched["sheet"]["name"] == sheet.name
