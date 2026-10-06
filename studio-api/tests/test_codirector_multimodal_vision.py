"""Co-Director multimodal vision — resolver, pixels on foundation path, honest errors."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.character_identity import ensure_character_identity_tables
from app.character_identity.crs_service import persist_crs_in_session
from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate, ReferenceAttach
from app.character_identity.service import attach_reference, create_profile
from app.character_identity.visual_context import resolve_character_visual_asset_id
from app.codirector.conversation.foundation.response_generation import (
    build_generation_messages,
    _trim_messages_to_budget,
)
from app.codirector.conversation.foundation.schemas import (
    ConversationState,
    DialoguePlan,
    IntentAnalysis,
)
from app.codirector.errors import VISION_UNAVAILABLE, CoDirectorError
from app.codirector.providers.base import ChatRequest, ProviderModel
from app.codirector.service import _prepare_foundation_request
from app.codirector.vision_input import (
    VisionLoadError,
    copy_images_onto_last_user,
    encode_ollama_images,
    is_visual_inspection_turn,
    load_vision_image,
    vision_unavailable,
)
from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.spatial_map.camera_shot_packet import _identity_for_character


def _apply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import fields as dataclass_fields

    import app.feature_flags as ff

    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture()
def db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Session:
    _apply_flags(monkeypatch)
    init_db()
    ensure_character_identity_tables()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _png(path: Path, color: tuple[int, int, int] = (220, 40, 40)) -> Path:
    img = Image.new("RGB", (48, 32), color)
    img.save(path, format="PNG")
    return path


def _project(db: Session) -> str:
    pid = f"vis-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name="Vision Fixture"))
    db.commit()
    return pid


def _character(db: Session, project_id: str, name: str = "Korri") -> str:
    profile = create_profile(
        db,
        project_id,
        CharacterProfileCreate(
            name=name,
            slug=name.lower(),
            role="lead",
            visual_description="A generic anime heroine with red hair.",
        ),
    )
    return profile.id


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


def test_visual_inspection_turn_detects_open_visual_question():
    assert is_visual_inspection_turn(
        "Describe Korri's visible hairstyle, eyes, ears, clothing, footwear, and major markings from her current reference."
    )
    assert is_visual_inspection_turn("What do you see in this image?")
    assert is_visual_inspection_turn(
        "I would like to see the created image more like what you see attached through GPT Image 2."
    )
    assert is_visual_inspection_turn("Use this as the visual reference.")
    assert is_visual_inspection_turn("Which one is darker and more industrial?")
    assert not is_visual_inspection_turn("What is the logline for Schnick Coffee?")
    assert not is_visual_inspection_turn("Create a character reference sheet.")
    assert not is_visual_inspection_turn("Create Korri's CRS.")


def test_resolver_prefers_crs_sheet_over_draft_reference(db: Session, tmp_path: Path):
    project_id = _project(db)
    character_id = _character(db, project_id)
    draft = _image_asset(db, project_id, _png(tmp_path / "draft.png", (10, 10, 200)), "draft-ref")
    sheet = _image_asset(db, project_id, _png(tmp_path / "sheet.png", (200, 10, 10)), "crs-sheet")
    attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(asset_id=draft, reference_role="reference_image", approval_status="draft"),
    )
    profile = db.get(CharacterProfileRow, character_id)
    persist_crs_in_session(db, profile, asset_id=sheet)
    db.commit()

    resolved = resolve_character_visual_asset_id(db, project_id, character_id)
    assert resolved == sheet


def test_resolver_falls_back_to_reference_image(db: Session, tmp_path: Path):
    project_id = _project(db)
    character_id = _character(db, project_id, "Anadriya")
    ref = _image_asset(db, project_id, _png(tmp_path / "ref.png"), "ref")
    attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(asset_id=ref, reference_role="reference_image"),
    )
    assert resolve_character_visual_asset_id(db, project_id, character_id) == ref


def test_character_switch_invalidates_old_visual_asset(db: Session, tmp_path: Path):
    project_id = _project(db)
    a = _character(db, project_id, "Korri")
    b = _character(db, project_id, "Anadriya")
    a_img = _image_asset(db, project_id, _png(tmp_path / "a.png", (255, 0, 0)), "a")
    b_img = _image_asset(db, project_id, _png(tmp_path / "b.png", (0, 0, 255)), "b")
    attach_reference(db, project_id, a, ReferenceAttach(asset_id=a_img, reference_role="reference_image"))
    attach_reference(db, project_id, b, ReferenceAttach(asset_id=b_img, reference_role="reference_image"))
    assert resolve_character_visual_asset_id(db, project_id, a) == a_img
    assert resolve_character_visual_asset_id(db, project_id, b) == b_img
    assert resolve_character_visual_asset_id(db, project_id, a) != b_img


def test_character_visual_asset_is_id_not_description(db: Session, tmp_path: Path):
    project_id = _project(db)
    character_id = _character(db, project_id)
    ref = _image_asset(db, project_id, _png(tmp_path / "ctx.png"), "ctx")
    attach_reference(db, project_id, character_id, ReferenceAttach(asset_id=ref, reference_role="reference_image"))
    resolved = resolve_character_visual_asset_id(db, project_id, character_id)
    assert resolved == ref


def test_direct_attachment_loads_jpeg_bytes(db: Session, tmp_path: Path):
    project_id = _project(db)
    asset_id = _image_asset(db, project_id, _png(tmp_path / "up.png", (12, 200, 12)), "upload")
    loaded = load_vision_image(db, asset_id, project_id=project_id)
    assert loaded.mime == "image/jpeg"
    assert loaded.jpeg_bytes[:2] == b"\xff\xd8"
    assert loaded.width > 0 and loaded.height > 0
    encoded = encode_ollama_images([loaded])
    assert encoded and len(encoded[0]) > 32


def test_missing_and_invalid_image_raise(db: Session, tmp_path: Path):
    project_id = _project(db)
    missing = str(uuid.uuid4())
    db.add(
        Asset(
            id=missing,
            project_id=project_id,
            tag="gone",
            kind="image",
            filename="gone.png",
            path=str(tmp_path / "does-not-exist.png"),
        )
    )
    db.commit()
    with pytest.raises(VisionLoadError):
        load_vision_image(db, missing, project_id=project_id)
    with pytest.raises(VisionLoadError):
        load_vision_image(db, "no-such-asset", project_id=project_id)
    err = vision_unavailable("the picture file could not be found.")
    assert err.code == VISION_UNAVAILABLE
    assert err.message.startswith("Vision input failed:")


def test_foundation_rebuild_keeps_images_on_last_user():
    long = "Describe the visible outfit arrangement and marking placement. " * 20
    recent = [{"role": "user", "content": long, "images": ["AAA", "BBB"]}]
    msgs = build_generation_messages(
        user_message=long,
        intent=IntentAnalysis(user_goal_summary="describe the reference"),
        plan=DialoguePlan(),
        state=ConversationState(),
        context_block="",
        project_title="Schnick Coffee",
        recent_messages=recent,
        max_context_tokens=2800,
    )
    last = msgs[-1]
    assert last["role"] == "user"
    assert last.get("images") == ["AAA", "BBB"]
    assert last["content"] == long


def test_trim_does_not_drop_only_image_user_turn():
    msgs = [
        {"role": "system", "content": "x" * 4000},
        {"role": "user", "content": "look at this", "images": ["IMG"]},
    ]
    trimmed = _trim_messages_to_budget(msgs, max_tokens=200)
    assert any(m.get("images") for m in trimmed if m.get("role") == "user")


def test_prepare_foundation_request_copies_images_from_chat_request():
    class _Prov:
        timeout_sec = 600.0

    chat = ChatRequest(
        request_id="r1",
        messages=[{"role": "user", "content": "hi", "images": ["PIXELS"]}],
        model_id="qwen3.6:35b-a3b",
        vision_trace={"hasImages": True, "imageCount": 1},
    )
    request, _timeout = _prepare_foundation_request(
        provider=_Prov(),
        chat_request=chat,
        generation_messages=[{"role": "user", "content": "hi"}],
    )
    assert request.messages[-1].get("images") == ["PIXELS"]
    assert request.vision_trace and request.vision_trace["hasImages"] is True


def test_copy_images_onto_repair_messages():
    dest = [{"role": "system", "content": "sys"}, {"role": "user", "content": "rewrite"}]
    src = [{"role": "user", "content": "original", "images": ["KEEP"]}]
    out = copy_images_onto_last_user(dest, src)
    assert out[-1]["images"] == ["KEEP"]


def test_non_vision_model_helper_returns_false():
    from app.codirector.providers.ollama import OllamaProvider
    from app.codirector.providers.base import ProviderHealthResult

    provider = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3-coder:30b")
    health = ProviderHealthResult(
        provider_id="ollama",
        display_name="Ollama",
        status="Ready",
        reachable=True,
        endpoint="http://127.0.0.1:11434",
        selected_model="qwen3-coder:30b",
        model_available=True,
        models=[
            ProviderModel(id="qwen3-coder:30b", name="qwen3-coder:30b", capabilities=["completion", "tools"]),
            ProviderModel(id="qwen3.6:35b-a3b", name="qwen3.6:35b-a3b", capabilities=["vision", "completion"]),
        ],
    )
    assert provider.model_supports_vision("qwen3-coder:30b", health) is False
    assert provider.model_supports_vision("qwen3.6:35b-a3b", health) is True


def test_ollama_vision_request_uses_larger_num_ctx():
    from app.codirector.providers.ollama import OllamaProvider

    provider = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3.6:35b-a3b")
    text_only = ChatRequest(
        request_id="ctx-text",
        messages=[{"role": "user", "content": "hello"}],
        model_id="qwen3.6:35b-a3b",
    )
    with_image = ChatRequest(
        request_id="ctx-vision",
        messages=[{"role": "user", "content": "Describe the outfit.", "images": ["abc123"]}],
        model_id="qwen3.6:35b-a3b",
    )
    assert provider._chat_options(text_only)["num_ctx"] == 2048
    assert provider._chat_options(with_image)["num_ctx"] >= 8192


def test_mini_identity_uses_same_visual_resolver(db: Session, tmp_path: Path):
    project_id = _project(db)
    character_id = _character(db, project_id)
    sheet = _image_asset(db, project_id, _png(tmp_path / "mini.png"), "mini-crs")
    draft = _image_asset(db, project_id, _png(tmp_path / "mini-draft.png", (1, 2, 3)), "mini-draft")
    attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(asset_id=draft, reference_role="reference_image"),
    )
    persist_crs_in_session(db, db.get(CharacterProfileRow, character_id), asset_id=sheet)
    db.commit()
    resolved = resolve_character_visual_asset_id(db, project_id, character_id)
    identity = _identity_for_character(db, project_id, character_id)
    assert resolved == sheet
    assert identity["approvedAssetId"] == resolved


def test_prepare_chat_request_runs_fal_vision_on_attachment(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.codirector.service import _prepare_chat_request

    project_id = _project(db)
    character_id = _character(db, project_id)
    asset_id = _image_asset(db, project_id, _png(tmp_path / "prep.png"), "prep")
    attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(asset_id=asset_id, reference_role="reference_image"),
    )

    async def _fake_vision(*, instructions: str, image_paths=None, **_kwargs):
        assert image_paths
        return {
            "ok": True,
            "provider": "fal",
            "model": "google/gemini-2.5-flash-lite",
            "output": "Cool industrial corridor, sodium lighting, steel and concrete.",
        }

    monkeypatch.setattr("app.codirector.vision.vision_review.chat_vision", _fake_vision)

    async def _run():
        return await _prepare_chat_request(
            db,
            messages=[{"role": "user", "content": "What do you see in this image?"}],
            project_id=project_id,
            scene_id=None,
            mode="chat",
            model="qwen3.6:35b-a3b",
            provider_id="ollama",
            request_id="vision-ok",
            attachment_ids=[asset_id],
            character_id=character_id,
        )

    _provider, chat_request, _manifest = asyncio.run(_run())
    system = next(m for m in chat_request.messages if m.get("role") == "system")
    assert "VISION FACTS" in system["content"]
    assert "industrial corridor" in system["content"]
    assert "was not performed" not in system["content"].lower()
    assert "not automatically run" not in system["content"].lower()
    assert chat_request.vision_trace
    assert chat_request.vision_trace["hasImages"] is True
    assert asset_id in (chat_request.vision_trace.get("assetIds") or [])
    assert chat_request.vision_turn.ok is True


def test_prepare_chat_request_reports_missing_image_honestly(db: Session, monkeypatch: pytest.MonkeyPatch):
    from app.codirector.service import _prepare_chat_request

    project_id = _project(db)
    character_id = _character(db, project_id)

    async def _run():
        return await _prepare_chat_request(
            db,
            messages=[{"role": "user", "content": "Describe the visible clothing and markings in this image."}],
            project_id=project_id,
            scene_id=None,
            mode="chat",
            model="qwen3.6:35b-a3b",
            provider_id="ollama",
            request_id="vision-missing",
            attachment_ids=["missing-asset"],
            character_id=character_id,
        )

    _provider, chat_request, _manifest = asyncio.run(_run())
    system = next(m for m in chat_request.messages if m.get("role") == "system")
    assert "I couldn't read that image because" in system["content"]
    assert "was not performed" not in system["content"].lower()
    assert chat_request.vision_turn.ok is False
