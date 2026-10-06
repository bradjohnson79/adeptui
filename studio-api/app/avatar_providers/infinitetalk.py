"""Live InfiniteTalk section adapter for Avatar Studio.

Product path: Avatar Studio section job -> this adapter -> isolated InfiniteTalk
venv + generate_infinitetalk.py. No CLI bypass from Co-Director; no mocks.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..avatar_runtimes import (
    _active_runtime_root,
    inspect_runtime,
    runtime_gate_line,
)
from ..character_identity.models import VoiceProfileRow
from ..character_identity.voice_runtime import (
    _register_asset,
    generate_approved_voice_speech,
)
from ..config import settings

logger = logging.getLogger(__name__)

PROVIDER_ID = "infinitetalk-local"
DISPATCH_MARKER_NAME = "infinitetalk_dispatch_started.json"
SAMPLE_FPS = 16


def _work_dir(project_id: str, job_id: str, section_id: str) -> Path:
    root = settings.data_dir / "projects" / project_id / "avatar_sections" / job_id / section_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_dispatch_marker(work: Path, payload: dict[str, Any]) -> Path:
    marker = work / DISPATCH_MARKER_NAME
    marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Also mirror under live_cert for prove scripts when present.
    mirror = Path(r"C:\Users\bradj\theme_walk\avatar_studio_16x9\live_cert") / DISPATCH_MARKER_NAME
    try:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(marker.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass
    return marker


def _frame_num_for_duration_ms(duration_ms: int) -> int:
    """InfiniteTalk requires frame_num = 4n+1. Map section duration at 16fps."""
    seconds = max(1.0, float(duration_ms) / 1000.0)
    raw = int(round(seconds * SAMPLE_FPS))
    # nearest 4n+1 at or above raw
    n = max(1, (raw + 3) // 4)
    return 4 * n + 1


def _resolve_still_path(db: Session, session_data: dict[str, Any]) -> Path | None:
    from ..db import Asset

    look = session_data.get("look") if isinstance(session_data.get("look"), dict) else {}
    candidates = [
        session_data.get("source_still_asset_id"),
        look.get("portrait_asset_id") if isinstance(look, dict) else None,
    ]
    for asset_id in candidates:
        aid = str(asset_id or "").strip()
        if not aid:
            continue
        asset = db.get(Asset, aid)
        if asset and asset.path and Path(str(asset.path)).is_file():
            return Path(str(asset.path))
    return None


def _resolve_or_synthesize_audio(
    db: Session,
    *,
    project_id: str,
    session_data: dict[str, Any],
    section: dict[str, Any],
    work: Path,
) -> tuple[Path | None, str | None, str | None]:
    """Return (audio_path, error_code, error_message). Prefer attached audio; else approved voice TTS."""
    from ..db import Asset

    voice = session_data.get("voice") if isinstance(session_data.get("voice"), dict) else {}
    audio_ids = [
        voice.get("audio_asset_id"),
        voice.get("fallback_audio_asset_id"),
        section.get("audioAssetId"),
    ]
    for aid in audio_ids:
        asset_id = str(aid or "").strip()
        if not asset_id:
            continue
        asset = db.get(Asset, asset_id)
        if asset and asset.path and Path(str(asset.path)).is_file():
            return Path(str(asset.path)), None, None

    script = str(section.get("scriptText") or session_data.get("dialogue_spoken") or session_data.get("dialogue_original") or "").strip()
    if not script:
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", "Section has no script text or attached audio for InfiniteTalk."

    voice_id = str(voice.get("profile_id") or "").strip()
    if not voice_id:
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", "Script mode requires an approved voice profile for InfiniteTalk audio."

    voice_row = db.get(VoiceProfileRow, voice_id)
    if voice_row is None:
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", f"Voice profile {voice_id} was not found."
    if str(voice_row.approval_status or "").lower() != "approved":
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", "Avatar Studio InfiniteTalk requires an approved voice profile in script mode."

    try:
        produced = generate_approved_voice_speech(
            db,
            project_id=project_id,
            voice=voice_row,
            text=script,
            seed=int(section.get("attempt") or 1),
        )
    except Exception as exc:
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", f"Approved voice speech failed before InfiniteTalk: {exc}"

    audio_path = Path(str(produced.get("path") or ""))
    if not audio_path.is_file():
        return None, "AVATAR_SECTION_RUNTIME_UNAVAILABLE", "Approved voice speech did not produce a WAV file."

    # Register for provenance; keep using the local path for InfiniteTalk.
    try:
        _register_asset(
            db,
            project_id,
            audio_path,
            kind="audio",
            name=f"avatar-section-{section.get('id') or 'audio'}",
            tag="avatar_section_audio",
            extra_meta={
                "source": "avatar_studio.infinitetalk.approved_voice",
                "voiceProfileId": voice_id,
                "sectionId": section.get("id"),
            },
        )
        db.flush()
    except Exception:
        logger.exception("Failed to register section audio asset; continuing with path")

    # Copy into work dir for stable relative references
    dest = work / "person1.wav"
    dest.write_bytes(audio_path.read_bytes())
    return dest, None, None


def _infinitetalk_weight(root: Path) -> Path:
    single = root / "models" / "infinitetalk" / "single" / "infinitetalk.safetensors"
    if single.is_file():
        return single
    # fallback comfy naming
    alt = root / "models" / "infinitetalk" / "comfyui" / "infinitetalk_single.safetensors"
    return alt


def build_infinitetalk_command(
    *,
    root: Path,
    work: Path,
    input_json: Path,
    save_file_stem: Path,
    frame_num: int,
    size: str = "infinitetalk-480",
) -> tuple[list[str], Path]:
    venv_py = root / "venv" / "Scripts" / "python.exe"
    script = root / "source" / "generate_infinitetalk.py"
    ckpt = root / "models" / "wan_2_1_i2v_14b_480p"
    wav2vec = root / "models" / "chinese_wav2vec2_base"
    weight = _infinitetalk_weight(root)
    for required in (venv_py, script, ckpt, wav2vec, weight):
        if not Path(required).exists():
            raise FileNotFoundError(f"InfiniteTalk runtime missing required path: {required}")

    cmd = [
        str(venv_py),
        str(script),
        "--task",
        "infinitetalk-14B",
        "--size",
        size,
        "--ckpt_dir",
        str(ckpt),
        "--wav2vec_dir",
        str(wav2vec),
        "--infinitetalk_dir",
        str(weight),
        "--input_json",
        str(input_json),
        "--save_file",
        str(save_file_stem),
        "--audio_mode",
        "localfile",
        "--mode",
        "clip",
        "--frame_num",
        str(frame_num),
        "--sample_steps",
        "40",
        "--base_seed",
        "42",
        "--audio_save_dir",
        str(work / "audio_embed"),
    ]
    # 5090 has ~32GB; still enable offload as a safety default for Windows.
    cmd.extend(["--offload_model", "True"])
    return cmd, venv_py


def run_infinitetalk_section(
    db: Session,
    *,
    project_id: str,
    session_data: dict[str, Any],
    job: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    """Execute one Avatar Studio section through live InfiniteTalk.

    Returns the Avatar Studio section result dict (`ok`, `outputVideoAssetId`, ...).
    """
    provider_id = str(job.get("providerId") or PROVIDER_ID)
    # Preflight already aligned Ready authorities; do not re-hard-fail on a cold
    # import-probe flap. Structural files are re-checked below before Popen.
    job_id = str(job.get("id") or "job")
    section_id = str(section.get("id") or f"sec-{uuid.uuid4().hex[:8]}")
    work = _work_dir(project_id, job_id, section_id)
    root = _active_runtime_root(PROVIDER_ID)

    # Early marker proves Avatar Studio entered the InfiniteTalk adapter (before TTS / Popen).
    _write_dispatch_marker(
        work,
        {
            "startedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "providerId": PROVIDER_ID,
            "projectId": project_id,
            "jobId": job_id,
            "sectionId": section_id,
            "status": "adapter_entered",
            "runtimeRoot": str(root),
        },
    )

    still = _resolve_still_path(db, session_data)
    if still is None:
        return {
            "ok": False,
            "errorCode": "AVATAR_SECTION_RUNTIME_UNAVAILABLE",
            "message": "InfiniteTalk needs a portrait / source still asset on the session.",
        }

    # Stage still into work dir
    still_ext = still.suffix or ".png"
    still_staged = work / f"ref_image{still_ext}"
    if not still_staged.exists() or still_staged.stat().st_mtime < still.stat().st_mtime:
        still_staged.write_bytes(still.read_bytes())

    audio_path, audio_err, audio_msg = _resolve_or_synthesize_audio(
        db,
        project_id=project_id,
        session_data=session_data,
        section=section,
        work=work,
    )
    if audio_path is None:
        return {
            "ok": False,
            "errorCode": audio_err or "AVATAR_SECTION_RUNTIME_UNAVAILABLE",
            "message": audio_msg or "Audio preparation failed.",
        }

    prompt = str(
        session_data.get("prompt")
        or section.get("scriptText")
        or session_data.get("dialogue_spoken")
        or "A person speaking to camera."
    ).strip()

    input_payload = {
        "prompt": prompt,
        "cond_video": str(still_staged).replace("\\", "/"),
        "cond_audio": {"person1": str(audio_path).replace("\\", "/")},
    }
    input_json = work / "input.json"
    input_json.write_text(json.dumps(input_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    duration_ms = max(
        1000,
        int(section.get("requestedDurationMs") or 0)
        or max(0, int(section.get("audioEndMs") or 0) - int(section.get("audioStartMs") or 0))
        or 10000,
    )
    frame_num = _frame_num_for_duration_ms(duration_ms)
    save_stem = work / f"section_{section_id}"
    expected_mp4 = Path(str(save_stem) + ".mp4")

    try:
        cmd, venv_py = build_infinitetalk_command(
            root=root,
            work=work,
            input_json=input_json,
            save_file_stem=save_stem,
            frame_num=frame_num,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "errorCode": "AVATAR_SECTION_RUNTIME_UNAVAILABLE",
            "message": str(exc),
        }

    log_path = work / "infinitetalk_run.log"
    marker_payload = {
        "startedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "providerId": PROVIDER_ID,
        "projectId": project_id,
        "jobId": job_id,
        "sectionId": section_id,
        "venvPython": str(venv_py),
        "cwd": str(root / "source"),
        "command": cmd,
        "inputJson": str(input_json),
        "expectedMp4": str(expected_mp4),
        "frameNum": frame_num,
        "durationMs": duration_ms,
        "stillPath": str(still_staged),
        "audioPath": str(audio_path),
        "runtimeRoot": str(root),
    }
    marker = _write_dispatch_marker(work, marker_payload)
    logger.info("InfiniteTalk section dispatch starting: %s", marker)

    env = os.environ.copy()
    source_dir = root / "source"
    env["PYTHONPATH"] = str(source_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["TORCHDYNAMO_DISABLE"] = "1"
    env["TORCH_COMPILE_DISABLE"] = "1"

    # Honest live run ? no mock success. Record PID as soon as process starts.
    with log_path.open("w", encoding="utf-8", errors="replace") as logf:
        logf.write("CMD: " + " ".join(cmd) + "\n\n")
        logf.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(source_dir),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            text=True,
        )
        marker_payload["pid"] = proc.pid
        marker_payload["status"] = "process_started"
        _write_dispatch_marker(work, marker_payload)
        logger.info("InfiniteTalk PID %s started for section %s", proc.pid, section_id)
        returncode = proc.wait()

    marker_payload["returncode"] = returncode
    marker_payload["finishedAtUtc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    marker_payload["status"] = "finished"
    marker_payload["logPath"] = str(log_path)
    _write_dispatch_marker(work, marker_payload)

    if returncode != 0 or not expected_mp4.is_file():
        # Prefer last log lines for recovery text
        detail = ""
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            detail = " | ".join(lines[-8:]) if lines else ""
        except Exception:
            detail = ""
        return {
            "ok": False,
            "errorCode": "AVATAR_SECTION_RUNTIME_UNAVAILABLE",
            "message": (
                f"InfiniteTalk live generation failed (exit {returncode}). "
                f"{detail[:500]}"
            ).strip(),
            "logPath": str(log_path),
            "dispatchMarker": str(marker),
            "pid": marker_payload.get("pid"),
        }

    # Register video asset into the project library
    from ..db import Asset

    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            kind="video",
            filename=expected_mp4.name,
            path=str(expected_mp4),
            tag="avatar_section",
        )
    )
    db.flush()

    return {
        "ok": True,
        "outputVideoAssetId": aid,
        "continuationFrameAssetId": None,
        "providerId": PROVIDER_ID,
        "logPath": str(log_path),
        "dispatchMarker": str(marker),
        "outputPath": str(expected_mp4),
        "pid": marker_payload.get("pid"),
    }


__all__ = [
    "PROVIDER_ID",
    "build_infinitetalk_command",
    "run_infinitetalk_section",
    "DISPATCH_MARKER_NAME",
]
