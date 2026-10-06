"""SAM 2.1 video tracking. Native video inpaint stays blocked."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from ...config import settings
from .cache import load_packet, load_track, store_packet, store_track
from .paths import SAM21_REVISION, sam_present
from .perception_router import creator_unavailable_message
from .selection_contracts import PerceptionSelectionPacket, SelectRequest, TrackRequest
from .selection_service import select

WorkerFn = Callable[[dict[str, Any]], dict[str, Any]]


def resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return found
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        winget = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if winget.is_dir():
            matches = sorted(winget.glob("**/ffmpeg.exe"))
            if matches:
                return str(matches[0])
    return ""


def extract_video_frame(video_path: str, dest_png: Path, time_sec: float) -> bool:
    ffmpeg = resolve_ffmpeg()
    if not ffmpeg or not Path(video_path).is_file():
        return False
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{max(0.0, time_sec):.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-an",
            str(dest_png),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return proc.returncode == 0 and dest_png.is_file()


def _asset_path(db: Any, project_id: str, asset_id: str) -> str:
    from pathlib import Path

    from ...db import Asset

    if db is None:
        return ""
    try:
        asset = db.get(Asset, asset_id)
    except Exception:
        return ""
    if asset is None or str(getattr(asset, "project_id", "")) != project_id:
        return ""
    path = str(getattr(asset, "path", "") or "")
    return path if path and Path(path).is_file() else ""


def track(
    db: Any,
    project_id: str,
    body: TrackRequest,
    *,
    worker: Optional[WorkerFn] = None,
) -> dict[str, Any]:
    if not sam_present() and worker is None:
        return {"ok": False, "message": creator_unavailable_message("track")}

    video_path = _asset_path(db, project_id, body.assetId)
    frames = list(body.frameTimesMs or [0, 1000, 2000])
    frame_dir = Path(settings.data_dir) / "image_product" / project_id / "track_frames" / body.assetId
    extracted: list[tuple[int, Path]] = []
    suffix = Path(video_path).suffix.lower() if video_path else ""
    is_video = suffix in {".mp4", ".mov", ".webm", ".mkv", ".avi"}
    if is_video and video_path:
        for ms in frames[:8]:
            dest = frame_dir / f"frame_{int(ms)}.png"
            if extract_video_frame(video_path, dest, int(ms) / 1000.0):
                extracted.append((int(ms), dest))
        if not extracted:
            return {
                "ok": False,
                "maskAssetId": "",
                "nativeVideoInpaint": False,
                "message": "Could not read frames from that video. Track needs a playable clip.",
            }
    first_image = str(extracted[0][1]) if extracted else video_path
    if first_image and Path(first_image).suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        return {
            "ok": False,
            "maskAssetId": "",
            "nativeVideoInpaint": False,
            "message": "Could not read frames from that video. Track needs a playable clip.",
        }

    seed = load_packet(project_id, body.seedSelectionId) if body.seedSelectionId else None
    if seed is None:
        from .worker_client import run_selection_worker as _select_worker

        def _frame_worker(payload: dict[str, Any]) -> dict[str, Any]:
            payload = dict(payload)
            if first_image:
                payload["imagePath"] = first_image
            return (worker or _select_worker)(payload)

        seeded = select(
            db,
            project_id,
            SelectRequest(
                assetId=body.assetId,
                point=body.point,
                box=body.box,
                label=body.label,
                role=body.role,
            ),
            worker=_frame_worker,
        )
        if not seeded.get("ok"):
            return seeded
        seed = seeded.get("selection") or {}

    from .worker_client import run_selection_worker

    payload = (worker or run_selection_worker)(
        {
            "mode": "track",
            "videoPath": video_path,
            "imagePath": first_image,
            "framePaths": [str(path) for _, path in extracted],
            "point": body.point or (seed.get("bounds") and None),
            "box": seed.get("bounds"),
            "label": body.label or seed.get("semanticLabel") or "",
            "frameTimesMs": frames,
        }
    )
    tracking_id = f"trk_{uuid4().hex[:12]}"
    packets: list[dict[str, Any]] = []
    frames_out = payload.get("frames") if isinstance(payload.get("frames"), list) else []
    if payload.get("ok") and frames_out:
        from .selection_service import _decode_png, _persist_mask

        for item in frames_out:
            if not isinstance(item, dict) or not item.get("maskPngBase64"):
                continue
            record = _persist_mask(
                project_id,
                body.assetId,
                _decode_png(str(item["maskPngBase64"])),
                "include" if body.role != "exclude" else "exclude",
                {
                    "trackingId": tracking_id,
                    "frameTimeMs": item.get("frameTimeMs"),
                    "modelId": "sam21-hiera-tiny",
                    "modelVersion": SAM21_REVISION,
                },
            )
            packet = PerceptionSelectionPacket(
                projectId=project_id,
                assetId=body.assetId,
                frameTimeMs=item.get("frameTimeMs"),
                semanticLabel=str(seed.get("semanticLabel") or body.label or "tracked"),
                maskAssetId=str(record["maskId"]),
                bounds=item.get("bounds") if isinstance(item.get("bounds"), dict) else None,
                confidence=item.get("confidence"),
                role=body.role,
                source="track",
                modelId="sam21-hiera-tiny",
                modelVersion=SAM21_REVISION,
                trackingId=tracking_id,
                provenance={"device": str(payload.get("device") or ""), "nativeVideoInpaint": False},
            )
            dumped = packet.model_dump()
            store_packet(dumped)
            packets.append(dumped)
    elif seed:
        seed["trackingId"] = tracking_id
        store_packet(seed)
        packets.append(seed)

    track_doc = {
        "trackingId": tracking_id,
        "projectId": project_id,
        "assetId": body.assetId,
        "seedSelectionId": seed.get("selectionId") if seed else "",
        "frames": packets,
        "nativeVideoInpaint": False,
        "disclosure": "Native video inpaint is unavailable. Tracked masks can drive still inpaint or Timeline range replacement.",
        "ok": bool(packets),
        "workerOk": bool(payload.get("ok")),
        "message": (
            "Tracked across the shot."
            if payload.get("ok") and len(packets) > 1
            else str(payload.get("message") or "Tracked the first frame. Paint later frames if needed.")
        ),
    }
    store_track(project_id, tracking_id, track_doc)
    return {"ok": True, **track_doc}


def get_track(project_id: str, tracking_id: str) -> dict[str, Any] | None:
    return load_track(project_id, tracking_id)
