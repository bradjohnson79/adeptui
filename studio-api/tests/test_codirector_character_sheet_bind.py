"""Character Creator refresh wording and reference-sheet id binding."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy.orm import Session

from app.character_identity import ensure_character_identity_tables
from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity import service as ci
from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags


def _apply_flags_in_place(environ: dict[str, str] | os._Environ | None = None) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def db() -> Session:
    os.environ["STUDIO_FEATURE_CHARACTER_IDENTITY_V1"] = "1"
    _apply_flags_in_place(os.environ)
    init_db()
    ensure_character_identity_tables()
    session = SessionLocal()
    yield session
    session.close()
    _apply_flags_in_place(os.environ)


def _project(db: Session) -> str:
    pid = f"crs-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="CRS Bind Test"))
    db.commit()
    return pid


def _profile(db: Session, project_id: str, name: str, description: str = "A lantern keeper with a grey coat.") -> str:
    created = ci.create_profile(
        db,
        project_id,
        CharacterProfileCreate(name=name, description=description),
    )
    return created.id


SHEET = (
    "Please create a multi-view Character Reference Sheet for Harbor "
    "using the Character Creator tool. Use the current Character Profile "
    "and any uploaded reference as identity."
)


def test_refresh_sentence_only_after_verified_create():
    from app.codirector.durable.agent import _tool_return_text
    from app.codirector.durable.approval import _verified_wording

    wording = _verified_wording(
        "character_creator.create_from_brief",
        {"name": "Harbor"},
    )
    assert "Harbor" in wording
    assert "Refresh the page" in wording

    class ToolReturnPart:
        content = '{"mutation_status": "proposed"}'

    class Message:
        parts = [ToolReturnPart()]

    awaiting = _tool_return_text([Message()])
    assert awaiting == "This is prepared and awaiting approval. Nothing has been placed or created yet."
    assert "Refresh" not in awaiting


def test_unique_name_stores_persisted_id(db: Session):
    from app.codirector.durable.bind import bind_request_arguments

    project_id = _project(db)
    character_id = _profile(db, project_id, "Harbor")
    args, refusal = bind_request_arguments(
        db,
        tool_id="character_creator.propose_visual_sheet",
        arguments={"characterId": "model-invented"},
        user_text=SHEET,
        project_id=project_id,
    )
    assert refusal is None
    assert args["characterId"] == character_id
    assert args["characterId"] != "model-invented"
    assert args["characterName"] == "Harbor"
    assert "lantern keeper" in args["profileSummary"]


def test_selected_context_supplies_the_same_id(db: Session):
    from app.codirector.durable.bind import bind_request_arguments

    project_id = _project(db)
    character_id = _profile(db, project_id, "Harbor")
    named, refusal = bind_request_arguments(
        db,
        tool_id="character_creator.propose_visual_sheet",
        arguments={},
        user_text=SHEET,
        project_id=project_id,
        selected_character_id=character_id,
    )
    assert refusal is None
    assert named["characterId"] == character_id

    open_only, open_refusal = bind_request_arguments(
        db,
        tool_id="character_creator.propose_visual_sheet",
        arguments={},
        user_text=(
            "Please create a multi-view Character Reference Sheet "
            "using the Character Creator tool."
        ),
        project_id=project_id,
        selected_character_id=character_id,
    )
    assert open_refusal is None
    assert open_only["characterId"] == character_id


def test_missing_and_duplicate_names_do_not_propose(db: Session):
    from app.codirector.durable.bind import bind_request_arguments

    project_id = _project(db)
    missing, missing_refusal = bind_request_arguments(
        db,
        tool_id="character_creator.propose_visual_sheet",
        arguments={"characterId": "invented"},
        user_text=SHEET.replace("Harbor", "Missingperson"),
        project_id=project_id,
    )
    assert missing.get("characterId") is None
    assert missing_refusal
    assert "couldn't find" in missing_refusal

    for suffix in ("a", "b"):
        db.add(
            CharacterProfileRow(
                id=f"dup-{suffix}-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                name="Alex",
                slug=f"alex-{suffix}",
                description="One of two people named Alex.",
            )
        )
    db.commit()
    duplicate, duplicate_refusal = bind_request_arguments(
        db,
        tool_id="character_creator.propose_visual_sheet",
        arguments={},
        user_text=SHEET.replace("Harbor", "Alex"),
        project_id=project_id,
    )
    assert duplicate.get("characterId") is None
    assert duplicate_refusal
    assert "More than one character" in duplicate_refusal


def test_sheet_contract_requires_stored_id_and_job():
    from app.codirector.durable.approval import _sheet_contract_matches

    arguments = {"characterId": "persisted-id"}
    assert not _sheet_contract_matches({"ok": True, "toolResult": {"ok": True}}, arguments)
    assert _sheet_contract_matches(
        {
            "ok": True,
            "toolResult": {
                "ok": True,
                "characterId": "persisted-id",
                "pack": {"jobs": {"hero": {"jobId": "job-1"}}},
            },
        },
        arguments,
    )
    assert not _sheet_contract_matches(
        {"ok": True, "toolResult": {"ok": True, "jobId": "job-1"}},
        {"characterId": ""},
    )


def test_second_approval_does_not_execute(monkeypatch: pytest.MonkeyPatch):
    import app.codirector.durable.approval as approval

    calls = {"execute": 0}

    monkeypatch.setattr(approval, "get_status", lambda _approval_id: "SUCCESS")
    monkeypatch.setattr(
        approval,
        "_proposal_payload",
        lambda *_args, **_kwargs: {
            "approval_id": "approve:wf:sheet",
            "tool_id": "character_creator.propose_visual_sheet",
            "arguments": {"characterId": "persisted-id"},
        },
    )

    def _execute(_payload):
        calls["execute"] += 1
        raise AssertionError("executed")

    monkeypatch.setattr(approval, "execute_approval", _execute)
    monkeypatch.setattr("app.codirector.durable.runtime.ensure_started", lambda: None)
    result = asyncio.run(
        approval.begin_approval(
            None,
            project_id="project",
            proposal_id="proposal",
            note=None,
            decided_by="user",
        )
    )
    assert result == "approve:wf:sheet"
    assert calls["execute"] == 0


def test_sheet_profile_text_survives_argument_sanitize():
    from app.codirector.tools.registry import find
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = find("character_creator.propose_visual_sheet")
    clean = sanitize_arguments(
        definition,
        {
            "characterId": "persisted-id",
            "characterName": "Harbor",
            "profileSummary": "A lantern keeper with a grey coat.",
            "invented": "drop-me",
        },
    )
    assert clean["characterId"] == "persisted-id"
    assert clean["characterName"] == "Harbor"
    assert clean["profileSummary"] == "A lantern keeper with a grey coat."
    assert "invented" not in clean


def test_sheet_request_selects_existing_tool():
    from app.codirector.durable.admission import exposed_tool_ids
    from app.codirector.durable.agent import _operation_tool
    from app.codirector.durable.bind import is_new_character_request, is_reference_sheet_request

    assert is_reference_sheet_request(SHEET)
    assert not is_new_character_request(SHEET)
    allowed = set(exposed_tool_ids(surface=None, user_text=SHEET))
    assert "character_creator.propose_visual_sheet" in allowed
    assert _operation_tool(SHEET, allowed) == "character_creator.propose_visual_sheet"

    create = "Create a new character named Harbor who keeps a lantern. Use Character Creator."
    assert is_new_character_request(create)
    assert not is_reference_sheet_request(create)
    create_allowed = set(exposed_tool_ids(surface=None, user_text=create))
    assert "character_creator.create_from_brief" in create_allowed
    assert _operation_tool(create, create_allowed) == "character_creator.create_from_brief"
