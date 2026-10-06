"""Capability handler: timeline.deposit_video

Wave 4 Omni — Co-Director deposits a completed 1F/3F Library VIDEO onto
Timeline Visual via the Wave 2B omni_visual_export contract.

Does NOT regenerate. Does NOT enqueue Comfy. Does NOT change 1F/3F generation
internals. Soft-depend: video → video_clips / media_mode=video / mediaType=video.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

_ASSET_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ONE_FRAME_RE = re.compile(r"\b(?:1\s*f(?:rame)?|one[\s-]?frame|i2v)\b", re.I)
_THREE_FRAME_RE = re.compile(r"\b(?:3\s*f(?:rame)?|three[\s-]?frame|multi[\s-]?frame)\b", re.I)
_OMNI_TAG_RE = re.compile(
    r"(?:one[\s_-]?frame|three[\s_-]?frame|1f|3f|minimax|h3|route[\s_-]?a|i2v)",
    re.I,
)


def infer_source_surface(text: str, explicit: str | None = None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    blob = text or ""
    if _THREE_FRAME_RE.search(blob):
        return "three-frame"
    if _ONE_FRAME_RE.search(blob):
        return "one-frame"
    return "codirector"


def _is_project_asset(asset: Any, project_id: str) -> bool:
    return asset is not None and str(getattr(asset, "project_id", "") or "") == project_id


def _is_project_video(asset: Any, project_id: str) -> bool:
    return _is_project_asset(asset, project_id) and str(getattr(asset, "kind", "") or "").lower() == "video"


def resolve_completed_video_asset_id(
    db: Session,
    project_id: str,
    *,
    prompt: str = "",
    attachment_asset_ids: list[str] | None = None,
    reference_asset_id: str = "",
) -> tuple[str, str]:
    """Return (asset_id, error_code). error_code empty on success.

    Explicit attachments/UUIDs are authoritative: non-video → VIDEO_REQUIRED.
    Only when no explicit candidate was supplied do we fall back to latest Omni video.
    """
    from ....db import Asset

    candidates: list[str] = []
    ref = str(reference_asset_id or "").strip()
    if ref:
        candidates.append(ref)
    for raw in attachment_asset_ids or []:
        uid = str(raw or "").strip()
        if uid and uid not in candidates:
            candidates.append(uid)
    for uid in _ASSET_UUID_RE.findall(prompt or ""):
        if uid not in candidates:
            candidates.append(uid)

    if candidates:
        for uid in candidates:
            asset = db.get(Asset, uid)
            if not _is_project_asset(asset, project_id):
                continue
            if _is_project_video(asset, project_id):
                return uid, ""
            return uid, "VIDEO_REQUIRED"
        return "", "ASSET_OWNERSHIP"

    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.kind == "video")
        .order_by(Asset.created_at.desc())
        .all()
    )
    best: tuple[int, str] | None = None
    for asset in rows:
        blob = " ".join(
            [
                str(getattr(asset, "tag", "") or ""),
                str(getattr(asset, "filename", "") or ""),
                str(getattr(asset, "prompt_meta_json", "") or ""),
            ]
        )
        score = 1
        if _OMNI_TAG_RE.search(blob):
            score += 4
        if _THREE_FRAME_RE.search(blob) or _ONE_FRAME_RE.search(blob):
            score += 2
        if best is None or score > best[0]:
            best = (score, str(asset.id))
    return (best[1], "") if best else ("", "ASSET_REQUIRED")


def resolve_deposit_scene_id(
    db: Session,
    project_id: str,
    *,
    scene_id: str = "",
) -> str:
    sid = str(scene_id or "").strip()
    if sid:
        return sid
    try:
        from ...project_grounding import build_project_grounding_snapshot

        snap = build_project_grounding_snapshot(db, project_id, None, workspace="timeline")
        active = snap.get("activeScene") or {}
        return str(active.get("id") or active.get("sceneId") or "").strip()
    except Exception:
        return ""


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    user_instructions: str = "",
    attachment_asset_ids: list[str] | None = None,
    reference_asset_id: str = "",
    scene_id: str = "",
    label: str = "",
    source_surface: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Deposit completed video onto Timeline Visual — no regeneration."""
    from ....director_timeline_w46.generation.canonical_generation_media import (
        classify_visual_placement,
    )
    from ....director_timeline_w46.generation.omni_visual_export import (
        export_completed_video_to_timeline,
    )
    from ....db import Asset

    speech = user_instructions or prompt
    surface = infer_source_surface(speech, source_surface or None)
    sid = resolve_deposit_scene_id(db, project_id, scene_id=scene_id)
    if not sid:
        return {
            "error": "Select a Timeline scene before depositing a completed video to Visual.",
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
        }

    asset_id, resolve_err = resolve_completed_video_asset_id(
        db,
        project_id,
        prompt=speech,
        attachment_asset_ids=attachment_asset_ids,
        reference_asset_id=reference_asset_id,
    )
    if resolve_err == "VIDEO_REQUIRED":
        return {
            "error": "Export to Timeline Visual accepts completed video only (image = reference).",
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
            "errorCode": "VIDEO_REQUIRED",
        }
    if not asset_id:
        return {
            "error": "No completed video asset was found to deposit. Attach a Library video or finish a 1F/3F take first.",
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
            "errorCode": resolve_err or "ASSET_REQUIRED",
        }

    asset = db.get(Asset, asset_id)
    kind = str(getattr(asset, "kind", "") or "").lower() if asset else ""
    try:
        cgm = classify_visual_placement(
            asset_id=asset_id,
            kind=kind or "video",
            label=label or None,
            source_surface=surface,
        )
    except ValueError as exc:
        return {
            "error": f"Deposit rejected: {exc}",
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
        }
    if cgm.mediaType != "video" or cgm.role != "visual_take":
        return {
            "error": "Export to Timeline Visual accepts completed video only (image = reference).",
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
            "errorCode": "VIDEO_REQUIRED",
        }

    result = export_completed_video_to_timeline(
        db,
        project_id,
        sid,
        asset_id,
        label=label or getattr(asset, "tag", None) or "Co-Director deposit",
        source_surface=surface,
    )
    if not result.get("ok"):
        code = str(result.get("error") or "EXPORT_FAILED")
        message = str(result.get("message") or code)
        return {
            "error": message,
            "errorCode": code,
            "child_jobs": [],
            "surface_type": "timeline_deposit",
            "status": "failed",
            "plan_data": {"deposit": result, "cgm": cgm.model_dump()},
        }

    job_id = str(execution_id or uuid4())
    ack = (
        f"Deposited the completed {surface} video onto Timeline Visual "
        f"(mediaType=video, media_mode=video). No regenerate."
    )
    return {
        "status": "completed",
        "result_asset_ids": [asset_id],
        "job_ids": [job_id],
        "child_jobs": [
            {
                "job_id": job_id,
                "label": "Deposit video to Timeline Visual",
                "status": "completed",
                "child_index": 0,
                "asset_id": asset_id,
                "metadata": {
                    "mediaType": "video",
                    "mediaMode": "video",
                    "visualClipId": result.get("visualClipId"),
                    "sourceSurface": surface,
                    "sceneId": sid,
                    "regenerated": False,
                    "cgmRole": cgm.role,
                },
            }
        ],
        "surface_type": "timeline_deposit",
        "creatorAck": ack,
        "plan_data": {
            "deposit": result,
            "cgm": cgm.model_dump(),
            "regenerated": False,
            "mediaType": "video",
            "mediaMode": "video",
        },
        "message": ack,
    }
