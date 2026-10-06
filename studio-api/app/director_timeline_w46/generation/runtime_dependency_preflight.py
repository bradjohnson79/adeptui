"""Verify Timeline generation dependencies before an expensive H3 job.

Durable identity stays on Library asset / voice profile ids. Staging into
Comfy input is a runtime step, never the stored identity.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset
from ...video_runtime.comfy_asset_stage import (
    ComfyAssetMissing,
    ComfyAssetStagingFailed,
    stage_h3_visual_asset,
    stage_library_asset,
)
from ...workflows.h3_ref2v_builder import (
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    frames_for_duration,
    resolve_h3_ref_image_size,
)
from .contracts import TimelineGenerationRequest
from .direct_reference import has_direct_reference_authority
from .r2v import H3_MECHANISM


def _label(slot: dict[str, Any], fallback: str) -> str:
    return str(slot.get("label") or slot.get("identityName") or fallback).strip() or fallback


def _is_h3(request: TimelineGenerationRequest) -> bool:
    gid = str(request.generatorId or "").lower()
    mech = str(((request.providerOptions or {}).get("r2v") or {}).get("mechanism") or "")
    return gid.startswith("minimax-h3") or mech == H3_MECHANISM




H3_REF_DURATION_MIN_SEC = 2.0
H3_REF_DURATION_MAX_SEC = 15.0
H3_REF_DURATION_TOTAL_MAX_SEC = 15.0


def _asset_duration_sec(asset: Asset | None) -> float | None:
    if asset is None:
        return None
    raw = getattr(asset, "duration_sec", None)
    try:
        value = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        value = 0.0
    if value > 0:
        return value
    meta_raw = getattr(asset, "prompt_meta_json", None) or ""
    if isinstance(meta_raw, str) and meta_raw.strip():
        try:
            import json

            meta = json.loads(meta_raw)
            if isinstance(meta, dict):
                for key in ("duration_sec", "duration", "durationSec"):
                    try:
                        cand = float(meta.get(key) or 0)
                    except (TypeError, ValueError):
                        cand = 0.0
                    if cand > 0:
                        return cand
        except Exception:
            pass
    return None


def _validate_h3_av_duration_guards(
    db: Session,
    slots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Refuse invalid MiniMax AV reference durations. Never silent-drop."""
    video_total = 0.0
    audio_total = 0.0
    for slot in slots:
        role = str(slot.get("role") or "").strip().lower()
        if role not in {"video", "audio"}:
            continue
        asset_id = str(slot.get("assetId") or "").strip()
        if not asset_id:
            continue
        if role == "video" and slot.get("videoIndex") is None:
            continue
        if role == "audio" and slot.get("audioIndex") is None:
            continue
        asset = db.get(Asset, asset_id)
        label = _label(slot, "A reference")
        duration = _asset_duration_sec(asset)
        if duration is None:
            return {
                "ok": False,
                "error": "H3_REF_DURATION_UNKNOWN",
                "message": (
                    f"{label} needs a known duration between "
                    f"{H3_REF_DURATION_MIN_SEC:.0f}–{H3_REF_DURATION_MAX_SEC:.0f}s "
                    "before MiniMax can use it as a reference."
                ),
            }
        if duration < H3_REF_DURATION_MIN_SEC - 1e-6 or duration > H3_REF_DURATION_MAX_SEC + 1e-6:
            return {
                "ok": False,
                "error": "H3_REF_DURATION_OUT_OF_RANGE",
                "message": (
                    f"{label} is {duration:.1f}s. MiniMax reference "
                    f"{'videos' if role == 'video' else 'audios'} must be "
                    f"{H3_REF_DURATION_MIN_SEC:.0f}–{H3_REF_DURATION_MAX_SEC:.0f}s each."
                ),
            }
        if role == "video":
            video_total += duration
        else:
            audio_total += duration
    if video_total > H3_REF_DURATION_TOTAL_MAX_SEC + 1e-6:
        return {
            "ok": False,
            "error": "H3_REF_VIDEO_DURATION_TOTAL",
            "message": (
                f"Video references total {video_total:.1f}s. MiniMax allows at most "
                f"{H3_REF_DURATION_TOTAL_MAX_SEC:.0f}s of video reference media."
            ),
        }
    if audio_total > H3_REF_DURATION_TOTAL_MAX_SEC + 1e-6:
        return {
            "ok": False,
            "error": "H3_REF_AUDIO_DURATION_TOTAL",
            "message": (
                f"Audio references total {audio_total:.1f}s. MiniMax allows at most "
                f"{H3_REF_DURATION_TOTAL_MAX_SEC:.0f}s of audio reference media."
            ),
        }
    return None

def preflight_generation_dependencies(
    db: Session,
    request: TimelineGenerationRequest,
) -> dict[str, Any]:
    """Fail closed before queueing when a required Library file cannot be staged."""
    r2v = (request.providerOptions or {}).get("r2v") if request.providerOptions else {}
    slots = [item for item in (r2v.get("slots") or []) if isinstance(item, dict)]
    voices_meta = (request.providerOptions or {}).get("characterVoices") or {}
    missing_voices = [str(name).strip() for name in (voices_meta.get("missing") or []) if str(name).strip()]
    report: dict[str, Any] = {
        "videoSource": "N/A",
        "pictures": [],
        "voices": [],
        "workflow": "N/A",
        "staged": [],
    }

    range_rep = (request.providerOptions or {}).get("rangeReplacement") or {}
    source_id = str(range_rep.get("sourceAssetId") or "").strip()
    if source_id:
        from pathlib import Path

        source = db.get(Asset, source_id)
        path = Path(str(getattr(source, "path", "") or "")) if source is not None else None
        if source is None or path is None or not path.is_file() or path.stat().st_size <= 0:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": "The current take video is missing from the Library.",
                "dependencies": {**report, "videoSource": "MISSING"},
            }
        report["videoSource"] = "READY"

    if not _is_h3(request):
        request.providerOptions = dict(request.providerOptions or {})
        request.providerOptions["runtimeDependencies"] = report
        return {"ok": True, "dependencies": report}

    # H3 FM3: Front transport packing (Front into ref sockets when Front exists).
    from .h3_front_identity import apply_h3_front_identity_to_request

    front_gate = apply_h3_front_identity_to_request(db, request)
    kept = front_gate.get("frontAvailableKeptCrs") or []
    report["h3FrontIdentity"] = {
        "status": (
            "REMAPPED" if front_gate.get("replaced") else (
                "WARN_CRS_ONLY" if front_gate.get("crsOnly") else (
                    "CRS_KEPT" if kept else "OK"
                )
            )
        ),
        "replaced": front_gate.get("replaced") or [],
        "crsOnly": front_gate.get("crsOnly") or [],
        "frontAvailableKeptCrs": kept,
        "warnings": front_gate.get("warnings") or [],
        "policy": front_gate.get("policy") or "h3_front_transport",
    }
    # Refresh slots after Front transport packing.
    r2v = (request.providerOptions or {}).get("r2v") if request.providerOptions else {}
    slots = [item for item in (r2v.get("slots") or []) if isinstance(item, dict)]

    if missing_voices:
        # Voices are OPTIONAL, not a generation blocker. A character without
        # an approved voice simply won't speak (no lip-sync audio). The H3
        # workflow runs fine with pictures only. Record the gap as a warning
        # in the dependency report so the UI can surface it, but do NOT block.
        report["voices"] = [{"label": name, "status": "MISSING"} for name in missing_voices]
        report["voiceWarnings"] = [
            {"label": name, "status": "MISSING", "message": f"{name} doesn't have an approved voice — this character won't speak in the generated video."}
            for name in missing_voices
        ]

    duration_gate = _validate_h3_av_duration_guards(db, slots) if _is_h3(request) else None
    if duration_gate is not None:
        return {**duration_gate, "dependencies": report}

    staged_images: list[str] = []
    staged_audio: list[str] = []
    staged_videos: list[str] = []
    report.setdefault("videos", [])
    for slot in slots:
        role = str(slot.get("role") or "").strip().lower()
        asset_id = str(slot.get("assetId") or "").strip()
        if not asset_id:
            continue
        if role == "audio" and slot.get("audioIndex") is None:
            continue
        if role == "video" and slot.get("videoIndex") is None:
            continue
        if role not in {"audio", "video"} and slot.get("pictureIndex") is None:
            continue
        label = _label(slot, "A required file")
        kind = "voices" if role == "audio" else ("videos" if role == "video" else "pictures")
        asset = db.get(Asset, asset_id)
        try:
            if asset is None:
                raise ComfyAssetMissing(f"{label} is missing from the Library.")
            # Image-type guard: visual slots (character/place/prop/reference/style)
            # require IMAGE assets. A voice .wav or video in a visual slot is a
            # contract violation — BLOCK before staging so the job never runs.
            if role not in {"audio", "video"}:
                asset_kind = str(getattr(asset, "kind", "") or "").lower()
                if asset_kind and asset_kind not in {"image", ""}:
                    raise ComfyAssetStagingFailed(
                        f"{label} is a {asset_kind} asset, but visual reference slots require an image. "
                        "A voice or video file cannot be used as a character/place/prop picture."
                    )
            if role in {"audio", "video"}:
                staged = stage_library_asset(asset)
            elif has_direct_reference_authority(request=request):
                staged = stage_library_asset(asset)
            else:
                staged = stage_h3_visual_asset(asset, role=role)
        except (ComfyAssetMissing, ComfyAssetStagingFailed) as exc:
            report[kind].append({"label": label, "assetId": asset_id, "status": "MISSING"})
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": str(exc),
                "dependencies": report,
            }
        report[kind].append(
            {
                "label": label,
                "assetId": asset_id,
                "voiceProfileId": slot.get("identityId") or None,
                "status": "READY",
                "comfyName": staged.comfy_name,
                "uploadedTensor": (staged.ledger or {}).get("uploaded") or "library_file",
                "durationSec": _asset_duration_sec(asset),
            }
        )
        report["staged"].append(
            {
                "assetId": asset_id,
                "comfyName": staged.comfy_name,
                "bytes": staged.bytes,
                "reused": staged.reused,
                "role": role,
            }
        )
        if role == "audio":
            staged_audio.append(staged.comfy_name)
        elif role == "video":
            staged_videos.append(staged.comfy_name)
        else:
            staged_images.append(staged.comfy_name)
        if getattr(asset, "comfy_name", None) != staged.comfy_name:
            asset.comfy_name = staged.comfy_name
            db.add(asset)

    if _is_h3(request):
        # Audio cannot be the sole Ref2VA input — must accompany image or video.
        if staged_audio and not staged_images and not staged_videos:
            return {
                "ok": False,
                "error": "H3_AUDIO_REQUIRES_VISUAL",
                "message": (
                    "MiniMax H3 audio references must accompany at least one image or video "
                    "reference. Add a character/place picture or a video reference, then generate."
                ),
                "dependencies": {**report, "workflow": "MISSING"},
            }
        if not staged_images and not staged_videos:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": "MiniMax needs at least one character/place picture or video reference from this project.",
                "dependencies": {**report, "workflow": "MISSING"},
            }
        if not staged_images:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": (
                    "MiniMax H3 Reference-to-Video still needs at least one reference picture "
                    "alongside video/audio conditioning."
                ),
                "dependencies": {**report, "workflow": "MISSING"},
            }
        try:
            # Use legalFrameCount from providerOptions if available (set by
            # request_builder.py). Fall back to frames_for_duration which now
            # snaps UP to the next legal 17k+5 count instead of rejecting.
            po = request.providerOptions or {}
            gen_length = int(po.get("legalFrameCount") or 0)
            if gen_length <= 0:
                gen_length = frames_for_duration(float(request.duration or 5.0))
            graph = build_h3_ref2v(
                prompt=str(request.prompt or "preflight"),
                ref_comfy_names=staged_images,
                filename_prefix="studio/h3_preflight",
                length=gen_length,
                fast=bool(po.get("draftMode") or po.get("fast_generation")),
                ref_image_size=resolve_h3_ref_image_size(
                    po.get("refImageSize") or po.get("ref_image_size")
                ),
                ref_audio_comfy_names=staged_audio or None,
                ref_video_comfy_names=staged_videos or None,
            )
            assert_h3_ref2v_graph(
                graph,
                expected_names=staged_images,
                expected_audio_names=staged_audio or None,
                expected_video_names=staged_videos or None,
                expect_fast=bool(po.get("draftMode") or po.get("fast_generation")),
            )
        except ValueError as exc:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": "MiniMax could not be prepared with the current pictures, videos, and voices.",
                "detail": str(exc),
                "dependencies": {**report, "workflow": "MISSING"},
            }
        report["workflow"] = "READY"

    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["runtimeDependencies"] = report
    return {"ok": True, "dependencies": report}
