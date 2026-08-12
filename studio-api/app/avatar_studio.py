"""Avatar Studio sessions and long-form section job orchestration."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .avatar_runtimes import inspect_runtime
from .character_identity.voice_runtime import _register_asset
from .config import settings
from .db import Base, Project, engine, get_db

router = APIRouter(tags=["avatar-studio"])

SECTION_PENDING = "pending"
SECTION_QUEUED = "queued"
SECTION_RUNNING = "running"
SECTION_COMPLETED = "completed"
SECTION_FAILED = "failed"
SECTION_RETAKE_REQUESTED = "retake_requested"
SECTION_APPROVED = "approved"

JOB_PLANNING = "planning"
JOB_QUEUED = "queued"
JOB_GENERATING = "generating"
JOB_PAUSED = "paused"
JOB_ASSEMBLING = "assembling"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"


class AvatarErrorCode(str, Enum):
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    SESSION_NOT_FOUND = "AVATAR_SESSION_NOT_FOUND"
    JOB_NOT_FOUND = "AVATAR_JOB_NOT_FOUND"
    SECTION_NOT_FOUND = "AVATAR_SECTION_NOT_FOUND"
    SECTION_INPUT_REQUIRED = "AVATAR_SECTION_INPUT_REQUIRED"
    APPROVED_VOICE_REQUIRED = "AVATAR_APPROVED_VOICE_REQUIRED"
    SECTION_NOT_RETRIABLE = "AVATAR_SECTION_NOT_RETRIABLE"
    PROVIDER_NOT_INSTALLED = "AVATAR_SECTION_PROVIDER_NOT_INSTALLED"
    PROVIDER_NOT_CERTIFIED = "AVATAR_SECTION_PROVIDER_NOT_CERTIFIED"
    RUNTIME_UNAVAILABLE = "AVATAR_SECTION_RUNTIME_UNAVAILABLE"
    SECTION_CANCELLED = "AVATAR_SECTION_CANCELLED"
    JOB_NOT_PAUSABLE = "AVATAR_JOB_NOT_PAUSABLE"
    JOB_NOT_RESUMABLE = "AVATAR_JOB_NOT_RESUMABLE"
    JOB_NOT_CANCELLABLE = "AVATAR_JOB_NOT_CANCELLABLE"
    ASSEMBLY_EMPTY = "AVATAR_ASSEMBLY_EMPTY"
    ASSEMBLY_INCOMPLETE = "AVATAR_ASSEMBLY_SECTIONS_INCOMPLETE"
    ASSEMBLY_TRANSITION_VALIDATION_REQUIRED = "AVATAR_ASSEMBLY_TRANSITION_VALIDATION_REQUIRED"
    LIPSYNC_REPAIR_PROVIDER_REQUIRED = "AVATAR_LIPSYNC_REPAIR_PROVIDER_REQUIRED"
    TIMELINE_REPLACE_CONFIRM_REQUIRED = "AVATAR_TIMELINE_REPLACE_CONFIRM_REQUIRED"


ERROR_DETAILS: dict[AvatarErrorCode, dict[str, Any]] = {
    AvatarErrorCode.PROJECT_NOT_FOUND: {
        "status": 404,
        "message": "This project could not be found.",
        "recovery": "Refresh the project and try again.",
    },
    AvatarErrorCode.SESSION_NOT_FOUND: {
        "status": 404,
        "message": "This Avatar Studio session could not be found.",
        "recovery": "Reload Avatar Studio and select a valid presenter session.",
    },
    AvatarErrorCode.JOB_NOT_FOUND: {
        "status": 404,
        "message": "This long-form avatar job could not be found.",
        "recovery": "Refresh the section list and retry.",
    },
    AvatarErrorCode.SECTION_NOT_FOUND: {
        "status": 404,
        "message": "That section is no longer available.",
        "recovery": "Reload the job and choose a current section.",
    },
    AvatarErrorCode.SECTION_INPUT_REQUIRED: {
        "status": 400,
        "message": "Add a script or attach approved voice audio before planning sections.",
        "recovery": "Return to the Create panel, then retry generation.",
    },
    AvatarErrorCode.APPROVED_VOICE_REQUIRED: {
        "status": 409,
        "message": "Avatar Studio can only use approved Voice Studio takes in Approved Voice mode.",
        "recovery": "Choose an approved Voice Studio take or switch back to Script mode.",
    },
    AvatarErrorCode.SECTION_NOT_RETRIABLE: {
        "status": 409,
        "message": "Only failed sections can be retried right now.",
        "recovery": "Pick a failed section or request a retake instead.",
    },
    AvatarErrorCode.PROVIDER_NOT_INSTALLED: {
        "status": 409,
        "message": "This avatar runtime is not installed yet.",
        "recovery": "Open Source Manager, install the runtime, then retry the failed section.",
    },
    AvatarErrorCode.PROVIDER_NOT_CERTIFIED: {
        "status": 409,
        "message": "This avatar runtime is still Experimental and not certified for live long-form generation.",
        "recovery": "Use Source Manager to verify the runtime or wait for a certified live generator path.",
    },
    AvatarErrorCode.RUNTIME_UNAVAILABLE: {
        "status": 409,
        "message": "The avatar runtime is installed but unavailable for a live section pass.",
        "recovery": "Verify the runtime health in Source Manager, then retry the failed section.",
    },
    AvatarErrorCode.SECTION_CANCELLED: {
        "status": 409,
        "message": "This section pass was cancelled before it finished.",
        "recovery": "Resume the job or retry only the cancelled section.",
    },
    AvatarErrorCode.JOB_NOT_PAUSABLE: {
        "status": 409,
        "message": "Only queued or generating jobs can be paused.",
        "recovery": "Start a planned job first, then pause while it is active.",
    },
    AvatarErrorCode.JOB_NOT_RESUMABLE: {
        "status": 409,
        "message": "This job is not waiting in a paused state.",
        "recovery": "Pause the job first or create a new planned pass.",
    },
    AvatarErrorCode.JOB_NOT_CANCELLABLE: {
        "status": 409,
        "message": "This job can no longer be cancelled.",
        "recovery": "Create a new planned pass or retry only the failed section you need.",
    },
    AvatarErrorCode.ASSEMBLY_EMPTY: {
        "status": 400,
        "message": "There are no completed sections ready for assembly yet.",
        "recovery": "Generate at least one section before assembling.",
    },
    AvatarErrorCode.ASSEMBLY_INCOMPLETE: {
        "status": 409,
        "message": "Every required section must complete before final assembly can continue.",
        "recovery": "Retry only the failed or missing sections, then assemble again.",
    },
    AvatarErrorCode.ASSEMBLY_TRANSITION_VALIDATION_REQUIRED: {
        "status": 409,
        "message": "Transition validation must run before the long-form job can be marked complete.",
        "recovery": "Validate section transitions, then retry assembly.",
    },
    AvatarErrorCode.LIPSYNC_REPAIR_PROVIDER_REQUIRED: {
        "status": 409,
        "message": "MuseTalk 1.5 is not installed, so Lip-Sync Repair cannot run yet.",
        "recovery": "Open Source Manager, install MuseTalk 1.5, then retry Lip-Sync Repair.",
    },
    AvatarErrorCode.TIMELINE_REPLACE_CONFIRM_REQUIRED: {
        "status": 409,
        "message": "Timeline already has Avatar Studio placement for this range.",
        "recovery": "Review the existing placement and confirm replacement explicitly.",
    },
}


class AvatarSessionRow(Base):
    __tablename__ = "avatar_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200), default="Avatar Session")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class AvatarProjectJobRow(Base):
    __tablename__ = "avatar_project_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    avatar_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default=JOB_PLANNING)
    assembly_state: Mapped[str] = mapped_column(String(64), default="not_requested")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


def ensure_avatar_tables() -> None:
    Base.metadata.create_all(
        bind=engine, tables=[AvatarSessionRow.__table__, AvatarProjectJobRow.__table__]
    )


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _error_payload(code: AvatarErrorCode | str, message: str | None = None, **extra: Any) -> dict[str, Any]:
    enum_code = AvatarErrorCode(code)
    detail = ERROR_DETAILS[enum_code]
    payload = {
        "code": enum_code.value,
        "message": message or detail["message"],
        "recovery": detail["recovery"],
    }
    payload.update(extra)
    return payload


def _raise_avatar_error(code: AvatarErrorCode | str, message: str | None = None, **extra: Any) -> HTTPException:
    enum_code = AvatarErrorCode(code)
    return HTTPException(
        status_code=int(ERROR_DETAILS[enum_code]["status"]),
        detail=_error_payload(enum_code, message, **extra),
    )


def _empty(project_id: str, name: str = "Avatar Session") -> dict[str, Any]:
    now = _now()
    sid = f"avs-{uuid.uuid4().hex[:10]}"
    return {
        "id": sid,
        "project_id": project_id,
        "name": name,
        "mode": "talking_portrait",
        "character_profile_id": None,
        "character_name": "",
        "continuity_lock": True,
        "active_job_id": None,
        "look": {
            "id": f"look-{uuid.uuid4().hex[:8]}",
            "name": "Default Look",
            "framing": "medium close-up",
            "wardrobe": "",
            "expression": "neutral",
            "pose": "upright",
            "camera_angle": "three-quarter",
            "lens": "50mm",
            "background": "neutral gray",
            "lighting": "soft key, gentle fill",
            "style": "cinematic live-action",
            "aspect": "16:9",
        },
        "voice": {
            "provider": "upload",
            "model": "",
            "speaker_id": "",
            "language": "en",
            "accent": "",
            "tone": "natural",
            "pitch": "medium",
            "pace": "moderate",
            "emotional_range": "restrained",
            "pronunciation_notes": "",
            "stability": "high",
            "usage_rights": "project",
            "audio_asset_id": None,
            "fallback_audio_asset_id": None,
            "profile_id": None,
            "approved_record_id": None,
            "approved_take_id": None,
        },
        "dialogue_original": "",
        "dialogue_spoken": "",
        "dialogue_adaptation_accepted": None,
        "performance": {
            "tone": "restrained",
            "eye_contact": "slightly off-camera",
            "head_movement": "minimal",
            "blink_frequency": "natural",
            "shoulder_movement": "low",
            "gesture_intensity": "low",
            "breathing": "subtle",
            "facial_expressiveness": "controlled",
            "energy": "moderate",
            "stillness": "high",
        },
        "camera": {
            "shot_size": "medium close-up",
            "lens": "50mm",
            "height": "eye level",
            "angle": "direct-to-camera",
            "movement": "static",
            "aspect": "16:9",
        },
        "background_mode": "solid",
        "background_notes": "Neutral studio background",
        "input_mode": "script",
        "presentation_style": "direct_presenter",
        "framing_choice": "medium_presenter",
        "background_choice": "studio_gradient",
        "duration_class": "story_section",
        "provider_mode": "best_match",
        "provider_choice": None,
        "model_id": "ltx_2_5_distilled",
        "prompt": "",
        "negative_prompt": (
            "identity drift, teeth distortion, frozen face, overactive facial motion, "
            "mouth drift, cropped chin, background warping, duplicate characters, blurry"
        ),
        "source_video_asset_id": None,
        "source_still_asset_id": None,
        "mouth_mask": {"placed": False},
        "lip_sync_method": "external",
        "takes": [],
        "links": {
            "script_document_id": None,
            "script_scene_heading_id": None,
            "script_scene_id": None,
            "script_source_label": "",
            "script_revision_version": None,
            "voice_record_id": None,
            "voice_take_id": None,
        },
        "created_at": now,
        "updated_at": now,
    }


def _validate(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    voice = data.get("voice") or {}
    if (
        not data.get("character_profile_id")
        and not data.get("character_name")
        and not data.get("source_still_asset_id")
    ):
        issues.append({"level": "warn", "text": "Identity reference missing"})
    if not voice.get("audio_asset_id") and data.get("lip_sync_method") == "external":
        issues.append({"level": "bad", "text": "Audio required for external lip-sync method"})
    if data.get("mode") == "existing_video_lipsync" and not data.get("source_video_asset_id"):
        issues.append({"level": "bad", "text": "Source video required"})
    mouth = data.get("mouth_mask") or {}
    if data.get("lip_sync_method") == "external" and not mouth.get("placed"):
        issues.append({"level": "warn", "text": "Mouth mask requires user confirmation"})
    if not (data.get("dialogue_original") or data.get("dialogue_spoken") or voice.get("audio_asset_id")):
        issues.append({"level": "warn", "text": "Dialogue empty"})
    if data.get("input_mode") == "approved_voice":
        if not _voice_has_approved_take(data):
            issues.append(
                {
                    "level": "bad",
                    "text": "Approved Voice mode requires an approved Voice Studio take",
                }
            )
    return issues


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _row_to_data(row: AvatarSessionRow) -> dict[str, Any]:
    data = _loads(row.data_json, _empty(row.project_id, row.name))
    if not isinstance(data, dict):
        data = _empty(row.project_id, row.name)
    data["id"] = row.id
    data["project_id"] = row.project_id
    data["name"] = row.name or data.get("name") or "Avatar Session"
    data["updated_at"] = row.updated_at or data.get("updated_at")
    data.setdefault("active_job_id", None)
    data["presentation_plan"] = _compose_presentation_plan(data, keep_existing=True)
    return data


def _job_to_row_data(row: AvatarProjectJobRow) -> dict[str, Any]:
    data = _loads(row.data_json, {})
    if not isinstance(data, dict):
        data = {}
    data["id"] = row.id
    data["projectId"] = row.project_id
    data["sessionId"] = row.session_id
    data["avatarId"] = row.avatar_id
    data["providerId"] = row.provider_id
    data["status"] = row.status or data.get("status") or JOB_PLANNING
    data["assemblyState"] = row.assembly_state or data.get("assemblyState") or "not_requested"
    data["createdAt"] = row.created_at or data.get("createdAt") or _now()
    data["updatedAt"] = row.updated_at or data.get("updatedAt") or data["createdAt"]
    data.setdefault("sections", [])
    data.setdefault("requestedDurationMs", 0)
    data.setdefault("completedDurationMs", 0)
    return data


def _write_session(row: AvatarSessionRow, data: dict[str, Any]) -> dict[str, Any]:
    data["updated_at"] = _now()
    row.name = str(data.get("name") or row.name or "Avatar Session")
    row.data_json = json.dumps(data, ensure_ascii=False)
    row.updated_at = str(data["updated_at"])
    return data


def _write_job(row: AvatarProjectJobRow, data: dict[str, Any]) -> dict[str, Any]:
    data["updatedAt"] = _now()
    row.provider_id = str(data.get("providerId") or row.provider_id or "")
    row.status = str(data.get("status") or row.status or JOB_PLANNING)
    row.assembly_state = str(data.get("assemblyState") or row.assembly_state or "not_requested")
    row.data_json = json.dumps(data, ensure_ascii=False)
    row.updated_at = str(data["updatedAt"])
    return data


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise _raise_avatar_error(AvatarErrorCode.PROJECT_NOT_FOUND)
    return project


def _session_or_404(db: Session, project_id: str, session_id: str) -> AvatarSessionRow:
    row = db.get(AvatarSessionRow, session_id)
    if not row or row.project_id != project_id:
        raise _raise_avatar_error(AvatarErrorCode.SESSION_NOT_FOUND)
    return row


def _job_or_404(db: Session, project_id: str, job_id: str) -> AvatarProjectJobRow:
    row = db.get(AvatarProjectJobRow, job_id)
    if not row or row.project_id != project_id:
        raise _raise_avatar_error(AvatarErrorCode.JOB_NOT_FOUND)
    return row


def _section_or_404(job: dict[str, Any], section_id: str) -> dict[str, Any]:
    for section in job.get("sections") or []:
        if str(section.get("id")) == section_id:
            return section
    raise _raise_avatar_error(AvatarErrorCode.SECTION_NOT_FOUND)


def _duration_class_ms(session: dict[str, Any]) -> int:
    duration_class = str(session.get("duration_class") or "story_section")
    return {
        "quick_update": 4000,
        "story_section": 6000,
        "chapter_pass": 8000,
    }.get(duration_class, 6000)


def _estimate_duration_ms(text: str, *, fallback_ms: int = 2000) -> int:
    words = len([part for part in re.split(r"\s+", text.strip()) if part])
    if not words:
        return fallback_ms
    return max(1500, int(round((words / 2.5) * 1000)))


def _voice_has_approved_take(session: dict[str, Any]) -> bool:
    voice = session.get("voice") or {}
    return bool(
        voice.get("audio_asset_id")
        and voice.get("approved_record_id")
        and voice.get("approved_take_id")
    )


def _require_approved_voice(session: dict[str, Any]) -> None:
    if str(session.get("input_mode") or "script") != "approved_voice":
        return
    if not _voice_has_approved_take(session):
        raise _raise_avatar_error(AvatarErrorCode.APPROVED_VOICE_REQUIRED)


def _resolved_audio_asset_id(session: dict[str, Any]) -> str | None:
    voice = session.get("voice") or {}
    if str(session.get("input_mode") or "script") == "approved_voice":
        return voice.get("audio_asset_id")
    return voice.get("fallback_audio_asset_id") or voice.get("audio_asset_id")


def _script_source_linkage(session: dict[str, Any]) -> dict[str, Any]:
    links = session.get("links") if isinstance(session.get("links"), dict) else {}
    return {
        "documentId": links.get("script_document_id"),
        "sceneHeadingId": links.get("script_scene_heading_id"),
        "sceneId": links.get("script_scene_id"),
        "label": links.get("script_source_label") or "",
        "revisionVersion": links.get("script_revision_version"),
    }


def _voice_provenance(session: dict[str, Any]) -> dict[str, Any]:
    voice = session.get("voice") or {}
    links = session.get("links") if isinstance(session.get("links"), dict) else {}
    return {
        "mode": session.get("input_mode") or "script",
        "provider": voice.get("provider"),
        "model": voice.get("model"),
        "audioAssetId": voice.get("audio_asset_id"),
        "fallbackAudioAssetId": voice.get("fallback_audio_asset_id"),
        "approvedRecordId": voice.get("approved_record_id") or links.get("voice_record_id"),
        "approvedTakeId": voice.get("approved_take_id") or links.get("voice_take_id"),
        "profileId": voice.get("profile_id"),
        "pronunciationNotes": voice.get("pronunciation_notes") or "",
        "approved": _voice_has_approved_take(session),
    }


def _audio_mix_linkage(session: dict[str, Any], job: dict[str, Any] | None = None) -> dict[str, Any]:
    voice = _voice_provenance(session)
    return {
        "openWorkspace": "audiostudio",
        "dialogueStemAssetId": voice.get("audioAssetId") or voice.get("fallbackAudioAssetId"),
        "voiceStudioMasterAssetId": voice.get("audioAssetId"),
        "destructiveOverwriteAllowed": False,
        "jobId": job.get("id") if isinstance(job, dict) else None,
    }


def _neighboring_context(job: dict[str, Any], section_id: str) -> dict[str, Any]:
    sections = list(job.get("sections") or [])
    for index, section in enumerate(sections):
        if str(section.get("id")) != section_id:
            continue
        previous_section = sections[index - 1] if index > 0 else None
        next_section = sections[index + 1] if index + 1 < len(sections) else None
        return {
            "previous": {
                "id": previous_section.get("id"),
                "summary": previous_section.get("presentationPlan", {}).get("summary"),
                "scriptText": previous_section.get("scriptText"),
            }
            if isinstance(previous_section, dict)
            else None,
            "next": {
                "id": next_section.get("id"),
                "summary": next_section.get("presentationPlan", {}).get("summary"),
                "scriptText": next_section.get("scriptText"),
            }
            if isinstance(next_section, dict)
            else None,
        }
    return {"previous": None, "next": None}


def _snapshot_section_version(section: dict[str, Any], *, reason: str, action_type: str) -> dict[str, Any]:
    return {
        "id": f"avver-{uuid.uuid4().hex[:10]}",
        "capturedAt": _now(),
        "reason": reason,
        "actionType": action_type,
        "status": section.get("status"),
        "outputVideoAssetId": section.get("outputVideoAssetId"),
        "continuationFrameAssetId": section.get("continuationFrameAssetId"),
        "attempt": section.get("attempt"),
        "presentationPlan": json.loads(json.dumps(section.get("presentationPlan") or {})),
        "retakeNote": section.get("retakeNote"),
    }


def _timeline_track_for_mode(mode: str) -> str:
    return {
        "full_presentation": "avatar-presenter",
        "selected_section": "avatar-presenter",
        "replace_section": "avatar-presenter",
        "create_alternate_take": "avatar-alternates",
    }.get(mode, "avatar-presenter")


def _timeline_clip_for_section(
    *,
    session: dict[str, Any],
    job: dict[str, Any],
    section: dict[str, Any],
    placement_mode: str,
    start_ms: int,
) -> dict[str, Any]:
    voice = _voice_provenance(session)
    source = _script_source_linkage(session)
    duration_ms = max(0, int(section.get("audioEndMs") or 0) - int(section.get("audioStartMs") or 0))
    return {
        "id": str(uuid.uuid4()),
        "kind": "avatar_section",
        "track": "avatar",
        "label": f"{session.get('character_name') or 'Presenter'} · Section {int(section.get('order') or 0) + 1}",
        "jobId": job.get("id"),
        "sectionId": section.get("id"),
        "avatarId": job.get("avatarId"),
        "providerId": job.get("providerId"),
        "assetId": section.get("outputVideoAssetId"),
        "startMs": int(start_ms),
        "durationMs": duration_ms,
        "placementMode": placement_mode,
        "provenance": {
            "assemblyVersion": 1,
            "sessionId": session.get("id"),
            "jobId": job.get("id"),
            "sectionId": section.get("id"),
            "script": source,
            "voice": voice,
            "retakeHistory": section.get("retakeHistory") or [],
            "sectionVersionHistory": section.get("versionHistory") or [],
        },
    }


def _build_timeline_proposal(
    *,
    session: dict[str, Any],
    job: dict[str, Any],
    placement_mode: str,
    selected_section_id: str | None,
    replace_section_id: str | None,
    track_id: str | None,
    start_ms: int,
) -> dict[str, Any]:
    sections = list(job.get("sections") or [])
    if selected_section_id:
        selected = [_section_or_404(job, selected_section_id)]
    else:
        selected = [
            section
            for section in sections
            if section.get("status") in (SECTION_COMPLETED, SECTION_APPROVED, SECTION_RETAKE_REQUESTED)
        ]
    ready = [
        section
        for section in selected
        if section.get("outputVideoAssetId")
        and section.get("status") in (SECTION_COMPLETED, SECTION_APPROVED, SECTION_RETAKE_REQUESTED)
    ]
    script_source = _script_source_linkage(session)
    voice = _voice_provenance(session)
    section_map = [
        {
            "sectionId": section.get("id"),
            "order": section.get("order"),
            "status": section.get("status"),
            "outputVideoAssetId": section.get("outputVideoAssetId"),
            "currentVersionId": section.get("currentVersionId"),
            "retakeCount": len(section.get("retakeHistory") or []),
        }
        for section in sections
    ]
    proposal = {
        "jobId": job.get("id"),
        "sessionId": session.get("id"),
        "placementMode": placement_mode,
        "trackId": track_id or _timeline_track_for_mode(placement_mode),
        "startMs": int(start_ms),
        "selectedSectionId": selected_section_id,
        "replaceSectionId": replace_section_id,
        "sectionIds": [section.get("id") for section in selected],
        "readySectionIds": [section.get("id") for section in ready],
        "clips": [
            _timeline_clip_for_section(
                session=session,
                job=job,
                section=section,
                placement_mode=placement_mode,
                start_ms=start_ms + max(0, int(section.get("audioStartMs") or 0)),
            )
            for section in ready
        ],
        "provenance": {
            "assemblyVersion": 1,
            "avatarId": job.get("avatarId"),
            "providerId": job.get("providerId"),
            "script": script_source,
            "voice": voice,
            "sectionMap": section_map,
            "retakeHistory": {
                str(section.get("id")): section.get("retakeHistory") or []
                for section in sections
            },
            "jobStatus": job.get("status"),
        },
        "audioMix": _audio_mix_linkage(session, job),
        "timelineWritten": False,
        "createdAt": _now(),
    }
    return proposal


def _chunk_script(script_text: str, target_duration_ms: int) -> list[str]:
    text = re.sub(r"\s+", " ", script_text or "").strip()
    if not text:
        return []
    target_words = max(8, int(round(target_duration_ms / 400)))
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > target_words:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = words
            continue
        if not current and words > target_words + 4:
            terms = sentence.split()
            for start in range(0, len(terms), target_words):
                chunks.append(" ".join(terms[start : start + target_words]).strip())
            current = []
            current_words = 0
            continue
        current.append(sentence)
        current_words += words
    if current:
        chunks.append(" ".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _style_direction(session: dict[str, Any]) -> dict[str, str]:
    presentation_style = str(session.get("presentation_style") or "direct_presenter")
    style_map = {
        "direct_presenter": {
            "delivery": "Clear, confident presenter delivery with direct language.",
            "gaze": "Hold steady eye contact with the lens for key lines.",
            "gesture": "Keep gestures compact and purposeful.",
            "pacing": "Measured pacing with short emphasis pauses.",
            "posture": "Upright posture with relaxed shoulders.",
            "transition": "Reset with a micro-pause and clean breath between chapters.",
        },
        "warm_host": {
            "delivery": "Welcoming delivery that stays grounded and conversational.",
            "gaze": "Friendly lens contact with soft glance resets at transitions.",
            "gesture": "Use open-handed gestures sparingly to invite the audience in.",
            "pacing": "Easy pacing with gentle breaths between beats.",
            "posture": "Open chest and relaxed posture.",
            "transition": "Bridge sections with a small smile reset and softened breath.",
        },
        "guided_explainer": {
            "delivery": "Instructional delivery that stays calm and precise.",
            "gaze": "Mostly lens-driven, with quick off-camera thought beats.",
            "gesture": "Use clarifying hand cues when introducing new ideas.",
            "pacing": "Slightly slower pacing for explanation-heavy moments.",
            "posture": "Centered posture with subtle forward intention.",
            "transition": "Pause briefly before the next concept and re-center the gaze.",
        },
        "stylized_performance": {
            "delivery": "A shaped, cinematic read with slightly heightened intention.",
            "gaze": "Use deliberate gaze changes to mark turning points.",
            "gesture": "Allow more sculpted gesture accents while keeping continuity.",
            "pacing": "Dynamic pacing with cleaner contrast between beats.",
            "posture": "Composed posture with stronger silhouette awareness.",
            "transition": "Use visible resets so each chapter lands with intent.",
        },
    }
    return style_map.get(presentation_style, style_map["direct_presenter"])


def _section_focus(index: int, total: int) -> str:
    if total <= 1:
        return "Single pass"
    if index == 0:
        return "Opening"
    if index == total - 1:
        return "Close"
    if index == 1:
        return "Build"
    return "Bridge"


def _summarize_chunk(chunk: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", chunk or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _compose_presentation_plan(
    session: dict[str, Any],
    *,
    target_duration_ms: int | None = None,
    keep_existing: bool = True,
) -> dict[str, Any]:
    existing = session.get("presentation_plan") if isinstance(session.get("presentation_plan"), dict) else {}
    style = _style_direction(session)
    existing_target_seconds = existing.get("sectionTargetSeconds")
    existing_target_ms = (
        int(round(float(existing_target_seconds) * 1000))
        if existing_target_seconds not in (None, "")
        else 0
    )
    target_ms = max(2000, int(target_duration_ms or existing_target_ms or _duration_class_ms(session)))
    script_text = str(session.get("dialogue_spoken") or session.get("dialogue_original") or "").strip()
    chunks = _chunk_script(script_text, target_ms) if script_text else []
    existing_sections = existing.get("sections") if isinstance(existing.get("sections"), list) else []
    background = str(
        existing.get("backgroundRecommendation")
        or session.get("background_notes")
        or (session.get("look") or {}).get("background")
        or "Clean presenter background with subject separation."
    ).strip()
    framing = str(
        existing.get("framingRecommendation")
        or (session.get("look") or {}).get("framing")
        or (session.get("camera") or {}).get("shot_size")
        or "medium close-up"
    ).strip()
    pronunciation = str(
        existing.get("pronunciationNotes")
        or ((session.get("voice") or {}).get("pronunciation_notes") or "")
    ).strip()
    continuity = str(existing.get("continuityChecklist") or "").strip() or (
        "Keep the same eye line, camera height, and background continuity across sections."
        if session.get("continuity_lock", True)
        else "Continuity lock is off, so review framing and posture before assembling."
    )
    retake_guidance = str(existing.get("retakeGuidance") or "").strip() or (
        "Retake only the drifting section. Match the handoff posture, eye line, and breath into the next beat."
    )
    sections: list[dict[str, Any]] = []
    cursor_ms = 0
    for index, chunk in enumerate(chunks):
        existing_section = existing_sections[index] if index < len(existing_sections) and isinstance(existing_sections[index], dict) else {}
        duration_ms = _estimate_duration_ms(chunk, fallback_ms=target_ms)
        sections.append(
            {
                "id": str(existing_section.get("id") or f"plansec-{index + 1}"),
                "label": str(existing_section.get("label") or _section_focus(index, len(chunks))),
                "summary": str(existing_section.get("summary") or _summarize_chunk(chunk)),
                "delivery": str(existing_section.get("delivery") or style["delivery"]),
                "gaze": str(existing_section.get("gaze") or style["gaze"]),
                "gesture": str(existing_section.get("gesture") or style["gesture"]),
                "pacing": str(existing_section.get("pacing") or style["pacing"]),
                "emphasis": str(
                    existing_section.get("emphasis")
                    or ("Underline the first phrase and land the final phrase cleanly.")
                ),
                "posture": str(existing_section.get("posture") or style["posture"]),
                "pronunciation": str(existing_section.get("pronunciation") or pronunciation),
                "transition": str(existing_section.get("transition") or style["transition"]),
                "background": str(existing_section.get("background") or background),
                "framing": str(existing_section.get("framing") or framing),
                "retakeFocus": str(
                    existing_section.get("retakeFocus")
                    or "Check timing, mouth phrasing, and the handoff into the next section."
                ),
                "continuity": str(existing_section.get("continuity") or continuity),
                "excerpt": _summarize_chunk(chunk, limit=90),
                "startMs": int(existing_section.get("startMs") or cursor_ms),
                "endMs": int(existing_section.get("endMs") or (cursor_ms + duration_ms)),
            }
        )
        cursor_ms += duration_ms
    summary = str(existing.get("summary") or "").strip()
    if not summary:
        summary = (
            "Break this presenter performance into concise sections with clean chapter handoffs,"
            " consistent posture, and emphasis that follows the script arc."
        )
    return {
        "version": "m4.12",
        "source": str(existing.get("source") or ("codirector" if keep_existing and existing else "manual")),
        "summary": summary,
        "sectioningStrategy": str(
            existing.get("sectioningStrategy")
            or "Chunk the script into creator-reviewable presenter beats with overlap for continuity."
        ),
        "sectionTargetSeconds": round(target_ms / 1000, 1),
        "deliveryStyle": str(existing.get("deliveryStyle") or style["delivery"]),
        "gazeStyle": str(existing.get("gazeStyle") or style["gaze"]),
        "gestureStyle": str(existing.get("gestureStyle") or style["gesture"]),
        "pacingStyle": str(existing.get("pacingStyle") or style["pacing"]),
        "chapterTransitionStyle": str(existing.get("chapterTransitionStyle") or style["transition"]),
        "emphasisNotes": str(
            existing.get("emphasisNotes")
            or "Save the strongest emphasis for chapter opens, pivots, and the close."
        ),
        "postureNotes": str(existing.get("postureNotes") or style["posture"]),
        "pronunciationNotes": pronunciation,
        "backgroundRecommendation": background,
        "framingRecommendation": framing,
        "continuityChecklist": continuity,
        "retakeGuidance": retake_guidance,
        "sections": sections,
        "updatedAt": _now(),
    }


def _project_video_dir(project_id: str) -> Path:
    root = Path(settings.data_dir) / "projects" / project_id / "assets" / "avatar_video"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _select_provider(session: dict[str, Any], requested_provider: str | None) -> str:
    return (
        str(requested_provider or "").strip()
        or str(session.get("provider_choice") or "").strip()
        or str(session.get("model_id") or "").strip()
        or "infinitetalk-local"
    )


def _build_section_plan(
    session: dict[str, Any],
    *,
    provider_id: str,
    target_duration_ms: int,
    overlap_ms: int,
    script_source_id: str | None,
) -> list[dict[str, Any]]:
    text = str(session.get("dialogue_spoken") or session.get("dialogue_original") or "").strip()
    audio_asset_id = _resolved_audio_asset_id(session)
    if not text and not audio_asset_id:
        raise _raise_avatar_error(AvatarErrorCode.SECTION_INPUT_REQUIRED)
    chunks = _chunk_script(text, target_duration_ms)
    if not chunks:
        chunks = [text or "Approved voice performance"]
    plan = _compose_presentation_plan(session, target_duration_ms=target_duration_ms, keep_existing=True)
    plan_sections = plan.get("sections") if isinstance(plan.get("sections"), list) else []
    shared_style_profile_id = f"avatar-style-{session['id']}"
    avatar_id = str(session.get("character_profile_id") or session.get("character_name") or session["id"])
    sections: list[dict[str, Any]] = []
    cursor_ms = 0
    for index, chunk in enumerate(chunks):
        plan_section = plan_sections[index] if index < len(plan_sections) and isinstance(plan_sections[index], dict) else {}
        duration_ms = _estimate_duration_ms(chunk, fallback_ms=target_duration_ms)
        overlap_before = overlap_ms if index > 0 else 0
        overlap_after = overlap_ms if index < len(chunks) - 1 else 0
        section_id = f"avssec-{uuid.uuid4().hex[:10]}"
        presentation_plan = {
            "avatarPresentationPlanVersion": "m4.12",
            "sharedStyleProfileId": shared_style_profile_id,
            "identityProfileRef": avatar_id,
            "characterName": session.get("character_name") or "Presenter",
            "scriptSourceId": script_source_id,
            "providerId": provider_id,
            "presentationStyle": session.get("presentation_style"),
            "framingChoice": session.get("framing_choice"),
            "backgroundChoice": session.get("background_choice"),
            "durationClass": session.get("duration_class"),
            "summary": plan_section.get("summary"),
            "delivery": plan_section.get("delivery"),
            "gaze": plan_section.get("gaze"),
            "gesture": plan_section.get("gesture"),
            "pacing": plan_section.get("pacing"),
            "emphasis": plan_section.get("emphasis"),
            "posture": plan_section.get("posture"),
            "pronunciation": plan_section.get("pronunciation"),
            "transition": plan_section.get("transition"),
            "backgroundRecommendation": plan_section.get("background"),
            "framingRecommendation": plan_section.get("framing"),
            "retakeFocus": plan_section.get("retakeFocus"),
            "continuityChecklist": plan_section.get("continuity"),
            "continuityLock": bool(session.get("continuity_lock")),
            "referenceStillAssetId": session.get("source_still_asset_id"),
            "sourceVideoAssetId": session.get("source_video_asset_id"),
            "continuity": {
                "sharedStyleProfileId": shared_style_profile_id,
                "previousSectionId": sections[-1]["id"] if sections else None,
                "requiresContinuationFrame": index > 0,
                "overlapBeforeMs": overlap_before,
                "overlapAfterMs": overlap_after,
            },
            "transitionValidation": {
                "required": index < len(chunks) - 1,
                "validated": False,
            },
        }
        sections.append(
            {
                "id": section_id,
                "order": index,
                "scriptText": chunk,
                "audioStartMs": cursor_ms,
                "audioEndMs": cursor_ms + duration_ms,
                "overlapBeforeMs": overlap_before,
                "overlapAfterMs": overlap_after,
                "continuationFrameAssetId": None,
                "outputVideoAssetId": None,
                "presentationPlan": presentation_plan,
                "status": SECTION_PENDING,
                "providerJobId": None,
                "errorCode": None,
                "errorMessage": None,
                "attempt": 1,
                "retryCount": 0,
                "versionHistory": [],
                "retakeHistory": [],
                "currentVersionId": f"avcur-{uuid.uuid4().hex[:10]}",
                "retakeRequest": None,
                "updatedAt": _now(),
            }
        )
        cursor_ms += duration_ms
    return sections


def _summarize_job(job: dict[str, Any]) -> dict[str, Any]:
    sections = list(job.get("sections") or [])
    completed_sections = [
        section for section in sections if section.get("status") in (SECTION_COMPLETED, SECTION_APPROVED)
    ]
    failed_sections = [section for section in sections if section.get("status") == SECTION_FAILED]
    pending_sections = [
        section
        for section in sections
        if section.get("status") in (SECTION_PENDING, SECTION_QUEUED, SECTION_RUNNING, SECTION_RETAKE_REQUESTED)
    ]
    job["completedDurationMs"] = sum(
        max(0, int(section.get("audioEndMs") or 0) - int(section.get("audioStartMs") or 0))
        for section in completed_sections
    )
    progress = {
        "totalSections": len(sections),
        "completedSections": len(completed_sections),
        "failedSections": len(failed_sections),
        "pendingSections": len(pending_sections),
    }
    job["progress"] = progress
    if job.get("status") == JOB_CANCELLED:
        job["assemblyState"] = "cancelled"
        return job
    if failed_sections:
        job["status"] = JOB_FAILED
        job["assemblyState"] = "waiting_for_section_retry"
        return job
    if pending_sections and job.get("status") != JOB_PAUSED:
        job["status"] = JOB_QUEUED
        job["assemblyState"] = "planned"
        return job
    if sections and len(completed_sections) == len(sections):
        validated = bool(((job.get("transitionValidation") or {}).get("validated")))
        job["status"] = JOB_ASSEMBLING if not validated else job.get("status") or JOB_ASSEMBLING
        job["assemblyState"] = (
            "transition_validation_required" if not validated else job.get("assemblyState") or "validated"
        )
        return job
    if not sections:
        job["status"] = JOB_PLANNING
        job["assemblyState"] = "not_requested"
    return job


def _runtime_dispatch_result(provider_id: str) -> dict[str, Any]:
    try:
        runtime = inspect_runtime(provider_id)
    except Exception:
        runtime = {"runtimeReady": False, "healthState": "not_installed"}
    health_state = str(runtime.get("healthState") or "not_installed")
    if health_state == "not_installed":
        return {
            "ok": False,
            "errorCode": AvatarErrorCode.PROVIDER_NOT_INSTALLED.value,
            "message": ERROR_DETAILS[AvatarErrorCode.PROVIDER_NOT_INSTALLED]["message"],
            "runtime": runtime,
        }
    if not runtime.get("runtimeReady"):
        return {
            "ok": False,
            "errorCode": AvatarErrorCode.RUNTIME_UNAVAILABLE.value,
            "message": ERROR_DETAILS[AvatarErrorCode.RUNTIME_UNAVAILABLE]["message"],
            "runtime": runtime,
        }
    return {
        "ok": False,
        "errorCode": AvatarErrorCode.PROVIDER_NOT_CERTIFIED.value,
        "message": ERROR_DETAILS[AvatarErrorCode.PROVIDER_NOT_CERTIFIED]["message"],
        "runtime": runtime,
    }


def _execute_section_generation(
    db: Session,
    *,
    project_id: str,
    provider_id: str,
    session_data: dict[str, Any],
    job: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    """Default live hook for M4.12.

    The honest default is failure until a provider-specific runtime is certified.
    Tests may monkeypatch this seam to simulate completed section assets.
    """

    return _runtime_dispatch_result(provider_id)


def _dispatch_job(row: AvatarProjectJobRow, session_data: dict[str, Any], db: Session) -> dict[str, Any]:
    job = _job_to_row_data(row)
    if job.get("status") in (JOB_PAUSED, JOB_CANCELLED, JOB_COMPLETED):
        return job
    job["status"] = JOB_GENERATING
    sections = list(job.get("sections") or [])
    for index, section in enumerate(sections):
        if section.get("status") not in (SECTION_PENDING, SECTION_QUEUED):
            continue
        section["status"] = SECTION_RUNNING
        section["providerJobId"] = f"provider-{uuid.uuid4().hex[:8]}"
        section["updatedAt"] = _now()
        result = _execute_section_generation(
            db,
            project_id=job["projectId"],
            provider_id=job["providerId"],
            session_data=session_data,
            job=job,
            section=section,
        )
        if result.get("ok"):
            section["status"] = SECTION_COMPLETED
            section["outputVideoAssetId"] = result.get("outputVideoAssetId")
            section["continuationFrameAssetId"] = result.get("continuationFrameAssetId")
            section["errorCode"] = None
            section["errorMessage"] = None
            if index + 1 < len(sections):
                next_section = sections[index + 1]
                next_section["continuationFrameAssetId"] = (
                    result.get("continuationFrameAssetId") or result.get("outputVideoAssetId")
                )
        else:
            section["status"] = SECTION_FAILED
            section["errorCode"] = result.get("errorCode")
            section["errorMessage"] = result.get("message")
            job["lastError"] = {
                "code": result.get("errorCode"),
                "message": result.get("message"),
                "sectionId": section.get("id"),
            }
        section["updatedAt"] = _now()
    job["sections"] = sections
    job = _summarize_job(job)
    if job.get("assemblyState") == "transition_validation_required":
        job["status"] = JOB_ASSEMBLING
    _write_job(row, job)
    db.commit()
    return job


def _new_job(
    project_id: str,
    session_id: str,
    session_data: dict[str, Any],
    *,
    provider_id: str,
    script_source_id: str | None,
    sections: list[dict[str, Any]],
    presentation_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    avatar_id = str(
        session_data.get("character_profile_id") or session_data.get("character_name") or session_id
    )
    return {
        "id": f"avjob-{uuid.uuid4().hex[:10]}",
        "projectId": project_id,
        "sessionId": session_id,
        "avatarId": avatar_id,
        "providerId": provider_id,
        "scriptSourceId": script_source_id,
        "audioAssetId": _resolved_audio_asset_id(session_data),
        "sections": sections,
        "assemblyState": "planned",
        "requestedDurationMs": sum(
            max(0, int(section.get("audioEndMs") or 0) - int(section.get("audioStartMs") or 0))
            for section in sections
        ),
        "completedDurationMs": 0,
        "status": JOB_QUEUED,
        "sharedStyleProfileId": f"avatar-style-{session_id}",
        "identityProfileRef": avatar_id,
        "presentationPlan": presentation_plan or _compose_presentation_plan(session_data),
        "scriptSource": _script_source_linkage(session_data),
        "voiceAsset": _voice_provenance(session_data),
        "audioMix": _audio_mix_linkage(session_data),
        "timelineProposal": None,
        "timelinePlacements": [],
        "assemblyVersion": 1,
        "retakeSummary": {},
        "transitionValidation": {"validated": False, "notes": "", "updatedAt": None},
        "createdAt": now,
        "updatedAt": now,
    }


class CreateSessionBody(BaseModel):
    name: str = "Avatar Session"
    character_profile_id: Optional[str] = None
    character_name: str = ""
    mode: str = "talking_portrait"
    bootstrap: dict[str, Any] = Field(default_factory=dict)


class TakeBody(BaseModel):
    asset_id: Optional[str] = None
    scene_id: Optional[str] = None
    label: str = "Take"
    status: str = "preview"
    performance_note: str = ""
    favorite: bool = False
    approved: bool = False


class CreateAvatarJobBody(BaseModel):
    providerId: Optional[str] = None
    scriptSourceId: Optional[str] = None
    startImmediately: bool = True
    overlapMs: Optional[int] = None
    targetSectionDurationMs: Optional[int] = None


class TransitionValidationBody(BaseModel):
    validated: bool = True
    notes: str = ""


class SectionRetakeBody(BaseModel):
    note: str = ""
    actionType: str = "regenerate_section"
    reason: str = ""


class TimelinePrepareBody(BaseModel):
    placementMode: str = "full_presentation"
    sectionId: Optional[str] = None
    replaceSectionId: Optional[str] = None
    trackId: Optional[str] = None
    startMs: int = 0
    confirmReplace: bool = False


@router.get("/projects/{project_id}/avatar-sessions")
def list_sessions(project_id: str, db: Session = Depends(get_db)):
    _project_or_404(db, project_id)
    rows = (
        db.query(AvatarSessionRow)
        .filter(AvatarSessionRow.project_id == project_id)
        .order_by(AvatarSessionRow.updated_at.desc())
        .all()
    )
    return [_row_to_data(r) for r in rows]


@router.post("/projects/{project_id}/avatar-sessions")
def create_session(project_id: str, body: CreateSessionBody, db: Session = Depends(get_db)):
    _project_or_404(db, project_id)
    data = _empty(project_id, body.name or "Avatar Session")
    data["mode"] = body.mode or "talking_portrait"
    if body.character_profile_id:
        data["character_profile_id"] = body.character_profile_id
    if body.character_name:
        data["character_name"] = body.character_name
    if body.bootstrap:
        data.update(
            {k: v for k, v in body.bootstrap.items() if k not in ("id", "project_id", "created_at")}
        )
        data["id"] = f"avs-{uuid.uuid4().hex[:10]}"
        data["project_id"] = project_id
        data["updated_at"] = _now()
    data["presentation_plan"] = _compose_presentation_plan(data, keep_existing=True)
    row = AvatarSessionRow(
        id=data["id"],
        project_id=project_id,
        name=data["name"],
        data_json=json.dumps(data, ensure_ascii=False),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    return data


@router.get("/projects/{project_id}/avatar-sessions/{session_id}")
def get_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = _session_or_404(db, project_id, session_id)
    return _row_to_data(row)


@router.patch("/projects/{project_id}/avatar-sessions/{session_id}")
def patch_session(project_id: str, session_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    row = _session_or_404(db, project_id, session_id)
    data = _row_to_data(row)
    for k, v in body.items():
        if k in ("id", "project_id", "created_at"):
            continue
        data[k] = v
    data["presentation_plan"] = _compose_presentation_plan(data, keep_existing=True)
    _write_session(row, data)
    db.commit()
    return data


@router.delete("/projects/{project_id}/avatar-sessions/{session_id}")
def delete_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = _session_or_404(db, project_id, session_id)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/avatar-sessions/{session_id}/validate")
def validate_session(project_id: str, session_id: str, db: Session = Depends(get_db)):
    row = _session_or_404(db, project_id, session_id)
    data = _row_to_data(row)
    issues = _validate(data)
    return {"ok": not any(i["level"] == "bad" for i in issues), "issues": issues}


@router.post("/projects/{project_id}/avatar-sessions/{session_id}/takes")
def add_take(project_id: str, session_id: str, body: TakeBody, db: Session = Depends(get_db)):
    row = _session_or_404(db, project_id, session_id)
    data = _row_to_data(row)
    takes = list(data.get("takes") or [])
    take = {
        "id": f"take-{uuid.uuid4().hex[:8]}",
        "label": body.label or f"Take {len(takes) + 1}",
        "asset_id": body.asset_id,
        "scene_id": body.scene_id,
        "status": body.status or "preview",
        "favorite": body.favorite,
        "approved": body.approved,
        "performance_note": body.performance_note,
        "created_at": _now(),
    }
    takes.append(take)
    data["takes"] = takes
    _write_session(row, data)
    db.commit()
    return take


@router.get("/projects/{project_id}/avatar-sessions/{session_id}/jobs")
def list_session_jobs(project_id: str, session_id: str, db: Session = Depends(get_db)):
    _session_or_404(db, project_id, session_id)
    rows = (
        db.query(AvatarProjectJobRow)
        .filter(
            AvatarProjectJobRow.project_id == project_id,
            AvatarProjectJobRow.session_id == session_id,
        )
        .order_by(AvatarProjectJobRow.updated_at.desc())
        .all()
    )
    return [_job_to_row_data(row) for row in rows]


@router.post("/projects/{project_id}/avatar-sessions/{session_id}/jobs")
def create_avatar_job(
    project_id: str, session_id: str, body: CreateAvatarJobBody, db: Session = Depends(get_db)
):
    session_row = _session_or_404(db, project_id, session_id)
    session_data = _row_to_data(session_row)
    _require_approved_voice(session_data)
    provider_id = _select_provider(session_data, body.providerId)
    plan_target_seconds = (
        (session_data.get("presentation_plan") or {}).get("sectionTargetSeconds")
        if isinstance(session_data.get("presentation_plan"), dict)
        else None
    )
    plan_target_ms = int(round(float(plan_target_seconds) * 1000)) if plan_target_seconds else 0
    target_duration_ms = max(
        2000,
        int(body.targetSectionDurationMs or plan_target_ms or _duration_class_ms(session_data)),
    )
    overlap_ms = max(0, int(body.overlapMs if body.overlapMs is not None else 250))
    session_data["presentation_plan"] = _compose_presentation_plan(
        session_data,
        target_duration_ms=target_duration_ms,
        keep_existing=True,
    )
    sections = _build_section_plan(
        session_data,
        provider_id=provider_id,
        target_duration_ms=target_duration_ms,
        overlap_ms=overlap_ms,
        script_source_id=body.scriptSourceId or _script_source_linkage(session_data).get("sceneHeadingId"),
    )
    job = _new_job(
        project_id,
        session_id,
        session_data,
        provider_id=provider_id,
        script_source_id=body.scriptSourceId or _script_source_linkage(session_data).get("sceneHeadingId"),
        sections=sections,
        presentation_plan=session_data.get("presentation_plan"),
    )
    job = _summarize_job(job)
    row = AvatarProjectJobRow(
        id=job["id"],
        project_id=project_id,
        session_id=session_id,
        avatar_id=job["avatarId"],
        provider_id=provider_id,
        status=job["status"],
        assembly_state=job["assemblyState"],
        data_json=json.dumps(job, ensure_ascii=False),
        created_at=job["createdAt"],
        updated_at=job["updatedAt"],
    )
    db.add(row)
    session_data["active_job_id"] = job["id"]
    _write_session(session_row, session_data)
    db.commit()
    if body.startImmediately:
        return _dispatch_job(row, session_data, db)
    return _job_to_row_data(row)


@router.get("/projects/{project_id}/avatar-jobs/{job_id}")
def get_avatar_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/pause")
def pause_avatar_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    if job.get("status") not in (JOB_QUEUED, JOB_GENERATING):
        raise _raise_avatar_error(AvatarErrorCode.JOB_NOT_PAUSABLE)
    job["status"] = JOB_PAUSED
    for section in job.get("sections") or []:
        if section.get("status") == SECTION_RUNNING:
            section["status"] = SECTION_QUEUED
    _write_job(row, job)
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/resume")
def resume_avatar_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    if job.get("status") not in (JOB_PAUSED, JOB_FAILED, JOB_QUEUED):
        raise _raise_avatar_error(AvatarErrorCode.JOB_NOT_RESUMABLE)
    for section in job.get("sections") or []:
        if section.get("status") in (SECTION_PENDING, SECTION_RETAKE_REQUESTED):
            section["status"] = SECTION_QUEUED
    job["status"] = JOB_QUEUED
    _write_job(row, job)
    db.commit()
    session_row = _session_or_404(db, project_id, row.session_id)
    return _dispatch_job(row, _row_to_data(session_row), db)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/cancel")
def cancel_avatar_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    if job.get("status") in (JOB_COMPLETED, JOB_CANCELLED):
        raise _raise_avatar_error(AvatarErrorCode.JOB_NOT_CANCELLABLE)
    for section in job.get("sections") or []:
        if section.get("status") in (SECTION_PENDING, SECTION_QUEUED, SECTION_RUNNING):
            section["status"] = SECTION_FAILED
            section["errorCode"] = AvatarErrorCode.SECTION_CANCELLED.value
            section["errorMessage"] = ERROR_DETAILS[AvatarErrorCode.SECTION_CANCELLED]["message"]
            section["updatedAt"] = _now()
    job["status"] = JOB_CANCELLED
    job["assemblyState"] = "cancelled"
    _write_job(row, job)
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/transition-validation")
def validate_avatar_transitions(
    project_id: str,
    job_id: str,
    body: TransitionValidationBody,
    db: Session = Depends(get_db),
):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    job["transitionValidation"] = {
        "validated": bool(body.validated),
        "notes": body.notes,
        "updatedAt": _now(),
    }
    if body.validated:
        job["assemblyState"] = "validated"
    _write_job(row, job)
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/sections/{section_id}/retry")
def retry_avatar_section(project_id: str, job_id: str, section_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    section = _section_or_404(job, section_id)
    if section.get("status") != SECTION_FAILED:
        raise _raise_avatar_error(AvatarErrorCode.SECTION_NOT_RETRIABLE)
    section["status"] = SECTION_QUEUED
    section["errorCode"] = None
    section["errorMessage"] = None
    section["providerJobId"] = None
    section["attempt"] = int(section.get("attempt") or 1) + 1
    section["retryCount"] = int(section.get("retryCount") or 0) + 1
    section["updatedAt"] = _now()
    job["status"] = JOB_QUEUED
    job["assemblyState"] = "planned"
    _write_job(row, job)
    db.commit()
    session_row = _session_or_404(db, project_id, row.session_id)
    return _dispatch_job(row, _row_to_data(session_row), db)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/sections/{section_id}/retake")
def request_avatar_section_retake(
    project_id: str,
    job_id: str,
    section_id: str,
    body: SectionRetakeBody,
    db: Session = Depends(get_db),
):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    section = _section_or_404(job, section_id)
    if section.get("status") not in (SECTION_COMPLETED, SECTION_APPROVED):
        raise _raise_avatar_error(AvatarErrorCode.SECTION_NOT_RETRIABLE)
    action_type = str(body.actionType or "regenerate_section").strip() or "regenerate_section"
    reason = str(body.reason or body.note or action_type.replace("_", " ")).strip()
    version_history = list(section.get("versionHistory") or [])
    snapshot = _snapshot_section_version(section, reason=reason, action_type=action_type)
    version_history.append(snapshot)
    neighboring_context = _neighboring_context(job, section_id)
    retake_history = list(section.get("retakeHistory") or [])
    retake_entry = {
        "id": f"retake-{uuid.uuid4().hex[:10]}",
        "actionType": action_type,
        "reason": reason,
        "note": body.note,
        "requestedAt": _now(),
        "preservedVersionId": snapshot["id"],
        "preservedOutputVideoAssetId": snapshot.get("outputVideoAssetId"),
        "neighboringContext": neighboring_context,
    }
    retake_history.append(retake_entry)
    section["status"] = SECTION_RETAKE_REQUESTED
    section["retakeNote"] = body.note
    section["retakeReason"] = reason
    section["retakeActionType"] = action_type
    section["retakeRequest"] = retake_entry
    section["versionHistory"] = version_history
    section["retakeHistory"] = retake_history
    section["currentVersionId"] = snapshot["id"]
    section["updatedAt"] = _now()
    job["status"] = JOB_QUEUED
    job["assemblyState"] = "planned"
    job["retakeSummary"] = {
        str(item.get("id")): len(item.get("retakeHistory") or [])
        for item in job.get("sections") or []
    }
    _write_job(row, job)
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/sections/{section_id}/approve")
def approve_avatar_section(project_id: str, job_id: str, section_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    section = _section_or_404(job, section_id)
    if section.get("status") not in (SECTION_COMPLETED, SECTION_APPROVED):
        raise _raise_avatar_error(AvatarErrorCode.SECTION_NOT_RETRIABLE)
    section["status"] = SECTION_APPROVED
    section["updatedAt"] = _now()
    _write_job(row, _summarize_job(job))
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/assemble")
def assemble_avatar_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    sections = list(job.get("sections") or [])
    if not sections:
        raise _raise_avatar_error(AvatarErrorCode.ASSEMBLY_EMPTY)
    incomplete = [
        section
        for section in sections
        if section.get("status") not in (SECTION_COMPLETED, SECTION_APPROVED)
    ]
    if incomplete:
        job["assemblyState"] = "waiting_for_section_retry"
        _write_job(row, job)
        db.commit()
        raise _raise_avatar_error(
            AvatarErrorCode.ASSEMBLY_INCOMPLETE,
            details={"blockingSectionIds": [section.get("id") for section in incomplete]},
        )
    if not bool((job.get("transitionValidation") or {}).get("validated")):
        job["assemblyState"] = "transition_validation_required"
        _write_job(row, job)
        db.commit()
        raise _raise_avatar_error(AvatarErrorCode.ASSEMBLY_TRANSITION_VALIDATION_REQUIRED)
    job["status"] = JOB_COMPLETED
    job["assemblyState"] = "assembled_stub"
    job["assembly"] = {
        "compositeVideoAssetId": None,
        "stub": True,
        "message": "Assembly contract passed, but this pass does not render a final composite video yet.",
        "validatedAt": (job.get("transitionValidation") or {}).get("updatedAt"),
        "provenance": {
            "assemblyVersion": int(job.get("assemblyVersion") or 1),
            "scriptSource": job.get("scriptSource") or {},
            "voiceAsset": job.get("voiceAsset") or {},
            "sectionMap": [
                {
                    "sectionId": section.get("id"),
                    "status": section.get("status"),
                    "versionHistory": section.get("versionHistory") or [],
                    "retakeHistory": section.get("retakeHistory") or [],
                }
                for section in sections
            ],
        },
    }
    _write_job(row, job)
    db.commit()
    return _job_to_row_data(row)


@router.post("/projects/{project_id}/avatar-jobs/{job_id}/timeline/prepare")
def prepare_avatar_timeline(
    project_id: str,
    job_id: str,
    body: TimelinePrepareBody,
    db: Session = Depends(get_db),
):
    row = _job_or_404(db, project_id, job_id)
    job = _job_to_row_data(row)
    session_row = _session_or_404(db, project_id, job["sessionId"])
    session = _row_to_data(session_row)
    placement_mode = str(body.placementMode or "full_presentation").strip() or "full_presentation"
    proposal = _build_timeline_proposal(
        session=session,
        job=job,
        placement_mode=placement_mode,
        selected_section_id=body.sectionId,
        replace_section_id=body.replaceSectionId,
        track_id=body.trackId,
        start_ms=body.startMs,
    )
    job["timelineProposal"] = proposal
    _write_job(row, job)
    db.commit()
    return {
        "ok": True,
        "job": _job_to_row_data(row),
        "timelineProposal": proposal,
        "timelineWritten": False,
    }
