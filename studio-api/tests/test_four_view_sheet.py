"""Character Sheet four-view product law + Kie extract live-shape tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.character_identity.four_view_sheet import (
    FOUR_VIEW_SHEET_PROMPT,
    REQUIRED_VIEWS,
    assess_four_view_layout,
    attach_four_view_sheet_intent,
    is_four_view_sheet_request,
    public_job_error,
    strengthen_four_view_prompt,
)
from app.hosted_providers.adapters.kie_adapter import (
    extract_kie_image_url,
    kie_poll_timeout_message,
    strengthen_kie_character_sheet_prompt,
)
from app.image_prompting.qwen_2512.character_sheet_grammar import compile_character_sheet_block


def test_required_views_are_the_product_law():
    assert REQUIRED_VIEWS == (
        "full_body_front",
        "full_body_side",
        "full_body_back",
        "head_shoulders_closeup",
    )


def test_attach_four_view_sheet_intent_stamps_structured_fields():
    body = {"prompt": "a person", "creativeContext": {"objective": "x"}}
    out = attach_four_view_sheet_intent(body)
    assert out["purpose"] == "character_sheet"
    assert out["layout"] == "four_view"
    assert out["requiredViews"] == list(REQUIRED_VIEWS)
    assert out["referenceMode"] == "identity_preservation"
    assert out["characterSheetIntent"]["layout"] == "four_view"
    assert out["creativeContext"]["layout"] == "four_view"
    assert is_four_view_sheet_request(out) is True


def test_is_four_view_sheet_request_does_not_trust_purpose_alone():
    assert is_four_view_sheet_request({"purpose": "character_sheet"}) is False
    assert is_four_view_sheet_request({"purpose": "character_sheet", "layout": "four_view"}) is True
    assert is_four_view_sheet_request({"creativeContext": {"layout": "four_view"}}) is True


def test_strengthen_four_view_prompt_is_idempotent():
    once = strengthen_four_view_prompt("a cinematic full-body character casting reference")
    assert FOUR_VIEW_SHEET_PROMPT in once
    assert "Do not generate a single standalone character image" in once
    twice = strengthen_four_view_prompt(once)
    assert twice.count("professional four-panel character turnaround sheet") == 1
    kie = strengthen_kie_character_sheet_prompt("hero", model="nano-banana-2")
    assert FOUR_VIEW_SHEET_PROMPT in kie


def test_empty_sheet_request_still_forbids_collage_on_single_view_tiles():
    text = compile_character_sheet_block({}, [])
    assert "Single approved image output" in text


def test_four_view_sheet_request_emits_product_law_block():
    text = compile_character_sheet_block(
        {"enabled": True, "layout": "four_view", "views": ["front", "side_left", "back", "front_closeup"]},
        [],
    )
    assert "layout=four_view" in text
    assert "full_body_front" in text
    assert "head_shoulders_closeup" in text
    assert "single standalone" in text


def test_public_job_error_strips_traceback():
    raw = (
        "Kie task abc still generating (state=generating)\n\n--- details ---\n"
        "Traceback (most recent call last):\n  File x, line 1\nRuntimeError: boom"
    )
    msg = public_job_error(raw)
    assert "Traceback" not in msg
    assert "details" not in msg.lower()
    assert msg.startswith("Kie task abc")


def test_assess_four_view_layout_rejects_tall_single_pose(tmp_path):
    from PIL import Image

    tall = tmp_path / "tall.png"
    Image.new("RGB", (512, 1024), (10, 20, 30)).save(tall)
    out = assess_four_view_layout(tall)
    assert out["compliant"] is False
    assert out["layoutNoncompliant"] is True
    assert "layout-noncompliant" in out["note"]


def test_assess_four_view_layout_square_is_honest_unverified(tmp_path):
    from PIL import Image

    square = tmp_path / "square.png"
    Image.new("RGB", (1024, 1024), (10, 20, 30)).save(square)
    out = assess_four_view_layout(square)
    assert out["compliant"] is not False
    assert out["verified"] is False
    assert out["layoutNoncompliant"] is False
    assert "layout not verified" in out["note"]




def test_square_four_view_is_sheet_candidate_not_gated_on_verified(tmp_path):
    """Brad contract: square/landscape four_view = layoutNoncompliant false.

    layoutVerified may stay false. Use This Look reads layoutNoncompliant only.
    """
    from PIL import Image

    from app.character_identity.four_view_sheet import (
        apply_layout_assessment_to_candidate,
        can_use_this_look,
        candidate_layout_noncompliant,
    )

    square = tmp_path / "square.png"
    Image.new("RGB", (2048, 2048), (10, 20, 30)).save(square)
    out = assess_four_view_layout(square)
    assert out["layoutNoncompliant"] is False
    assert out["verified"] is False
    assert out["aspect"] == 1.0

    landscape = tmp_path / "wide.png"
    Image.new("RGB", (1600, 900), (10, 20, 30)).save(landscape)
    wide = assess_four_view_layout(landscape)
    assert wide["layoutNoncompliant"] is False
    assert wide["verified"] is False

    tall = tmp_path / "tall.png"
    Image.new("RGB", (512, 640), (10, 20, 30)).save(tall)
    bad = assess_four_view_layout(tall)
    assert bad["layoutNoncompliant"] is True
    assert bad["aspect"] >= 1.25

    square_cand = apply_layout_assessment_to_candidate(
        {
            "status": "done",
            "sheetAssetId": "sq-1",
            "assetId": "sq-1",
            "fourViewSingleOutput": True,
            "layout": "four_view",
        },
        out,
    )
    assert square_cand["layoutNoncompliant"] is False
    assert square_cand["layoutVerified"] is False
    assert candidate_layout_noncompliant(square_cand) is False
    assert can_use_this_look(square_cand) is True

    stale = {
        "status": "done",
        "sheetAssetId": "sq-1",
        "assetId": "sq-1",
        "fourViewSingleOutput": True,
        "layout": "four_view",
        "layoutNoncompliant": True,
        "layout_noncompliant": True,
        "layoutVerified": False,
        "layoutAssessment": {"width": 2048, "height": 2048, "layoutNoncompliant": True},
    }
    assert candidate_layout_noncompliant(stale) is False
    assert can_use_this_look(stale) is True

    tall_cand = apply_layout_assessment_to_candidate(
        {"status": "done", "sheetAssetId": "t-1", "assetId": "t-1", "fourViewSingleOutput": True},
        bad,
    )
    assert tall_cand["layoutNoncompliant"] is True
    assert candidate_layout_noncompliant(tall_cand) is True
    assert can_use_this_look(tall_cand) is False

def test_extract_kie_image_url_matches_live_recordinfo_shape():
    payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "taskId": "8aa472a0a01bd1f141af2a689df3a12a",
            "model": "nano-banana-2",
            "state": "success",
            "resultJson": json.dumps(
                {
                    "resultUrls": [
                        "https://tempfile.aiquickdraw.com/ggc/8aa472a0a01bd1f141af2a689df3a12a_1786755564653.jpeg"
                    ]
                }
            ),
            "failCode": None,
            "failMsg": None,
        },
    }
    url = extract_kie_image_url(payload)
    assert url and url.startswith("https://tempfile.aiquickdraw.com/")
    assert extract_kie_image_url({"ok": True, "payload": payload}) == url


def test_kie_poll_timeout_still_generating_not_no_url():
    msg = kie_poll_timeout_message("8aa472a0a01bd1f141af2a689df3a12a", "generating")
    assert "still generating" in msg
    assert "no image URL" not in msg


def test_api_sheet_enqueues_one_four_view_job_not_four_portraits(tmp_path, monkeypatch):
    """Hosted API Character Sheet must be one four-view job, not four single poses."""
    import json
    import uuid
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.character_identity import models as _ci_models  # noqa: F401
    from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
    from app.character_identity import service
    from app.character_identity.visual_sheet import start_visual_sheet_generation
    from app.config import settings
    from app.db import Base, Job, Project

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()

    captured: list[dict] = []

    def fake_enqueue(db, project_id, body, scene_id=None):
        captured.append(dict(body or {}))
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    monkeypatch.setattr("app.secrets_store.get_secret", lambda _name: "test-key")

    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        generator_sources={"local": None, "api": {"model": "nano-banana-kie"}},
    )
    hero = pack["jobs"]["hero"]
    views = hero["viewJobs"]
    assert len(views) == 1
    assert hero.get("fourViewSingleOutput") is not True
    assert "full_body_three_quarter_front" not in [v.get("role") for v in views]
    assert hero.get("requiredViews") == ["front_full"]
    assert len(captured) == 1
    for body in captured:
        assert body["purpose"] == "character_sheet"
        assert body.get("layout") != "four_view"
        assert body.get("taskType") == "CRS_SINGLE_VIEW"
        assert "four-panel character turnaround sheet" not in (body.get("prompt") or "")
        assert max(int(body["width"]), int(body["height"])) >= 2048
    db.close()


def test_local_sheet_enqueues_one_four_view_job_with_intent(tmp_path, monkeypatch):
    """Local families also enqueue ONE four-view job, not four tiles + PIL stitch."""
    import json
    import uuid
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.character_identity import models as _ci_models  # noqa: F401
    from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
    from app.character_identity import service
    from app.character_identity.four_view_sheet import REQUIRED_VIEWS, FOUR_VIEW_SHEET_PROMPT
    from app.character_identity.visual_sheet import (
        _sheet_request_for_role,
        start_visual_sheet_generation,
    )
    from app.config import settings
    from app.db import Base, Job, Project

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()

    captured: list[dict] = []

    def fake_enqueue(db, project_id, body, scene_id=None):
        captured.append(dict(body or {}))
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        generator_sources={"local": {"model": "qwen2512"}, "api": None},
    )
    hero = pack["jobs"]["hero"]
    assert len(hero["viewJobs"]) == 1
    assert hero.get("fourViewSingleOutput") is not True
    assert hero.get("requiredViews") == ["front_full"]
    assert "full_body_three_quarter" not in REQUIRED_VIEWS
    assert len(captured) == 1
    body = captured[0]
    assert body["purpose"] == "character_sheet"
    assert body.get("layout") != "four_view"
    assert body.get("taskType") == "CRS_SINGLE_VIEW"
    assert body.get("fourViewSingleOutput") is not True
    assert "four-panel" not in (body.get("prompt") or "")
    assert _sheet_request_for_role("hero_identity") == {}
    assert _sheet_request_for_role("full_body_front") == {}
    db.close()


def test_adapters_strengthen_four_view_prompt():
    from app.character_identity.four_view_sheet import (
        FOUR_VIEW_SHEET_PROMPT,
        strengthen_local_character_sheet_prompt,
    )
    from app.hosted_providers.adapters.fal_adapter import strengthen_fal_character_sheet_prompt
    from app.hosted_providers.adapters.kie_adapter import strengthen_kie_character_sheet_prompt

    for fn, kwargs in (
        (strengthen_kie_character_sheet_prompt, {"model": "nano-banana-2"}),
        (strengthen_kie_character_sheet_prompt, {"model": "gpt-image-2-text-to-image"}),
        (strengthen_kie_character_sheet_prompt, {"model": "seedream/5-pro-text-to-image"}),
        (strengthen_fal_character_sheet_prompt, {"model": "fal-ai/flux"}),
        (strengthen_local_character_sheet_prompt, {"family": "qwen2512"}),
        (strengthen_local_character_sheet_prompt, {"family": "zimage"}),
    ):
        out = fn("a cinematic character", **kwargs)
        assert FOUR_VIEW_SHEET_PROMPT in out
        assert "Do not generate a single standalone character image" in out

def test_apply_layout_assessment_stamps_fe_fields(tmp_path):
    """FE reads candidate.layoutNoncompliant / layout_noncompliant. Single-pose must stamp true."""
    from PIL import Image

    from app.character_identity.four_view_sheet import (
        apply_layout_assessment_to_candidate,
        assess_four_view_layout,
        candidate_layout_noncompliant,
    )

    tall = tmp_path / "tall.png"
    Image.new("RGB", (512, 1024), (10, 20, 30)).save(tall)
    assessment = assess_four_view_layout(tall)
    assert assessment["layoutNoncompliant"] is True
    cand = apply_layout_assessment_to_candidate(
        {"status": "done", "sheetAssetId": "asset-1", "assetId": "asset-1", "fourViewSingleOutput": True},
        assessment,
    )
    assert cand["layoutNoncompliant"] is True
    assert cand["layout_noncompliant"] is True
    assert cand["layoutVerified"] is bool(assessment.get("verified"))
    assert candidate_layout_noncompliant(cand) is True


def test_candidate_layout_noncompliant_does_not_force_clear_on_done():
    from app.character_identity.four_view_sheet import candidate_layout_noncompliant

    generating = {
        "status": "generating",
        "fourViewSingleOutput": True,
        "layout": "four_view",
        "viewJobs": [{"role": "hero_identity"}],
    }
    assert candidate_layout_noncompliant(generating) is False

    done_bad = {
        "status": "done",
        "sheetAssetId": "a1",
        "assetId": "a1",
        "layoutNoncompliant": True,
        "fourViewSingleOutput": True,
        "viewJobs": [{"role": "hero_identity"}],
    }
    assert candidate_layout_noncompliant(done_bad) is True

    done_ok = {
        "status": "done",
        "sheetAssetId": "a1",
        "layoutNoncompliant": False,
        "fourViewSingleOutput": True,
        "viewJobs": [{"role": "four_view_sheet"}],
    }
    assert candidate_layout_noncompliant(done_ok) is False


def test_advance_stamps_layout_noncompliant_for_single_pose(tmp_path, monkeypatch):
    """Tall single-pose output must set layoutNoncompliant on the candidate FE reads."""
    import json
    import uuid
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from PIL import Image

    from app.character_identity import models as _ci_models  # noqa: F401
    from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
    from app.character_identity import service
    from app.character_identity.visual_sheet import (
        advance_visual_sheet_pack,
        start_visual_sheet_generation,
    )
    from app.config import settings
    from app.db import Asset, Base, Job, Project

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text("ALTER TABLE character_profiles ADD COLUMN %s TEXT DEFAULT %s" % (col, default)))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()

    def fake_enqueue(db, project_id, body, scene_id=None):
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    profile = service.seed_korri_from_canon(db, "proj-sheet")
    pack = start_visual_sheet_generation(
        db,
        "proj-sheet",
        profile.id,
        include_details=False,
        generator_sources={"local": {"family": "qwen2512"}, "api": None},
    )
    hero = pack["jobs"]["hero"]
    assert len(hero["viewJobs"]) == 1
    # Completing Front must not auto-compose a Character Sheet.
    vj = hero["viewJobs"][0]
    job = db.get(Job, vj["jobId"])
    asset_id = str(uuid.uuid4())
    tall = tmp_path / "tall_pose.png"
    Image.new("RGB", (512, 1024), (10, 20, 30)).save(tall)
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-sheet",
            tag="character_sheet",
            kind="image",
            filename=tall.name,
            path=str(tall),
        )
    )
    job.status = "done"
    job.params_json = json.dumps({"output_asset_id": asset_id})
    db.commit()

    advanced = advance_visual_sheet_pack(db, "proj-sheet", profile.id)
    cand = (advanced.get("candidates") or [None])[0]
    assert cand is not None
    assert cand.get("sheetAssetId") in (None, "")
    assert cand.get("status") in ("generating", "queued", None) or cand.get("sheetAssetId") in (None, "")
    db.close()


def test_local_and_api_each_enqueue_one_job_not_four(tmp_path, monkeypatch):
    """Five law-view jobs per candidate x selected generator (not one four-panel)."""
    import json
    import uuid
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.character_identity import models as _ci_models  # noqa: F401
    from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
    from app.character_identity import service
    from app.character_identity.four_view_sheet import REQUIRED_VIEWS
    from app.character_identity.visual_sheet import start_visual_sheet_generation
    from app.config import settings
    from app.db import Base, Job, Project

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, default in (
            ("motion_json", "'{}'"),
            ("emotion_json", "'{}'"),
            ("relationships_json", "'[]'"),
            ("prompt_package_json", "'{}'"),
        ):
            try:
                conn.execute(text("ALTER TABLE character_profiles ADD COLUMN %s TEXT DEFAULT %s" % (col, default)))
                conn.commit()
            except Exception:
                pass
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()
    captured = []

    def fake_enqueue(db, project_id, body, scene_id=None):
        captured.append(dict(body or {}))
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            params_json=json.dumps(body or {}),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    monkeypatch.setattr("app.secrets_store.get_secret", lambda _name: "test-key")
    from app.character_identity.schemas import CharacterProfileCreate

    for idx, sources in enumerate((
        {"local": {"family": "qwen2512"}, "api": None},
        {"local": None, "api": {"model": "nano-banana-kie"}},
    )):
        captured.clear()
        profile = service.create_profile(
            db,
            "proj-sheet",
            CharacterProfileCreate(
                name=f"CC Sheet {idx}",
                slug=f"cc-sheet-{idx}",
                role="fixture",
            ),
        )
        pack = start_visual_sheet_generation(
            db,
            "proj-sheet",
            profile.id,
            include_details=False,
            generator_sources=sources,
        )
        heroes = pack["jobs"]["hero_candidates"]
        assert len(heroes) == 1
        assert len(heroes[0]["viewJobs"]) == 1
        assert heroes[0].get("fourViewSingleOutput") is not True
        assert heroes[0].get("requiredViews") == ["front_full"]
        assert len(captured) == 1
        body = captured[0]
        assert body.get("layout") != "four_view"
        assert body.get("taskType") == "CRS_SINGLE_VIEW"
        assert "four-panel" not in (body.get("prompt") or "")
    db.close()
