"""G2+G5: CRS_GENERATION enqueues law views, not one four-panel job."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.character_identity import models as _ci_models  # noqa: F401
from app.asset_graph import AssetEdge as _AssetEdge  # noqa: F401
from app.character_identity import service
from app.character_identity.four_view_sheet import REQUIRED_VIEWS
from app.character_identity.visual_sheet import (
    CANDIDATE_SHEET_VIEW_ROLES,
    LAW_VIEW_SINGLE_FIGURE_RULES,
    QWEN_REF_WORKFLOW_KEY,
    _candidate_view_specs,
    crs_2k_view_pixels,
    start_visual_sheet_generation,
)
from app.config import settings
from app.db import Base, Job, Project
from app.image_product.compile import prompt_purpose_for_expand
from app.image_product.prompt_intel import expand_prompt


LAW_ROLES = (
    "hero_identity",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)


def _session(tmp_path, monkeypatch):
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
    db = Session()
    db.add(Project(id="proj-sheet", name="Sheet Test"))
    db.commit()
    return db


def test_crs_start_plans_four_views_not_five_view_or_one_panel(tmp_path, monkeypatch):
    db = _session(tmp_path, monkeypatch)
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
        include_performance=False,
        generator_sources={"local": {"model": "qwen2512"}, "api": None},
    )
    hero = pack["jobs"]["hero"]
    views = hero["viewJobs"]
    assert len(views) == 4
    assert [v["role"] for v in views] == list(LAW_ROLES)
    assert list(CANDIDATE_SHEET_VIEW_ROLES) == list(LAW_ROLES)
    assert [s[0] for s in _candidate_view_specs()] == list(LAW_ROLES)
    assert "full_body_three_quarter" not in REQUIRED_VIEWS
    assert hero.get("fourViewSingleOutput") is not True
    assert hero.get("layout") == "four_view"
    assert len(captured) == 4

    vw, vh = crs_2k_view_pixels()
    assert max(vw, vh) >= 2048

    for body in captured:
        blob = json.dumps(body)
        assert QWEN_REF_WORKFLOW_KEY not in blob
        assert body.get("forceWorkflowKey") != QWEN_REF_WORKFLOW_KEY
        assert (body.get("creativeContext") or {}).get("workflowKey") != QWEN_REF_WORKFLOW_KEY
        assert body.get("taskType") == "CRS_SINGLE_VIEW"
        assert body.get("fourViewSingleOutput") is not True
        assert body.get("layout") != "four_view"
        assert max(int(body["width"]), int(body["height"])) >= 2048
        prompt = str(body.get("prompt") or "")
        negative = str(body.get("negative_prompt") or body.get("negativePrompt") or "")
        blob = f"{prompt}\n{negative}".lower()
        _assert_crs_law_view_prompt_clean(blob)
        assert "qwen2512.ref" not in blob
        assert body.get("useExpandedPrompt") is False
        expanded = expand_prompt(
            prompt,
            purpose=prompt_purpose_for_expand(body, str(body.get("purpose") or "")),
        )["expandedPrompt"].lower()
        assert "character sheet" not in expanded
        assert "purpose: character sheet" not in expanded

    roles = [str(b.get("viewRole") or b.get("role")) for b in captured]
    assert "full_body_three_quarter_front" not in roles
    assert roles == list(LAW_ROLES)
    db.close()


FORBIDDEN_CRS_VIEW_PROMPT_TERMS = (
    "four-view",
    "four-panel",
    "character sheet",
    "turnaround",
    "collage",
    "multiple views",
)

REQUIRED_CRS_VIEW_SINGLE_FIGURE = (
    "one person only",
    "one figure",
    "no other people",
    "no grid",
    "no collage",
    "no turnaround sheet",
    "no multiple poses in one image",
)


def _assert_crs_law_view_prompt_clean(blob: str) -> None:
    """Required anti-collage tokens present; leftover sheet-layout wording gone."""
    low = str(blob or "").lower()
    for token in REQUIRED_CRS_VIEW_SINGLE_FIGURE:
        assert token in low, f"missing required law-view token {token!r}"
    for token in LAW_VIEW_SINGLE_FIGURE_RULES:
        assert token.lower() in low, f"missing law-view negative {token!r}"
    scrubbed = low
    for token in REQUIRED_CRS_VIEW_SINGLE_FIGURE:
        scrubbed = scrubbed.replace(token, " ")
    for term in FORBIDDEN_CRS_VIEW_PROMPT_TERMS:
        assert term not in scrubbed, f"forbidden sheet-layout term {term!r} remains"

VIEW_NAME_TOKENS = {
    "hero_identity": ("FRONT", "front-facing"),
    "full_body_three_quarter_front": ("THREE-QUARTER", "3/4"),
    "full_body_side_left": ("SIDE", "side-profile"),
    "full_body_back": ("BACK", "back-facing"),
    "closeup_front": ("CLOSE-UP", "close-up"),
}


def test_planned_crs_view_prompts_are_one_camera_not_four_view():
    """CRS law views: one camera each. Adept composes the labeled 3x2 sheet."""
    from app.character_identity.visual_sheet import (
        PROFILE_GUIDED_VIEW_INSTRUCTIONS,
        _candidate_view_specs,
        _compile_visual_prompt,
        _negative_rules_for_view,
    )

    profile = {"name": "TestChar", "species": "human"}
    planned = []
    for role, goal, comp, neg in _candidate_view_specs():
        pkg = _compile_visual_prompt(
            profile,
            prompt_goal=goal,
            composition=dict(comp),
            references=[],
            role=role,
            extra_negative_constraints=_negative_rules_for_view(role, neg),
            sheet_request={},
        )
        instruction = PROFILE_GUIDED_VIEW_INSTRUCTIONS[role]
        assert instruction in pkg.prompt
        assert "one camera only" in pkg.prompt
        assert "this view only" in pkg.prompt
        for token in VIEW_NAME_TOKENS[role]:
            assert token.lower() in pkg.prompt.lower()
        combined = f"{pkg.prompt}\n{pkg.negative_prompt}".lower()
        _assert_crs_law_view_prompt_clean(combined)
        leftover = {
            "taskType": "CRS_GENERATION",
            "purpose": "character_sheet",
            "layout": "law_views",
            "fourViewSingleOutput": False,
            "prompt": pkg.prompt,
        }
        live = expand_prompt(
            pkg.prompt,
            purpose=prompt_purpose_for_expand(leftover, "character_sheet"),
        )["expandedPrompt"].lower()
        assert "character sheet" not in live, f"{role} live expand leaked character sheet"
        planned.append((role, pkg.prompt))
    assert [role for role, _ in planned] == list(LAW_ROLES)


def test_crs_law_view_live_expand_omits_character_sheet_purpose():
    leftover = {
        "taskType": "CRS_GENERATION",
        "purpose": "character_sheet",
        "layout": "law_views",
        "fourViewSingleOutput": False,
        "creativeContext": {"taskType": "CRS_GENERATION", "layout": "law_views"},
    }
    purpose = prompt_purpose_for_expand(leftover, "character_sheet")
    assert purpose == ""
    expanded = expand_prompt("compiled single-camera prompt", purpose=purpose)["expandedPrompt"]
    assert "character sheet" not in expanded.lower()
    assert "purpose: character sheet" not in expanded.lower()

    four = {
        "layout": "four_view",
        "purpose": "character_sheet",
        "fourViewSingleOutput": True,
    }
    four_purpose = prompt_purpose_for_expand(four, "character_sheet")
    assert four_purpose == "character_sheet"
    four_expanded = expand_prompt("hosted four panel", purpose=four_purpose)["expandedPrompt"]
    assert "purpose: character sheet" in four_expanded.lower()
