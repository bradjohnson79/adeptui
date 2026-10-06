"""Co-Director chat vision intake — fal pixels, no false capability denial."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.codirector.context_enrichment import attachment_context_block
from app.codirector.generation_memory.contracts import CanonicalGenerationRequest
from app.codirector.generation_memory.inherit import apply_typed_inheritance
from app.codirector.vision.turn import (
    IMAGE_RESOLVE_FAILED,
    VISION_READY,
    collect_image_asset_ids,
    infer_reference_role,
    is_visual_reference_generation_turn,
    needs_chat_vision,
    run_chat_vision_turn,
)
from app.codirector.vision_input import VisionLoadError, load_vision_image
from app.db import Asset, Project, SessionLocal, init_db


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _png(path: Path, color: tuple[int, int, int] = (40, 40, 40)) -> Path:
    Image.new("RGB", (64, 48), color).save(path, format="PNG")
    return path


def _project(db: Session, name: str = "Vision Proj") -> str:
    pid = f"vis-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _image_asset(db: Session, project_id: str, path: Path, tag: str) -> str:
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=path.name,
            path=str(path),
        )
    )
    db.commit()
    return aid


def test_live_utterance_needs_vision_and_is_style_reference():
    text = "I would like to see the created image more like what you see attached through GPT Image 2."
    assert needs_chat_vision(text, ["asset-1"]) is True
    assert is_visual_reference_generation_turn(text) is True
    assert infer_reference_role(text) == "visual_environment_style"


def test_attachment_label_is_not_pixels():
    label = "[Attached: Venture Corridor scene.png]"
    assert "Venture Corridor" in label
    assert needs_chat_vision("thanks", []) is False


def test_wrong_project_asset_fails_closed(db: Session, tmp_path: Path):
    proj_a = _project(db, "A")
    proj_b = _project(db, "B")
    asset_id = _image_asset(db, proj_a, _png(tmp_path / "a.png"), "secret")
    with pytest.raises(VisionLoadError) as caught:
        load_vision_image(db, asset_id, project_id=proj_b)
    assert "not part of this project" in caught.value.reason


def test_run_chat_vision_turn_sends_pixels_to_fal(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_id = _project(db)
    asset_id = _image_asset(db, project_id, _png(tmp_path / "vent.png", (20, 20, 20)), "Venture Corridor scene.png")
    seen: dict[str, object] = {}

    async def _fake_vision(*, instructions: str, image_paths=None, **_kwargs):
        seen["instructions"] = instructions
        seen["paths"] = [str(p) for p in (image_paths or [])]
        assert image_paths
        assert Path(image_paths[0]).is_file()
        assert Path(image_paths[0]).stat().st_size > 32
        return {
            "ok": True,
            "provider": "fal",
            "model": "google/gemini-2.5-flash-lite",
            "output": "Dim sodium lighting, dense industrial pipes, worn steel, deep perspective corridor.",
        }

    monkeypatch.setattr("app.codirector.vision.vision_review.chat_vision", _fake_vision)
    turn = asyncio.run(
        run_chat_vision_turn(
            db,
            project_id=project_id,
            attachment_ids=[asset_id],
            user_text="What do you see in this image?",
        )
    )
    assert turn.ok is True
    assert turn.status == VISION_READY
    assert turn.provider == "fal"
    assert "sodium lighting" in turn.facts
    assert "VISION FACTS" in turn.context_block
    assert "was not performed" not in turn.context_block.lower()
    assert "not automatically run" not in turn.context_block.lower()
    assert turn.vision_trace["hasImages"] is True
    assert seen["paths"]


def test_run_chat_vision_turn_wrong_project_honest(db: Session, tmp_path: Path):
    proj_a = _project(db, "A")
    proj_b = _project(db, "B")
    asset_id = _image_asset(db, proj_a, _png(tmp_path / "x.png"), "x")
    turn = asyncio.run(
        run_chat_vision_turn(
            db,
            project_id=proj_b,
            attachment_ids=[asset_id],
            user_text="What do you see?",
        )
    )
    assert turn.ok is False
    assert turn.status == IMAGE_RESOLVE_FAILED
    assert "couldn't read that image because" in turn.creator_failure.lower()
    assert "not part of this project" in turn.error
    assert "do not invent image contents" in turn.context_block.lower()


def test_run_chat_vision_turn_compares_two_images(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_id = _project(db)
    dark = _image_asset(db, project_id, _png(tmp_path / "dark.png", (10, 10, 10)), "dark")
    light = _image_asset(db, project_id, _png(tmp_path / "light.png", (220, 220, 220)), "light")
    seen: dict[str, object] = {}

    async def _fake_vision(*, instructions: str, image_paths=None, **_kwargs):
        seen["count"] = len(list(image_paths or []))
        return {
            "ok": True,
            "provider": "fal",
            "model": "google/gemini-2.5-flash-lite",
            "output": "Image 1 is darker and more industrial than image 2.",
        }

    monkeypatch.setattr("app.codirector.vision.vision_review.chat_vision", _fake_vision)
    turn = asyncio.run(
        run_chat_vision_turn(
            db,
            project_id=project_id,
            attachment_ids=[dark, light],
            user_text="Which one is darker and more industrial?",
        )
    )
    assert turn.ok is True
    assert seen["count"] == 2
    assert "darker" in turn.facts


def test_attachment_context_includes_vision_facts_not_denial(db: Session, tmp_path: Path):
    project_id = _project(db)
    asset_id = _image_asset(db, project_id, _png(tmp_path / "v.png"), "Venture Corridor scene.png")
    block = attachment_context_block(
        db,
        project_id=project_id,
        attachment_ids=[asset_id],
        vision_block="=== VISION FACTS (pixels were read by Adept vision) ===\nWorn steel corridor.",
    )
    assert "Venture Corridor" in block
    assert "VISION FACTS" in block
    assert "not automatically run" not in block.lower()
    assert "was not performed" not in block.lower()


def test_generation_memory_inherits_vision_facts_and_reference():
    prior = CanonicalGenerationRequest(
        requestId="r1",
        projectId="p1",
        originalUserInstructions="more like the attached",
        referenceAssetIds=["asset-vent"],
        visionFacts="Sodium lighting, industrial density.",
        referenceRole="visual_environment_style",
    )
    nxt, audit = apply_typed_inheritance(prior, overrides={}, project_id="p1")
    assert nxt.referenceAssetIds == ["asset-vent"]
    assert nxt.visionFacts == "Sodium lighting, industrial density."
    assert nxt.referenceRole == "visual_environment_style"
    assert "referenceAssetIds" in audit.inherited
    assert "visionFacts" in audit.inherited


def test_collect_ids_prefers_current_attachments(db: Session):
    ids = collect_image_asset_ids(
        db,
        "proj",
        attachment_ids=["a1"],
        messages=[{"role": "user", "content": "hi", "attachment_ids": ["old"]}],
        user_text="hi",
    )
    assert ids == ["a1"]


def test_collect_ids_does_not_steal_older_attach_on_fresh_generate(db: Session):
    ids = collect_image_asset_ids(
        db,
        "proj",
        attachment_ids=[],
        messages=[
            {
                "role": "user",
                "content": "What do you see?",
                "attachment_ids": ["5567e90b-8038-4484-a394-ec5b3b9ac2eb"],
            },
            {"role": "assistant", "content": "Two figures holding hands."},
            {"role": "user", "content": "Generate a new image of the Venture corridor with Flux."},
        ],
        user_text="Generate a new image of the Venture corridor with Flux.",
    )
    assert ids == []


def test_collect_ids_reuses_prior_attach_when_creator_refers_back(db: Session):
    ids = collect_image_asset_ids(
        db,
        "proj",
        attachment_ids=[],
        messages=[
            {
                "role": "user",
                "content": "What do you see?",
                "attachment_ids": ["5567e90b-8038-4484-a394-ec5b3b9ac2eb"],
            },
            {"role": "assistant", "content": "Two figures holding hands."},
            {"role": "user", "content": "Make it more like this."},
        ],
        user_text="Make it more like this.",
    )
    assert ids == ["5567e90b-8038-4484-a394-ec5b3b9ac2eb"]
