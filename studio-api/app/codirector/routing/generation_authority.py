"""Co-Director generation authority: first-frame, animate-it, standalone vs Timeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from ...db import Asset, Job, ProjectTraitRow


AUTHORITY_CATEGORY = "codirector_generation_authority"
LAST_FIRST_FRAME_KEY = "last_first_frame"

_FIRST_FRAME_RE = re.compile(
    r"\b(?:create|generate|make|render|draw)\b.+\bfirst\s+frame\b",
    re.I,
)
_ANIMATE_IT_RE = re.compile(
    r"\b(?:animate\s+(?:it|this|that)|make\s+(?:it|this|that)\s+(?:a\s+)?(?:video|clip)|"
    r"turn\s+(?:it|this|that)\s+into\s+(?:a\s+)?(?:video|clip))\b",
    re.I,
)
_STANDALONE_T2V_RE = re.compile(
    r"\b(?:create|generate|make|render)\b.+\b(?:text[- ]to[- ]video|t2v)\b",
    re.I,
)
_STANDALONE_I2V_RE = re.compile(
    r"\b(?:create|generate|make|render)\b.+\bvideo\b.+\b(?:this|that|the)\s+(?:frame|image|still|picture)\b",
    re.I,
)
_STANDALONE_VIDEO_VERSION_RE = re.compile(
    r"\b(?:create|generate|make|render)\b.+\bvideo\s+version\b.+\b(?:this|that|the)\b",
    re.I,
)
_STANDALONE_MULTI_RE = re.compile(
    r"\b(?:create|generate|make|render)\b.+\b(?:3|three)[- ]frame\b.+\bvideo\b",
    re.I,
)
_STANDALONE_VIDEO_RE = re.compile(
    r"\b(?:create|generate|make|render)\b.+\b(?:a\s+)?(?:video|clip)\b",
    re.I,
)
_TIMELINE_PREPARE_RE = re.compile(
    r"\b(?:put|add|place|move|insert)\b.+\b(?:shot|track|batch)\s*\d+.+\b(?:on|to|into|in)\s+(?:the\s+)?timeline\b",
    re.I,
)
_TIMELINE_SCENE_PREPARE_RE = re.compile(
    # "<verb> a scene ... in Timeline" (scene-first phrasing)
    r"\b(?:build|create|make|prepare|set\s+up|write|draft|produce|generate|render)\b.+\b(?:scene|establishing\s+shot|shot)\b.+\btimeline\b"
    # "<verb> a Timeline scene/prompt/shot ..." (Timeline-first phrasing — the
    # most natural creator order: "Create a Timeline scene using …")
    r"|\b(?:build|create|make|prepare|set\s+up|write|draft|produce|generate|render)\b.+\btimeline\b.+\b(?:scene|prompt|establishing\s+shot)\b"
    r"|\b(?:build|create|make|prepare|set\s+up)\s+(?:this|a|the)\s+scene\b"
    r"|\bscene\s+will\s+be\s+created\s+in\s+timeline\b",
    re.I,
)
_TIMELINE_GENERATE_SHOT_RE = re.compile(
    r"\b(?:generate|render|run)\s+(?:this\s+|that\s+|the\s+)?shot\s*(\d+)\b",
    re.I,
)
_TIMELINE_GENERATE_TRACK_RE = re.compile(
    r"\b(?:generate|render|run)\s+(?:this\s+|that\s+|the\s+)?(?:track|batch)\b",
    re.I,
)
_EXPLICIT_VIDEO_JOB_RE = re.compile(
    r"\buse\s+(ltx|kling|seedance|see\s*dance|minimax(?:\s*-?\s*h3)?|wan|hunyuan(?:15|13b)?)"
    r"(?:\s+for this(?:\s+(?:one|shot|clip|video|take))?)\b",
    re.I,
)
_NAMED_VIDEO_ENGINE_RE = re.compile(
    r"\b(?:"
    r"minimax(?:\s*-?\s*h3)?|\bh3\b|"
    r"ltx(?:\s*-?\s*2(?:[.\s]*[35])?)?|"
    r"seedance|see\s*dance|kling|"
    r"hunyuan(?:\s*1[35]b)?|\bwan(?:\s*2(?:\.\d+)?)?\b"
    r")\b",
    re.I,
)
_DURATION_VIDEO_SHOT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*-?\s*seconds?\b.+\b(?:shot|clip|video|take)\b"
    r"|\b(?:shot|clip|video|take)\b.+\b\d+(?:\.\d+)?\s*-?\s*seconds?\b",
    re.I,
)
_TIMELINE_WORKSPACES = frozenset({"timeline", "timeline_suite", "director", "editor"})
_INTERROGATIVE_VIDEO_RE = re.compile(
    r"\b(?:did you|do you|confirm|job id|right\?|what did you|you just generated|"
    r"explain|tell me how)\b"
    r"|^\s*(?:what|why|which|who|how)\b",
    re.I,
)


def looks_like_video_production_request(message: str) -> bool:
    """True when the ask is a video take, not a still picture.

    Creators say “5-second MiniMax H3 shot” without the words video/clip/t2v.
    That must not collapse into image.generate.
    """

    text = message or ""
    if not text.strip():
        return False
    if _INTERROGATIVE_VIDEO_RE.search(text):
        return False
    if is_first_frame_request(text):
        return False
    if is_standalone_video_request(text):
        return True
    if _EXPLICIT_VIDEO_JOB_RE.search(text):
        return True
    if _NAMED_VIDEO_ENGINE_RE.search(text) and re.search(
        r"\b(?:shot|clip|video|take|t2v|i2v|r2v)\b", text, re.I
    ):
        return True
    if _DURATION_VIDEO_SHOT_RE.search(text):
        return True
    return False


@dataclass(frozen=True)
class GenerationAuthority:
    capability: str
    kind: str
    owner: str  # "codirector" | "timeline"
    production_role: str = ""
    shot_index: Optional[int] = None
    video_mode: str = ""  # t2v | i2v | multi_frame | animate


def is_first_frame_request(message: str) -> bool:
    return bool(_FIRST_FRAME_RE.search(message or ""))


def is_animate_it_request(message: str) -> bool:
    return bool(_ANIMATE_IT_RE.search(message or ""))


def is_timeline_prepare_request(message: str) -> bool:
    return bool(_TIMELINE_PREPARE_RE.search(message or ""))


def is_timeline_scene_prepare_request(message: str) -> bool:
    text = message or ""
    if _TIMELINE_GENERATE_SHOT_RE.search(text):
        return False
    return bool(_TIMELINE_SCENE_PREPARE_RE.search(text))


def is_timeline_owned_generation(message: str) -> bool:
    text = message or ""
    if _TIMELINE_GENERATE_SHOT_RE.search(text):
        return True
    if _TIMELINE_GENERATE_TRACK_RE.search(text) and re.search(r"\btimeline\b", text, re.I):
        return True
    return False


def is_standalone_video_request(message: str) -> bool:
    text = message or ""
    if is_timeline_owned_generation(text) or is_timeline_prepare_request(text):
        return False
    if is_animate_it_request(text):
        return True
    if _STANDALONE_T2V_RE.search(text) or _STANDALONE_I2V_RE.search(text) or _STANDALONE_MULTI_RE.search(text):
        return True
    if _STANDALONE_VIDEO_RE.search(text):
        return True
    return False


def classify_generation_authority(
    message: str,
    *,
    workspace: str | None = None,
) -> Optional[GenerationAuthority]:
    text = message or ""
    tab = str(workspace or "").strip().lower()
    from .atlas_intent import atlas_capability_for_message

    atlas_cap = atlas_capability_for_message(text)
    if atlas_cap == "atlas.assign":
        return GenerationAuthority(
            capability="atlas.assign",
            kind="atlas_assign",
            owner="codirector",
        )
    if atlas_cap == "atlas.generate":
        return GenerationAuthority(
            capability="atlas.generate",
            kind="atlas_generate",
            owner="codirector",
        )
    if is_timeline_prepare_request(text):
        return GenerationAuthority(
            capability="timeline.add_asset",
            kind="timeline_prepare",
            owner="timeline",
        )
    if is_timeline_scene_prepare_request(text):
        return GenerationAuthority(
            capability="timeline.prepare_scene",
            kind="timeline_scene_prepare",
            owner="timeline",
        )
    shot = _TIMELINE_GENERATE_SHOT_RE.search(text)
    if shot:
        return GenerationAuthority(
            capability="timeline.generate_shot",
            kind="timeline_owned_generation",
            owner="timeline",
            shot_index=int(shot.group(1)),
        )
    if is_timeline_owned_generation(text):
        return GenerationAuthority(
            capability="timeline.generate_shot",
            kind="timeline_owned_generation",
            owner="timeline",
        )
    if is_first_frame_request(text):
        return GenerationAuthority(
            capability="image.generate",
            kind="first_frame",
            owner="codirector",
            production_role="video_first_frame",
        )
    if is_animate_it_request(text):
        return GenerationAuthority(
            capability="video.generate",
            kind="animate_it",
            owner="codirector",
            video_mode="i2v",
        )
    timeline_surface = tab in _TIMELINE_WORKSPACES or bool(re.search(r"\btimeline\b", text, re.I))
    if timeline_surface and _INTERROGATIVE_VIDEO_RE.search(text):
        return None
    if timeline_surface and (
        is_standalone_video_request(text) or looks_like_video_production_request(text)
    ):
        return GenerationAuthority(
            capability="timeline.prepare_scene",
            kind="timeline_scene_prepare",
            owner="timeline",
        )
    if _EXPLICIT_VIDEO_JOB_RE.search(text):
        # Job-scoped provider only. Do not assume I2V — that blocked bare T2V.
        return GenerationAuthority(
            capability="video.generate",
            kind="standalone_video",
            owner="codirector",
            video_mode="t2v",
        )
    if _STANDALONE_MULTI_RE.search(text):
        return GenerationAuthority(
            capability="video.generate",
            kind="standalone_video",
            owner="codirector",
            video_mode="multi_frame",
        )
    if _STANDALONE_I2V_RE.search(text) or _STANDALONE_VIDEO_VERSION_RE.search(text):
        return GenerationAuthority(
            capability="video.generate",
            kind="standalone_video",
            owner="codirector",
            video_mode="i2v",
        )
    if _STANDALONE_T2V_RE.search(text) or _STANDALONE_VIDEO_RE.search(text):
        return GenerationAuthority(
            capability="video.generate",
            kind="standalone_video",
            owner="codirector",
            video_mode="t2v",
        )
    if looks_like_video_production_request(text):
        if tab in _TIMELINE_WORKSPACES:
            return GenerationAuthority(
                capability="timeline.prepare_scene",
                kind="timeline_scene_prepare",
                owner="timeline",
            )
        return GenerationAuthority(
            capability="video.generate",
            kind="standalone_video",
            owner="codirector",
            video_mode="t2v",
        )
    return None


def remember_first_frame(
    db: Session,
    project_id: str,
    *,
    execution_id: str,
    job_id: str = "",
    asset_id: str = "",
    intended_video_provider: str = "",
    prompt: str = "",
) -> None:
    payload = {
        "executionId": execution_id,
        "jobId": job_id,
        "assetId": asset_id,
        "intendedVideoProvider": intended_video_provider,
        "prompt": prompt,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == AUTHORITY_CATEGORY,
            ProjectTraitRow.key == LAST_FIRST_FRAME_KEY,
        )
        .first()
    )
    raw = json.dumps(payload)
    if row:
        row.value = raw
        row.provenance = "CODEX_GENERATION_AUTHORITY"
    else:
        db.add(
            ProjectTraitRow(
                id=str(uuid4()),
                project_id=project_id,
                category=AUTHORITY_CATEGORY,
                key=LAST_FIRST_FRAME_KEY,
                value=raw,
                provenance="CODEX_GENERATION_AUTHORITY",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    db.commit()


def load_last_first_frame(db: Session, project_id: str) -> dict[str, Any]:
    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == AUTHORITY_CATEGORY,
            ProjectTraitRow.key == LAST_FIRST_FRAME_KEY,
        )
        .first()
    )
    if row is None or not row.value:
        return {}
    try:
        data = json.loads(row.value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_job_output_asset_id(params: dict[str, Any] | None) -> str:
    """Canonical Job output id. Inbound aliases collapse to output_asset_id."""

    data = params or {}
    raw = data.get("output_asset_id")
    if raw in (None, ""):
        raw = data.get("outputAssetId")
    if raw in (None, "") and isinstance(data.get("outputAssetIds"), list) and data["outputAssetIds"]:
        raw = data["outputAssetIds"][0]
    if raw in (None, ""):
        raw = data.get("resultAssetId") or data.get("assetId")
    if isinstance(raw, list) and raw:
        raw = raw[0]
    return str(raw or "").strip()


def resolve_animate_source_asset(db: Session, project_id: str) -> Optional[str]:
    """Resolve 'it' to the most recent first-frame asset for this project."""

    remembered = load_last_first_frame(db, project_id)
    asset_id = str(remembered.get("assetId") or "").strip()
    if asset_id:
        asset = db.get(Asset, asset_id)
        if asset is not None and asset.project_id == project_id:
            return asset.id

    job_id = str(remembered.get("jobId") or "").strip()
    if job_id:
        job = db.get(Job, job_id)
        if job is not None and job.project_id == project_id:
            try:
                params = json.loads(job.params_json or "{}")
            except Exception:
                params = {}
            candidate = normalize_job_output_asset_id(params)
            if candidate:
                return candidate

    recent = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.kind == "image")
        .order_by(Asset.created_at.desc())
        .limit(8)
        .all()
    )
    first_frames = []
    for asset in recent:
        try:
            meta = json.loads(asset.prompt_meta_json or "{}")
        except Exception:
            meta = {}
        if str(meta.get("productionRole") or "") == "video_first_frame":
            first_frames.append(asset.id)
    if first_frames:
        return first_frames[0]
    if recent:
        return recent[0].id
    return None


def is_action_first_generation_turn(message: str) -> bool:
    """True when Co-Director must dispatch generate now (not Timeline prepare)."""

    from .atlas_intent import is_atlas_assign_request, is_atlas_generate_request

    if is_atlas_generate_request(message):
        return True
    if is_atlas_assign_request(message):
        return False
    authority = classify_generation_authority(message)
    if authority is None:
        return False
    return authority.capability in {
        "image.generate",
        "video.generate",
        "timeline.generate_shot",
    }
