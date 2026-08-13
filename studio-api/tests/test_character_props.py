"""Phase 6 Props workspace — backend tests.

Covers the three required guarantees:

(a) Max 4 props per character — a 5th prop is rejected with a clear 400.
(b) A prop image is a CHARACTER-ASSOCIATED Library asset: when a prop is
    created/approved with a library_asset_id, project_library.service
    .assign_asset is invoked with entity_type="character" and
    entity_id=characterId so the image lives in the character's library
    folder.
(c) No duplicate binary — the SAME Asset row is reused (the prop's
    library_asset_id points at the existing Library asset; no new Asset is
    created for the prop).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity import service
from app.character_identity.schemas import PropCreate
from app.db import Asset, Base, Project


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
    session.add(Project(id="proj-props", name="Props Test"))
    session.commit()
    yield session
    session.close()


def _make_png(path: Path) -> str:
    from PIL import Image

    Image.new("RGB", (128, 128), (80, 60, 120)).save(str(path), format="PNG")
    return str(path)


def _seed_character(db) -> str:
    profile = service.seed_korri_from_canon(db, "proj-props")
    return profile.id


def _attach_hero_sheet(db, character_id: str, tmp_path) -> str:
    """Attach a canonical hero_identity sheet so prop generation can be reference-locked."""
    from app.character_identity.schemas import ReferenceAttach

    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-props",
            tag="character_sheet",
            kind="image",
            filename="sheet.png",
            path=_make_png(tmp_path / "sheet.png"),
        )
    )
    db.commit()
    service.attach_reference(
        db,
        "proj-props",
        character_id,
        ReferenceAttach(
            asset_id=asset_id,
            reference_role="hero_identity",
            source_type="upload",
            canonical=True,
            approval_status="approved",
            notes="Canonical sheet for props test",
        ),
    )
    return asset_id


# ---------------------------------------------------------------------------
# (a) Max 4 props per character
# ---------------------------------------------------------------------------


def test_max_four_props_per_character_enforced(db):
    character_id = _seed_character(db)
    for i in range(service.MAX_PROPS_PER_CHARACTER):
        service.create_prop(
            db,
            "proj-props",
            character_id,
            PropCreate(name=f"Prop {i + 1}", description=f"Accessory {i + 1}"),
        )
    # The 5th prop must be rejected with a clear 400.
    with pytest.raises(Exception) as exc_info:
        service.create_prop(
            db,
            "proj-props",
            character_id,
            PropCreate(name="Prop 5", description="Should be rejected"),
        )
    detail = getattr(exc_info.value, "detail", None) or str(exc_info.value)
    detail_str = str(detail)
    assert "PROP_LIMIT_REACHED" in detail_str or "at most" in detail_str
    # Exactly 4 props persisted.
    props = service.list_props(db, "proj-props", character_id)
    assert len(props) == service.MAX_PROPS_PER_CHARACTER


def test_max_four_props_via_api_returns_400(db):
    from fastapi import HTTPException

    character_id = _seed_character(db)
    for i in range(service.MAX_PROPS_PER_CHARACTER):
        service.create_prop(
            db,
            "proj-props",
            character_id,
            PropCreate(name=f"Prop {i + 1}"),
        )
    with pytest.raises(HTTPException) as exc_info:
        service.create_prop(db, "proj-props", character_id, PropCreate(name="Prop 5"))
    assert exc_info.value.status_code == 400
    assert "PROP_LIMIT_REACHED" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# (b) Prop is a character-associated Library asset
# ---------------------------------------------------------------------------


def test_prop_with_library_asset_registers_character_association(db, tmp_path, monkeypatch):
    character_id = _seed_character(db)
    # Create a Library image asset (simulating an upload or generated image).
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-props",
            tag="prop_image",
            kind="image",
            filename="prop.png",
            path=_make_png(tmp_path / "prop.png"),
        )
    )
    db.commit()

    calls: list[dict] = []

    def fake_assign_asset(dbs, asset, **kwargs):
        calls.append({"asset_id": asset.id, **kwargs})
        # Return a minimal meta-like object; the real helper writes library meta.

    monkeypatch.setattr(
        "app.project_library.service.assign_asset",
        fake_assign_asset,
    )

    service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Staff", description="A carved wooden staff", library_asset_id=asset_id),
    )

    assert len(calls) == 1, "assign_asset must be called once when library_asset_id is supplied"
    call = calls[0]
    assert call["asset_id"] == asset_id
    assert call["entity_type"] == "character"
    assert call["entity_id"] == character_id


def test_approve_prop_registers_character_association(db, tmp_path, monkeypatch):
    character_id = _seed_character(db)
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-props",
            tag="prop_image",
            kind="image",
            filename="prop.png",
            path=_make_png(tmp_path / "prop.png"),
        )
    )
    db.commit()

    calls: list[dict] = []

    def fake_assign_asset(dbs, asset, **kwargs):
        calls.append({"asset_id": asset.id, **kwargs})

    monkeypatch.setattr(
        "app.project_library.service.assign_asset",
        fake_assign_asset,
    )

    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Earrings", description="Wooden earrings"),
    )
    # Approve without an image must fail with a clear 400.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        service.approve_prop(db, "proj-props", character_id, created["id"])
    assert exc_info.value.status_code == 400

    # Now link the image and approve — assign_asset should fire.
    from app.character_identity.models import CharacterPropRow

    row = db.get(CharacterPropRow, created["id"])
    row.library_asset_id = asset_id
    db.commit()

    result = service.approve_prop(db, "proj-props", character_id, created["id"])
    assert result["approval_status"] == "approved"
    assert result["library_asset_id"] == asset_id
    assert len(calls) == 1
    assert calls[0]["entity_type"] == "character"
    assert calls[0]["entity_id"] == character_id


# ---------------------------------------------------------------------------
# (c) No duplicate binary
# ---------------------------------------------------------------------------


def test_prop_reuses_existing_library_asset_no_duplicate_binary(db, tmp_path):
    character_id = _seed_character(db)
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-props",
            tag="prop_image",
            kind="image",
            filename="prop.png",
            path=_make_png(tmp_path / "prop.png"),
        )
    )
    db.commit()

    before = db.query(Asset).filter(Asset.kind == "image").count()
    service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Pendant", description="A sun pendant", library_asset_id=asset_id),
    )
    after = db.query(Asset).filter(Asset.kind == "image").count()
    # No new Asset row was created — the prop points at the existing Library asset.
    assert after == before, "prop creation must not duplicate the binary asset"

    # The prop row references the same asset id.
    props = service.list_props(db, "proj-props", character_id)
    assert props[0]["library_asset_id"] == asset_id


def test_delete_prop_does_not_delete_library_asset(db, tmp_path):
    """Removing a prop clears the character_props row but keeps the Library
    image as a reusable project resource (consistent with delete_profile)."""
    character_id = _seed_character(db)
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-props",
            tag="prop_image",
            kind="image",
            filename="prop.png",
            path=_make_png(tmp_path / "prop.png"),
        )
    )
    db.commit()
    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Pendant", library_asset_id=asset_id),
    )
    service.delete_prop(db, "proj-props", character_id, created["id"])
    # Prop row gone.
    props = service.list_props(db, "proj-props", character_id)
    assert props == []
    # Library asset still present.
    assert db.get(Asset, asset_id) is not None


def test_update_prop_patches_editable_fields(db):
    from app.character_identity.schemas import PropUpdate

    character_id = _seed_character(db)
    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Staff", description="A staff"),
    )
    updated = service.update_prop(
        db,
        "proj-props",
        character_id,
        created["id"],
        PropUpdate(name="Korri's Staff", description="A carved wooden staff with sun glyphs"),
    )
    assert updated["name"] == "Korri's Staff"
    assert updated["description"] == "A carved wooden staff with sun glyphs"
    # approval_status untouched by update.
    assert updated["approval_status"] == "draft"
    props = service.list_props(db, "proj-props", character_id)
    assert props[0]["name"] == "Korri's Staff"


def test_update_prop_unknown_character_returns_404(db):
    from fastapi import HTTPException

    from app.character_identity.schemas import PropUpdate

    with pytest.raises(HTTPException) as exc_info:
        service.update_prop(db, "proj-props", "no-such-char", "no-such-prop", PropUpdate(name="x"))
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Generation enqueue path reuses the existing image-generation pipeline
# ---------------------------------------------------------------------------


def test_generate_prop_enqueues_reference_locked_job(db, tmp_path, monkeypatch):
    character_id = _seed_character(db)
    _attach_hero_sheet(db, character_id, tmp_path)

    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Staff", description="A carved wooden staff"),
    )

    enqueued: list[dict] = []

    def fake_enqueue(dbs, project_id, body):
        from app.db import Job

        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="image",
            status="queued",
            progress=0.0,
            stage="Queued",
            message="",
            params_json="{}",
        )
        dbs.add(job)
        dbs.commit()
        enqueued.append({"project_id": project_id, "body": body, "job_id": job.id})
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)

    result = service.generate_prop_image(db, "proj-props", character_id, created["id"])
    assert result["status"] == "queued"
    assert len(enqueued) == 1
    body = enqueued[0]["body"]
    # Reuses the existing enqueue path (storyboard_jobs.enqueue_imagegen_job).
    assert body["modelFamilyPreference"] == "zimage"
    assert body["source_asset_id"]  # reference-locked to the character sheet
    assert body["creativeContext"]["referenceLocked"] is True
    assert body["creativeContext"]["characterId"] == character_id
    assert body["creativeContext"]["propId"] == created["id"]
    # Prop row records the pending job id.
    from app.character_identity.models import CharacterPropRow

    row = db.get(CharacterPropRow, created["id"])
    assert row.generation_job_id == result["jobId"]


def test_generate_prop_requires_character_sheet(db, tmp_path, monkeypatch):
    from fastapi import HTTPException

    character_id = _seed_character(db)
    # No canonical hero_identity sheet attached yet.
    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Staff", description="A staff"),
    )
    with pytest.raises(HTTPException) as exc_info:
        service.generate_prop_image(db, "proj-props", character_id, created["id"])
    assert exc_info.value.status_code == 400
    assert "NO_CHARACTER_SHEET" in str(exc_info.value.detail)


def test_get_prop_status_links_output_asset_when_done(db, tmp_path, monkeypatch):
    import json

    from app.db import Job
    from app.character_identity.models import CharacterPropRow

    character_id = _seed_character(db)
    _attach_hero_sheet(db, character_id, tmp_path)
    created = service.create_prop(
        db,
        "proj-props",
        character_id,
        PropCreate(name="Korri's Staff", description="A carved wooden staff"),
    )

    def fake_enqueue(dbs, project_id, body):
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="image",
            status="queued",
            progress=0.0,
            stage="Queued",
            message="",
            params_json="{}",
        )
        dbs.add(job)
        dbs.commit()
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    gen = service.generate_prop_image(db, "proj-props", character_id, created["id"])

    # Simulate the queue worker completing the job and producing an output asset.
    out_asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=out_asset_id,
            project_id="proj-props",
            tag="prop_image",
            kind="image",
            filename="staff.png",
            path=_make_png(tmp_path / "staff.png"),
        )
    )
    job = db.get(Job, gen["jobId"])
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": out_asset_id})
    db.commit()

    status = service.get_prop_status(db, "proj-props", character_id, created["id"])
    assert status["jobStatus"] == "done"
    assert status["library_asset_id"] == out_asset_id
    # The prop row now references the output asset (no duplicate binary).
    row = db.get(CharacterPropRow, created["id"])
    assert row.library_asset_id == out_asset_id


if __name__ == "__main__":
    import pytest as _pytest

    sys.exit(_pytest.main([__file__, "-v"]))
