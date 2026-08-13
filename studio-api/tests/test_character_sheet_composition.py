"""Phase 5 — Character Creator Simplification: composed 4-view Character Sheet tests.

Covers three required areas:

(a) 4 views → structural identity-consistency validation → ONE composed 2x2
    Character Sheet asset, with the 4 source view assets retained as lineage.
(b) Reference-first routing hierarchy:
    - reference attached → reference-capable Certified family first (zimage),
      NEVER a text-only family (Illustrious) for reference-locked candidates;
    - no reference → style recommendation first (anime → Illustrious).
(c) Use-as-Character-Identity: a user-provided (upload/library) reference
    becomes a candidate WITHOUT generation, is approve-gated, records
    ``generationUsed=false`` provenance, and preserves the original Library
    asset id (no binary duplication).
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401  (ensure asset_edges table is created)
from app.character_identity import service
from app.character_identity.visual_sheet import (
    CANDIDATE_SHEET_VIEW_ROLES,
    CHARACTER_SHEET_GRID_COLS,
    CHARACTER_SHEET_GRID_ROWS,
    COMPOSITION_INTENT_CHARACTER_SHEET,
    REFERENCE_LOCKED_FAMILY,
    REFERENCE_LOCKED_WORKFLOW_KEY,
    TEXT_ONLY_FAMILIES,
    _build_candidate_routing_plan,
    _candidate_view_specs,
    _compose_character_sheet_grid,
    _validate_candidate_view_consistency,
    advance_visual_sheet_pack,
    get_visual_sheet_pack,
    start_visual_sheet_generation,
)
from app.db import Asset, Base, Job, Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE character_profiles ADD COLUMN {col} TEXT DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-sheet", name="Sheet Test"))
    session.commit()
    yield session
    session.close()


def _make_png(path: Path) -> str:
    from PIL import Image

    Image.new("RGB", (256, 256), (200, 100, 50)).save(str(path), format="PNG")
    return str(path)


# ---------------------------------------------------------------------------
# (a) 4 views → validate → one composed sheet, 4 sources kept as lineage
# ---------------------------------------------------------------------------


def test_candidate_view_specs_are_four_views_in_grid_order():
    specs = _candidate_view_specs()
    assert len(specs) == 4
    roles = [s[0] for s in specs]
    assert roles == list(CANDIDATE_SHEET_VIEW_ROLES)
    # Grid is 2x2.
    assert CHARACTER_SHEET_GRID_COLS * CHARACTER_SHEET_GRID_ROWS == 4


def test_validate_candidate_view_consistency_passes_for_four_done_views():
    entries = [
        {
            "role": role,
            "status": "done",
            "assetId": f"asset-{i}",
            "seed": 12345,
            "modelFamily": "zimage",
            "workflowKey": "zimage.ref_edit",
            "referenceLocked": True,
        }
        for i, role in enumerate(CANDIDATE_SHEET_VIEW_ROLES)
    ]
    result = _validate_candidate_view_consistency(entries)
    assert result["ok"] is True
    assert result["reasons"] == []
    assert len(result["assetIds"]) == 4


def test_validate_candidate_view_consistency_fails_when_a_view_not_done():
    entries = [
        {
            "role": role,
            "status": "done" if i != 1 else "queued",
            "assetId": f"asset-{i}" if i != 1 else None,
            "seed": 1,
            "modelFamily": "zimage",
            "workflowKey": "zimage.ref_edit",
            "referenceLocked": True,
        }
        for i, role in enumerate(CANDIDATE_SHEET_VIEW_ROLES)
    ]
    result = _validate_candidate_view_consistency(entries)
    assert result["ok"] is False
    assert any("not done" in r for r in result["reasons"])


def test_validate_candidate_view_consistency_fails_on_inconsistent_seed():
    entries = [
        {
            "role": role,
            "status": "done",
            "assetId": f"asset-{i}",
            "seed": 100 + i,  # different seeds
            "modelFamily": "zimage",
            "workflowKey": "zimage.ref_edit",
            "referenceLocked": True,
        }
        for i, role in enumerate(CANDIDATE_SHEET_VIEW_ROLES)
    ]
    result = _validate_candidate_view_consistency(entries)
    assert result["ok"] is False
    assert any("inconsistent seeds" in r for r in result["reasons"])


def test_compose_character_sheet_grid_produces_2x2_png(tmp_path):
    from PIL import Image

    view_paths = [_make_png(tmp_path / f"view_{i}.png") for i in range(4)]
    out = tmp_path / "sheet.png"
    result = _compose_character_sheet_grid(view_paths, str(out))
    assert result == str(out)
    assert out.is_file()
    im = Image.open(out)
    tile = 1024
    assert im.size == (tile * CHARACTER_SHEET_GRID_COLS, tile * CHARACTER_SHEET_GRID_ROWS)


def test_compose_character_sheet_grid_rejects_wrong_view_count(tmp_path):
    with pytest.raises(ValueError):
        _compose_character_sheet_grid([_make_png(tmp_path / "v.png")], str(tmp_path / "o.png"))


def test_advance_composes_four_views_into_one_sheet_with_lineage(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(db, "proj-sheet", profile.id, include_details=False)
    hero = pack["jobs"]["hero"]
    view_jobs = hero["viewJobs"]
    assert len(view_jobs) == 4

    # Complete each of the 4 view jobs with a real PNG output asset.
    source_ids: list[str] = []
    for i, vj in enumerate(view_jobs):
        job = db.get(Job, vj["jobId"])
        asset_id = str(uuid.uuid4())
        asset_path = _make_png(tmp_path / f"src_{i}.png")
        db.add(
            Asset(
                id=asset_id,
                project_id="proj-sheet",
                tag=f"view_{vj['role']}",
                kind="image",
                filename=Path(asset_path).name,
                path=asset_path,
            )
        )
        job.status = "done"
        job.params_json = json.dumps({"output_asset_id": asset_id})
        source_ids.append(asset_id)
    db.commit()

    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    candidates = advanced.get("candidates") or []
    assert candidates, "expected at least one candidate after advance"
    cand = candidates[0]
    sheet_id = cand.get("sheetAssetId") or cand.get("assetId")
    assert sheet_id, "composed sheet asset id must be set"
    assert cand.get("assetId") == sheet_id, "creator-facing assetId is the composed sheet"
    # 4 source views retained as lineage.
    assert set(cand.get("sourceAssetIds") or []) == set(source_ids)
    # role_assets hero_identity points to the composed sheet.
    role_assets = advanced.get("roleAssets") or {}
    assert role_assets.get("hero_identity") == sheet_id
    # The composed sheet asset exists in the Library with lineage metadata.
    sheet_asset = db.get(Asset, sheet_id)
    assert sheet_asset is not None
    assert sheet_asset.tag == "character_sheet"
    meta = json.loads(sheet_asset.prompt_meta_json or "{}")
    assert meta.get("compositionIntent") == COMPOSITION_INTENT_CHARACTER_SHEET
    assert set(meta.get("sourceAssetIds") or []) == set(source_ids)
    # No binary duplication: 4 source assets remain distinct from the sheet.
    assert sheet_id not in source_ids


# ---------------------------------------------------------------------------
# (b) Reference-first routing hierarchy
# ---------------------------------------------------------------------------


def test_reference_locked_routing_never_uses_text_only_family():
    """An attached reference must NEVER route to a text-only family (Illustrious)."""
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-1")
    for route in plan:
        assert route["modelFamilyPreference"] == REFERENCE_LOCKED_FAMILY
        assert route["workflowKey"] == REFERENCE_LOCKED_WORKFLOW_KEY
        assert route["modelFamilyPreference"] not in TEXT_ONLY_FAMILIES
        assert route["referenceLocked"] is True


def test_reference_locked_routing_prefers_reference_capable_family():
    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id="sheet-1")
    # zimage.ref_edit is the only Certified reference-capable workflow today.
    assert all(r["modelFamilyPreference"] == "zimage" for r in plan)
    assert all(r["source_asset_id"] == "sheet-1" for r in plan)


def test_no_reference_routing_style_first_for_anime():
    """No reference → style recommendation first (anime → Illustrious XL)."""
    plan = _build_candidate_routing_plan(
        candidate_count=4, reference_asset_id=None, visual_style="anime"
    )
    # The first candidate should prefer the anime style family (Illustrious)
    # when no reference is attached.
    from app.character_identity.visual_sheet import _no_reference_families_for_style

    distinct = _no_reference_families_for_style("anime")
    assert distinct, "anime style must resolve to at least one family"
    assert plan[0]["modelFamilyPreference"] == distinct[0]
    assert plan[0]["referenceLocked"] is False
    assert plan[0]["source_asset_id"] is None


def test_no_reference_routing_distinct_families_used_once_first():
    from app.character_identity.visual_sheet import NO_REFERENCE_TXT2IMG_FAMILIES

    plan = _build_candidate_routing_plan(candidate_count=4, reference_asset_id=None)
    families = [r["modelFamilyPreference"] for r in plan]
    distinct = list(NO_REFERENCE_TXT2IMG_FAMILIES)
    for i, fam in enumerate(distinct):
        assert families[i] == fam
    assert set(families) == set(distinct)


def test_user_control_law_all_sources_disabled_enqueues_zero_jobs():
    """User Control Law (D2): an explicit all-disabled generator_sources selection
    must refuse generation (zero jobs) rather than silently falling back."""
    with pytest.raises(ValueError, match="No image generator enabled"):
        _build_candidate_routing_plan(
            candidate_count=4,
            reference_asset_id=None,
            generator_sources={"local": None, "api": None},
        )


def test_user_control_law_local_only_still_routes():
    """Local-only enabled → routing still produces a plan (local default)."""
    plan = _build_candidate_routing_plan(
        candidate_count=2,
        reference_asset_id=None,
        generator_sources={"local": {"family": "qwen2512"}, "api": None},
    )
    assert len(plan) == 2


def test_user_control_law_omitted_sources_preserves_default_routing():
    """Legacy callers that omit generator_sources get unchanged default routing."""
    plan = _build_candidate_routing_plan(candidate_count=2, reference_asset_id=None)
    assert len(plan) == 2


def test_recommend_image_family_reference_locked_avoids_text_only():
    """recommend_image_family must not route a reference-locked request to Illustrious."""
    from app.image_product.recommend import recommend_image_family

    # Even with an anime style + a text-only style preference, a reference
    # attachment must keep the family reference-capable (never Illustrious).
    out = recommend_image_family(
        prompt="anime character sheet",
        purpose="character_sheet",
        style="anime",
        reference_asset_id="sheet-1",
    )
    assert out["referenceLocked"] is True
    assert out["recommendedFamily"] != "illustrious"
    assert out["recommendedFamily"] not in ("illustrious",)


def test_recommend_image_family_no_reference_style_first_anime():
    """Without a reference, anime style routing may select Illustrious."""
    from app.image_product.recommend import recommend_image_family

    out = recommend_image_family(
        prompt="anime character sheet",
        purpose="character_sheet",
        style="anime",
    )
    assert out["referenceLocked"] is False
    # Anime style prefers Illustrious when it is executable; otherwise falls back.
    assert out["recommendedFamily"] in ("illustrious", "qwen2512", "zimage")


# ---------------------------------------------------------------------------
# (c) Use-as-Character-Identity (approve-gated, generationUsed=false)
# ---------------------------------------------------------------------------


def test_approve_upload_candidate_records_generation_used_false_and_preserves_asset(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    # A user-provided upload reference becomes a candidate WITHOUT generation.
    upload_id = str(uuid.uuid4())
    upload_path = _make_png(tmp_path / "upload.png")
    db.add(
        Asset(
            id=upload_id,
            project_id="proj-sheet",
            tag="user_upload",
            kind="image",
            filename="upload.png",
            path=upload_path,
        )
    )
    db.commit()

    # It becomes hero_identity ONLY after explicit approve-candidate.
    result = service.approve_character_candidate(
        db,
        "proj-sheet",
        profile.id,
        asset_id=upload_id,
        reference_role="hero_identity",
        source_type="upload",
        notes="Use-as-Character-Identity from upload",
    )
    assert result["canonical"] is True
    assert result["approvalStatus"] == "approved"
    assert result["generationUsed"] is False
    assert result["sourceType"] == "upload"

    # The original Library asset id is preserved (no binary duplication).
    assert result["assetId"] == upload_id
    # No new asset was created for the candidate.
    assert db.query(Asset).filter(Asset.id == upload_id).count() == 1

    # Provenance is recorded on the reference row.
    from app.character_identity.models import CharacterReferenceAssetRow

    row = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == profile.id,
            CharacterReferenceAssetRow.reference_role == "hero_identity",
            CharacterReferenceAssetRow.canonical.is_(True),
        )
        .first()
    )
    assert row is not None
    lineage = json.loads(row.generation_lineage_json or "{}")
    assert lineage["generationUsed"] is False
    assert lineage["sourceType"] == "upload"
    assert lineage["originalAssetId"] == upload_id


def test_approve_library_candidate_records_generation_used_false(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    lib_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=lib_id,
            project_id="proj-sheet",
            tag="library_pick",
            kind="image",
            filename="lib.png",
            path=_make_png(tmp_path / "lib.png"),
        )
    )
    db.commit()
    result = service.approve_character_candidate(
        db,
        "proj-sheet",
        profile.id,
        asset_id=lib_id,
        reference_role="hero_identity",
        source_type="library",
    )
    assert result["generationUsed"] is False
    assert result["sourceType"] == "library"
    assert result["assetId"] == lib_id


def test_approve_generation_candidate_records_generation_used_true(db, tmp_path):
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    gen_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=gen_id,
            project_id="proj-sheet",
            tag="generated_candidate",
            kind="image",
            filename="gen.png",
            path=_make_png(tmp_path / "gen.png"),
        )
    )
    db.commit()
    result = service.approve_character_candidate(
        db,
        "proj-sheet",
        profile.id,
        asset_id=gen_id,
        reference_role="hero_identity",
        source_type="generation",
    )
    assert result["generationUsed"] is True
    assert result["sourceType"] == "generation"


def test_approve_candidate_idempotent_preserves_generation_used_false(db, tmp_path):
    """Re-approving the same upload keeps generationUsed=false (no flip to true)."""
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    upload_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=upload_id,
            project_id="proj-sheet",
            tag="user_upload",
            kind="image",
            filename="upload.png",
            path=_make_png(tmp_path / "upload.png"),
        )
    )
    db.commit()
    first = service.approve_character_candidate(
        db, "proj-sheet", profile.id, asset_id=upload_id, source_type="upload"
    )
    second = service.approve_character_candidate(
        db, "proj-sheet", profile.id, asset_id=upload_id, source_type="upload"
    )
    assert first["generationUsed"] is False
    assert second["generationUsed"] is False
    assert second["replaced"] is False


if __name__ == "__main__":
    import pytest as _pytest

    sys.exit(_pytest.main([__file__, "-v"]))
