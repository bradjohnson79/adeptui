"""Spawn the isolated stills worker. Never load DINO/SAM into VideoChat3."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from .boxes import normalize_box
from .contracts import (
    NormalizedBox,
    PerceptionEntity,
    PerceptionPacket,
    PerceptionProvenance,
    strip_provider_payload,
)
from .paths import worker_python
from .preflight import preflight_for_stills, request_generator_release

logger = logging.getLogger(__name__)


def _asset_path(db: Any, project_id: str, asset_id: str) -> str:
    from ...db import Asset

    asset = db.get(Asset, asset_id) if db is not None else None
    if asset is None or str(getattr(asset, "project_id", "")) != project_id:
        return ""
    return str(getattr(asset, "path", "") or "")


def run_stills_perception(
    *,
    project_id: str,
    map_id: str,
    source_asset_id: str,
    db: Any = None,
) -> PerceptionPacket:
    packet = PerceptionPacket(
        projectId=project_id,
        mapId=map_id,
        sourceAssetId=source_asset_id,
        availability="unavailable",
    )
    lease = request_generator_release()
    preflight = preflight_for_stills()
    packet.provenance = PerceptionProvenance(
        modelIds=["grounding-dino-tiny", "sam2.1-hiera-tiny", "depth-anything-v2-small"],
        device="",
        leaseEvidence={"comfyFree": lease, "preflight": preflight},
        worker="stills-perception",
    )
    if not preflight.get("ok") and not preflight.get("unknownVram"):
        packet.reason = "Not enough GPU memory for automatic boxes. You can place people yourself."
        return packet

    image_path = _asset_path(db, project_id, source_asset_id)
    if not image_path or not Path(image_path).is_file():
        packet.reason = "The scene picture is missing."
        return packet

    python = worker_python()
    if not Path(python).is_file():
        packet.reason = "Automatic boxes need their own installed environment. You can place people yourself."
        return packet
    studio_api_root = Path(__file__).resolve().parents[3]
    try:
        completed = subprocess.run(
            [str(python), "-m", "app.codirector.perception.worker"],
            input=json.dumps({"imagePath": image_path}),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=str(studio_api_root),
        )
    except Exception as exc:
        packet.reason = f"Geometry worker did not start: {exc}"[:240]
        return packet

    raw_text = (completed.stdout or "").strip().splitlines()
    payload: dict[str, Any] = {}
    if raw_text:
        try:
            payload = json.loads(raw_text[-1])
        except Exception:
            payload = {}
    payload = strip_provider_payload(payload if isinstance(payload, dict) else {})
    if not payload.get("ok"):
        packet.reason = str(payload.get("reason") or "Automatic boxes unavailable.")
        return packet

    entities: list[PerceptionEntity] = []
    for item in payload.get("entities") or []:
        if not isinstance(item, dict):
            continue
        clean = strip_provider_payload(item)
        box = clean.get("box") if isinstance(clean.get("box"), dict) else None
        if box:
            box = normalize_box(box)
        entities.append(
            PerceptionEntity(
                label=str(clean.get("label") or ""),
                kindHint=clean.get("kindHint") or "unknown",
                box=NormalizedBox.model_validate(box) if box else None,
                maskAssetId=str(clean.get("maskAssetId") or ""),
                confidence=clean.get("confidence"),
                ordinalDepth=clean.get("ordinalDepth") or "unknown",
            )
        )
    packet.entities = entities
    packet.availability = "testing"
    packet.reason = "Geometry boxes are Testing. Accept is still required."
    packet.provenance.device = str(payload.get("device") or "cuda:0")
    return packet
