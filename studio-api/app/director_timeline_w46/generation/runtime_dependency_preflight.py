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

    staged_images: list[str] = []
    staged_audio: list[str] = []
    for slot in slots:
        role = str(slot.get("role") or "")
        asset_id = str(slot.get("assetId") or "").strip()
        if not asset_id or role == "video":
            continue
        if role == "audio" and slot.get("audioIndex") is None:
            continue
        if role != "audio" and slot.get("pictureIndex") is None:
            continue
        label = _label(slot, "A required file")
        kind = "voices" if role == "audio" else "pictures"
        asset = db.get(Asset, asset_id)
        try:
            if asset is None:
                raise ComfyAssetMissing(f"{label} is missing from the Library.")
            # Image-type guard: visual slots (character/place/prop/reference/style)
            # require IMAGE assets. A voice .wav or video in a visual slot is a
            # contract violation — BLOCK before staging so the job never runs.
            if role != "audio" and role != "video":
                asset_kind = str(getattr(asset, "kind", "") or "").lower()
                if asset_kind and asset_kind not in {"image", ""}:
                    raise ComfyAssetStagingFailed(
                        f"{label} is a {asset_kind} asset, but visual reference slots require an image. "
                        "A voice or video file cannot be used as a character/place/prop picture."
                    )
            if role == "audio" or role == "video":
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
            }
        )
        report["staged"].append(
            {
                "assetId": asset_id,
                "comfyName": staged.comfy_name,
                "bytes": staged.bytes,
                "reused": staged.reused,
            }
        )
        if role == "audio":
            staged_audio.append(staged.comfy_name)
        else:
            staged_images.append(staged.comfy_name)
        if getattr(asset, "comfy_name", None) != staged.comfy_name:
            asset.comfy_name = staged.comfy_name
            db.add(asset)

    if _is_h3(request):
        if not staged_images:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": "MiniMax needs at least one character or place picture from this project.",
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
                ref_audio_comfy_names=staged_audio,
            )
            assert_h3_ref2v_graph(
                graph,
                expected_names=staged_images,
                expected_audio_names=staged_audio,
                expect_fast=bool(po.get("draftMode") or po.get("fast_generation")),
            )
        except ValueError as exc:
            return {
                "ok": False,
                "error": "DEPENDENCY_NOT_READY",
                "message": "MiniMax could not be prepared with the current pictures and voices.",
                "detail": str(exc),
                "dependencies": {**report, "workflow": "MISSING"},
            }
        report["workflow"] = "READY"

    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["runtimeDependencies"] = report
    return {"ok": True, "dependencies": report}
