"""Timeline reference persistence + hydration contract."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project
from app.director_timeline import PromptSegment
from app.director_timeline_bindings import dump_prompt_name_bindings, parse_prompt_name_bindings
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service


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
    session.add(Project(id="proj-ref", name="Cade Scenes"))
    session.add(
        Asset(
            id="asset-earth",
            project_id="proj-ref",
            tag="environment_reference",
            kind="image",
            filename="earth horizon.png",
            path="earth.png",
        )
    )
    session.add(
        Asset(
            id="asset-venture",
            project_id="proj-ref",
            tag="prop_reference_sheet",
            kind="image",
            filename="venture.png",
            path="venture.png",
        )
    )
    session.add(
        Asset(
            id="asset-cade",
            project_id="proj-ref",
            tag="prop_reference_sheet",
            kind="image",
            filename="cade.png",
            path="cade.png",
        )
    )
    session.commit()
    yield session
    session.close()


def test_prompt_name_binding_roundtrip_keeps_canonical_ids():
    raw = [
        {
            "bindingId": "bind-earth",
            "promptName": "Earth Horizon",
            "type": "environment",
            "tag": "#EarthHorizon",
            "assetId": "asset-earth",
            "identityId": "",
            "referenceSheetId": "",
        },
        {
            "binding_id": "bind-venture",
            "prompt_name": "Venture Spaceship",
            "type": "prop",
            "tag": "%VentureSpaceship",
            "asset_id": "asset-venture",
            "identity_id": "prop-venture",
            "reference_sheet_id": "asset-venture",
        },
    ]
    parsed = parse_prompt_name_bindings(raw)
    dumped = dump_prompt_name_bindings(parsed)
    assert dumped[0]["tag"] == "#EarthHorizon"
    assert dumped[0]["asset_id"] == "asset-earth"
    assert dumped[1]["identity_id"] == "prop-venture"
    assert dumped[1]["reference_sheet_id"] == "asset-venture"
    again = dump_prompt_name_bindings(json.loads(json.dumps(dumped)))
    assert again == dumped


def test_library_environment_attach_does_not_require_ers(db):
    row = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-earth",
            "scope_type": "scene",
            "scope_id": "scene-fresh",
            "reference_type": "environment",
            "usage_modes": ["environment"],
            "alias": "EarthHorizon",
        },
    )
    assert row["id"]
    assert row["asset_id"] == "asset-earth"
    assert row["reference_type"] == "environment"
    assert not row.get("broken")
    fetched = service.get_one(db, "proj-ref", row["id"])
    assert fetched["id"] == row["id"]
    assert fetched["asset_id"] == "asset-earth"


def test_same_alias_allowed_on_two_scenes(db):
    first = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-venture",
            "scope_type": "scene",
            "scope_id": "scene-a",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "VentureSpaceship",
        },
    )
    second = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-venture",
            "scope_type": "scene",
            "scope_id": "scene-b",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "VentureSpaceship",
        },
    )
    assert first["id"] != second["id"]
    assert first["alias"] == "VentureSpaceship"
    assert second["alias"] == "VentureSpaceship"


def test_attach_idempotent_and_sets_identity(db):
    first = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-cade",
            "scope_type": "scene",
            "scope_id": "scene-fresh",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "CadeSStarfighter",
            "identity_id": "prop-cade",
        },
    )
    second = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-cade",
            "scope_type": "scene",
            "scope_id": "scene-fresh",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "CadeSStarfighter",
            "identity_id": "prop-cade",
        },
    )
    assert first["id"] == second["id"]
    assert second["identity_id"] == "prop-cade"
    assert len(service.list_for_scope(db, "proj-ref", "scene", "scene-fresh")) == 1


def test_prompt_segment_persists_canonical_fields():
    seg = PromptSegment(
        id="ps1",
        text="orbit #EarthHorizon %VentureSpaceship %CadeSStarfighter",
        reference_binding_ids=["bind-e", "bind-v", "bind-c"],
        reference_name_bindings=[
            {
                "binding_id": "bind-e",
                "prompt_name": "Earth Horizon",
                "type": "environment",
                "tag": "#EarthHorizon",
                "asset_id": "asset-earth",
            },
            {
                "binding_id": "bind-v",
                "prompt_name": "Venture Spaceship",
                "type": "prop",
                "tag": "%VentureSpaceship",
                "asset_id": "asset-venture",
                "identity_id": "prop-venture",
                "reference_sheet_id": "asset-venture",
            },
            {
                "binding_id": "bind-c",
                "prompt_name": "Cade's Starfighter",
                "type": "prop",
                "tag": "%CadeSStarfighter",
                "asset_id": "asset-cade",
                "identity_id": "prop-cade",
            },
        ],
    )
    dumped = dump_prompt_name_bindings(seg.reference_name_bindings)
    assert [row["tag"] for row in dumped] == ["#EarthHorizon", "%VentureSpaceship", "%CadeSStarfighter"]
    assert [row["asset_id"] for row in dumped] == ["asset-earth", "asset-venture", "asset-cade"]


def test_resolve_prop_prefers_exact_display_label(monkeypatch):
    class FakeProp:
        def __init__(self, prop_id: str, label: str, tag: str, sheet: str, project_id: str = "proj-ref"):
            self.id = prop_id
            self.display_label = label
            self.tag = tag
            self.advanced_sheet_asset_id = sheet
            self.library_asset_id = sheet
            self.project_id = project_id

    props = [
        FakeProp("smoke", "Upload Smoke Advanced Ship", "UploadSmoke", "sheet-smoke"),
        FakeProp("venture", "Venture Spaceship", "VentureSpaceship", "sheet-venture"),
    ]
    monkeypatch.setattr("app.prop_creator.service.list_visible_props", lambda db, project_id: props)
    monkeypatch.setattr("app.prop_creator.readiness.approved_primary_asset_id", lambda prop: prop.library_asset_id)
    from app.codirector.production.reference_resolver import _resolve_prop

    hit = _resolve_prop(None, "proj-ref", "Venture Spaceship")
    assert hit.status == "found"
    assert hit.entity_id == "venture"
    assert hit.bindable_asset_id == "sheet-venture"
    assert hit.canonical_tag == "%VentureSpaceship"

    sheet_query = _resolve_prop(None, "proj-ref", "Venture Spaceship Prop Reference Sheet")
    assert sheet_query.entity_id == "venture"
    assert sheet_query.bindable_asset_id == "sheet-venture"


def test_project_local_asset_does_not_remap_generic_tag(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.codirector.production.timeline_builder import _project_local_asset_id
    from app.db import Asset, Base, Project
    from app.scene_references import models as _sr_models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Project(id="proj-ref", name="Cade Scenes"))
    session.add(Project(id="proj-other", name="Other"))
    src = tmp_path / "VentureSpaceship Advanced PRS.png"
    src.write_bytes(b"venture-sheet")
    smoke = tmp_path / "UploadSmokeAdvancedShip Advanced PRS.png"
    smoke.write_bytes(b"smoke-sheet")
    session.add(
        Asset(
            id="foreign-venture",
            project_id="proj-other",
            tag="advanced_prop_reference_sheet",
            kind="image",
            filename="VentureSpaceship Advanced PRS.png",
            path=str(src),
        )
    )
    session.add(
        Asset(
            id="local-smoke",
            project_id="proj-ref",
            tag="advanced_prop_reference_sheet",
            kind="image",
            filename="UploadSmokeAdvancedShip Advanced PRS.png",
            path=str(smoke),
        )
    )
    session.commit()
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    local_id = _project_local_asset_id(session, "proj-ref", "foreign-venture")
    assert local_id
    assert local_id != "local-smoke"
    adopted = session.get(Asset, local_id)
    assert adopted is not None
    assert adopted.project_id == "proj-ref"
    assert "VentureSpaceship" in adopted.filename
    session.close()


def test_named_scene_is_not_always_establishing_shot():
    from app.codirector.production.contracts import (
        CameraSpec,
        DirectorSceneIntent,
        ResolvedReference,
        SceneIntentEnvironment,
        SceneIntentSubject,
        SceneProductionSpec,
    )
    from app.codirector.production.timeline_builder import _scene_name, is_technical_scene_name

    technical = SceneProductionSpec(
        project_id="proj-ref",
        source_user_prompt="build a scene in Timeline named Hydration Repair Fresh 1, using Earth Horizon",
        camera=CameraSpec(shot_type="establishing"),
        director_intent=DirectorSceneIntent(
            environment=SceneIntentEnvironment(name="Earth Horizon"),
            subjects=[SceneIntentSubject(name="Venture Spaceship", role="primary")],
        ),
        references=[
            ResolvedReference(
                status="found",
                query="Earth Horizon",
                expected_type="environment",
                display_name="Earth Horizon",
                asset_type="environment",
            ),
            ResolvedReference(
                status="found",
                query="Venture Spaceship",
                expected_type="prop",
                display_name="Venture Spaceship",
                asset_type="prop",
            ),
        ],
    )
    assert is_technical_scene_name("Hydration Repair Fresh 1789583789145")
    assert _scene_name(technical) == "Venture Spaceship at Earth Horizon"

    cinematic = SceneProductionSpec(
        project_id="proj-ref",
        source_user_prompt="build a scene in Timeline named Venture in Orbit, using Earth Horizon",
        camera=CameraSpec(shot_type="establishing"),
    )
    assert _scene_name(cinematic) == "Venture in Orbit"
