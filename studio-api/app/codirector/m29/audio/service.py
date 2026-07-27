"""M2.9 audio production service.

Generate (dialogue/sfx/music): no native TTS/SFX generator on platform — fixture CI only.
Import (real stems): honest path for WAV bytes the user already has.
Process (normalize/cleanup): real ffmpeg path when asset files exist.

A cue only reaches the Director timeline when it carries an asset that exists on disk. A
fixture asset id names nothing, so it stays a cue row and never fabricates a timeline clip.
"""

from __future__ import annotations

import hashlib
import json
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..db import ensure_m29_tables
from ..fixtures import fixture_audio_result
from ..providers import (
    ProviderUnavailable,
    process_audio_ffmpeg,
    validate_audio_ops,
    wants_fixture,
)
from ..store import create_asset_version, enqueue_executive_job

_WAV_RIFF = b"RIFF"
_WAV_WAVE = b"WAVE"


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def resolve_real_audio_path(db: Session, asset_id: str | None) -> Path | None:
    """Path on disk for `asset_id`, or None when nothing real backs it.

    Two registries can own an audio file: the studio `assets` table (imports, ffmpeg
    output) and the M2.9 asset-version ledger (sandbox adapters record `assetPath` in
    their metadata). Either counts as real; a fixture id matches neither.
    """

    if not asset_id:
        return None
    from ..providers import resolve_asset_path

    path = resolve_asset_path(db, asset_id)
    if path is not None:
        return path

    ensure_m29_tables()
    rows = db.execute(
        text(
            "SELECT metadata_json FROM m29_asset_versions WHERE asset_id = :aid "
            "ORDER BY created_at DESC"
        ),
        {"aid": asset_id},
    ).mappings().all()
    for row in rows:
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            continue
        candidate = meta.get("assetPath")
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _write_scene_clip(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    kind: str,
    asset_id: str,
    start_sec: float,
    duration_sec: float,
    volume: float,
) -> bool:
    """Upsert one cue onto the scene's DirectorTimeline. False when the scene is unusable."""

    from ....db import Scene
    from ....director_timeline import (
        TimelineClip,
        dumps_director_timeline,
        parse_director_timeline,
    )

    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        return False
    tl = parse_director_timeline(
        scene.director_json,
        fallback_duration=float(scene.duration_sec or 5),
        fallback_prompt=scene.prompt or "",
    )
    track = tl.sfx_clips if kind == "sfx" else tl.audio_clips
    for existing in track:
        if existing.asset_id == asset_id and abs(float(existing.start) - start_sec) < 1e-6:
            existing.length = duration_sec
            existing.volume = volume
            break
    else:
        track.append(
            TimelineClip(
                asset_id=asset_id,
                start=start_sec,
                length=duration_sec,
                volume=volume,
                label=kind,
            )
        )
    scene.director_json = dumps_director_timeline(tl)
    db.commit()
    return True


def _cue_row(db: Session, cue_id: str) -> dict[str, Any] | None:
    ensure_m29_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, scene_id, cue_kind, status, asset_id, start_sec, "
            "duration_sec, metadata_json FROM m29_audio_cues WHERE id = :id"
        ),
        {"id": cue_id},
    ).mappings().first()
    return dict(row) if row else None


def _cue_metadata(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(row.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _update_cue(
    db: Session,
    cue_id: str,
    *,
    status: str | None = None,
    scene_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    sets = []
    params: dict[str, Any] = {"id": cue_id}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if scene_id is not None:
        sets.append("scene_id = :sid")
        params["sid"] = scene_id
    if metadata is not None:
        sets.append("metadata_json = :meta")
        params["meta"] = json.dumps(metadata)
    if not sets:
        return
    db.execute(text(f"UPDATE m29_audio_cues SET {', '.join(sets)} WHERE id = :id"), params)
    db.commit()


def _wav_duration_sec(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
    except (wave.Error, OSError):
        return None
    if not rate:
        return None
    return round(frames / float(rate), 4)


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
                {
                    "jobId": job.id,
                    "cueId": cue_id,
                    "versionId": ver["id"],
                    "projectId": project_id,
                    "timelinePlaced": AudioService._auto_place(
                        db,
                        project_id=project_id,
                        cue_id=cue_id,
                        scene_id=scene_id,
                        kind=kind,
                        asset_id=result["assetId"],
                        start_sec=start_sec,
                        duration_sec=duration_sec,
                    ),
                }
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
                            "timelinePlaced": AudioService._auto_place(
                                db,
                                project_id=project_id,
                                cue_id=cue_id,
                                scene_id=scene_id,
                                kind=kind,
                                asset_id=asset_id,
                                start_sec=start_sec,
                                duration_sec=float(result.get("durationSec") or duration_sec),
                            ),
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
        op_names = validate_audio_ops(ops or [])
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
            "appliedOps": op_names,
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
        placed = False
        if scene_id:
            placed = _write_scene_clip(
                db,
                project_id=project_id,
                scene_id=scene_id,
                kind=kind,
                asset_id=asset_id,
                start_sec=start_sec,
                duration_sec=duration_sec,
                volume=volume,
            )
        return {
            "cueId": cue_id,
            "kind": kind,
            "assetId": asset_id,
            "startSec": start_sec,
            "durationSec": duration_sec,
            "status": "placed",
            "fixture": False,
            "projectId": project_id,
            "sceneId": scene_id,
            "timelinePlaced": placed,
        }

    @staticmethod
    def _auto_place(
        db: Session,
        *,
        project_id: str,
        cue_id: str,
        scene_id: str | None,
        kind: str,
        asset_id: str | None,
        start_sec: float,
        duration_sec: float,
        volume: float = 1.0,
    ) -> bool:
        """Place a just-generated cue when a real asset and a real scene both exist."""

        if not scene_id or not asset_id:
            return False
        if resolve_real_audio_path(db, asset_id) is None:
            return False
        if not _write_scene_clip(
            db,
            project_id=project_id,
            scene_id=scene_id,
            kind=kind,
            asset_id=asset_id,
            start_sec=start_sec,
            duration_sec=duration_sec,
            volume=volume,
        ):
            return False
        row = _cue_row(db, cue_id) or {}
        meta = _cue_metadata(row)
        meta.update({"volume": volume, "timelinePlaced": True, "placedAt": _now()})
        _update_cue(db, cue_id, status="placed", metadata=meta)
        return True

    @staticmethod
    def promote_cue_to_timeline(
        db: Session,
        *,
        project_id: str,
        cue_id: str,
        scene_id: str | None = None,
        volume: float | None = None,
        ducking: bool | None = None,
    ) -> dict[str, Any]:
        """Move an existing cue onto the Director timeline.

        Explicit counterpart to the auto-placement in `generate`/`import_audio`, for cues
        that acquired their asset later. Refuses a cue whose asset id names no file — a
        placeholder on the timeline would read as finished sound work that does not exist.
        """

        row = _cue_row(db, cue_id)
        if not row or row["project_id"] != project_id:
            raise KeyError(cue_id)
        target_scene = scene_id or row["scene_id"]
        if not target_scene:
            raise ValueError("cue has no sceneId; pass sceneId to promote it")
        asset_id = row["asset_id"]
        if not asset_id:
            raise ValueError(
                f"cue {cue_id} has no assetId (status={row['status']}); "
                "generate or import audio before promoting it"
            )
        if resolve_real_audio_path(db, asset_id) is None:
            raise ValueError(
                f"asset {asset_id} has no file on disk; refusing to place a placeholder cue "
                "on the Director timeline"
            )

        meta = _cue_metadata(row)
        gain = float(volume if volume is not None else meta.get("volume", 1.0))
        duck = bool(ducking if ducking is not None else meta.get("ducking", False))
        kind = row["cue_kind"]
        start_sec = float(row["start_sec"] or 0.0)
        duration_sec = float(row["duration_sec"] or 2.0)
        if not _write_scene_clip(
            db,
            project_id=project_id,
            scene_id=target_scene,
            kind=kind,
            asset_id=asset_id,
            start_sec=start_sec,
            duration_sec=duration_sec,
            volume=gain,
        ):
            raise KeyError(target_scene)

        meta.update(
            {"volume": gain, "ducking": duck, "timelinePlaced": True, "placedAt": _now()}
        )
        _update_cue(db, cue_id, status="placed", scene_id=target_scene, metadata=meta)
        return {
            "cueId": cue_id,
            "projectId": project_id,
            "sceneId": target_scene,
            "kind": kind,
            "assetId": asset_id,
            "startSec": start_sec,
            "durationSec": duration_sec,
            "volume": gain,
            "ducking": duck,
            "status": "placed",
            "timelinePlaced": True,
            "fixture": False,
        }

    @staticmethod
    def import_audio(
        db: Session,
        *,
        project_id: str,
        content: bytes,
        filename: str = "import.wav",
        kind: str = "sfx",
        scene_id: str | None = None,
        start_sec: float = 0.0,
        duration_sec: float | None = None,
        volume: float = 1.0,
        ducking: bool = False,
        tag: str = "",
    ) -> dict[str, Any]:
        """Register real WAV bytes as an Asset, then cue and place them.

        This is the honest sound path while no generative audio provider exists on the
        platform: the file is the user's, the duration is read from its header, and the
        resulting cue is indistinguishable on the timeline from generated audio.
        """

        ensure_m29_tables()
        from ....config import settings
        from ....db import Asset, Project

        if not content:
            raise ValueError("audio import requires file content")
        if not (content[:4] == _WAV_RIFF and content[8:12] == _WAV_WAVE):
            raise ValueError("audio import expects RIFF/WAVE bytes (real .wav)")
        project = db.get(Project, project_id)
        if not project:
            raise KeyError(project_id)

        asset_id = str(uuid.uuid4())
        dest_dir = settings.data_dir / "assets" / project_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}.wav"
        dest.write_bytes(content)
        sha256 = hashlib.sha256(content).hexdigest()
        measured = _wav_duration_sec(dest)
        length = float(duration_sec if duration_sec is not None else (measured or 2.0))

        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag=(tag or "").lstrip("@").strip(),
                kind="audio",
                filename=filename or dest.name,
                path=str(dest),
            )
        )
        db.commit()

        version = create_asset_version(
            db,
            project_id=project_id,
            department="audio",
            status="generated",
            asset_id=asset_id,
            metadata={
                "kind": kind,
                "imported": True,
                "fixture": False,
                "filename": filename,
                "assetPath": str(dest),
                "sha256": sha256,
                "bytes": len(content),
                "durationSec": measured,
            },
        )

        placement = AudioService.place_cue(
            db,
            project_id=project_id,
            kind=kind,
            asset_id=asset_id,
            start_sec=start_sec,
            duration_sec=length,
            scene_id=scene_id,
            volume=volume,
            ducking=ducking,
        )
        return {
            **placement,
            "assetId": asset_id,
            "versionId": version["id"],
            "assetPath": str(dest),
            "sha256": sha256,
            "bytes": len(content),
            "measuredDurationSec": measured,
            "durationSec": length,
            "imported": True,
            "provider": "user_import",
        }

    @staticmethod
    def revise_cue_gain(
        db: Session,
        *,
        project_id: str,
        cue_id: str,
        volume: float,
    ) -> dict[str, Any]:
        """Change one placed cue's gain on both the cue row and its timeline clip."""

        row = _cue_row(db, cue_id)
        if not row or row["project_id"] != project_id:
            raise KeyError(cue_id)
        gain = float(volume)
        if gain < 0:
            raise ValueError("volume must be >= 0")
        meta = _cue_metadata(row)
        meta["volume"] = gain
        _update_cue(db, cue_id, metadata=meta)
        placed = False
        if row["scene_id"] and row["asset_id"]:
            placed = _write_scene_clip(
                db,
                project_id=project_id,
                scene_id=row["scene_id"],
                kind=row["cue_kind"],
                asset_id=row["asset_id"],
                start_sec=float(row["start_sec"] or 0.0),
                duration_sec=float(row["duration_sec"] or 2.0),
                volume=gain,
            )
        return {
            "cueId": cue_id,
            "projectId": project_id,
            "sceneId": row["scene_id"],
            "assetId": row["asset_id"],
            "kind": row["cue_kind"],
            "volume": gain,
            "timelineUpdated": placed,
        }
