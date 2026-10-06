"""Global Character / Prop / Environment visibility contract."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate
from fastapi import HTTPException

from app.character_identity.cc_v2 import get_status
from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow
from app.character_identity.service import (
    create_profile,
    get_profile,
    get_profile_by_id,
    list_profiles,
    require_owned_profile,
    update_profile,
)
from app.db import Asset, Project, SessionLocal, init_db
from app.creator_scope.contract import group_scope_items
from app.creator_scope.service import ensure_creator_scope_tables
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
    pid = f"scope-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def test_character_global_visible_in_other_project_local_is_not(db: Session):
    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    local = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="TestLocalCharacter", slug="testlocalcharacter"),
    )
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="TestGlobalCharacter", slug="testglobalcharacter", is_global=True),
    )
    assert local.is_global is False
    assert glob.is_global is True
    names_b = {p.name for p in list_profiles(db, project_b)}
    assert "TestGlobalCharacter" in names_b
    assert "TestLocalCharacter" not in names_b
    names_a = {p.name for p in list_profiles(db, project_a)}
    assert "TestGlobalCharacter" in names_a
    assert "TestLocalCharacter" in names_a


def test_character_global_off_hides_from_new_pickers_but_id_still_resolves(db: Session):
    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="Renkoka", slug="renkoka", is_global=True),
    )
    assert any(p.id == glob.id for p in list_profiles(db, project_b))
    update_profile(db, project_a, glob.id, CharacterProfileUpdate(is_global=False))
    assert not any(p.id == glob.id for p in list_profiles(db, project_b))
    still = get_profile_by_id(db, glob.id)
    assert still.id == glob.id
    assert still.is_global is False


def test_character_tag_collision_blocks_global_duplicate(db: Session):
    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    create_profile(db, project_a, CharacterProfileCreate(name="Korri", slug="korri"))
    with pytest.raises(Exception) as exc:
        create_profile(db, project_b, CharacterProfileCreate(name="Korri", slug="korri", is_global=True))
    detail = exc.value.detail if hasattr(exc.value, "detail") else {}
    if isinstance(detail, dict):
        assert detail.get("code") in {"TAG_COLLISION", "PROFILE_NAME_ALREADY_EXISTS"}


def test_group_scope_keeps_owned_global_under_project():
    pid = "proj-a"
    items = [
        {"id": "1", "project_id": "proj-a", "isGlobal": True, "name": "Mine"},
        {"id": "2", "project_id": "proj-b", "isGlobal": True, "name": "Other"},
    ]
    grouped = group_scope_items(items, pid)
    assert [i["id"] for i in grouped["project"]] == ["1"]
    assert [i["id"] for i in grouped["global"]] == ["2"]


def test_prop_and_environment_global_visibility(db: Session):
    from app.environment_reference_sheet.orchestrator import create_sheet
    from app.environment_reference_sheet.store import list_visible_sheets, save_sheet, sync_environment_scope
    from app.prop_creator.service import create_or_update_prop, list_props

    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    local_prop = create_or_update_prop(db, project_a, name="TestLocalProp", is_global=False)
    global_prop = create_or_update_prop(db, project_a, name="TestGlobalProp", is_global=True)
    names_b = {p.display_label for p in list_props(db, project_b)}
    assert "TestGlobalProp" in names_b
    assert "TestLocalProp" not in names_b
    names_a = {p.display_label for p in list_props(db, project_a)}
    assert "TestGlobalProp" in names_a
    assert "TestLocalProp" in names_a
    assert local_prop.project_id == project_a
    assert global_prop.is_global is True

    local_env = create_sheet(project_id=project_a, name="TestLocalEnv", description="local")
    global_env = create_sheet(project_id=project_a, name="TestGlobalEnv", description="global", is_global=True)
    save_sheet(local_env)
    save_sheet(global_env)
    sync_environment_scope(db, local_env)
    sync_environment_scope(db, global_env)
    env_b = {s.name for s in list_visible_sheets(db, project_b)}
    assert "TestGlobalEnv" in env_b
    assert "TestLocalEnv" not in env_b


def test_get_profile_visible_global_from_other_project(db: Session):
    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="Cami", slug="cami", is_global=True),
    )
    viewed = get_profile(db, project_b, glob.id)
    assert viewed.id == glob.id
    assert viewed.project_id == project_a


def test_foreign_global_generation_is_owner_required_not_missing_profile(db: Session):
    project_a = _project(db, "Owner Project")
    project_b = _project(db, "Cade Scenes")
    token = uuid.uuid4().hex[:8]
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(
            name=f"TestGlobalCharacter{token}",
            slug=f"testglobalcharacter{token}",
            is_global=True,
        ),
    )
    readable = get_profile(db, project_b, glob.id)
    assert readable.id == glob.id
    with pytest.raises(HTTPException) as exc:
        require_owned_profile(db, project_b, glob.id)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "OWNER_REQUIRED"
    status = get_status(db, project_b, glob.id)
    assert status["characterId"] == glob.id
    assert "Character Profile not found" not in str(status)
    with pytest.raises(HTTPException) as patch_exc:
        update_profile(db, project_b, glob.id, CharacterProfileUpdate(name="Cade O'Connor"))
    assert patch_exc.value.status_code == 403
    assert patch_exc.value.detail["code"] == "OWNER_REQUIRED"


def test_owned_profile_is_editable_and_cc_v2_resolves(db: Session):
    project_id = _project(db, "Cade Scenes")
    token = uuid.uuid4().hex[:8]
    local = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name=f"Cade O'Connor {token}", slug=f"cade-oconnor-{token}"),
    )
    owned = require_owned_profile(db, project_id, local.id)
    assert owned.id == local.id
    assert owned.project_id == project_id
    status = get_status(db, project_id, local.id)
    assert status["characterId"] == local.id
    assert status["name"] == local.name


def test_reconcile_recreates_missing_local_profile_without_new_id(db: Session):
    project_id = _project(db, "Cade Scenes")
    token = uuid.uuid4().hex[:8]
    created = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name=f"Cade O'Connor {token}", slug=f"cade-oconnor-heal-{token}"),
    )
    character_id = created.id
    asset_id = f"cade-front-{token}"
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="cade-front",
            kind="image",
            filename="cade.png",
            path="cade.png",
        )
    )
    db.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=character_id,
            asset_id=asset_id,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    row = db.get(CharacterProfileRow, character_id)
    assert row is not None
    db.delete(row)
    db.commit()
    assert db.get(CharacterProfileRow, character_id) is None

    healed = get_profile(db, project_id, character_id)
    assert healed.id == character_id
    assert healed.project_id == project_id
    assert healed.name == created.name
    assert healed.is_global is False

    other = _project(db, "Other")
    with pytest.raises(HTTPException) as exc:
        require_owned_profile(db, other, character_id)
    assert exc.value.status_code == 404


def test_global_backing_file_and_crs_visible_from_other_project(db: Session):
    from app.character_identity.crs_service import get_crs_summary
    from app.creator_scope.service import resolve_readable_asset, sync_scope
    from app.creator_scope.contract import ENTITY_CHARACTER

    project_a = _project(db, "Owner")
    project_b = _project(db, "Viewer")
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="GlobalCade", slug="globalcade", is_global=True),
    )
    local = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="LocalCade", slug="localcade", is_global=False),
    )
    global_asset = f"global-front-{uuid.uuid4().hex[:8]}"
    local_asset = f"local-front-{uuid.uuid4().hex[:8]}"
    db.add(Asset(id=global_asset, project_id=project_a, tag="front", kind="image", filename="g.png", path="g.png"))
    db.add(Asset(id=local_asset, project_id=project_a, tag="front", kind="image", filename="l.png", path="l.png"))
    db.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=glob.id,
            asset_id=global_asset,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=local.id,
            asset_id=local_asset,
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
            source_type="upload",
        )
    )
    db.commit()
    sync_scope(
        db,
        entity_type=ENTITY_CHARACTER,
        entity_id=glob.id,
        owning_project_id=project_a,
        is_global=True,
        tag="globalcade",
        name="GlobalCade",
        identity_asset_id=global_asset,
    )
    sync_scope(
        db,
        entity_type=ENTITY_CHARACTER,
        entity_id=local.id,
        owning_project_id=project_a,
        is_global=False,
        tag="localcade",
        name="LocalCade",
        identity_asset_id=local_asset,
    )
    assert resolve_readable_asset(db, project_b, global_asset) is not None
    assert resolve_readable_asset(db, project_b, local_asset) is None
    summary = get_crs_summary(db, project_b, glob.id)
    assert summary is not None
    assert summary.approved_reference_asset_id == global_asset
    assert get_crs_summary(db, project_b, local.id) is None


def test_global_character_current_voice_audio_readable_from_other_project(db: Session):
    from app.character_identity.schemas import VoiceProfileCreate
    from app.character_identity.service import approve_voice_profile, create_voice_profile
    from app.creator_scope.service import resolve_readable_asset, sync_scope
    from app.creator_scope.contract import ENTITY_CHARACTER

    project_a = _project(db, "Owner")
    project_b = _project(db, "Viewer")
    glob = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="VoiceCade", slug="voicecade", is_global=True),
    )
    audio_id = f"voice-preview-{uuid.uuid4().hex[:8]}"
    db.add(Asset(id=audio_id, project_id=project_a, tag="voice", kind="audio", filename="v.wav", path="v.wav"))
    db.commit()
    voice = create_voice_profile(
        db,
        project_a,
        glob.id,
        VoiceProfileCreate(name="VoiceCade Clone", source_mode="CLONE", provider="qwen3-tts"),
    )
    from app.character_identity.models import VoiceProfileRow

    row = db.get(VoiceProfileRow, voice["id"])
    assert row is not None
    row.approved_preview_asset_id = audio_id
    db.commit()
    approve_voice_profile(db, project_a, glob.id, voice["id"])
    sync_scope(
        db,
        entity_type=ENTITY_CHARACTER,
        entity_id=glob.id,
        owning_project_id=project_a,
        is_global=True,
        tag="voicecade",
        name="VoiceCade",
        identity_asset_id="",
    )
    assert resolve_readable_asset(db, project_b, audio_id) is not None
    local_audio = f"local-voice-{uuid.uuid4().hex[:8]}"
    db.add(Asset(id=local_audio, project_id=project_a, tag="voice", kind="audio", filename="l.wav", path="l.wav"))
    db.commit()
    assert resolve_readable_asset(db, project_b, local_audio) is None


def test_character_update_toggles_is_global_same_id(db: Session):
    project_a = _project(db, "Owner")
    project_b = _project(db, "Viewer")
    row = create_profile(
        db,
        project_a,
        CharacterProfileCreate(name="ToggleChar", slug="togglechar", is_global=False),
    )
    cid = row.id
    assert not any(p.id == cid for p in list_profiles(db, project_b))
    updated = update_profile(db, project_a, cid, CharacterProfileUpdate(is_global=True))
    assert updated.id == cid
    assert updated.is_global is True
    assert any(p.id == cid for p in list_profiles(db, project_b))
    off = update_profile(db, project_a, cid, CharacterProfileUpdate(is_global=False))
    assert off.id == cid
    assert off.is_global is False
    assert not any(p.id == cid for p in list_profiles(db, project_b))


def test_normalize_profile_name_collapses_case_and_space():
    from app.creator_scope.contract import normalize_profile_name

    assert normalize_profile_name("  Cade's Starfighter ") == "cade's starfighter"
    assert normalize_profile_name("CADE'S   STARFIGHTER") == "cade's starfighter"
    assert normalize_profile_name("Cade's Starfighter") == normalize_profile_name(" cade's starfighter ")


def test_prop_duplicate_display_name_is_blocked(db: Session):
    from app.prop_creator.service import PropCreatorError, create_or_update_prop

    project_a = _project(db, "Cade Scenes")
    first = create_or_update_prop(db, project_a, name="Cade's Starfighter")
    with pytest.raises(PropCreatorError) as exc:
        create_or_update_prop(db, project_a, name=" cade's starfighter ")
    assert exc.value.status_code == 409
    assert exc.value.code == "PROFILE_NAME_ALREADY_EXISTS"
    assert exc.value.extra.get("existingId") == first.id
    same = create_or_update_prop(db, project_a, prop_id=first.id, name="Cade's Starfighter")
    assert same.id == first.id


def test_prop_local_blocked_by_visible_global(db: Session):
    from app.prop_creator.service import PropCreatorError, create_or_update_prop

    project_a = _project(db, "Owner")
    project_b = _project(db, "Viewer")
    create_or_update_prop(db, project_a, name="GlobalCollisionTest", is_global=True)
    with pytest.raises(PropCreatorError) as exc:
        create_or_update_prop(db, project_b, name="GlobalCollisionTest", is_global=False)
    assert exc.value.code == "PROFILE_NAME_ALREADY_EXISTS"


def test_environment_numbered_name_is_not_the_unsuffixed_name(db: Session):
    from app.creator_scope.contract import (
        ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE,
        CreatorScopeError,
        canonical_tag,
        normalize_profile_name,
    )
    from app.environment_reference_sheet.creator_save import upsert_environment_creator_sheet

    assert normalize_profile_name("Schnick Coffee House #2") != normalize_profile_name("Schnick Coffee House")
    assert canonical_tag("Schnick Coffee House #2") != canonical_tag("Schnick Coffee House")

    project_a = _project(db, "Env Suffix")
    first, created = upsert_environment_creator_sheet(
        db, project_id=project_a, payload={"name": "Schnick Coffee House"}
    )
    assert created is True
    second, created_second = upsert_environment_creator_sheet(
        db, project_id=project_a, payload={"name": "Schnick Coffee House #2"}
    )
    assert created_second is True
    assert second.sheetId != first.sheetId

    with pytest.raises(CreatorScopeError) as exc:
        upsert_environment_creator_sheet(
            db, project_id=project_a, payload={"name": "Schnick Coffee House"}
        )
    assert exc.value.code == "PROFILE_NAME_ALREADY_EXISTS"
    assert exc.value.message == ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE


def test_environment_create_does_not_silent_reuse_name(db: Session):
    from app.creator_scope.contract import CreatorScopeError
    from app.environment_reference_sheet.creator_save import upsert_environment_creator_sheet

    project_a = _project(db, "Env")
    first, created = upsert_environment_creator_sheet(db, project_id=project_a, payload={"name": "Venture Bridge"})
    assert created is True
    with pytest.raises(CreatorScopeError) as exc:
        upsert_environment_creator_sheet(db, project_id=project_a, payload={"name": "venture  bridge"})
    assert exc.value.code == "PROFILE_NAME_ALREADY_EXISTS"
    again, created_again = upsert_environment_creator_sheet(
        db,
        project_id=project_a,
        payload={"name": "Venture Bridge", "sheetId": first.sheetId},
    )
    assert created_again is False
    assert again.sheetId == first.sheetId


def test_cd_reuses_existing_prop_name(db: Session):
    from app.creator_scope.contract import ENTITY_PROP
    from app.creator_scope.service import reuse_existing_profile
    from app.prop_creator.service import create_or_update_prop

    project_a = _project(db, "CD")
    prop = create_or_update_prop(db, project_a, name="Cade's Starfighter")
    reused = reuse_existing_profile(db, entity_type=ENTITY_PROP, project_id=project_a, name="CADE'S STARFIGHTER")
    assert reused is not None
    assert reused["reused"] is True
    assert reused["existingId"] == prop.id


def test_character_duplicate_name_blocked(db: Session):
    project_a = _project(db, "Chars")
    first = create_profile(db, project_a, CharacterProfileCreate(name="Duplicate Test Character"))
    with pytest.raises(HTTPException) as exc:
        create_profile(db, project_a, CharacterProfileCreate(name="duplicate test character"))
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "PROFILE_NAME_ALREADY_EXISTS"
    assert detail.get("existingId") == first.id
