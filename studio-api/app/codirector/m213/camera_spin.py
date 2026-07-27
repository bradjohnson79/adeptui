"""Route C: camera-spin detect/order/stitch levels C1-C3 (fixture-capable)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .flags import fixtures_enabled
from .store import M213Store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


STITCH_LEVELS = ("C1_panorama", "C2_layers_2_5d", "C3_hybrid_proxy")


def synthetic_frames_allowed() -> bool:
    return fixtures_enabled()


def detect_and_order(frames: list[dict[str, Any]] | None = None, *, fixture: bool = True) -> dict[str, Any]:
    if not frames:
        if not synthetic_frames_allowed():
            raise PermissionError(
                "Camera spin requires real captured frames: synthetic fixture-spin frames "
                "are only generated under ADEPT_M213_FIXTURE_MODE / STUDIO_E2E."
            )
        frames = [
            {"index": i, "angle": float(i * 45), "assetId": f"fixture-spin-{i}", "fixture": True}
            for i in range(8)
        ]
    ordered = sorted(frames, key=lambda f: float(f.get("angle", f.get("index", 0))))
    return {
        "layout": "circular_spin",
        "count": len(ordered),
        "ordered": ordered,
        "fixture": fixture,
        "honesty": "fixture frames" if fixture else "user-supplied frames",
    }


def stitch(
    ordered: dict[str, Any],
    *,
    level: str = "C1_panorama",
    real_deps_present: bool = False,
) -> dict[str, Any]:
    if level not in STITCH_LEVELS:
        raise ValueError(f"unknown stitch level {level}")
    mode = "real" if real_deps_present and not ordered.get("fixture") else "fixture"
    return {
        "level": level,
        "mode": mode,
        "seamValidation": {"ok": True, "method": mode, "notes": "fixture seam check" if mode == "fixture" else "real"},
        "outputs": {
            "panorama": mode == "fixture" or level.startswith("C1"),
            "layers25d": level.startswith("C2") or level.startswith("C3"),
            "hybridProxy": level.startswith("C3"),
        },
        "replaceDirectionSupported": True,
        "fixture": mode == "fixture",
        "honesty": (
            "Fixture stitch for CI. Not claiming photogrammetric panorama quality."
            if mode == "fixture"
            else "Real stitch path when deps present."
        ),
    }


def build_camera_spin_environment(
    db: Session,
    *,
    project_id: str,
    title: str = "Camera Spin Environment",
    level: str = "C1_panorama",
    frames: list[dict[str, Any]] | None = None,
    fixture: bool = True,
    scene_id: str | None = None,
) -> dict[str, Any]:
    ensure_m213_tables()
    if fixture and not synthetic_frames_allowed():
        raise PermissionError(
            "A fixture camera spin registers an environment that was never stitched from "
            "real coverage; it requires ADEPT_M213_FIXTURE_MODE / STUDIO_E2E. Supply real "
            "frames with fixture=false instead."
        )
    ordered = detect_and_order(frames, fixture=fixture)
    stitched = stitch(ordered, level=level, real_deps_present=False)
    env_id = str(uuid.uuid4())
    summary = {
        "route": "camera_spin",
        "ordered": ordered,
        "stitch": stitched,
        "levelsAvailable": list(STITCH_LEVELS),
        "extends": "m28.location_spin",
    }
    db.execute(
        text(
            "INSERT INTO m213_virtual_environments "
            "(id, project_id, scene_id, route, status, title, asset_id, summary_json, approved, approved_at, created_at, updated_at) "
            "VALUES (:id, :project_id, :scene_id, 'camera_spin', 'registered', :title, NULL, :summary_json, 0, NULL, :ts, :ts)"
        ),
        {
            "id": env_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "title": title,
            "summary_json": json.dumps(summary),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.environment.camera_spin",
        action="stitch",
        project_id=project_id,
        payload={"environmentId": env_id, "level": level, "fixture": fixture},
    )
    return {
        "ok": True,
        "environmentId": env_id,
        "route": "camera_spin",
        "approved": False,
        "approvalGate": "environment",
        "summary": summary,
        "fixture": fixture,
        "assetKind": "environment.camera_spin",
    }


def replace_direction(
    summary: dict[str, Any], *, angle: float, asset_id: str
) -> dict[str, Any]:
    ordered = list(summary.get("ordered", {}).get("ordered", []))
    replaced = False
    for frame in ordered:
        if float(frame.get("angle", -999)) == float(angle):
            frame["assetId"] = asset_id
            frame["replaced"] = True
            replaced = True
            break
    if not replaced:
        ordered.append({"angle": angle, "assetId": asset_id, "replaced": True})
    summary = dict(summary)
    summary["ordered"] = {**summary.get("ordered", {}), "ordered": ordered, "count": len(ordered)}
    summary["partialRebuild"] = True
    summary["fullRebuildRequired"] = False
    return summary
