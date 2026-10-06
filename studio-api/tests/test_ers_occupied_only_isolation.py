"""Occupied-only retry must never enqueue cardinal or 3D siblings."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest


@pytest.fixture()
def db_session():
    from app.character_identity import ensure_character_identity_tables
    from app.db import SessionLocal, init_db

    init_db()
    ensure_character_identity_tables()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def project(db_session):
    from app.db import Project

    row = Project(id=str(uuid.uuid4()), name="Occupied isolation project")
    db_session.add(row)
    db_session.commit()
    return row


def _character(db_session, project_id: str):
    from app.character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow

    row = CharacterProfileRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Special Agent Jacob Barnes",
        slug="special-agent-jacob-barnes",
        species_or_type="human",
        visual_description="short dark hair, black suit",
        approval_status="approved",
        status="APPROVED",
    )
    db_session.add(row)
    db_session.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=row.id,
            asset_id="jacob-hero",
            reference_role="hero_identity",
            approval_status="approved",
            canonical=True,
        )
    )
    db_session.commit()
    return row


def _document(map_id: str, character_id: str):
    return SimpleNamespace(
        id=map_id,
        title="Lab",
        sceneDescription="corridor",
        sceneIntent=None,
        backgroundAssetId="atlas",
        widthMeters=10,
        depthMeters=10,
        metersPerCell=1,
        version=1,
        savedVersion="1",
        backgroundAlignment=None,
        characters=[
            SimpleNamespace(
                id="place-1",
                characterId=character_id,
                label="Special Agent Jacob Barnes",
                name="Special Agent Jacob Barnes",
                visible=True,
                normalizedX=0.0,
                normalizedY=0.0,
                yawDegrees=0,
            )
        ],
        props=[],
        cameras=[],
        environmentalAnchors=[],
        anchors=[],
    )


def _package(project_id: str, map_id: str, *, siblings: dict[str, str]):
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage

    return EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id=map_id,
        master_environment_asset_id=siblings.get("master"),
        directional_assets={
            "north": siblings.get("north"),
            "east": siblings.get("east"),
            "south": siblings.get("south"),
            "west": siblings.get("west"),
        },
        ers_composite_asset_id=siblings.get("composite"),
        metadata={
            "components": dict(siblings),
            "threeDRepresentationAssetId": siblings.get("three_d"),
            "occupiedScaleAssetId": siblings.get("occupied"),
            "sheet_id": "sheet-1",
            "grounding_fingerprint": "fp-1",
            "lineageFingerprint": "fp-1",
            "placementFingerprint": "place-1",
            "characterRevision": 1,
        },
    )


def _sheet():
    return SimpleNamespace(sheetId="sheet-1")


def _install_isolation_spies(monkeypatch):
    from app.codirector.capabilities.handlers import ers_generate
    from app.environment_reference_sheet import store as sheet_store
    from app.spatial_map import ers_component_pipeline as pipeline

    enqueued: list[str] = []
    composed: list[str] = []

    def fake_enqueue(_db, _project_id, body, scene_id=None):
        component = str((body.get("creativeContext") or {}).get("ersComponent") or "")
        enqueued.append(component)
        return {"jobId": f"job-{component}-{len(enqueued)}"}

    def fake_compose(_db, project_id, *, package, sheet, spatial_document_id=""):
        composed.append(str(package.id))
        meta = dict(package.metadata or {})
        meta["occupiedCompose"] = "components_2k"
        package.metadata = meta
        package.ers_composite_asset_id = "composite-new"
        return {
            "ers_composite_asset_id": "composite-new",
            "machineJsonAssetId": "machine-new",
            "package_id": package.id,
            "has_reference": True,
        }

    monkeypatch.setattr(ers_generate, "_enqueue_ers_image_product", fake_enqueue)
    monkeypatch.setattr(ers_generate, "_stamp_ers_job_on_sheet", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "persist_composed_ers", fake_compose)
    monkeypatch.setattr(pipeline, "_append_execution_child", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "_stamp_execution_complete", lambda *a, **k: None)
    monkeypatch.setattr(sheet_store, "save_sheet", lambda *a, **k: None)
    monkeypatch.setattr(sheet_store, "load_sheet", lambda *a, **k: _sheet())
    return enqueued, composed


SIBLINGS = {
    "master": "master-a",
    "north": "north-a",
    "east": "east-a",
    "south": "south-a",
    "west": "west-a",
    "three_d": "three-d-a",
    "occupied": "occupied-old",
    "composite": "composite-old",
}


def test_occupied_only_retry_enqueues_occupied_child_only(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import accepted_from_package, start_ers_component_pipeline
    from app.spatial_map.ers_persistence import save_ers_package

    jacob = _character(db_session, project.id)
    enqueued, composed = _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    map_id = str(uuid.uuid4())
    package = _package(project.id, map_id, siblings=SIBLINGS)
    save_ers_package(db_session, project.id, package)
    before = accepted_from_package(package)

    started = start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-1",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=package,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        retry_component="occupied",
    )

    assert enqueued == ["occupied"]
    assert composed == []
    assert [child["metadata"]["ersComponent"] for child in started["child_jobs"]] == ["occupied"]
    assert started["plan_data"]["ersStage"] == "Generating Occupied scale"
    after = accepted_from_package(package)
    for key in ("master", "north", "east", "south", "west", "three_d"):
        assert after.get(key) == before.get(key) == SIBLINGS[key]


def test_occupied_pass_composes_without_cardinal_jobs(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import accepted_from_package, advance_ers_component, start_ers_component_pipeline
    from app.spatial_map.ers_persistence import load_ers_package, save_ers_package

    jacob = _character(db_session, project.id)
    enqueued, composed = _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    from app.spatial_map import ers_character_identity_gate as gate_mod

    monkeypatch.setattr(
        gate_mod,
        "apply_occupied_identity_gate",
        lambda *a, **k: {"verdict": "PASS", "reason": "same face", "characterNames": ["Special Agent Jacob Barnes"]},
    )
    map_id = str(uuid.uuid4())
    package = _package(project.id, map_id, siblings=SIBLINGS)
    save_ers_package(db_session, project.id, package)
    start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-2",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=package,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        retry_component="occupied",
    )
    assert enqueued == ["occupied"]

    advanced = advance_ers_component(
        db_session,
        project.id,
        asset_id="occupied-new",
        sheet_id="sheet-1",
        package_id=package.id,
        component="occupied",
        execution_id="exec-2",
    )
    assert enqueued == ["occupied"]
    assert composed == [package.id]
    assert advanced.get("ers_composite_asset_id") == "composite-new"
    assert advanced.get("advanced") not in {"north", "east", "south", "west", "three_d", "master"}
    saved = load_ers_package(db_session, project.id, package.id)
    after = accepted_from_package(saved)
    assert after["master"] == "master-a"
    assert after["north"] == "north-a"
    assert after["east"] == "east-a"
    assert after["south"] == "south-a"
    assert after["west"] == "west-a"
    assert after["three_d"] == "three-d-a"
    assert after["occupied"] == "occupied-new"
    assert saved.ers_composite_asset_id == "composite-new"
    assert (saved.metadata or {}).get("identityGateResult", {}).get("verdict") == "PASS"


def test_occupied_identity_fail_does_not_enqueue_siblings(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import accepted_from_package, advance_ers_component, start_ers_component_pipeline
    from app.spatial_map.ers_persistence import load_ers_package, save_ers_package
    from app.spatial_map import ers_character_identity_gate as gate_mod

    jacob = _character(db_session, project.id)
    enqueued, composed = _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    monkeypatch.setattr(
        gate_mod,
        "apply_occupied_identity_gate",
        lambda *a, **k: {
            "verdict": "FAIL_CHARACTER_IDENTITY",
            "reason": "Expected Special Agent Jacob Barnes, but the approved character identity was not verified.",
            "characterNames": ["Special Agent Jacob Barnes"],
        },
    )
    map_id = str(uuid.uuid4())
    package = _package(project.id, map_id, siblings=SIBLINGS)
    save_ers_package(db_session, project.id, package)
    start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-3",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=package,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        retry_component="occupied",
    )
    failed = advance_ers_component(
        db_session,
        project.id,
        asset_id="occupied-bad",
        sheet_id="sheet-1",
        package_id=package.id,
        component="occupied",
        execution_id="exec-3",
    )
    assert enqueued == ["occupied"]
    assert composed == []
    assert failed.get("retry_component") == "occupied"
    assert failed.get("identityGateResult", {}).get("verdict") == "FAIL_CHARACTER_IDENTITY"
    saved = load_ers_package(db_session, project.id, package.id)
    after = accepted_from_package(saved)
    assert after["occupied"] == "occupied-old"
    for key in ("master", "north", "east", "south", "west", "three_d"):
        assert after[key] == SIBLINGS[key]


def test_collage_asset_id_keeps_original_sheet_even_when_tiles_exist():
    from app.spatial_map.ers_component_pipeline import package_uses_collage_occupied

    package = _package("proj", "map", siblings=SIBLINGS)
    assert package_uses_collage_occupied(package) is False
    package.metadata["collageAssetId"] = "original-sensenova-sheet"
    assert package_uses_collage_occupied(package) is True


def test_full_start_with_collage_does_not_set_occupied_only(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import start_ers_component_pipeline
    from app.spatial_map.ers_persistence import load_ers_package, save_ers_package

    jacob = _character(db_session, project.id)
    _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    map_id = str(uuid.uuid4())
    package = _package(project.id, map_id, siblings=SIBLINGS)
    package.metadata["collageAssetId"] = "32cfec5b-5110-43bc-bd0f-96e089f287d0"
    package.metadata["occupiedScaleAssetId"] = None
    components = dict(package.metadata.get("components") or {})
    components.pop("occupied", None)
    package.metadata["components"] = components
    save_ers_package(db_session, project.id, package)
    start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-full-collage",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=package,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        retry_component="",
    )
    saved = load_ers_package(db_session, project.id, package.id)
    assert (saved.metadata or {}).get("occupiedOnly") is not True
    assert (saved.metadata or {}).get("retryComponent") != "occupied"


def test_full_start_clears_leftover_occupied_only_flag(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import start_ers_component_pipeline
    from app.spatial_map.ers_persistence import load_ers_package, save_ers_package

    jacob = _character(db_session, project.id)
    _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    map_id = str(uuid.uuid4())
    package = _package(project.id, map_id, siblings=SIBLINGS)
    package.metadata["collageAssetId"] = "32cfec5b-5110-43bc-bd0f-96e089f287d0"
    package.metadata["occupiedOnly"] = True
    package.metadata["retryComponent"] = "occupied"
    save_ers_package(db_session, project.id, package)
    start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-clear-occupied-only",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=package,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        retry_component="",
    )
    saved = load_ers_package(db_session, project.id, package.id)
    assert (saved.metadata or {}).get("occupiedOnly") is not True
    assert (saved.metadata or {}).get("retryComponent") != "occupied"


def test_creator_regenerate_force_full_enqueues_master_not_recompose(db_session, project, monkeypatch):
    from app.spatial_map.ers_component_pipeline import accepted_from_package, start_ers_component_pipeline
    from app.spatial_map.ers_persistence import save_ers_package

    jacob = _character(db_session, project.id)
    enqueued, composed = _install_isolation_spies(monkeypatch)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate._public_asset_url",
        lambda aid: f"https://assets.example/{aid}",
    )
    map_id = str(uuid.uuid4())
    silent = _package(project.id, map_id, siblings=SIBLINGS)
    save_ers_package(db_session, project.id, silent)
    restitch = start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-silent",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}},
        package=silent,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
    )
    assert enqueued == []
    assert composed
    assert restitch["status"] == "completed"
    assert restitch["child_jobs"][0]["metadata"]["ers_pipeline"] == "recompose"

    enqueued.clear()
    composed.clear()
    forced = _package(project.id, map_id, siblings=SIBLINGS)
    save_ers_package(db_session, project.id, forced)
    started = start_ers_component_pipeline(
        db_session,
        project.id,
        execution_id="exec-force-full",
        body={"sourceAssetId": "atlas-env", "creativeContext": {}, "forceFull": True},
        package=forced,
        sheet=_sheet(),
        spatial_document=_document(map_id, jacob.id),
        force_full=True,
    )
    assert enqueued == ["master"]
    assert composed == []
    assert accepted_from_package(forced) == {}
    assert started["plan_data"]["ersStage"] == "Generating Master"
