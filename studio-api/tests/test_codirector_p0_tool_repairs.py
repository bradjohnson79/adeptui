"""c1-tool-registry P0/P1 repair regressions.

Drives the REAL path: registry.get -> sanitize_arguments -> mutation_handler.apply
against a disposable test DB. Proves the sanitizer no longer strips the repaired
parameters and the handlers persist real values (not the degraded defaults the
audit found).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import fields as dataclass_fields
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags_in_place(environ=None) -> None:
    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture(autouse=True)
def enable_character_identity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)
    yield
    _apply_flags_in_place(os.environ)


@pytest.fixture()
def db() -> Session:
    init_db()
    from app.character_identity import ensure_character_identity_tables

    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()


def _new_project(db: Session, name: str = "c1 Repair Project") -> str:
    pid = f"c1-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _apply(tool_id: str, raw_args: dict[str, Any], ctx) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    handler = registry.mutation_handler(tool_id).apply
    result = handler(ctx, sanitized)
    return result, sanitized


def _preview(tool_id: str, raw_args: dict[str, Any], ctx):
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    return registry.mutation_handler(tool_id).preview(ctx, sanitized)


def _make_bible(db: Session, project_id: str) -> None:
    from app.codirector.bible import operations as ops
    from app.codirector.bible.schemas import BibleEntity

    ops.create_bible_with_first_version(
        db,
        project_id=project_id,
        entities=[BibleEntity(entityType="project_profile", entityKey="project-profile",
                              displayName="Project Profile", data={"description": "seed"})],
        facts=[],
        summary="seed",
        change_reason="seed",
        created_by="test",
    )


def _current_entities(db: Session, project_id: str) -> list:
    from app.codirector.bible import operations as ops

    bible = ops.get_bible(db, project_id)
    version = ops.get_current_version(db, bible)
    return [ops.entity_row_to_schema(r) for r in ops.entities_for_version(db, version.id)]


def _create_character(db: Session, project_id: str) -> str:
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import character_creator as cc

    ctx = ToolContext(db=db, project_id=project_id)
    result = cc.apply_create_from_brief(ctx, {"name": "Korri Test", "brief": "A resourceful engineer.", "role": "lead"})
    return result["profile"]["id"]


def test_propose_traits_succeeds_and_persists_array(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    cid = _create_character(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    traits = [{"category": "personality", "key": "core_trait", "value": "resourceful"},
              {"category": "personality", "key": "flaw", "value": "stubborn"}]
    result, sanitized = _apply("character_creator.propose_traits",
                               {"characterId": cid, "traits": traits, "provenance": "PROPOSED_BY_CHARACTER_CREATOR"}, ctx)
    assert sanitized["traits"] == traits
    assert sanitized["provenance"] == "PROPOSED_BY_CHARACTER_CREATOR"
    assert result["ok"] is True
    assert result["count"] == 2
    assert result["characterId"] == cid


def test_propose_traits_rejects_missing_traits_array(db: Session) -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    cid = _create_character(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    with pytest.raises(CoDirectorError) as exc:
        _apply("character_creator.propose_traits", {"characterId": cid}, ctx)
    assert exc.value.details["parameter"] == "traits"


def test_propose_relationships_succeeds_and_persists_array(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    cid = _create_character(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    relationships = [{"targetCharacter": "marcus", "relationship": "rival", "tone": "tense"}]
    result, sanitized = _apply("character_creator.propose_relationships",
                               {"characterId": cid, "relationships": relationships}, ctx)
    assert sanitized["relationships"] == relationships
    assert result["ok"] is True
    assert result["persisted"] is True
    assert any(r["targetCharacter"] == "marcus" for r in result["relationships"])


def test_propose_character_update_persists_supplied_data(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    data = {"description": "A resourceful engineer", "personality": "practical", "backstory": "field ops"}
    result, sanitized = _apply("propose_character_update",
                               {"entityKey": "korri", "displayName": "Korri", "data": data}, ctx)
    assert sanitized["data"] == data
    assert "bibleVersionNumber" in result
    entities = _current_entities(db, pid)
    character = next(e for e in entities if e.entityType == "character")
    assert character.data.get("description") == "A resourceful engineer"
    assert character.data.get("personality") == "practical"
    assert character.data.get("backstory") == "field ops"
    assert character.displayName == "Korri"


def test_propose_canon_record_persists_entity_and_scene(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    result, sanitized = _apply("propose_canon_record",
                               {"claim": "Korri carries a multitool", "entityStableId": "ent-1", "sceneId": "scene-1"}, ctx)
    assert sanitized["entityStableId"] == "ent-1"
    assert sanitized["sceneId"] == "scene-1"
    canon = result["canonRecord"]
    assert canon["data"]["entityStableId"] == "ent-1"
    assert canon["data"]["sceneId"] == "scene-1"


def test_propose_canon_supersession_persists_entity(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    first, _ = _apply("propose_canon_record", {"claim": "old claim", "entityStableId": "ent-1"}, ctx)
    old_stable = first["canonRecord"]["stableId"]
    result, sanitized = _apply("propose_canon_supersession",
                               {"claim": "new claim", "supersedesStableId": old_stable, "entityStableId": "ent-2"}, ctx)
    assert sanitized["entityStableId"] == "ent-2"
    assert result["canonRecord"]["data"]["entityStableId"] == "ent-2"
    assert result["canonRecord"]["data"]["supersedesStableId"] == old_stable


def test_propose_continuity_update_persists_full_state(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    result, sanitized = _apply("propose_continuity_update",
                               {"aspect": "wardrobe", "entityStableId": "ent-1", "sceneId": "scene-1",
                                "expectedValue": "red coat", "actualValue": "blue coat", "resolved": True}, ctx)
    assert sanitized["entityStableId"] == "ent-1"
    assert sanitized["resolved"] is True
    state = result["continuityState"]
    assert state["data"]["entityStableId"] == "ent-1"
    assert state["data"]["sceneId"] == "scene-1"
    assert state["data"]["expectedValue"] == "red coat"
    assert state["data"]["actualValue"] == "blue coat"
    assert state["data"]["resolved"] is True


def test_propose_production_decision_persists_rationale_and_bindings(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    result, sanitized = _apply("propose_production_decision",
                               {"decision": "Shoot night exterior", "rationale": "Matches the noir tone",
                                "entityStableId": "ent-1", "sceneId": "scene-1"}, ctx)
    assert sanitized["rationale"] == "Matches the noir tone"
    assert sanitized["entityStableId"] == "ent-1"
    decision = result["decision"]
    assert decision["data"]["rationale"] == "Matches the noir tone"
    assert decision["data"]["entityStableId"] == "ent-1"
    assert decision["data"]["sceneId"] == "scene-1"


def test_propose_reference_link_persists_purpose_and_primary(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=pid, tag="Korri ref", kind="image", filename="korri.png", path=""))
    db.commit()
    _apply("propose_character_update",
           {"entityKey": "korri", "displayName": "Korri", "data": {"description": "engineer"}}, ctx)
    entities = _current_entities(db, pid)
    character = next(e for e in entities if e.entityType == "character")
    target_stable = character.stableId
    result, sanitized = _apply("propose_reference_link",
                               {"assetId": asset_id, "targetStableId": target_stable,
                                "purpose": "wardrobe", "primary": True}, ctx)
    assert sanitized["purpose"] == "wardrobe"
    assert sanitized["primary"] is True
    link = result["referenceLink"]
    assert link["data"]["purpose"] == "wardrobe"
    assert link["data"]["primary"] is True


def test_propose_visual_language_update_round_trips_data(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    _make_bible(db, pid)
    ctx = ToolContext(db=db, project_id=pid)
    data = {"description": "cool blues palette", "colorPalette": "cool blues", "lightingStyle": "heavy grain"}
    result, sanitized = _apply("propose_visual_language_update", {"data": data}, ctx)
    assert sanitized["data"] == data
    assert "bibleVersionNumber" in result
    entities = _current_entities(db, pid)
    vl = next(e for e in entities if e.entityType == "visual_language")
    assert vl.data.get("colorPalette") == "cool blues"
    assert vl.data.get("lightingStyle") == "heavy grain"


def test_references_attach_persists_usage_modes_and_roles(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    sid = str(uuid.uuid4())
    db.merge(Scene(id=sid, project_id=pid, index=0, name="Scene 1", prompt="x", duration_sec=5.0, director_json=""))
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=pid, tag="Korri ref", kind="image", filename="korri.png", path=""))
    db.commit()
    ctx = ToolContext(db=db, project_id=pid, scene_id=sid)
    result, sanitized = _apply("references.attach",
                               {"assetId": asset_id, "scopeType": "scene", "scopeId": sid,
                                "referenceType": "character", "usageModes": ["identity", "appearance"],
                                "referenceRoles": ["hero"]}, ctx)
    assert sanitized["usageModes"] == ["identity", "appearance"]
    assert sanitized["referenceRoles"] == ["hero"]
    assert result["usage_modes"] == ["identity", "appearance"]
    assert result["reference_roles"] == ["hero"]
    assert result.get("_evidence", {}).get("persisted") is True


def test_propose_asset_library_assignment_round_trips_folder_id(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=pid, tag="prop", kind="image", filename="prop.png", path=""))
    db.commit()
    ctx = ToolContext(db=db, project_id=pid)
    result, sanitized = _apply("propose_asset_library_assignment",
                               {"assetId": asset_id, "folderId": "folder-123", "systemKey": "characters"}, ctx)
    assert sanitized["folderId"] == "folder-123"
    assert result["ok"] is True


def test_posecraft_preview_lines_carry_affects_intent(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    ctx = ToolContext(db=db, project_id=pid)
    preview = _preview("posecraft.add_figure", {"archetypeId": "adult-male"}, ctx)
    assert "Affects: project" in preview.lines


def test_library_preview_lines_carry_diff_detail(db: Session) -> None:
    from app.codirector.tools.definitions import ToolContext

    pid = _new_project(db)
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=pid, tag="prop", kind="image", filename="prop.png", path=""))
    db.commit()
    ctx = ToolContext(db=db, project_id=pid)
    preview = _preview("propose_asset_library_assignment",
                       {"assetId": asset_id, "systemKey": "characters"}, ctx)
    joined = " | ".join(preview.lines)
    assert f"assetId: {asset_id}" in joined
    assert "systemKey: characters" in joined


# ---------------------------------------------------------------------------
# sanitize_arguments: array / object coercion (valid pass, wrong-type reject,
# oversize reject)
# ---------------------------------------------------------------------------


def _traits_def():
    from app.codirector.tools import registry

    return registry.get("character_creator.propose_traits")


def test_sanitize_array_valid_pass() -> None:
    from app.codirector.tools.sanitize import sanitize_arguments

    traits = [{"category": "personality", "key": "k", "value": "v"}]
    sanitized = sanitize_arguments(
        _traits_def(),
        {"characterId": "c1", "traits": traits},
    )
    assert sanitized["traits"] == traits


def test_sanitize_array_wrong_type_rejected() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools.sanitize import sanitize_arguments

    with pytest.raises(CoDirectorError) as exc:
        sanitize_arguments(_traits_def(), {"characterId": "c1", "traits": "not-an-array"})
    assert exc.value.details["parameter"] == "traits"

    with pytest.raises(CoDirectorError):
        sanitize_arguments(_traits_def(), {"characterId": "c1", "traits": {"k": "v"}})


def test_sanitize_array_oversize_rejected() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools.sanitize import MAX_ARRAY_ITEMS, sanitize_arguments

    too_many = [{"category": "x", "key": "k", "value": "v"} for _ in range(MAX_ARRAY_ITEMS + 1)]
    with pytest.raises(CoDirectorError) as exc:
        sanitize_arguments(_traits_def(), {"characterId": "c1", "traits": too_many})
    assert exc.value.details["parameter"] == "traits"


def test_sanitize_array_rejects_non_json_item() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools.sanitize import sanitize_arguments

    # bytes items are not JSON-compatible and not in the allowed scalar/object set
    with pytest.raises(CoDirectorError):
        sanitize_arguments(_traits_def(), {"characterId": "c1", "traits": [b"raw-bytes"]})


def test_sanitize_object_valid_pass() -> None:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get("propose_character_update")
    data = {"description": "engineer", "personality": "practical"}
    sanitized = sanitize_arguments(definition, {"entityKey": "korri", "data": data})
    assert sanitized["data"] == data


def test_sanitize_object_wrong_type_rejected() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get("propose_character_update")
    with pytest.raises(CoDirectorError) as exc:
        sanitize_arguments(definition, {"entityKey": "korri", "data": ["not", "an", "object"]})
    assert exc.value.details["parameter"] == "data"
    with pytest.raises(CoDirectorError):
        sanitize_arguments(definition, {"entityKey": "korri", "data": "string"})


def test_sanitize_object_oversize_rejected() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import MAX_OBJECT_CHARS, sanitize_arguments

    definition = registry.get("propose_character_update")
    huge = {"description": "x" * (MAX_OBJECT_CHARS + 50)}
    with pytest.raises(CoDirectorError) as exc:
        sanitize_arguments(definition, {"entityKey": "korri", "data": huge})
    assert exc.value.details["parameter"] == "data"


def test_sanitize_object_rejects_non_json_value() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get("propose_character_update")
    with pytest.raises(CoDirectorError):
        sanitize_arguments(definition, {"entityKey": "korri", "data": {"bad": b"bytes"}})
