"""M2.9 audio production service.

Generate (dialogue/sfx/music): no native TTS/SFX generator on platform — fixture CI only.
Process (normalize/cleanup): real ffmpeg path when asset files exist.
"""

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
from ..providers import ProviderUnavailable, process_audio_ffmpeg, wants_fixture
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
                payload={
                    **payload,
                    "assetId": result["assetId"],
                    "cueId": cue_id,
                    "fixtureComplete": True,
                },
                scene_id=scene_id,
                owner=owner,
            )
            result.update(
                {"jobId": job.id, "cueId": cue_id, "versionId": ver["id"], "projectId": project_id}
            )
            return result

        # M2.10b sandbox: sync generate via registry when flag + registryId authorize.
        registry_id = payload.get("registryId") or payload.get("providerKey")
        if registry_id:
            try:
                from ...m210b.flags import m210b_audio_sandbox_enabled
                from ...m210b.registry import get_adapter
            except ImportError:
                pass
            else:
                if m210b_audio_sandbox_enabled() and get_adapter(str(registry_id)) is not None:
                    job = enqueue_executive_job(
                        db,
                        project_id=project_id,
                        job_type=JobType.AUDIO_GENERATE,
                        payload={**payload, "sceneId": scene_id},
                        scene_id=scene_id,
                        owner=owner,
                    )
                    result = AudioService.execute_job(
                        db, {**payload, "sceneId": scene_id}, project_id
                    )
                    cue_id = uuid.uuid4().hex
                    asset_id = result.get("assetId")
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
                            "aid": asset_id,
                            "start": start_sec,
                            "dur": float(result.get("durationSec") or duration_sec),
                            "meta": json.dumps(
                                {
                                    "prompt": prompt,
                                    "m210b": True,
                                    "sandboxOnly": True,
                                    "productionApproved": False,
                                    "registryId": str(registry_id),
                                    "assetPath": result.get("assetPath"),
                                    "sha256": result.get("sha256"),
                                }
                            ),
                            "c": _now(),
                        },
                    )
                    db.commit()
                    result.update(
                        {
                            "jobId": job.id,
                            "cueId": cue_id,
                            "projectId": project_id,
                            "providerMissing": False,
                        }
                    )
                    return result

        # No generative audio provider on native platform - enqueue job that will Block honestly.
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.AUDIO_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        cue_id = uuid.uuid4().hex
        db.execute(
            text(
                "INSERT INTO m29_audio_cues "
                "(id, project_id, scene_id, cue_kind, status, asset_id, start_sec, duration_sec, "
                "metadata_json, created_at) "
                "VALUES (:id, :pid, :sid, :kind, :status, NULL, :start, :dur, :meta, :c)"
            ),
            {
                "id": cue_id,
                "pid": project_id,
                "sid": scene_id,
                "kind": kind,
                "status": "draft",
                "start": start_sec,
                "dur": duration_sec,
                "meta": json.dumps({"prompt": prompt, "awaitingProvider": True}),
                "c": _now(),
            },
        )
        db.commit()
        return {
            "jobId": job.id,
            "cueId": cue_id,
            "kind": kind,
            "fixture": False,
            "projectId": project_id,
            "status": "queued",
            "providerMissing": True,
        }

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
        if fixture_mode_enabled():
            payload["fixtureComplete"] = True
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
            if wants_fixture(payload):
                return {
                    "assetId": payload.get("assetId"),
                    "ops": payload.get("ops") or [],
                    "fixture": True,
                    "status": "processed",
                }
            return process_audio_ffmpeg(db, project_id=project_id, payload=payload)

        if wants_fixture(payload):
            return fixture_audio_result(payload)

        # M2.10b sandbox audio: try registry adapter when flag + execution lock authorize.
        registry_id = payload.get("registryId") or payload.get("providerKey")
        if registry_id:
            try:
                from ...m210b.flags import m210b_audio_sandbox_enabled
                from ...m210b.registry import get_adapter
                from ...m210b.schemas import AudioGenerateRequest
            except ImportError:
                registry_id = None
            else:
                if m210b_audio_sandbox_enabled():
                    adapter = get_adapter(str(registry_id))
                    if adapter is not None:
                        kind = str(payload.get("kind") or "dialogue")
                        cap_map = {
                            "dialogue": "audio.dialogue.generate",
                            "sfx": "audio.sfx.generate",
                            "ambience": "audio.sfx.generate",
                            "music": "audio.music.generate",
                        }
                        req = AudioGenerateRequest(
                            capabilityId=str(
                                payload.get("capabilityId") or cap_map.get(kind, "audio.dialogue.generate")
                            ),
                            projectId=project_id,
                            sceneId=payload.get("sceneId"),
                            prompt=str(payload.get("prompt") or ""),
                            durationSec=float(payload.get("durationSec") or 2.0),
                            seed=payload.get("seed"),
                            timelineIntent=payload.get("timelineIntent"),
                            providerKey=payload.get("providerKey"),
                            registryId=str(registry_id),
                            negativePrompt=payload.get("negativePrompt"),
                            sampleRate=int(payload.get("sampleRate") or 48000),
                            channels=int(payload.get("channels") or 1),
                            format=str(payload.get("format") or "wav"),
                            kind=kind,
                        )
                        result = adapter.generate(req)
                        asset_id = result.assetId or f"m210b-{registry_id}-{uuid.uuid4().hex[:10]}"
                        ver = create_asset_version(
                            db,
                            project_id=project_id,
                            department="audio",
                            status="generated",
                            asset_id=asset_id,
                            metadata={
                                "kind": kind,
                                "sandboxOnly": True,
                                "productionApproved": False,
                                "m210b": True,
                                "registryId": registry_id,
                                "assetPath": result.assetPath,
                                "sha256": result.sha256,
                                "provenance": result.provenance,
                                "fixture": bool(result.fixture),
                                "prompt": req.prompt,
                            },
                        )
                        return {
                            "assetId": asset_id,
                            "versionId": ver["id"],
                            "kind": kind,
                            "status": "generated",
                            "fixture": bool(result.fixture),
                            "sandboxOnly": True,
                            "productionApproved": False,
                            "registryId": registry_id,
                            "assetPath": result.assetPath,
                            "sha256": result.sha256,
                            "durationSec": result.durationSec,
                            "sampleRate": result.sampleRate,
                            "provenance": result.provenance,
                            "projectId": project_id,
                        }

        # Honest: no dialogue/sfx/music generative provider on native platform.
        raise ProviderUnavailable(
            "No native generative audio provider (TTS/SFX/music) is installed; "
            "audio.generate remains unavailable outside ADEPT_M29_FIXTURE_MODE. "
            "Use audio_process (ffmpeg) for normalize/cleanup, or upload stems."
        )

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

    @staticmethod
    def place_cue(
        db: Session,
        *,
        project_id: str,
        kind: str,
        asset_id: str,
        start_sec: float = 0.0,
        duration_sec: float = 2.0,
        scene_id: str | None = None,
        volume: float = 1.0,
        ducking: bool = False,
    ) -> dict[str, Any]:
        """Deterministic cue placement onto m29_audio_cues (+ optional director timeline)."""
        ensure_m29_tables()
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
                "status": "placed",
                "aid": asset_id,
                "start": start_sec,
                "dur": duration_sec,
                "meta": json.dumps({"volume": volume, "ducking": ducking, "fixture": False}),
                "c": _now(),
            },
        )
        db.commit()
        if scene_id:
            from ....db import Scene
            from ....director_timeline import (
                TimelineClip,
                dumps_director_timeline,
                parse_director_timeline,
            )

            scene = db.get(Scene, scene_id)
            if scene and scene.project_id == project_id:
                tl = parse_director_timeline(
                    scene.director_json,
                    fallback_duration=float(scene.duration_sec or 5),
                    fallback_prompt=scene.prompt or "",
                )
                clip = TimelineClip(
                    asset_id=asset_id,
                    start=start_sec,
                    length=duration_sec,
                    volume=volume,
                    label=kind,
                )
                if kind == "sfx":
                    tl.sfx_clips.append(clip)
                else:
                    tl.audio_clips.append(clip)
                scene.director_json = dumps_director_timeline(tl)
                db.commit()
        return {
            "cueId": cue_id,
            "kind": kind,
            "assetId": asset_id,
            "startSec": start_sec,
            "durationSec": duration_sec,
            "status": "placed",
            "fixture": False,
            "projectId": project_id,
        }
