"""Co-Director generation ready notices — conversational completion append.

When a CD-linked execution reaches a genuine terminal state with a verified
Library asset (or fails/cancels), append exactly one user-facing assistant
message to the same project conversation. Dedupe is by stable message_id
(genrdy:{execution_id}), never by text. Law #39: no job/asset ids or raw
provider errors in the main chat sentence.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# plan_data keys (open bag — does not rename frozen ExecutionPlan fields)
LINK_KEY = "cdGenLink"
EMITTED_KEY = "cdGenReady"

# Stable message id prefix; full id must fit String(64).
MSG_ID_PREFIX = "genrdy:"

# Capabilities / surface → creator-facing media kind
_CAPABILITY_KIND: dict[str, str] = {
    "image.generate": "image",
    "image.edit": "image",
    "image.generate_batch": "image",
    "ers.generate": "image",
    "atlas.generate": "image",
    "scene.generate": "image",
    "storyboard.generate": "image",
    "character.generate_visual_sheet": "image",
    "video.generate": "video",
    "video.three_frame": "video",
    "timeline.generate_shot": "video",
    "timeline.prepare_scene": "video",
    "audio.sfx": "sfx",
    "sfx.generate": "sfx",
    "audio.ambience": "ambience",
    "ambience.generate": "ambience",
    "audio.music": "music",
    "music.generate": "music",
    "voice.generate": "voice",
    "audio.voice": "voice",
    "audio.tts": "voice",
}

_SURFACE_KIND: dict[str, str] = {
    "image_generation": "image",
    "storyboard_generation": "image",
    "ers_generation": "image",
    "scene_generation": "image",
    "atlas_shot_generation": "video",
    "voice_generation": "voice",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def media_kind_for_plan(plan: Any) -> str:
    """Resolve creator-facing media kind from capability / surface / plan_data."""
    pd = dict(getattr(plan, "plan_data", None) or {})
    explicit = str(pd.get("mediaKind") or pd.get("media_kind") or pd.get("modality") or "").strip().lower()
    if explicit in {"image", "video", "sfx", "ambience", "music", "voice", "audio"}:
        return "sfx" if explicit == "audio" else explicit
    cap = str(getattr(plan, "capability", "") or "").strip().lower()
    if cap in _CAPABILITY_KIND:
        return _CAPABILITY_KIND[cap]
    for key, kind in _CAPABILITY_KIND.items():
        if key.split(".")[-1] in cap or cap.endswith(key):
            return kind
    if "sfx" in cap:
        return "sfx"
    if "ambience" in cap or "ambient" in cap:
        return "ambience"
    if "music" in cap:
        return "music"
    if "voice" in cap or "tts" in cap:
        return "voice"
    if "video" in cap or "shot" in cap:
        return "video"
    surface = str(getattr(plan, "surface_type", "") or "").strip().lower()
    if surface in _SURFACE_KIND:
        return _SURFACE_KIND[surface]
    return "image"


def _voice_subject(plan: Any) -> str:
    pd = dict(getattr(plan, "plan_data", None) or {})
    for key in ("characterName", "character_name", "speakerName", "speaker_name", "voiceName", "voice_name"):
        raw = str(pd.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _possessive(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return ""
    if cleaned.lower().endswith("s"):
        return f"{cleaned}'"
    return f"{cleaned}'s"


def build_ready_copy(kind: str, *, subject: str = "") -> tuple[str, str]:
    """Return (sentence, action_label) for a ready notice. No ids."""
    if kind == "video":
        return "Your video is ready.", "View video"
    if kind == "sfx":
        return "Your sound effect is ready.", "Listen"
    if kind == "ambience":
        return "Your ambience is ready.", "Listen"
    if kind == "music":
        return "Your music cue is ready.", "Listen"
    if kind == "voice":
        if subject:
            return f"{_possessive(subject)} voice clip is ready.", "Listen"
        return "Your voice clip is ready.", "Listen"
    return "Your image is ready.", "View image"


def build_fail_copy(kind: str) -> tuple[str, str]:
    noun = {
        "image": "image",
        "video": "video",
        "sfx": "sound effect",
        "ambience": "ambience",
        "music": "music cue",
        "voice": "voice clip",
    }.get(kind, "generation")
    return f"The {noun} couldn't be completed.", "Details"


def build_cancel_copy(kind: str) -> str:
    noun = {
        "image": "image",
        "video": "video",
        "sfx": "sound effect",
        "ambience": "ambience",
        "music": "music cue",
        "voice": "voice clip",
    }.get(kind, "generation")
    return f"The {noun} generation was cancelled."


def notice_message_id(execution_id: str) -> str:
    eid = str(execution_id or "").strip()
    # Keep under 64 chars for the DB column.
    body = eid[: 64 - len(MSG_ID_PREFIX)]
    return f"{MSG_ID_PREFIX}{body}"


def stamp_generation_link(plan: Any, *, request_id: str | None = None) -> bool:
    """Persist conversation ↔ execution linkage on the pack (CD-started gens)."""
    if plan is None:
        return False
    pd = dict(getattr(plan, "plan_data", None) or {})
    if isinstance(pd.get(LINK_KEY), dict) and pd[LINK_KEY].get("linked"):
        # Refresh request id if newly available.
        rid = str(request_id or getattr(plan, "user_turn_id", None) or "").strip()
        if rid and not pd[LINK_KEY].get("requestId"):
            pd[LINK_KEY] = {**pd[LINK_KEY], "requestId": rid}
            plan.plan_data = pd
            return True
        return False
    rid = str(
        request_id
        or getattr(plan, "user_turn_id", None)
        or pd.get("requestId")
        or pd.get("request_id")
        or ""
    ).strip()
    pd[LINK_KEY] = {
        "linked": True,
        "requestId": rid or None,
        "linkedAt": _now_iso(),
        "v": 1,
    }
    plan.plan_data = pd
    return True


def is_cd_linked(plan: Any) -> bool:
    """True when this pack was started through Co-Director (or explicitly linked)."""
    if plan is None:
        return False
    pd = dict(getattr(plan, "plan_data", None) or {})
    link = pd.get(LINK_KEY)
    if isinstance(link, dict) and link.get("linked"):
        return True
    # CD classifier / user turn is sufficient linkage for packs created by dispatch.
    if str(getattr(plan, "user_turn_id", None) or "").strip():
        return True
    if str(getattr(plan, "classifier_source", "") or "").strip():
        return True
    return False


def _asset_accessible(db: Session, asset_id: str | None) -> bool:
    """Verified Library asset: row exists and path is present/readable when set."""
    if not asset_id:
        return False
    try:
        from ...db import Asset

        row = db.get(Asset, str(asset_id))
    except Exception:
        return False
    if row is None:
        return False
    path = str(getattr(row, "path", "") or "").strip()
    if not path:
        # Some Library registrations may resolve via id-only serving; row is enough.
        return True
    try:
        return os.path.isfile(path) or os.path.isdir(path)
    except Exception:
        return False


def _first_accessible_asset(db: Session, plan: Any) -> Optional[str]:
    candidates: list[str] = []
    for aid in list(getattr(plan, "result_asset_ids", None) or []):
        s = str(aid or "").strip()
        if s and s not in candidates:
            candidates.append(s)
    for child in list(getattr(plan, "child_jobs", None) or []):
        s = str(getattr(child, "asset_id", None) or "").strip()
        if s and s not in candidates:
            candidates.append(s)
    for aid in candidates:
        if _asset_accessible(db, aid):
            return aid
    return None


def _preview_kind_for(media_kind: str) -> str:
    if media_kind in {"sfx", "ambience", "music", "voice"}:
        return "audio"
    if media_kind == "video":
        return "video"
    return "image"


def _technical_blob(plan: Any) -> str | None:
    """Collapsed Details payload — never shown as the main chat sentence."""
    parts: list[str] = []
    err = str(getattr(plan, "error", "") or "").strip()
    if err:
        parts.append(err)
    for child in list(getattr(plan, "child_jobs", None) or []):
        cerr = str(getattr(child, "error", None) or "").strip()
        if cerr:
            parts.append(cerr)
    if not parts:
        return None
    # Bound size; keep provider detail behind Details only.
    blob = "\n".join(parts)
    return blob[:4000]


def _already_emitted(plan: Any) -> bool:
    pd = dict(getattr(plan, "plan_data", None) or {})
    emitted = pd.get(EMITTED_KEY)
    return isinstance(emitted, dict) and bool(emitted.get("messageId"))


def maybe_emit_generation_ready_notice(
    db: Session,
    project_id: str,
    plan: Any,
    *,
    previous_status: str | None = None,
) -> Optional[dict[str, Any]]:
    """Append one conversational ready/fail/cancel notice when newly terminal.

    Exactly-once via message_id dedupe + plan_data stamp. Skips historical
    already-terminal packs (no previous→terminal transition) unless a linked
    pack has never recorded a notice (recover path for crash mid-emit).
    """
    if not project_id or plan is None:
        return None
    execution_id = str(getattr(plan, "execution_id", "") or "").strip()
    if not execution_id:
        return None
    if not is_cd_linked(plan):
        return None
    if _already_emitted(plan):
        return dict((plan.plan_data or {}).get(EMITTED_KEY) or {})

    raw_status = getattr(plan, "status", "")
    status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
    if status not in {"completed", "failed", "cancelled"}:
        return None

    prev = str(previous_status or "").strip().lower()
    # Avoid flooding historical completed packs on first load / hydrate.
    # Allow emit when previous was non-terminal OR empty (fresh transition in
    # this advance call). When previous is already the same terminal status,
    # skip — hydrate of old packs hits advance early-return before this hook,
    # but cancel/fail re-entry is still guarded by _already_emitted + message_id.
    if prev in {"completed", "failed", "cancelled"} and prev == status:
        return None

    kind = media_kind_for_plan(plan)
    message_id = notice_message_id(execution_id)
    asset_id: Optional[str] = None
    action_label = ""
    technical: Optional[str] = None
    outcome = status

    if status == "cancelled":
        content = build_cancel_copy(kind)
        outcome = "cancelled"
    elif status == "failed":
        content, action_label = build_fail_copy(kind)
        technical = _technical_blob(plan)
        outcome = "failed"
    else:
        # completed — require verified accessible Library asset
        asset_id = _first_accessible_asset(db, plan)
        if not asset_id:
            content, action_label = build_fail_copy(kind)
            technical = _technical_blob(plan) or "The generation finished without a Library asset."
            outcome = "failed"
        else:
            content, action_label = build_ready_copy(kind, subject=_voice_subject(plan))
            outcome = "ready"

    # Bubble sentence stays conversational; the action label is a separate control
    # (View image / Listen / Details) so the UI does not double the same words.
    chat_content = content

    attachment: dict[str, Any] = {
        "kind": "generation_ready",
        "outcome": outcome,
        "modality": kind,
        "mediaKind": kind,
        "previewKind": _preview_kind_for(kind),
        "actionLabel": action_label or None,
        "executionId": execution_id,
        "name": action_label or content[:80],
    }
    if asset_id:
        attachment["assetId"] = asset_id
    if technical:
        attachment["technical"] = technical

    pd = dict(getattr(plan, "plan_data", None) or {})
    link = pd.get(LINK_KEY) if isinstance(pd.get(LINK_KEY), dict) else {}
    request_id = str(
        (link or {}).get("requestId")
        or getattr(plan, "user_turn_id", None)
        or ""
    ).strip() or None

    try:
        from ..conversation_events import EventInput, append_events

        batch = append_events(
            db,
            project_id,
            [
                EventInput(
                    role="assistant",
                    content=chat_content,
                    event_type="message",
                    message_id=message_id,
                    client_request_id=message_id,
                    message_type="answer",
                    status=outcome,
                    attachments=[attachment],
                    request_id=request_id,
                    actor="assistant",
                )
            ],
        )
        db.flush()
    except Exception:
        logger.exception(
            "generation ready notice append failed project=%s execution=%s",
            project_id,
            execution_id,
        )
        return None

    emitted = {
        "messageId": message_id,
        "outcome": outcome,
        "modality": kind,
        "actionLabel": action_label or None,
        "assetId": asset_id,
        "content": chat_content,
        "technical": technical,
        "executionId": execution_id,
        "previewKind": _preview_kind_for(kind),
        "emittedAt": _now_iso(),
        "duplicate": bool(getattr(batch, "duplicate_count", 0)),
    }
    pd[EMITTED_KEY] = emitted
    plan.plan_data = pd
    return emitted


def emit_after_terminal(
    db: Session,
    project_id: str,
    plan: Any,
    *,
    previous_status: str | None = None,
) -> Optional[dict[str, Any]]:
    """Public hook for advance/cancel — stamp emit marker onto the pack when new."""
    result = maybe_emit_generation_ready_notice(
        db, project_id, plan, previous_status=previous_status
    )
    return result


def image_model_label(family: str) -> str:
    """Creator name for a local image family. Unknown families stay generic."""
    key = str(family or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    labels = {
        "qwen2512": "Qwen Image",
        "qwenimage2512": "Qwen Image",
        "qwenimage": "Qwen Image",
        "qwen": "Qwen Image",
        "zimage": "Z-Image",
        "flux": "FLUX",
        "flux1": "FLUX",
        "krea2": "Krea 2",
        "krea": "Krea 2",
        "illustrious": "Illustrious",
        "illustriousxl": "Illustrious",
        "sd15": "Stable Diffusion",
        "sdxl": "Stable Diffusion",
        "checkpoint": "Local checkpoint",
    }
    return labels.get(key) or "Local image model"


def append_image_job_card(
    db: Session,
    project_id: str,
    job_id: str,
    *,
    family: str = "",
    aspect: str = "",
    width: int = 0,
    height: int = 0,
) -> None:
    """Tell the conversation a local still has started, with the job to watch."""
    from ..conversation_events import EventInput, append_events

    project = str(project_id or "").strip()
    job = str(job_id or "").strip()
    if not project or not job:
        return
    label = image_model_label(family)
    frame = str(aspect or "").strip()
    if frame:
        content = f"{label} is making this still at {frame}."
    else:
        content = f"{label} is making this still."
    message_id = f"imgjob:{job}"[:64]
    append_events(
        db,
        project,
        [
            EventInput(
                role="assistant",
                content=content,
                message_id=message_id,
                client_request_id=message_id,
                actor="assistant",
                attachments=[
                    {
                        "kind": "image_job",
                        "jobId": job,
                        "modelLabel": label,
                        "aspect": frame,
                        "width": int(width or 0),
                        "height": int(height or 0),
                        "provider": "Local",
                    }
                ],
            )
        ],
    )


def append_concept_still(db: Session, project_id: str, asset_id: str, job_id: str) -> None:
    """Put one finished Image Generator still into the same Co-Director conversation."""

    from ..conversation_events import EventInput, append_events

    asset = str(asset_id or "").strip()
    project = str(project_id or "").strip()
    job = str(job_id or "").strip()
    if not asset or not project or not job:
        return
    message_id = f"concept:{job}"[:64]
    append_events(
        db,
        project,
        [
            EventInput(
                role="assistant",
                content="The image has been successfully completed. You can find it in the Library.",
                message_id=message_id,
                client_request_id=message_id,
                actor="assistant",
                attachments=[
                    {
                        "kind": "generation_ready",
                        "outcome": "ready",
                        "modality": "image",
                        "mediaKind": "image",
                        "previewKind": "image",
                        "noticeOnly": True,
                        "assetId": asset,
                        "executionId": job,
                    }
                ],
            )
        ],
    )
