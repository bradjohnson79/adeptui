"""Persist Timeline takes per project/shot — never destroy prior takes."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings

_LOCK = threading.RLock()


def _path(project_id: str) -> Path:
    return settings.data_dir / "timeline_retakes" / f"{project_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(project_id: str) -> dict[str, Any]:
    path = _path(project_id)
    if not path.exists():
        return {"schemaVersion": 1, "projectId": project_id, "shots": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"schemaVersion": 1, "projectId": project_id, "shots": {}}
        raw.setdefault("shots", {})
        return raw
    except (OSError, ValueError, TypeError):
        return {"schemaVersion": 1, "projectId": project_id, "shots": {}}


def _save(project_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = _path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data["projectId"] = project_id
    data["updatedAt"] = _now()
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return data


def list_project_takes(project_id: str) -> dict[str, Any]:
    with _LOCK:
        return _load(project_id)


def get_shot_takes(project_id: str, shot_id: str) -> dict[str, Any]:
    with _LOCK:
        data = _load(project_id)
        shot = data.get("shots", {}).get(shot_id) or {
            "shotId": shot_id,
            "takes": [],
            "activeTakeId": None,
            "editHistory": [],
        }
        return {"ok": True, "projectId": project_id, "shot": shot, "mock": False}


def ensure_baseline_take(
    project_id: str,
    *,
    shot_id: str,
    scene_id: str | None,
    asset_id: str | None,
    job_id: str | None,
    prompt: str,
    duration_sec: float = 5.0,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register Take 1 if none exists. Never replaces existing takes."""
    with _LOCK:
        data = _load(project_id)
        shots = data.setdefault("shots", {})
        shot = shots.get(shot_id) or {
            "shotId": shot_id,
            "sceneId": scene_id,
            "takes": [],
            "activeTakeId": None,
            "editHistory": [],
            "originalPrompt": prompt,
        }
        if shot.get("takes"):
            shots[shot_id] = shot
            _save(project_id, data)
            return shot
        take_id = str(uuid.uuid4())
        take = {
            "takeId": take_id,
            "label": "Take 1 — Approved Baseline",
            "takeNumber": 1,
            "assetId": asset_id,
            "jobId": job_id,
            "prompt": prompt,
            "deltaInstruction": None,
            "durationSec": duration_sec,
            "retake": False,
            "sourceTakeId": None,
            "engine": "MiniMax H3",
            "provenance": {
                "engine": "MiniMax H3",
                "deployment": "private-local",
                "access": "owner-only",
                "runtime": "route-a",
                "retake": False,
                "apiUsed": False,
                "ltxUsed": False,
                **(provenance or {}),
            },
            "createdAt": _now(),
            "cancelled": False,
        }
        shot["takes"] = [take]
        shot["activeTakeId"] = take_id
        shot["sceneId"] = scene_id
        shot["originalPrompt"] = prompt
        shot["editHistory"] = [
            {
                "at": _now(),
                "action": "baseline_registered",
                "takeId": take_id,
                "reversible": True,
            }
        ]
        shots[shot_id] = shot
        _save(project_id, data)
        return shot


def add_alternate_take(
    project_id: str,
    *,
    shot_id: str,
    source_take_id: str,
    asset_id: str | None,
    job_id: str | None,
    prompt: str,
    delta_instruction: str,
    duration_sec: float = 5.0,
    provenance: dict[str, Any] | None = None,
    activate: bool = False,
) -> dict[str, Any]:
    """Add Take N as alternate. Original takes remain. History is append-only."""
    with _LOCK:
        data = _load(project_id)
        shots = data.setdefault("shots", {})
        shot = shots.get(shot_id)
        if not shot or not shot.get("takes"):
            raise ValueError("Baseline take missing — register Take 1 first.")
        # Ghost take guard: cancelled jobs must not register
        if provenance and provenance.get("status") == "cancelled":
            raise ValueError("Cancelled jobs cannot create Timeline takes.")
        n = len(shot["takes"]) + 1
        take_id = str(uuid.uuid4())
        take = {
            "takeId": take_id,
            "label": f"Take {n}",
            "takeNumber": n,
            "assetId": asset_id,
            "jobId": job_id,
            "prompt": prompt,
            "deltaInstruction": delta_instruction,
            "durationSec": duration_sec,
            "retake": True,
            "sourceTakeId": source_take_id,
            "engine": "MiniMax H3",
            "provenance": {
                "engine": "MiniMax H3",
                "deployment": "private-local",
                "access": "owner-only",
                "runtime": "route-a",
                "retake": True,
                "sourceTakeId": source_take_id,
                "apiUsed": False,
                "ltxUsed": False,
                "projectId": project_id,
                "shotId": shot_id,
                "originalPrompt": shot.get("originalPrompt") or prompt,
                "deltaInstruction": delta_instruction,
                **(provenance or {}),
            },
            "createdAt": _now(),
            "cancelled": False,
        }
        shot["takes"].append(take)
        shot.setdefault("editHistory", []).append(
            {
                "at": _now(),
                "action": "add_alternate_take",
                "takeId": take_id,
                "sourceTakeId": source_take_id,
                "reversible": True,
            }
        )
        if activate:
            shot["activeTakeId"] = take_id
            shot["editHistory"].append(
                {
                    "at": _now(),
                    "action": "set_active_take",
                    "takeId": take_id,
                    "reversible": True,
                }
            )
        shots[shot_id] = shot
        _save(project_id, data)
        return shot


def set_active_take(project_id: str, shot_id: str, take_id: str) -> dict[str, Any]:
    with _LOCK:
        data = _load(project_id)
        shot = (data.get("shots") or {}).get(shot_id)
        if not shot:
            raise ValueError("Shot not found")
        if not any(t.get("takeId") == take_id for t in shot.get("takes") or []):
            raise ValueError("Take not found")
        prior = shot.get("activeTakeId")
        shot["activeTakeId"] = take_id
        shot.setdefault("editHistory", []).append(
            {
                "at": _now(),
                "action": "set_active_take",
                "takeId": take_id,
                "previousActiveTakeId": prior,
                "reversible": True,
            }
        )
        data["shots"][shot_id] = shot
        _save(project_id, data)
        return shot
