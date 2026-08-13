"""Phase 6 — Character Variants backend tests.

Covers:
* Max 12 variants per character enforced (13th rejected with 400).
* Original canonical sheet is immutable (deleting a variant never touches the
  hero_identity reference).
* Variant generation is reference-locked to the ORIGINAL canonical sheet —
  the generation request carries the canonical sheet asset id as the
  reference (source_asset_id).
* Variant persists required fields (name, description, characterSheetAssetId
  lineage, createdAt).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity import models as ci_models  # noqa: F401
from app.character_identity import service as ci_service
from app.character_identity import variants as variant_service
from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach
from app.continuity import models as continuity_models  # noqa: F401
from app.continuity import service as continuity_service
from app.db import Asset, Base, Project


@pytest.fixture()
def db(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-v", name="Variants Test"))
    # Canonical sheet asset for the character.
    session.add(
        Asset(
            id="canon-sheet",
            project_id="proj-v",
            tag="character_sheet",
            kind="image",
            filename="canon.png",
            path="canon.png",
        )
    )
    # Extra assets to serve as composed-sheet view outputs in advance tests.
    for i in range(4):
        session.add(
            Asset(
                id=f"view-{i}",
                project_id="proj-v",
                tag="view",
                kind="image",
                filename=f"v{i}.png",
                path=f"v{i}.png",
            )
        )
    session.commit()
    yield session
    session.close()


def _make_character(db, name="Korri"):
    profile = ci_service.create_profile(db, "proj-v", CharacterProfileCreate(name=name))
    return profile.id


def _attach_canonical_sheet(db, character_id, asset_id="canon-sheet"):
    """Attach the canonical hero_identity sheet (approved) to the character."""
    ci_service.attach_reference(
        db,
        "proj-v",
        character_id,
        ReferenceAttach(
            asset_id=asset_id,
            reference_role="hero_identity",
            source_type="upload",
            canonical=True,
            approval_status="approved",
            notes="Canonical Original sheet",
        ),
    )
    return asset_id


def test_max_12_variants_enforced(db):
    cid = _make_character(db)
    _attach_canonical_sheet(db, cid)
    # Create 12 variants (the max). The Original is separate (not a variant row).
    for i in range(12):
        v = variant_service.create_variant_for_character(
            db, "proj-v", cid, name=f"Variant {i + 1}", description=f"look {i + 1}"
        )
        assert v["name"] == f"Variant {i + 1}"
    # The 13th must be rejected with a clear 400.
    with pytest.raises(Exception) as ei:
        variant_service.create_variant_for_character(
            db, "proj-v", cid, name="Variant 13", description="too many"
        )
    detail = ei.value.detail if hasattr(ei.value, "detail") else ei.value
    assert "VARIANT_LIMIT_REACHED" in str(detail) or "13" in str(detail)


def test_original_immutable_on_variant_delete(db):
    cid = _make_character(db)
    canonical = _attach_canonical_sheet(db, cid)
    v = variant_service.create_variant_for_character(
        db, "proj-v", cid, name="Winter Coat", description="heavy winter coat"
    )
    # Delete the variant.
    result = variant_service.delete_variant(db, "proj-v", v["id"])
    assert result["deleted"] is True
    # The Original canonical sheet reference is untouched.
    refs = ci_service.list_references(db, "proj-v", cid)
    hero = [r for r in refs if r["reference_role"] == "hero_identity"]
    assert hero, "Original hero_identity reference must survive variant deletion"
    assert hero[0]["asset_id"] == canonical
    assert hero[0]["approval_status"] == "approved"
    # Variant is gone.
    listing = variant_service.list_variants_for_character(db, "proj-v", cid)
    assert listing["variants"] == []
    assert listing["original"]["characterSheetAssetId"] == canonical


def test_variant_generation_uses_canonical_sheet_as_reference(db):
    cid = _make_character(db)
    canonical = _attach_canonical_sheet(db, cid)
    v = variant_service.create_variant_for_character(
        db, "proj-v", cid, name="Battle Armor", description="ornate battle armor"
    )
    result = variant_service.enqueue_variant_generation(db, "proj-v", cid, v["id"])
    assert result["ok"] is True
    gen = result["generation"]
    # The generation request MUST carry the canonical sheet as the reference.
    assert gen["canonicalSheetAssetId"] == canonical
    assert gen["referenceAssetId"] == canonical
    assert gen["referenceLocked"] is True
    # Every enqueued view job is reference-locked to the canonical sheet.
    assert gen["viewJobs"], "variant generation must enqueue 4 view jobs"
    assert len(gen["viewJobs"]) == 4
    from app.db import Job

    for vj in gen["viewJobs"]:
        job = db.get(Job, vj["jobId"])
        assert job is not None
        params = json.loads(job.params_json or "{}")
        # The canonical sheet participates as the source image (reference lock).
        assert params.get("source_asset_id") == canonical, (
            "view job must carry canonical sheet as source_asset_id"
        )
        # The variant description (wardrobe/look delta) is injected into the prompt
        # on top of the identity-locked reference conditioning.
        assert "ornate battle armor" in (params.get("prompt") or "")


def test_variant_persists_required_fields(db):
    cid = _make_character(db)
    _attach_canonical_sheet(db, cid)
    v = variant_service.create_variant_for_character(
        db, "proj-v", cid, name="Formal Gown", description="elegant formal gown"
    )
    # Required fields persisted by the continuity backend.
    assert v["id"]
    assert v["name"] == "Formal Gown"
    assert v["description"] == "elegant formal gown"
    assert v["createdAt"]
    assert v["identityId"]
    assert v["identityVersionId"]
    # characterSheetAssetId starts null; populated after generation completes.
    assert v["characterSheetAssetId"] is None
    assert v["generationStatus"] is None

    # After enqueuing generation, the variant row carries the sheet lineage.
    variant_service.enqueue_variant_generation(db, "proj-v", cid, v["id"])
    listing = variant_service.list_variants_for_character(db, "proj-v", cid)
    assert len(listing["variants"]) == 1
    refreshed = listing["variants"][0]
    assert refreshed["generationStatus"] == "generating"
    assert refreshed["canonicalSheetAssetId"] == "canon-sheet"
    assert refreshed["referenceAssetId"] == "canon-sheet"
    assert refreshed["referenceLocked"] is True


def test_no_canonical_sheet_blocks_generation(db):
    cid = _make_character(db)
    # No canonical sheet attached.
    v = variant_service.create_variant_for_character(
        db, "proj-v", cid, name="No Sheet", description="nothing"
    )
    with pytest.raises(Exception) as ei:
        variant_service.enqueue_variant_generation(db, "proj-v", cid, v["id"])
    detail = ei.value.detail if hasattr(ei.value, "detail") else ei.value
    assert "NO_CANONICAL_SHEET" in str(detail)


def test_character_to_version_link_resolved(db):
    cid = _make_character(db)
    _attach_canonical_sheet(db, cid)
    identity_id, version_id = variant_service.resolve_identity_for_character(db, "proj-v", cid)
    assert identity_id and version_id
    # Idempotent — resolves the same identity/version on second call.
    identity_id2, version_id2 = variant_service.resolve_identity_for_character(db, "proj-v", cid)
    assert identity_id2 == identity_id
    assert version_id2 == version_id
    # The identity is linked back to the character profile.
    from app.continuity.models import VisualIdentityRow

    vi = db.get(VisualIdentityRow, identity_id)
    assert vi.character_profile_id == cid
