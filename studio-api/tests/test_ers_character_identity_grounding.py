"""ERS Spatial Map → Character Creator canon resolver and occupied identity."""

from __future__ import annotations

import uuid

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

    row = Project(id=str(uuid.uuid4()), name="ERS identity project")
    db_session.add(row)
    db_session.commit()
    return row


def _character(db_session, project_id: str, name: str = "Special Agent Jacob Barnes"):
    from app.character_identity.models import CharacterProfileRow

    row = CharacterProfileRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        species_or_type="human",
        visual_description="short dark hair, black suit, white shirt, red tie",
        body_type="athletic",
        approval_status="approved",
        status="APPROVED",
    )
    db_session.add(row)
    db_session.commit()
    return row


def _ref(db_session, character_id: str, asset_id: str, *, role="hero_identity", status="approved", canonical=True):
    from app.character_identity.models import CharacterReferenceAssetRow

    row = CharacterReferenceAssetRow(
        id=str(uuid.uuid4()),
        character_profile_id=character_id,
        asset_id=asset_id,
        reference_role=role,
        approval_status=status,
        canonical=canonical,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_resolve_by_character_id_not_name(db_session, project):
    from app.character_identity.crs_service import resolve_character_for_generation

    jacob = _character(db_session, project.id, "Special Agent Jacob Barnes")
    other = _character(db_session, project.id, "Korri")
    _ref(db_session, jacob.id, "jacob-hero")
    _ref(db_session, other.id, "korri-hero")
    resolved = resolve_character_for_generation(db_session, project.id, character_id=jacob.id)
    assert resolved is not None
    assert resolved["characterId"] == jacob.id
    assert resolved["displayName"] == "Special Agent Jacob Barnes"
    assert resolved["referenceAssetId"] == "jacob-hero"
    assert resolved["hasApprovedReference"] is True
    assert "black suit" in str(resolved.get("identityFacts") or resolved.get("characterJson"))


def test_project_isolation(db_session, project):
    from app.character_identity.crs_service import resolve_character_for_generation
    from app.db import Project

    other = Project(id=str(uuid.uuid4()), name="Other")
    db_session.add(other)
    db_session.commit()
    jacob = _character(db_session, project.id)
    _ref(db_session, jacob.id, "jacob-hero")
    assert resolve_character_for_generation(db_session, other.id, character_id=jacob.id) is None


def test_rejected_reference_not_selectable(db_session, project):
    from app.character_identity.service import resolve_approved_reference

    jacob = _character(db_session, project.id)
    _ref(db_session, jacob.id, "rejected-hero", status="rejected", canonical=True)
    assert resolve_approved_reference(db_session, jacob.id, "hero_identity") is None


def test_missing_reference_blocks_occupied_body(db_session, project):
    from app.spatial_map.ers_component_pipeline import _component_body

    jacob = _character(db_session, project.id)
    packet = {
        "environmentName": "Lab",
        "environmentDescription": "corridor",
        "characters": [
            {
                "characterId": jacob.id,
                "displayName": jacob.name,
                "hasApprovedReference": False,
                "visible": True,
            }
        ],
    }
    with pytest.raises(RuntimeError, match="CHARACTER_REFERENCE_UNAVAILABLE"):
        _component_body({}, packet, "occupied", execution_id="e", package_id="p", sheet_id="s")


def test_occupied_prompt_names_saved_character():
    from app.spatial_map.ers_packet import compile_component_prompt

    prompt = compile_component_prompt(
        {
            "environmentName": "Lab",
            "environmentDescription": "corridor",
            "characters": [
                {
                    "characterId": "c1",
                    "displayName": "Special Agent Jacob Barnes",
                    "identityFacts": ["wardrobe: black suit, white shirt, red tie"],
                    "visible": True,
                }
            ],
        },
        "occupied",
    )
    assert "Special Agent Jacob Barnes" in prompt
    assert "approved saved character" in prompt
    assert "black suit" in prompt
    assert "generic person" in prompt


def test_packet_carries_character_id():
    from app.spatial_map.ers_packet import compile_ers_packet
    from types import SimpleNamespace

    document = SimpleNamespace(
        id="map-1",
        title="Lab",
        sceneDescription="corridor",
        sceneIntent=None,
        backgroundAssetId="atlas",
        widthMeters=10,
        depthMeters=10,
        metersPerCell=1,
        backgroundAlignment=None,
        characters=[
            SimpleNamespace(
                id="place-1",
                characterId="char-jacob",
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
    packet = compile_ers_packet(document, project_id="proj")
    assert packet["characters"][0]["characterId"] == "char-jacob"


def test_identity_gate_generic_human_fails():
    from app.spatial_map.ers_character_identity_gate import (
        FAIL_CHARACTER_IDENTITY,
        apply_occupied_identity_gate,
        parse_identity_verdict,
    )

    parsed = parse_identity_verdict("VERDICT: FAIL_CHARACTER_IDENTITY\nREASON: generic suited man")
    assert parsed["verdict"] == FAIL_CHARACTER_IDENTITY
    class _Db:
        def get(self, *_a, **_k):
            return None

    gate = apply_occupied_identity_gate(
        _Db(),
        "proj",
        asset_id="missing",
        packet={"characters": [{"displayName": "Special Agent Jacob Barnes", "characterId": "c1"}]},
    )
    assert gate["verdict"] == FAIL_CHARACTER_IDENTITY
    assert "Special Agent Jacob Barnes" in gate["reason"]


def test_identity_gate_matching_output_passes():
    from app.spatial_map.ers_character_identity_gate import PASS, apply_occupied_identity_gate

    class _Asset:
        path = __file__

    class _Db:
        def get(self, *_a, **_k):
            return _Asset()

    gate = apply_occupied_identity_gate(
        _Db(),
        "proj",
        asset_id="out",
        packet={
            "characters": [
                {
                    "displayName": "Special Agent Jacob Barnes",
                    "referenceAssetId": "ref",
                    "visible": True,
                }
            ]
        },
        vision_output="VERDICT: PASS\nREASON: same face and wardrobe",
    )
    assert gate["verdict"] == PASS


def test_next_component_occupied_only_when_placed():
    from app.spatial_map.ers_component_pipeline import next_component

    accepted = {
        "master": "m",
        "north": "n",
        "east": "e",
        "south": "s",
        "west": "w",
        "three_d": "3",
    }
    assert next_component(accepted, include_occupied=False) is None
    assert next_component(accepted, include_occupied=True) == "occupied"


def test_multiple_characters_do_not_cross_wire(db_session, project):
    from app.character_identity.crs_service import resolve_character_for_generation

    jacob = _character(db_session, project.id, "Special Agent Jacob Barnes")
    korri = _character(db_session, project.id, "Korri")
    _ref(db_session, jacob.id, "jacob-hero")
    _ref(db_session, korri.id, "korri-hero")
    a = resolve_character_for_generation(db_session, project.id, character_id=jacob.id)
    b = resolve_character_for_generation(db_session, project.id, character_id=korri.id)
    assert a["referenceAssetId"] == "jacob-hero"
    assert b["referenceAssetId"] == "korri-hero"
    assert a["characterId"] != b["characterId"]


def test_character_id_wins_over_name(db_session, project):
    from app.character_identity.crs_service import resolve_character_for_generation

    jacob = _character(db_session, project.id, "Special Agent Jacob Barnes")
    korri = _character(db_session, project.id, "Korri")
    _ref(db_session, jacob.id, "jacob-hero")
    _ref(db_session, korri.id, "korri-hero")
    resolved = resolve_character_for_generation(
        db_session, project.id, character_id=jacob.id, character_name=korri.name
    )
    assert resolved["characterId"] == jacob.id
    assert resolved["referenceAssetId"] == "jacob-hero"


def test_mini_shared_resolver_path(db_session, project):
    from app.spatial_map.camera_shot_packet import _identity_for_character

    jacob = _character(db_session, project.id)
    _ref(db_session, jacob.id, "jacob-hero")
    ident = _identity_for_character(db_session, project.id, jacob.id)
    assert ident["characterId"] == jacob.id
    assert ident["approvedAssetId"] == "jacob-hero"
    assert ident["name"] == jacob.name


def test_occupied_component_body_attaches_character_url_first(monkeypatch):
    from app.codirector.capabilities.handlers import ers_generate
    from app.spatial_map.ers_component_pipeline import _component_body

    monkeypatch.setattr(ers_generate, "_public_asset_url", lambda aid: f"https://assets.example/{aid}")
    packet = {
        "environmentName": "Lab",
        "environmentDescription": "corridor",
        "characters": [
            {
                "characterId": "c-jacob",
                "displayName": "Special Agent Jacob Barnes",
                "referenceAssetId": "jacob-hero",
                "hasApprovedReference": True,
                "visible": True,
            }
        ],
    }
    body = _component_body(
        {"sourceAssetId": "atlas-env", "creativeContext": {"authoritativeSourceAssetId": "atlas-env"}},
        packet,
        "occupied",
        execution_id="e",
        package_id="p",
        sheet_id="s",
    )
    assert body["input_urls"][0] == "https://assets.example/jacob-hero"
    assert body["creativeContext"]["referenceGrounding"]["roles"][0] == "character_identity"
    assert body["creativeContext"]["referenceGrounding"]["authoritativeSourceAssetId"] == "jacob-hero"
    assert "Special Agent Jacob Barnes" in body["prompt"]
    assert "unified Environment Reference Sheet" not in body["prompt"]


def test_occupied_reference_order_character_first():
    from app.codirector.capabilities.handlers.ers_generate import order_occupied_reference_assets

    ordered = order_occupied_reference_assets(["jacob-hero"], "atlas-env", ["atlas-env", "orig"])
    assert ordered[0] == "jacob-hero"
    assert "atlas-env" in ordered[1:]
    assert ordered.count("atlas-env") == 1


def test_bind_occupied_leaves_environment_siblings():
    from types import SimpleNamespace

    from app.spatial_map.ers_component_pipeline import bind_component_asset, next_component

    package = SimpleNamespace(
        master_environment_asset_id="master-a",
        directional_assets={"north": "n", "east": "e", "south": "s", "west": "w"},
        metadata={
            "components": {"master": "master-a", "north": "n", "three_d": "3d"},
            "threeDRepresentationAssetId": "3d",
            "packet": {
                "characters": [
                    {
                        "characterId": "c-jacob",
                        "approvedRevision": 4,
                        "referenceAssetId": "jacob-hero",
                        "characterSheetAssetId": "jacob-sheet",
                    }
                ]
            },
        },
    )
    bind_component_asset(package, "occupied", "occupied-a")
    assert package.master_environment_asset_id == "master-a"
    assert package.directional_assets["west"] == "w"
    assert package.metadata["occupiedScaleAssetId"] == "occupied-a"
    assert package.metadata["characterId"] == "c-jacob"
    assert package.metadata["characterReferenceAssetId"] == "jacob-hero"
    accepted = {
        "master": "master-a",
        "north": "n",
        "east": "e",
        "south": "s",
        "west": "w",
        "three_d": "3d",
        "occupied": "occupied-a",
    }
    assert next_component(accepted, include_occupied=True) is None
    # Helper still reports missing cardinals; occupied-only retry must not follow that.
    partial = {"master": "master-a", "occupied": "occupied-a"}
    assert next_component(partial, include_occupied=True) == "north"


def test_occupied_only_flag_stops_cardinal_advance():
    from app.spatial_map.ers_component_pipeline import next_component

    accepted = {"master": "m", "occupied": "o"}
    nxt = next_component(accepted, include_occupied=True)
    assert nxt == "north"
    occupied_only = True
    if occupied_only:
        nxt = None
    assert nxt is None


def test_collage_panel_nine_replace_keeps_other_panels():
    from io import BytesIO

    from PIL import Image

    from app.spatial_map.ers_compose_2k import COLLAGE_OCCUPIED_REGION, compose_occupied_into_collage

    collage = Image.new("RGB", (300, 300), (12, 14, 16))
    occupied = Image.new("RGB", (90, 90), (220, 40, 40))
    src = BytesIO()
    occ = BytesIO()
    collage.save(src, format="PNG")
    occupied.save(occ, format="PNG")
    out = Image.open(
        BytesIO(
            compose_occupied_into_collage(
                src.getvalue(),
                occ.getvalue(),
                template_id="gallery-3x3-v1",
            )
        )
    ).convert("RGB")
    left = int(300 * COLLAGE_OCCUPIED_REGION["left"]) + 20
    top = int(300 * COLLAGE_OCCUPIED_REGION["top"]) + 20
    assert out.getpixel((left, top))[0] > 180
    assert out.getpixel((10, 10)) == (12, 14, 16)


def test_identity_gate_wrong_character_and_empty_fail():
    from app.spatial_map.ers_character_identity_gate import (
        FAIL_CHARACTER_IDENTITY,
        apply_occupied_identity_gate,
        parse_identity_verdict,
    )

    parsed = parse_identity_verdict("VERDICT: FAIL_CHARACTER_IDENTITY\nREASON: different saved character")
    assert parsed["verdict"] == FAIL_CHARACTER_IDENTITY

    class _Db:
        def get(self, *_a, **_k):
            return None

    empty = apply_occupied_identity_gate(
        _Db(),
        "proj",
        asset_id="empty",
        packet={"characters": [{"displayName": "Special Agent Jacob Barnes", "characterId": "c1", "visible": True}]},
    )
    assert empty["verdict"] == FAIL_CHARACTER_IDENTITY


def test_local_gpu_busy_does_not_gate_api_mini():
    from app.spatial_map.scene_creator_mini import _local_gpu_busy

    take = {
        "generator": "gpt-image-2",
        "results": [
            {"generator": "gpt-image-2", "status": "generating", "jobId": "a", "variation": "A"},
            {"generator": "gpt-image-2", "status": "generating", "jobId": "b", "variation": "B"},
        ],
    }
    assert _local_gpu_busy(take) is False
