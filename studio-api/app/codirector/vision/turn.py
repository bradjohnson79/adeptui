"""Co-Director chat-turn vision — reuse load_vision_image + chat_vision.

Not a second provider. Fal-only via vision_review.chat_vision.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..vision_input import (
    LoadedVisionImage,
    VisionLoadError,
    build_vision_trace,
    is_visual_inspection_turn,
    load_vision_image,
)

VISION_READY = "Vision Ready"
VISION_PROVIDER_UNAVAILABLE = "Vision Provider Unavailable"
IMAGE_RESOLVE_FAILED = "Image Resolve Failed"
UNSUPPORTED_IMAGE_TYPE = "Unsupported Image Type"

_REFERENCE_REUSE_RE = re.compile(
    r"\b(?:"
    r"same (?:visual )?reference|that same reference|the same reference|"
    r"use that (?:same )?(?:visual )?reference|use the (?:same )?(?:attached|reference)|"
    r"that (?:attached|reference)(?: image)? again|the attached(?: image)? again|"
    r"those (?:same )?images?|the (?:previous|last) (?:attached )?image"
    r")\b",
    re.I,
)

_COMPARE_RE = re.compile(
    r"\b(?:"
    r"which (?:one|image|picture)|compare|darker|more industrial|"
    r"side by side|difference between"
    r")\b",
    re.I,
)

_VISUAL_REFERENCE_GEN_RE = re.compile(
    r"(?:"
    r"more like what you see attached|more like (?:this|the attached|what you see)|"
    r"look(?:s)? more like|match(?:es)? the (?:lighting|style|materials|visual)|"
    r"use this as (?:the )?(?:visual |style |environment )?reference|"
    r"visual (?:style )?reference|what you see attached|"
    r"created image more like|like (?:the |this )?(?:attached|reference)"
    r")",
    re.I,
)

_CHARACTER_ROLE_RE = re.compile(
    r"\b(?:character reference|identity reference|her face|his face|who they are)\b",
    re.I,
)
_FIRST_FRAME_ROLE_RE = re.compile(r"\b(?:first frame|opening frame|start frame)\b", re.I)
_EDIT_ROLE_RE = re.compile(r"\b(?:edit this|change this image|from this (?:photo|image))\b", re.I)

_VISION_FACTS_INSTRUCTIONS = (
    "You are Adept Co-Director vision. You can see the attached image pixels. "
    "Return structured visual facts only — what is actually visible. "
    "Cover: lighting, palette, architecture, materials, composition, perspective, "
    "atmosphere, style, surface wear, key forms, visual motifs. "
    "Be specific and concrete. Do not invent unseen content. "
    "Do not ask the creator to describe the image. "
    "If more than one image is attached, compare them directly."
)


@dataclass
class ChatVisionTurn:
    status: str = VISION_READY
    ok: bool = False
    facts: str = ""
    role: str = ""
    asset_ids: list[str] = field(default_factory=list)
    loaded: list[LoadedVisionImage] = field(default_factory=list)
    provider: str = "fal"
    model: str = ""
    error: str = ""
    reason_code: str = ""
    context_block: str = ""
    creator_failure: str = ""
    vision_trace: dict[str, Any] = field(default_factory=dict)


def refers_to_prior_visual(text: str | None) -> bool:
    raw = text or ""
    return bool(_REFERENCE_REUSE_RE.search(raw)) or bool(
        re.search(r"\b(?:this|the|that) (?:attached )?(?:image|picture|photo|reference)\b", raw, re.I)
    )


def is_visual_compare_turn(text: str | None) -> bool:
    return bool(_COMPARE_RE.search(text or ""))


def is_visual_reference_generation_turn(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_VISUAL_REFERENCE_GEN_RE.search(raw))


def needs_chat_vision(text: str | None, attachment_ids: list[str] | None) -> bool:
    ids = [str(v).strip() for v in (attachment_ids or []) if str(v).strip()]
    if ids:
        return True
    raw = text or ""
    return (
        is_visual_inspection_turn(raw)
        or is_visual_reference_generation_turn(raw)
        or is_visual_compare_turn(raw)
        or refers_to_prior_visual(raw)
    )


def infer_reference_role(text: str | None) -> str:
    raw = text or ""
    if _CHARACTER_ROLE_RE.search(raw):
        return "character"
    if _FIRST_FRAME_ROLE_RE.search(raw):
        return "first_frame"
    if _EDIT_ROLE_RE.search(raw):
        return "edit_source"
    if is_visual_reference_generation_turn(raw) or refers_to_prior_visual(raw):
        return "visual_environment_style"
    if is_visual_inspection_turn(raw) or is_visual_compare_turn(raw):
        return "inspection"
    return "visual_environment_style"


def collect_image_asset_ids(
    db: Any,
    project_id: str | None,
    *,
    attachment_ids: list[str] | None,
    messages: list[dict[str, Any]] | None = None,
    user_text: str = "",
) -> list[str]:
    seen: list[str] = []

    def _add(raw: Any) -> None:
        value = str(raw or "").strip()
        if value and value not in seen:
            seen.append(value)

    for value in attachment_ids or []:
        _add(value)
    if seen:
        return seen
    refer_back = refers_to_prior_visual(user_text) or is_visual_reference_generation_turn(user_text)
    for msg in reversed(list(messages or [])):
        if str(msg.get("role") or "") != "user":
            continue
        for value in msg.get("attachment_ids") or msg.get("attachmentIds") or []:
            _add(value)
        atts = msg.get("attachments") or []
        if isinstance(atts, list):
            for item in atts:
                if isinstance(item, dict):
                    _add(item.get("assetId") or item.get("asset_id"))
                else:
                    _add(item)
        # Fresh turns use only this-turn attachments. Older attaches stay
        # available when the creator refers back ("make it more like this").
        if seen or not refer_back:
            break
    if seen:
        return seen
    if not project_id or not refer_back:
        return []
    try:
        from sqlalchemy import select

        from ...db import CoDirectorConversationEvent
        from ..conversation_events import event_to_message

        rows = list(
            db.scalars(
                select(CoDirectorConversationEvent)
                .where(CoDirectorConversationEvent.project_id == project_id)
                .order_by(CoDirectorConversationEvent.sequence.desc())
                .limit(40)
            )
        )
        for row in rows:
            msg = event_to_message(row)
            if str(msg.get("role") or "") != "user":
                continue
            for value in msg.get("attachment_ids") or []:
                _add(value)
            if seen:
                return seen
    except Exception:
        pass
    try:
        from ..generation_memory.store import list_image_requests

        rows = list_image_requests(db, project_id)
        if rows:
            for value in rows[0][1].referenceAssetIds or []:
                _add(value)
    except Exception:
        pass
    return seen


def _status_for_load_error(err: VisionLoadError) -> str:
    reason = (err.reason or "").lower()
    if "not an image" in reason:
        return UNSUPPORTED_IMAGE_TYPE
    return IMAGE_RESOLVE_FAILED


def _status_for_provider_error(result: dict[str, Any]) -> str:
    blob = " ".join(
        str(result.get(key) or "")
        for key in ("error", "reason", "reason_code")
    ).lower()
    if "no_vlm" in blob or "no_fal" in blob or "not configured" in blob:
        return VISION_PROVIDER_UNAVAILABLE
    if "unreadable" in blob or "no_image" in blob:
        return IMAGE_RESOLVE_FAILED
    return VISION_PROVIDER_UNAVAILABLE


def _creator_failure(status: str, reason: str) -> str:
    clean = (reason or "the vision request failed").strip()
    if status == VISION_PROVIDER_UNAVAILABLE:
        return f"I couldn't read that image because the vision provider is unavailable ({clean})."
    if status == UNSUPPORTED_IMAGE_TYPE:
        return f"I couldn't read that image because it is not a supported image type ({clean})."
    if status == IMAGE_RESOLVE_FAILED:
        return f"I couldn't read that image because {clean}"
    return f"I couldn't read that image because {clean}"


def vision_facts_context_block(turn: ChatVisionTurn) -> str:
    if turn.ok and turn.facts.strip():
        names = ", ".join(turn.asset_ids[:8]) or "attached image"
        role = turn.role or "visual_environment_style"
        return "\n".join(
            [
                "=== VISION FACTS (pixels were read by Adept vision) ===",
                f"status: {VISION_READY}",
                f"provider: {turn.provider or 'fal'}",
                f"model: {turn.model or 'fal-ai/any-llm/vision'}",
                f"reference_role: {role}",
                f"asset_ids: {names}",
                "Adept resolved these project images and the vision layer inspected the pixels.",
                "You do not need filesystem access. You have visual understanding for this turn.",
                "Never say you cannot access file uploads, attachments, or external links.",
                "Do not ask the creator to describe lighting, style, materials, or other visible properties.",
                "Do not invent details beyond these facts.",
                "",
                turn.facts.strip(),
            ]
        )
    reason = turn.error or "the image could not be read"
    return "\n".join(
        [
            "=== VISION RESULT ===",
            f"status: {turn.status}",
            turn.creator_failure or _creator_failure(turn.status, reason),
            "Do not invent image contents.",
            "Do not claim Adept is a text-only assistant or that file uploads are unsupported.",
            "Vision is a core Co-Director capability; this turn failed for the reason above.",
        ]
    )


def _write_temp_jpegs(images: list[LoadedVisionImage]) -> list[Path]:
    temps: list[Path] = []
    for image in images:
        tmp = tempfile.NamedTemporaryFile(prefix="adept-cd-vision-", suffix=".jpg", delete=False)
        tmp.write(image.jpeg_bytes)
        tmp.close()
        temps.append(Path(tmp.name))
    return temps


async def run_chat_vision_turn(
    db: Any,
    *,
    project_id: str | None,
    attachment_ids: list[str],
    user_text: str = "",
) -> ChatVisionTurn:
    """Load project-scoped pixels and call canonical fal chat_vision."""

    from .vision_review import chat_vision

    ids = [str(v).strip() for v in (attachment_ids or []) if str(v).strip()]
    turn = ChatVisionTurn(role=infer_reference_role(user_text), asset_ids=list(ids))
    if not project_id:
        turn.status = IMAGE_RESOLVE_FAILED
        turn.error = "no project is open."
        turn.creator_failure = _creator_failure(turn.status, turn.error)
        turn.context_block = vision_facts_context_block(turn)
        turn.vision_trace = {"hasImages": False, "failed": True, "status": "failed", "error": turn.error}
        return turn
    if not ids:
        turn.status = IMAGE_RESOLVE_FAILED
        turn.error = "no image attachment could be resolved for this turn."
        turn.creator_failure = _creator_failure(turn.status, turn.error)
        turn.context_block = vision_facts_context_block(turn)
        turn.vision_trace = {"hasImages": False, "failed": True, "status": "failed", "error": turn.error}
        return turn

    loaded: list[LoadedVisionImage] = []
    try:
        for asset_id in ids[:8]:
            loaded.append(load_vision_image(db, asset_id, project_id=project_id, source="attachment"))
    except VisionLoadError as err:
        turn.status = _status_for_load_error(err)
        turn.error = err.reason
        turn.asset_ids = list(ids)
        turn.creator_failure = _creator_failure(turn.status, err.reason)
        turn.context_block = vision_facts_context_block(turn)
        turn.vision_trace = {
            "hasImages": False,
            "failed": True,
            "status": "failed",
            "error": err.reason,
            "assetIds": ids,
        }
        return turn

    turn.loaded = loaded
    turn.asset_ids = [item.asset_id for item in loaded]
    temps = _write_temp_jpegs(loaded)
    try:
        result = await chat_vision(
            instructions=_VISION_FACTS_INSTRUCTIONS + "\n\nCreator request:\n" + (user_text or "").strip(),
            image_paths=temps,
        )
    finally:
        for temp in temps:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    if not result.get("ok"):
        turn.status = _status_for_provider_error(result)
        turn.error = str(result.get("error") or result.get("reason") or "vision provider error")
        turn.provider = str(result.get("provider") or "fal")
        turn.model = str(result.get("model") or "")
        turn.creator_failure = _creator_failure(turn.status, turn.error)
        turn.context_block = vision_facts_context_block(turn)
        turn.vision_trace = {
            **build_vision_trace(loaded, model_id=turn.model),
            "hasImages": True,
            "failed": True,
            "status": "failed",
            "error": turn.error,
            "encodedCount": len(loaded),
        }
        return turn

    turn.ok = True
    turn.status = VISION_READY
    turn.facts = str(result.get("output") or "").strip()
    turn.provider = str(result.get("provider") or "fal")
    turn.model = str(result.get("model") or "")
    turn.context_block = vision_facts_context_block(turn)
    turn.vision_trace = {
        **build_vision_trace(loaded, model_id=turn.model),
        "hasImages": True,
        "failed": False,
        "status": "ok",
        "encodedCount": len(loaded),
        "provider": turn.provider,
        "factsChars": len(turn.facts),
    }
    return turn
