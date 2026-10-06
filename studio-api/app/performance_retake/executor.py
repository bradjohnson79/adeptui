"""Performance Retake executor — 11-stage pipeline.

Reuses proven patterns from media_retake, comfy_asset_stage, lipsync_runtime,
and the Qwen2.5-Omni worker client.  Never mutates the master file.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..codirector.video_intelligence.worker_client import run_av_perception
from ..comfy_client import comfy
from ..config import settings
from ..db import Asset, Scene
from ..media_ops import run_ffmpeg
from ..video_runtime.comfy_asset_stage import (
    ComfyAssetMissing,
    stage_h3_visual_asset,
    stage_library_asset,
)
from ..video_runtime.seed_resolve import comfy_noise_seed
from ..workflows.h3_ref2v_builder import frames_for_duration
from ..workflows.lipsync_runtime import extract_output_path_from_history
from .contracts import (
    CharacterSheetRef,
    PerformanceRetakeError,
    PerformanceRetakeSpec,
    RetakeBeat,
    RetakeReferences,
    RetakeWindow,
    validate_spec,
)
from .h3_retake_graph import assert_h3_retake_graph, build_h3_retake_graph
from .prompt_compile import compile_performance_prompt

LOGGER = logging.getLogger(__name__)

# Stage names for error messages.
S_RAZOR = "RAZOR"
S_QWEN_PRE = "QWEN_PRE_REVIEW"
S_VOICE = "VOICE"
S_STAGE = "STAGE"
S_GRAPH = "GRAPH"
S_PROMPT = "PROMPT"
S_RENDER = "RENDER"
S_TRIM = "TRIM"
S_STITCH = "STITCH"
S_QWEN_POST = "QWEN_POST_REVIEW"
S_PERSIST = "PERSIST"

H3_DEFAULT_STEPS = 20
# Live failure 7db0b365: default 60s POST /prompt timed out (httpx.ReadTimeout
# with an empty message) after Qwen Omni pre-review. H3 graph accept can stall
# while VRAM settles or Comfy validates LoadVideo + MiniMaxH3ReferenceToVideo.
H3_SUBMIT_TIMEOUT_SEC = 180.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_video(path: Path) -> dict[str, Any]:
    """Reuse the media_retake ffprobe helper."""
    from ..media_retake.executor import _probe_video as _media_probe

    return _media_probe(path)


def _cut_window(
    master: Path,
    window_path: Path,
    start_sec: float,
    end_sec: float,
    fps: float,
    log: Callable[[str], None],
) -> None:
    """Lossless ffmpeg cut; re-encode only if copy fails."""
    window_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_ffmpeg(
            [
                "-ss",
                str(start_sec),
                "-to",
                str(end_sec),
                "-i",
                str(master),
                "-c",
                "copy",
                str(window_path),
            ]
        )
        log(f"[performance-retake] {S_RAZOR}: lossless copy cut succeeded")
        return
    except RuntimeError as exc:
        log(
            f"[performance-retake] {S_RAZOR}: copy cut failed ({exc}), "
            "re-encoding window"
        )

    run_ffmpeg(
        [
            "-ss",
            str(start_sec),
            "-to",
            str(end_sec),
            "-i",
            str(master),
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-an",
            str(window_path),
        ]
    )
    log(f"[performance-retake] {S_RAZOR}: re-encoded window cut completed")


def _try_probe(path: Path) -> dict[str, Any] | None:
    try:
        return _probe_video(path)
    except Exception:
        return None


def _recover_h3_render(
    history_entry: dict[str, Any],
    *,
    filename_prefix: str,
    expected_width: int,
    expected_height: int,
    min_duration_sec: float,
    log: Callable[[str], None],
) -> Path:
    """Resolve the H3 MP4. Never accept a LatentSync leftover.

    Live failure 35f215b9: H3 SaveVideo writes the MP4 under outputs.images
    (not videos/gifs). The LatentSync extractor skipped it and fell back to
    the newest latentsync_*_out.mp4 — a 346x256 / 1.28s clip.
    """
    prefix_token = Path(filename_prefix).name
    candidates: list[Path] = []
    try:
        candidates.extend(comfy.find_output_files(history_entry))
    except Exception as exc:
        log(f"[performance-retake] {S_RENDER}: find_output_files failed: {exc}")
    extracted = extract_output_path_from_history(history_entry)
    if extracted:
        candidates.append(extracted)
    try:
        output_root = Path(settings.comfy_output_dir)
        for root_path in (output_root, output_root / "studio"):
            if root_path.is_dir() and prefix_token:
                candidates.extend(sorted(root_path.glob(f"{prefix_token}*.mp4")))
    except OSError:
        pass

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if not path:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(Path(path))

    def _acceptable(path: Path) -> bool:
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".webm", ".mov"}:
            return False
        if "latentsync" in path.name.lower():
            return False
        probe = _try_probe(path)
        if probe is None:
            return prefix_token and prefix_token in path.name
        width = int(probe.get("width") or 0)
        duration = float(probe.get("duration") or 0.0)
        if expected_width and width and width < int(expected_width * 0.9):
            log(
                f"[performance-retake] {S_RENDER}: reject {path.name} "
                f"width={width} (expected ~{expected_width})"
            )
            return False
        if min_duration_sec and duration and duration < (min_duration_sec * 0.8):
            log(
                f"[performance-retake] {S_RENDER}: reject {path.name} "
                f"duration={duration:.3f}s (expected ~{min_duration_sec:.3f}s)"
            )
            return False
        return True

    ranked = [p for p in unique if prefix_token and prefix_token in p.name]
    for path in ranked + [p for p in unique if p not in ranked]:
        if _acceptable(path):
            log(f"[performance-retake] {S_RENDER}: recovered render {path.name}")
            return path
    raise PerformanceRetakeError(
        f"[performance-retake] {S_RENDER}: no acceptable H3 output recovered "
        f"(prefix={filename_prefix!r}, candidates={[p.name for p in unique]})"
    )


def _trim_video(
    source: Path,
    dest: Path,
    target_length_sec: float,
    fps: float,
) -> None:
    """Trim generated clip to the exact window length.

    Re-encode by default. Stream-copy is unsafe on H3 outputs whose first
    keyframe is late — live job 35f215b9 produced a 74KB stub that way
    when the wrong source was also selected.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(source),
            "-t",
            str(target_length_sec),
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(dest),
        ]
    )


def _splice_subwindow(
    master: Path,
    final_path: Path,
    trimmed: Path,
    window: RetakeWindow,
    scene_duration_sec: float,
    fps: float,
    log: Callable[[str], None],
) -> None:
    """Splice the trimmed window back into an untouched master copy.

    Uses the ffmpeg concat demuxer.  Re-encodes only if the copy concat fails.
    """
    work_dir = final_path.parent / f"_perfretake_splice_{final_path.stem[-6:]}"
    work_dir.mkdir(parents=True, exist_ok=True)
    head = work_dir / "head.mp4"
    tail = work_dir / "tail.mp4"

    run_ffmpeg(
        [
            "-i",
            str(master),
            "-t",
            str(window.startSec),
            "-c",
            "copy",
            str(head),
        ]
    )
    run_ffmpeg(
        [
            "-i",
            str(master),
            "-ss",
            str(window.endSec),
            "-t",
            str(max(0.0, scene_duration_sec - window.endSec)),
            "-c",
            "copy",
            str(tail),
        ]
    )

    list_file = work_dir / "concat.txt"
    parts: list[Path] = [head, trimmed, tail]
    lines: list[str] = []
    for p in parts:
        escaped = str(p.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    try:
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(final_path),
            ]
        )
        log(f"[performance-retake] {S_STITCH}: lossless copy splice succeeded")
    except RuntimeError as exc:
        log(
            f"[performance-retake] {S_STITCH}: copy splice failed ({exc}), "
            "re-encoding concat"
        )
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                str(final_path),
            ]
        )
        log(f"[performance-retake] {S_STITCH}: re-encoded splice completed")
    finally:
        if list_file.exists():
            list_file.unlink(missing_ok=True)


def _scene_dialogue_lines(scene: Scene) -> list[str]:
    """Best-effort extraction of old dialogue lines from the scene row."""
    lines: list[str] = []
    try:
        data = json.loads(scene.director_json or "{}")
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    for key in ("audio_clips", "lipsync", "clips"):
        clips = data.get(key)
        if isinstance(clips, list):
            for clip in clips:
                if isinstance(clip, dict):
                    text = (clip.get("text") or clip.get("label") or "").strip()
                    if text:
                        lines.append(text)

    if scene.prompt:
        # Pull any quoted dialogue from the scene prompt as a leak guard.
        for match in _DIALOGUE_QUOTE_RE.findall(scene.prompt):
            lines.append(match.strip())

    return lines


_DIALOGUE_QUOTE_RE = re.compile(r'"([^"]{3,})"')


def _resolve_seed(scene: Scene) -> int:
    raw = scene.seed
    if raw is not None and int(raw) >= 0:
        return int(raw)
    return int(comfy_noise_seed(None))


async def _prepare_comfy_for_h3_submit(log: Callable[[str], None]) -> None:
    """Settle GPU after Qwen Omni, then /free idle Comfy models before H3.

    Matches the production H3 Ref2V path in queue_worker. Never restarts Comfy.
    """
    from ..codirector.video_intelligence.gpu_lease import (
        comfy_generation_active,
        wait_for_free_vram,
    )

    wait = wait_for_free_vram(min_gb=12.0, timeout_sec=30.0, interval_sec=2.0)
    log(
        f"[performance-retake] {S_RENDER}: vram settle "
        f"ok={wait.get('ok')} free={wait.get('freeVramGb')} "
        f"waited={wait.get('waitedSec')}s"
    )
    active = comfy_generation_active()
    if active.get("active"):
        log(
            f"[performance-retake] {S_RENDER}: Comfy queue busy "
            f"(running={active.get('running')} pending={active.get('pending')}); "
            "skipping /free"
        )
        return
    try:
        await comfy.free_memory(unload_models=True, free_memory=True)
        log(f"[performance-retake] {S_RENDER}: requested Comfy /free before H3 submit")
    except Exception as exc:
        log(f"[performance-retake] {S_RENDER}: Comfy /free skipped: {exc}")


def _stage_window_video(window_source: Path, scene_id: str, log: Callable[[str], None]) -> str:
    """Plain-copy the source window into Comfy input under studio/{scene_id}.mp4."""
    subfolder = "studio"
    name = f"{subfolder}/{scene_id}.mp4"
    dest = settings.comfy_input_dir / subfolder / f"{scene_id}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(window_source, dest)
    log(f"[performance-retake] {S_STAGE}: staged window video as {name}")
    return name


def _stage_character_sheets(
    db: Session,
    sheets: list[CharacterSheetRef],
    log: Callable[[str], None],
) -> list[str]:
    comfy_names: list[str] = []
    for sheet in sheets:
        asset = db.get(Asset, sheet.assetId)
        if not asset:
            raise PerformanceRetakeError(
                f"[performance-retake] {S_STAGE}: character sheet asset "
                f"{sheet.assetId} not found"
            )
        try:
            staged = stage_h3_visual_asset(asset, role="character", subfolder="studio")
        except ComfyAssetMissing as exc:
            raise PerformanceRetakeError(
                f"[performance-retake] {S_STAGE}: character sheet missing: {exc}"
            ) from exc
        comfy_names.append(staged.comfy_name)
        log(
            f"[performance-retake] {S_STAGE}: staged character sheet "
            f"{sheet.assetId} as {staged.comfy_name}"
        )
    return comfy_names


def _stage_voice_lines(
    db: Session,
    beats: list[RetakeBeat],
    log: Callable[[str], None],
) -> list[str]:
    comfy_names: list[str] = []
    for beat in beats:
        if beat.kind != "dialogue" or not beat.voiceAssetId:
            continue
        asset = db.get(Asset, beat.voiceAssetId)
        if not asset:
            raise PerformanceRetakeError(
                f"[performance-retake] {S_VOICE}: voice asset {beat.voiceAssetId} "
                f"for {beat.characterName} not found"
            )
        try:
            staged = stage_library_asset(asset, subfolder="studio")
        except ComfyAssetMissing as exc:
            raise PerformanceRetakeError(
                f"[performance-retake] {S_VOICE}: voice asset missing: {exc}"
            ) from exc
        comfy_names.append(staged.comfy_name)
        log(
            f"[performance-retake] {S_STAGE}: staged voice line "
            f"{beat.voiceAssetId} as {staged.comfy_name}"
        )
    return comfy_names


def _perception_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize the full Qwen2.5-Omni AV payload, KEEPING speechSegments —
    the dialogue verdicts (speaker timing, old-dialogue removal, no invented
    lines) are impossible without the audio track's speech evidence."""
    return {
        "available": True,
        "modelId": str(payload.get("modelId") or payload.get("model") or "qwen2-5-omni"),
        "summary": str(payload.get("summary") or ""),
        "speechSegments": list(payload.get("speechSegments") or []),
        "audioEvents": list(payload.get("audioEvents") or []),
        "visualEvents": list(payload.get("visualEvents") or []),
        "motionEvents": list(payload.get("motionEvents") or []),
        "characters": list(payload.get("characters") or []),
    }


def _default_question() -> str:
    return (
        "Watch this clip AND listen to its audio track. "
        "Name visible characters, their actions, camera movement, framing, and lighting. "
        "Transcribe every spoken line with its start/end time and which character speaks it. "
        "State explicitly if any face looks sliced, warped, duplicated, or pasted on. "
        "State explicitly any time range with no speech. "
        "Do not invent facts you cannot see or hear."
    )


async def execute_performance_retake(
    db: Session,
    spec: PerformanceRetakeSpec,
    *,
    job_id: str,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the Performance Retake 11-stage pipeline.

    Returns a result dict with outputPath, sidecarPath, reviews, and SHA256s.
    Raises PerformanceRetakeError on any failure.
    """
    try:
        return await _run_pipeline(db, spec, job_id=job_id, log=log)
    except PerformanceRetakeError:
        raise
    except Exception as exc:
        raise PerformanceRetakeError(
            f"[performance-retake] pipeline failed: {exc}"
        ) from exc


async def _run_pipeline(
    db: Session,
    spec: PerformanceRetakeSpec,
    *,
    job_id: str,
    log: Callable[[str], None],
) -> dict[str, Any]:
    log(f"[performance-retake] starting job {job_id[:8]} spec v{spec.specVersion}")

    scene = db.get(Scene, spec.sceneId)
    if not scene:
        raise PerformanceRetakeError(
            f"[performance-retake] scene {spec.sceneId} not found"
        )
    if not scene.output_path:
        raise PerformanceRetakeError(
            "[performance-retake] scene has no rendered master video"
        )
    master_path = Path(scene.output_path)
    if not master_path.is_file():
        raise PerformanceRetakeError(
            f"[performance-retake] master video missing: {master_path}"
        )

    master_sha_before = _sha256(master_path)

    probe = _probe_video(master_path)
    fps = float(probe["fps"] or scene.fps or 24)
    width = int(probe["width"] or scene.width or 1152)
    height = int(probe["height"] or scene.height or 640)
    scene_duration = float(probe["duration"] or spec.masterDurationSec or 0.0)

    # S1 RAZOR
    if spec.window.scope == "whole_shot":
        window_path = master_path
        log(f"[performance-retake] {S_RAZOR}: whole_shot — using master {master_path.name}")
    else:
        work_dir = (
            settings.data_dir
            / "projects"
            / spec.projectId
            / "renders"
            / f"_perfretake_{job_id[:8]}"
        )
        work_dir.mkdir(parents=True, exist_ok=True)
        window_path = work_dir / f"window_{job_id[:8]}.mp4"
        _cut_window(
            master_path,
            window_path,
            spec.window.startSec,
            spec.window.endSec,
            fps,
            log,
        )

    # S2 QWEN PRE-REVIEW
    qwen_pre: dict[str, Any] | None = None
    shot_observation = ""
    if spec.qwenPreReview:
        try:
            perception = run_av_perception(
                str(window_path),
                question=_default_question(),
                model_id="qwen2-5-omni",
                timeout_sec=300.0,
                start_sec=0.0,
                duration_sec=float(spec.window.length or 6.0),
            )
            qwen_pre = _perception_summary(perception)
            shot_observation = str(perception.get("summary") or "")
            log(f"[performance-retake] {S_QWEN_PRE}: observation collected")
        except Exception as exc:
            qwen_pre = {"available": False, "reason": str(exc)[:500]}
            log(
                f"[performance-retake] {S_QWEN_PRE}: perception unavailable — {exc}"
            )

    # S3 VOICE — verify assets exist; actual rendering is the caller's responsibility.
    for beat in spec.dialogue_beats:
        if not beat.voiceAssetId:
            raise PerformanceRetakeError(
                f"[performance-retake] {S_VOICE}: beat for {beat.characterName} "
                "has no voiceAssetId"
            )
        asset = db.get(Asset, beat.voiceAssetId)
        if not asset or not asset.path or not Path(asset.path).is_file():
            raise PerformanceRetakeError(
                f"[performance-retake] {S_VOICE}: voice asset {beat.voiceAssetId} "
                f"for {beat.characterName} missing on disk"
            )
    log(f"[performance-retake] {S_VOICE}: verified {len(spec.dialogue_beats)} dialogue voice asset(s)")

    # S4 STAGE
    window_comfy_name = _stage_window_video(window_path, spec.sceneId, log)
    ref_comfy_names = _stage_character_sheets(db, spec.references.characterSheets, log)
    ref_audio_names = _stage_voice_lines(db, spec.beats, log)

    # S5/S6 PROMPT + GRAPH
    forbidden_dialogue = _scene_dialogue_lines(scene)
    prompt = compile_performance_prompt(
        spec,
        shot_observation=shot_observation,
        forbidden_dialogue=forbidden_dialogue,
    )
    log(f"[performance-retake] {S_PROMPT}: compiled {len(prompt)}-char performance prompt")

    length = frames_for_duration(spec.window.length)
    seed = _resolve_seed(scene)
    filename_prefix = f"studio/{spec.projectId[:8]}_perfretake_{job_id[:8]}"

    try:
        graph = build_h3_retake_graph(
            prompt=prompt,
            ref_comfy_names=ref_comfy_names,
            ref_video_comfy_name=window_comfy_name,
            filename_prefix=filename_prefix,
            seed=seed,
            width=width,
            height=height,
            length=length,
            steps=H3_DEFAULT_STEPS,
            ref_image_size="match",
            fast=spec.quality == "fast",
            ref_audio_comfy_names=ref_audio_names or None,
            include_source_audio=spec.references.includeSourceAudio,
        )
        assert_h3_retake_graph(
            graph,
            expected_names=ref_comfy_names,
            expected_video_name=window_comfy_name,
            expected_audio_names=ref_audio_names or None,
            expect_source_audio=spec.references.includeSourceAudio,
            expect_fast=spec.quality == "fast",
            expected_prompt=prompt,
            expected_width=width,
            expected_height=height,
        )
    except Exception as exc:
        raise PerformanceRetakeError(
            f"[performance-retake] {S_GRAPH}: graph build/assert failed: {exc}"
        ) from exc
    log(f"[performance-retake] {S_GRAPH}: built H3 retake graph ({len(graph)} nodes)")

    # S7 RENDER
    # No workflow_key: H3 model components are not catalogued in the workflow
    # readiness registry (the production MiniMax H3 Route A adapter bypasses that
    # layer for the same reason and direct-posts to /prompt). Node-type validation
    # still runs here via assert_graph_runnable against the live :8188 catalogue,
    # and assert_h3_retake_graph above pins the H3 model files and ref wiring.
    await _prepare_comfy_for_h3_submit(log)
    try:
        prompt_id = await comfy.queue_prompt(graph, timeout_sec=H3_SUBMIT_TIMEOUT_SEC)
        log(f"[performance-retake] {S_RENDER}: queued Comfy prompt {prompt_id[:16]}")
        history_entry = await comfy.wait_for_prompt(prompt_id, timeout_sec=900.0)
    except Exception as exc:
        raise PerformanceRetakeError(
            f"[performance-retake] {S_RENDER}: Comfy submission or wait failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    rendered_path = _recover_h3_render(
        history_entry,
        filename_prefix=filename_prefix,
        expected_width=width,
        expected_height=height,
        min_duration_sec=float(spec.window.length or 0.0),
        log=log,
    )

    # S8 TRIM/STITCH
    work_dir = (
        settings.data_dir
        / "projects"
        / spec.projectId
        / "renders"
        / f"_perfretake_{job_id[:8]}"
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    hash6 = uuid.uuid4().hex[:6]
    out_dir = settings.data_dir / "projects" / spec.projectId / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"scene_{scene.index}_perfretake_{hash6}.mp4"

    rendered_probe = _try_probe(rendered_path) or {}
    rendered_duration = float(rendered_probe.get("duration") or 0.0)
    close_enough = (
        rendered_duration > 0
        and abs(rendered_duration - float(spec.window.length)) <= 0.35
    )
    if spec.window.scope == "whole_shot" and close_enough:
        shutil.copy2(rendered_path, final_path)
        log(
            f"[performance-retake] {S_TRIM}: whole_shot — H3 render "
            f"{rendered_duration:.3f}s already matches window "
            f"{spec.window.length:.3f}s; skip trim"
        )
    elif spec.window.scope == "whole_shot":
        _trim_video(rendered_path, final_path, spec.window.length, fps)
        log(f"[performance-retake] {S_TRIM}: whole_shot — re-encoded to {spec.window.length}s")
    else:
        trimmed_path = work_dir / f"trim_{hash6}.mp4"
        _trim_video(rendered_path, trimmed_path, spec.window.length, fps)
        log(f"[performance-retake] {S_TRIM}: trimmed render to {spec.window.length}s")
        _splice_subwindow(
            master_path,
            final_path,
            trimmed_path,
            spec.window,
            scene_duration,
            fps,
            log,
        )
    log(f"[performance-retake] {S_STITCH}: final retake at {final_path.name}")

    # S9 AUDIO AUTHORITY: the window audio is H3 native output only.
    # No additional audio layering is performed.

    # S10 QWEN POST-REVIEW
    qwen_post: dict[str, Any] | None = None
    if spec.qwenPostReview:
        try:
            perception = run_av_perception(
                str(final_path),
                question=_default_question(),
                model_id="qwen2-5-omni",
                timeout_sec=300.0,
                start_sec=0.0,
                duration_sec=float(spec.window.length or 6.0),
            )
            qwen_post = _perception_summary(perception)
            log(f"[performance-retake] {S_QWEN_POST}: post-review collected")
        except Exception as exc:
            qwen_post = {
                "available": False,
                "reason": str(exc)[:500],
                "postReview": "unavailable",
            }
            log(
                f"[performance-retake] {S_QWEN_POST}: post-review unavailable — {exc}"
            )

    # S11 PERSIST
    master_sha_after = _sha256(master_path)
    if master_sha_after != master_sha_before:
        raise PerformanceRetakeError(
            f"[performance-retake] {S_PERSIST}: master file was mutated during retake "
            "(SHA256 mismatch)"
        )

    output_sha = _sha256(final_path)
    sidecar_path = final_path.with_suffix(".provenance.json")
    sidecar = {
        "producer": "performance_retake",
        "specVersion": 1,
        "spec": _spec_to_dict(spec),
        "generator": spec.generator,
        "seed": seed,
        "masterSha256": master_sha_before,
        "outputSha256": output_sha,
        "qwenPreReview": qwen_pre,
        "qwenPostReview": qwen_post,
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    sidecar_path.write_text(
        json.dumps(sidecar, indent=2, default=str),
        encoding="utf-8",
    )

    # Provenance pointer only — NOT Timeline Preview Visual authority (use video_clips/rtclip_*).\n    scene.lipsync_output_path = str(final_path)
    db.commit()
    log(f"[performance-retake] {S_PERSIST}: wrote sidecar {sidecar_path.name}")

    return {
        "ok": True,
        "outputPath": str(final_path),
        "sidecarPath": str(sidecar_path),
        "window": _window_to_dict(spec.window),
        "beats": [_beat_to_dict(b) for b in spec.beats],
        "generator": spec.generator,
        "qwenPreReview": qwen_pre,
        "qwenPostReview": qwen_post,
        "masterSha256Before": master_sha_before,
        "masterSha256After": master_sha_after,
    }


def _spec_to_dict(spec: PerformanceRetakeSpec) -> dict[str, Any]:
    return {
        "projectId": spec.projectId,
        "sceneId": spec.sceneId,
        "window": _window_to_dict(spec.window),
        "beats": [_beat_to_dict(b) for b in spec.beats],
        "references": {
            "characterSheets": [
                {"characterId": c.characterId, "assetId": c.assetId}
                for c in spec.references.characterSheets
            ],
            "sourceVideo": spec.references.sourceVideo,
            "includeSourceAudio": spec.references.includeSourceAudio,
        },
        "masterDurationSec": spec.masterDurationSec,
        "generator": spec.generator,
        "quality": spec.quality,
        "qwenPreReview": spec.qwenPreReview,
        "qwenPostReview": spec.qwenPostReview,
        "specVersion": spec.specVersion,
    }


def _window_to_dict(window: RetakeWindow) -> dict[str, Any]:
    return {
        "startSec": window.startSec,
        "endSec": window.endSec,
        "scope": window.scope,
        "boundarySource": window.boundarySource,
    }


def _beat_to_dict(beat: RetakeBeat) -> dict[str, Any]:
    return {
        "kind": beat.kind,
        "startSec": beat.startSec,
        "endSec": beat.endSec,
        "characterId": beat.characterId,
        "characterName": beat.characterName,
        "line": beat.line,
        "voiceAssetId": beat.voiceAssetId,
    }
