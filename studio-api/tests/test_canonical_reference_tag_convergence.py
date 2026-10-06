"""One canonical prompt tag per identity. Collision suffixes never go to the generator."""

from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.creator_scope.identity_tag import is_forbidden_prompt_token, prompt_canonical_tag
from app.db import Asset, Base, Project
from app.prop_creator.service import create_or_update_prop
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service
from app.scene_references.aliases import unique_alias
FORBIDDEN = (
    "VentureSpaceship2",
    "VentureSpaceship3",
    "venture-spaceship-4",
    "EarthHorizon2",
    "CadeSStarfighter2",
    "CadeSStarfighter3",
)


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
    session.add(Project(id="proj-korri", name="Korri"))
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
            id="asset-venture-prs",
            project_id="proj-ref",
            tag="advanced_prop_reference_sheet",
            kind="image",
            filename="VentureSpaceship Advanced PRS.png",
            path="venture.png",
        )
    )
    session.add(
        Asset(
            id="asset-smoke",
            project_id="proj-ref",
            tag="advanced_prop_reference_sheet",
            kind="image",
            filename="UploadSmokeAdvancedShip Advanced PRS.png",
            path="smoke.png",
        )
    )
    session.add(
        Asset(
            id="asset-cade",
            project_id="proj-ref",
            tag="advanced_prop_reference_sheet",
            kind="image",
            filename="CadeSStarfighter Advanced PRS.png",
            path="cade.png",
        )
    )
    session.commit()
    yield session
    session.close()


def test_convergence_does_not_rewrite_unrelated_view_aliases():
    from app.creator_scope.identity_converge import is_converged_identity_alias, rewrite_legacy_prompt_tags

    assert is_converged_identity_alias("VentureSpaceship3")
    assert is_converged_identity_alias("EarthHorizon2")
    assert is_converged_identity_alias("CadeSStarfighter3")
    assert not is_converged_identity_alias("KorriFront2")
    assert not is_converged_identity_alias("Anadriya3")
    assert not is_converged_identity_alias("VentureCorridor4")
    assert rewrite_legacy_prompt_tags("hold @KorriFront2 near #VentureCorridor3") == "hold @KorriFront2 near #VentureCorridor3"


def test_prompt_grammar_is_stable():
    assert prompt_canonical_tag("prop", "Venture Spaceship") == "%VentureSpaceship"
    assert prompt_canonical_tag("prop", "Cade's Starfighter") == "%CadeSStarfighter"
    assert prompt_canonical_tag("environment", "Earth Horizon") == "#EarthHorizon"
    assert prompt_canonical_tag("prop", "Venture Spaceship", "venture-spaceship-4") == "%VentureSpaceship"
    assert prompt_canonical_tag("prop", "Venture Spaceship", "VentureSpaceship3") == "%VentureSpaceship"
    assert prompt_canonical_tag("environment", "Earth Horizon", "EarthHorizon2") == "#EarthHorizon"
    assert prompt_canonical_tag("prop", "", "%VentureSpaceship3") == "%VentureSpaceship"
    assert prompt_canonical_tag("prop", "", "%venture-spaceship-4") == ""
    from app.creator_scope.identity_tag import sanitize_generator_tag

    assert sanitize_generator_tag("prop", "@VentureSpaceship") == "%VentureSpaceship"
    assert sanitize_generator_tag("prop", "%VentureSpaceship3") == "%VentureSpaceship"
    assert sanitize_generator_tag("environment", "#EarthHorizon2") == "#EarthHorizon"
    assert (
        sanitize_generator_tag("prop", "%VentureSpaceship3", "advanced_prop_reference_sheet")
        == "%VentureSpaceship"
    )
    assert (
        sanitize_generator_tag("prop", "%VentureSpaceship3", "VentureSpaceship Advanced PRS")
        == "%VentureSpaceship"
    )
    from app.director_timeline_w46.generation.direct_reference import _canonical_tag

    assert _canonical_tag("%VentureSpaceship3", "prop", "entity") == "%VentureSpaceship"
    assert _canonical_tag("VentureSpaceship", "prop", "entity") == "%VentureSpaceship"
    assert is_forbidden_prompt_token("%VentureSpaceship3 #EarthHorizon2") == [
        "VentureSpaceship3",
        "EarthHorizon2",
    ]


def test_existing_prop_save_and_global_do_not_change_canonical_tag():
    from app.creator_scope.service import ensure_creator_scope_tables
    from app.db import Project, SessionLocal, init_db

    init_db()
    ensure_creator_scope_tables()
    session = SessionLocal()
    try:
        pid = f"proj-canonical-venture-{os.urandom(4).hex()}"
        if session.get(Project, pid) is None:
            session.add(Project(id=pid, name="Canonical Venture"))
            session.commit()
        prop = create_or_update_prop(session, pid, name="Venture Spaceship")
        assert prop.canonical_tag == "%VentureSpaceship"
        frozen = prop.canonical_tag
        db_slug = prop.tag
        saved = create_or_update_prop(
            session,
            pid,
            prop_id=prop.id,
            name="Venture Spaceship",
            description="Orbital carrier",
            is_global=True,
        )
        assert saved.id == prop.id
        assert saved.canonical_tag == frozen == "%VentureSpaceship"
        assert saved.tag == db_slug
        assert saved.is_global is True
        again = create_or_update_prop(
            session,
            pid,
            prop_id=prop.id,
            name="Venture Spaceship",
            description="Updated notes only",
            is_global=True,
        )
        assert again.canonical_tag == "%VentureSpaceship"
        assert again.tag == db_slug
        blob = json.dumps(again.model_dump())
        for token in FORBIDDEN:
            assert token not in blob
    finally:
        session.close()


def test_identity_attach_does_not_mint_suffix(db):
    first = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-venture-prs",
            "scope_type": "scene",
            "scope_id": "scene-a",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "VentureSpaceship",
            "identity_id": "prop-venture",
        },
    )
    second = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-smoke",
            "scope_type": "scene",
            "scope_id": "scene-a",
            "reference_type": "prop",
            "usage_modes": ["prop"],
            "alias": "VentureSpaceship",
            "identity_id": "prop-venture",
        },
    )
    assert first["id"] == second["id"]
    assert second["alias"] == "VentureSpaceship"
    assert second["display_token"] == "%VentureSpaceship"
    assert second["canonical_tag"] == "%VentureSpaceship"
    assert "2" not in second["alias"]
    assert "3" not in second["alias"]


def test_same_identity_two_scenes_same_canonical_tag(db):
    a = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-venture-prs",
            "scope_type": "scene",
            "scope_id": "scene-a",
            "reference_type": "prop",
            "alias": "VentureSpaceship",
            "identity_id": "prop-venture",
        },
    )
    b = service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-venture-prs",
            "scope_type": "scene",
            "scope_id": "scene-b",
            "reference_type": "prop",
            "alias": "VentureSpaceship",
            "identity_id": "prop-venture",
        },
    )
    assert a["id"] != b["id"]
    assert a["canonical_tag"] == b["canonical_tag"] == "%VentureSpaceship"


def test_unique_alias_does_not_suffix_identity_tokens(db):
    service.attach(
        db,
        "proj-ref",
        {
            "asset_id": "asset-earth",
            "scope_type": "scene",
            "scope_id": "scene-a",
            "reference_type": "environment",
            "alias": "EarthHorizon",
        },
    )
    token, adjusted = unique_alias(
        db,
        "proj-ref",
        "EarthHorizon",
        scope_type="scene",
        scope_id="scene-a",
        allow_collision_suffix=False,
    )
    assert token == "EarthHorizon"
    assert adjusted is False


def test_resolve_binding_id_ignores_sheet_asset_name(monkeypatch):
    from app.director_timeline_w46.generation.reference_compile import resolve_binding_id
    from types import SimpleNamespace

    class FakeRepo:
        @staticmethod
        def get_binding(db, project_id, binding_id):
            return SimpleNamespace(id=binding_id)

        @staticmethod
        def binding_to_dict(row):
            return {"id": row.id}

    def fake_enrich(db, data):
        return {
            "asset_id": "asset-venture-prs",
            "identity_id": "prop-venture",
            "identity_name": "",
            "media_kind": "entity",
            "alias": "VentureSpaceship3",
            "canonical_tag": "%VentureSpaceship3",
            "display_token": "%VentureSpaceship3",
            "reference_type": "prop",
            "asset_name": "advanced_prop_reference_sheet",
            "approval_status": "approved",
            "approved_sheet_asset_id": "asset-venture-prs",
            "broken": False,
        }

    monkeypatch.setattr("app.scene_references.repository.get_binding", FakeRepo.get_binding)
    monkeypatch.setattr("app.scene_references.repository.binding_to_dict", FakeRepo.binding_to_dict)
    monkeypatch.setattr("app.scene_references.service._enrich", fake_enrich)
    resolved = resolve_binding_id(object(), "proj-ref", "bind-venture")
    assert resolved["canonicalTag"] == "%VentureSpaceship"
    assert "3" not in (resolved["canonicalTag"] or "")
    assert "Advanced" not in (resolved["canonicalTag"] or "")
    assert "sheet" not in (resolved["canonicalTag"] or "").lower()


def test_semantic_contract_keeps_prop_percent_prefix():
    from types import SimpleNamespace

    from app.director_timeline_w46.generation.semantic_contract import build_contract

    contract = build_contract(
        slots=[
            SimpleNamespace(
                role="character",
                label="%VentureSpaceship",
                pictureIndex=1,
                assetId="asset-venture-prs",
                identityId="prop-venture",
                aliases=["VentureSpaceship", "%VentureSpaceship"],
            )
        ],
        authored="orbit the carrier",
    )
    assert contract.characters[0].tag == "%VentureSpaceship"
    assert not contract.characters[0].tag.startswith("@%")


def test_backfill_sanitizes_legacy_canonical_tag(monkeypatch):
    from app.director_timeline_w46.generation import prompt_token_bindings as mod

    def fake_resolve(db, project_id, binding_id, **kwargs):
        return {
            "bindingId": binding_id,
            "assetId": "asset-venture-prs",
            "identityId": "prop-venture",
            "alias": "VentureSpaceship3",
            "canonicalTag": "%VentureSpaceship3",
            "displayToken": "%VentureSpaceship3",
            "referenceType": "prop",
            "broken": False,
            "approvedSheetAssetId": "asset-venture-prs",
        }

    monkeypatch.setattr(
        "app.director_timeline_w46.generation.reference_compile.resolve_binding_id",
        fake_resolve,
    )
    filled = mod.backfill_name_binding_identities(
        [
            {
                "binding_id": "bind-venture",
                "prompt_name": "Venture Spaceship",
                "type": "prop",
                "tag": "%VentureSpaceship3",
            }
        ],
        db=object(),
        project_id="proj",
    )
    assert filled[0].tag == "%VentureSpaceship"


def test_legacy_suffix_migrates_once_to_canonical(db):
    from app.creator_scope.identity_converge import rewrite_legacy_prompt_tags
    from app.director_timeline import PromptSegment
    from app.director_timeline_w46.generation.prompt_token_bindings import hydrate_segment_prompt_tokens
    from app.scene_references.models import SceneReferenceBinding

    row = SceneReferenceBinding(
        id="bind-venture",
        project_id="proj-ref",
        asset_id="asset-venture-prs",
        scope_type="scene",
        scope_id="scene-legacy",
        reference_type="prop",
        alias="VentureSpaceship3",
        identity_id="prop-venture",
        enabled=True,
        usage_modes_json="[]",
        reference_roles_json="[]",
    )
    db.add(row)
    db.commit()
    seg = PromptSegment(
        text="orbit %VentureSpaceship3",
        reference_binding_ids=["bind-venture"],
        reference_name_bindings=[
            {
                "binding_id": "bind-venture",
                "prompt_name": "Venture Spaceship",
                "type": "prop",
                "tag": "%VentureSpaceship3",
            }
        ],
    )
    hydrate_segment_prompt_tokens(
        seg,
        [
            {
                "id": "bind-venture",
                "alias": "VentureSpaceship",
                "asset_name": "Venture Spaceship",
                "display_token": "%VentureSpaceship",
                "canonical_tag": "%VentureSpaceship",
                "reference_type": "prop",
                "media_kind": "entity",
            }
        ],
        db=db,
        project_id="proj-ref",
    )
    assert seg.reference_name_bindings[0].tag == "%VentureSpaceship"
    assert rewrite_legacy_prompt_tags(seg.text) == "orbit %VentureSpaceship"
    for token in FORBIDDEN:
        assert token not in (seg.reference_name_bindings[0].tag or "")


def test_resolve_prop_uses_stored_canonical_not_kebab(monkeypatch):
    class FakeProp:
        def __init__(self):
            self.id = "2601f525-a32e-401a-bc1a-b17b1fe92817"
            self.display_label = "Venture Spaceship"
            self.tag = "venture-spaceship-4"
            self.canonical_tag = "%VentureSpaceship"
            self.advanced_sheet_asset_id = "asset-venture-prs"
            self.library_asset_id = "asset-venture-prs"
            self.project_id = "proj-korri"
            self.is_global = True
            self.isGlobal = True

    monkeypatch.setattr("app.prop_creator.service.list_visible_props", lambda db, project_id: [FakeProp()])
    monkeypatch.setattr("app.prop_creator.readiness.approved_primary_asset_id", lambda prop: prop.library_asset_id)
    from app.codirector.production.reference_resolver import _resolve_prop

    hit = _resolve_prop(None, "proj-ref", "Venture Spaceship")
    assert hit.canonical_tag == "%VentureSpaceship"
    assert hit.entity_id == FakeProp().id
    assert hit.is_global is True
    assert "4" not in hit.canonical_tag
    assert "venture-spaceship" not in hit.canonical_tag


def test_stored_prefixed_suffix_never_survives_identity_or_codirector(monkeypatch):
    from app.scene_references.identity_resolve import canonical_tag_for_prop
    from types import SimpleNamespace

    stale = SimpleNamespace(
        display_label="Venture Spaceship",
        canonical_tag="%VentureSpaceship3",
        tag="venture-spaceship-4",
    )
    assert canonical_tag_for_prop(stale) == "%VentureSpaceship"

    class FakeProp:
        def __init__(self):
            self.id = "2601f525-a32e-401a-bc1a-b17b1fe92817"
            self.display_label = "Venture Spaceship"
            self.tag = "venture-spaceship-4"
            self.canonical_tag = "%VentureSpaceship3"
            self.advanced_sheet_asset_id = "asset-venture-prs"
            self.library_asset_id = "asset-venture-prs"
            self.project_id = "proj-korri"
            self.is_global = True
            self.isGlobal = True

    monkeypatch.setattr("app.prop_creator.service.list_visible_props", lambda db, project_id: [FakeProp()])
    monkeypatch.setattr("app.prop_creator.readiness.approved_primary_asset_id", lambda prop: prop.library_asset_id)
    from app.codirector.production.reference_resolver import _resolve_prop
    from app.codirector.production.canonical_tags import prompt_facing_tag

    hit = _resolve_prop(None, "proj-ref", "Venture Spaceship")
    assert hit.canonical_tag == "%VentureSpaceship"
    assert prompt_facing_tag("%", "%VentureSpaceship3", "Venture Spaceship") == "%VentureSpaceship"
    assert prompt_facing_tag("#", "#EarthHorizon2", "Earth Horizon") == "#EarthHorizon"


def test_compiled_entity_metadata_uses_canonical_percent_tag(monkeypatch):
    from app.director_timeline import DirectorTimeline, PromptSegment
    from app.director_timeline_w46.contracts import BatchBlock, DurationState
    from app.director_timeline_w46.generation.reference_compile import apply_compiled_references

    def fake_resolve(db, project_id, binding_id, **kwargs):
        return {
            "bindingId": binding_id,
            "assetId": "asset-venture-prs",
            "identityId": "prop-venture",
            "mediaKind": "entity",
            "referenceType": "prop",
            "alias": "VentureSpaceship3",
            "canonicalTag": "%VentureSpaceship",
            "displayToken": "%VentureSpaceship",
            "broken": False,
            "approvalStatus": "approved",
            "approvedSheetAssetId": "asset-venture-prs",
        }

    monkeypatch.setattr(
        "app.director_timeline_w46.generation.reference_compile.resolve_binding_id",
        fake_resolve,
    )
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(start=0, length=5, text="orbit %VentureSpaceship", reference_binding_ids=["bind-venture"])
        ],
    )
    batch = BatchBlock(sceneId="scene-1", generatorId="minimax-hailuo-02", duration=DurationState(plannedDuration=5))
    apply_compiled_references(batch, timeline, db=object(), project_id="proj-ref")
    entity = next(r for r in batch.references if r.get("role") == "entity_reference")
    assert entity["tag"] == "%VentureSpaceship"
    assert not str(entity["tag"]).startswith("@")
    assert "3" not in str(entity["tag"])
