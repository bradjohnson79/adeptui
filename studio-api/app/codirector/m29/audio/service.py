"""M2.9 audio production service."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..db import ensure_m29_tables
from ..fixtures import fixture_audio_result
from ..store import create_asset_version, enqueue_executive_job


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class AudioService:
    @staticmethod
    def generate(
        db: Session,
        *,
        project_id: str,
        kind: str = "dialogue",
        prompt: str = "M2.9 audio",
        scene_id: str | None = None,
        owner: str = "user",
        start_sec: float = 0.0,
        duration_sec: float = 2.0,
        **params: Any,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        payload = {
            "kind": kind,
            "prompt": prompt,
            "m29": True,
            "startSec": start_sec,
            "durationSec": duration_sec,
            **params,
        }
        if fixture_mode_enabled():
            result = fixture_audio_result(payload)
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="audio",
                status="generated",
                asset_id=result["assetId"],
                metadata={"kind": kind, "fixture": True, "prompt": prompt},
            )
            cue_id = uuid.uuid4().hex
            db.execute(
                text(
                    "INSERT INTO m29_audio_cues "
                    "(id, project_id, scene_id, cue_kind, status, asset_id, start_sec, duration_sec, "
                    "metadata_json, created_at) "
                    "VALUES (:id, :pid, :sid, :kind, :status, :aid, :start, :dur, :meta, :c)"
                ),
                {
                    "id": cue_id,
                    "pid": project_id,
                    "sid": scene_id,
                    "kind": kind,
                    "status": "generated",
                    "aid": result["assetId"],
                    "start": start_sec,
                    "dur": duration_sec,
                    "meta": json.dumps({"fixture": True, "prompt": prompt}),
                    "c": _now(),
                },
            )
            db.commit()
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=JobType.AUDIO_GENERATE,
                payload={**payload, "assetId": result["assetId"], "cueId": cue_id, "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "cueId": cue_id, "versionId": ver["id"], "projectId": project_id})
            return result
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.AUDIO_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {"jobId": job.id, "kind": kind, "fixture": False, "projectId": project_id, "status": "queued"}

    @staticmethod
    def process(
        db: Session,
        *,
        project_id: str,
        asset_id: str,
        ops: list | None = None,
        scene_id: str | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        payload = {"assetId": asset_id, "ops": ops or [], "m29": True, "process": True}
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.AUDIO_PROCESS,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {
            "jobId": job.id,
            "assetId": asset_id,
            "ops": ops or [],
            "fixture": fixture_mode_enabled(),
            "status": "processed" if fixture_mode_enabled() else "queued",
            "projectId": project_id,
        }

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if payload.get("process"):
            return {
                "assetId": payload.get("assetId"),
                "ops": payload.get("ops") or [],
                "fixture": fixture_mode_enabled(),
                "status": "processed",
            }
        return fixture_audio_result(payload)

    @staticmethod
    def list_cues(db: Session, project_id: str) -> list[dict[str, Any]]:
        ensure_m29_tables()
        rows = db.execute(
            text(
                "SELECT id, project_id, scene_id, cue_kind, status, asset_id, start_sec, duration_sec, "
                "metadata_json, created_at FROM m29_audio_cues WHERE project_id = :pid ORDER BY start_sec"
            ),
            {"pid": project_id},
        ).mappings().all()
        return [
            {
                "id": r["id"],
                "projectId": r["project_id"],
                "sceneId": r["scene_id"],
                "kind": r["cue_kind"],
                "status": r["status"],
                "assetId": r["asset_id"],
                "startSec": r["start_sec"],
                "durationSec": r["duration_sec"],
                "metadata": json.loads(r["metadata_json"] or "{}"),
                "createdAt": r["created_at"],
            }
            for r in rows
        ]
