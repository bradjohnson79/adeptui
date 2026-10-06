"""Bounded Mask/Repair Inpaint â€” painted still applied only to the marked range."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.db import Asset, Base, Job, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import service, store
from app.director_timeline_w46.contracts import ApprovedClip, SceneTimelineMaster
from app.director_timeline_w46.inpaint_repair import (
    NATIVE_DISCLOSURE,
    apply_inpaint_repair,
    extract_repair_frame,
    submit_inpaint_repair,
    submit_video_retake,
)
from app.director_timeline_w46.keyframe_repair import overlay_repaired_still_on_window
from app.director_timeline_w46.range_replacement import extract_cut_in_frame_asset
from app.production_control.generator_authority import timeline_generator_snapshot


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Keyframe Repair", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="corridor walk",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        pytest.skip("ffmpeg required")
    return ffmpeg


def _color_video(path: Path, color: str, seconds: float) -> None:
    ffmpeg = _ffmpeg()
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64:d={seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not path.is_file():
        pytest.skip(f"ffmpeg color video failed: {(proc.stderr or '')[:200]}")


def _solid_png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (64, 64), color).save(path)


def _center_mask(path: Path) -> None:
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    for x in range(20, 44):
        for y in range(20, 44):
            img.putpixel((x, y), (255, 255, 255))
    img.save(path)


def _seed_batch(db: Session, project_id: str, scene_id: str, *, asset_id: str | None) -> tuple[str, str]:
    ws = service.workspace(db, project_id, scene_id)
    assert ws.get("ok")
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, project_id, scene_id)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = "ltx-local"
    batch.status = "Approved"
    if asset_id:
        batch.approvedClip = ApprovedClip(assetId=asset_id, executionSnapshotId="snap_seed")
    store.save_master(db, project_id, scene_id, master)
    from app.director_timeline_w46.orchestrator import add_repair_range

    added = add_repair_range(
        db,
        project_id,
        scene_id,
        batch_id,
        {"start": 1.0, "length": 1.0, "label": "Repair", "inPaintStrategy": "keyframe_repair"},
        policy="stack_advanced",
    )
    assert added.get("ok"), added
    ranges = added.get("ranges") or []
    return batch_id, ranges[-1]["id"]


def test_overlay_keeps_unpainted_motion(tmp_path):
    source = tmp_path / "source.mp4"
    dest = tmp_path / "out.mp4"
    still = tmp_path / "still.png"
    mask = tmp_path / "mask.png"
    _color_video(source, "blue", 2.0)
    _solid_png(still, (255, 0, 0))
    _center_mask(mask)
    result = overlay_repaired_still_on_window(
        source_path=source,
        repaired_still_path=still,
        mask_path=mask,
        dest_path=dest,
        start=0.5,
        length=1.0,
        source_duration=2.0,
    )
    assert result.get("ok") is True, result
    assert dest.is_file()


def test_extract_frame_requires_generated_take(db_scene):
    db, pid, sid = db_scene
    batch_id, repair_id = _seed_batch(db, pid, sid, asset_id=None)
    result = extract_repair_frame(db, pid, sid, batch_id, repair_id)
    assert result.get("ok") is False
    assert result.get("error") == "GENERATED_TAKE_REQUIRED"


def test_submit_refuses_without_prompt_or_mask(db_scene, tmp_path):
    db, pid, sid = db_scene
    video = tmp_path / "take.mp4"
    _color_video(video, "green", 3.0)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="take",
        kind="video",
        filename=video.name,
        path=str(video),
        scope="project",
    )
    db.add(asset)
    db.commit()
    batch_id, repair_id = _seed_batch(db, pid, sid, asset_id=asset.id)
    missing_prompt = submit_inpaint_repair(
        db, pid, sid, batch_id, repair_id, prompt="  ", mask_png_base64="abc"
    )
    assert missing_prompt.get("error") == "REPAIR_PROMPT_REQUIRED"
    missing_mask = submit_inpaint_repair(
        db, pid, sid, batch_id, repair_id, prompt="remove the glitch", mask_png_base64=""
    )
    assert missing_mask.get("error") == "MASK_REQUIRED"


def test_submit_does_not_queue_full_batch_generate(db_scene, tmp_path):
    db, pid, sid = db_scene
    video = tmp_path / "take.mp4"
    _color_video(video, "green", 3.0)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="take",
        kind="video",
        filename=video.name,
        path=str(video),
        scope="project",
    )
    db.add(asset)
    db.commit()
    batch_id, repair_id = _seed_batch(db, pid, sid, asset_id=asset.id)
    png = tmp_path / "mask.png"
    _center_mask(png)
    import base64

    mask_b64 = base64.b64encode(png.read_bytes()).decode("ascii")

    def fake_enqueue(db_arg, project_id, body):
        assert body.get("operation") == "image.inpaint"
        assert body.get("sourceAssetId")
        assert body.get("masks")
        first_mask = body["masks"][0]
        assert first_mask.get("maskId")
        assert first_mask.get("maskAssetId") == first_mask.get("maskId")
        return {"ok": True, "jobId": "job-inpaint-1", "workflowKey": "zimage.inpaint"}

    with patch("app.director_timeline_w46.inpaint_repair.enqueue_edit", side_effect=fake_enqueue):
        with patch("app.director_timeline_w46.orchestrator.submit_batch_generation") as full_batch:
            result = submit_inpaint_repair(
                db,
                pid,
                sid,
                batch_id,
                repair_id,
                prompt="clean the corridor wall",
                mask_png_base64=mask_b64,
            )
            full_batch.assert_not_called()
    assert result.get("ok") is True, result
    assert result.get("jobId") == "job-inpaint-1"
    assert "unavailable" in result.get("disclosure", "").lower()


def test_apply_attaches_candidate_without_approving(db_scene, tmp_path):
    db, pid, sid = db_scene
    video = tmp_path / "take.mp4"
    still = tmp_path / "still.png"
    mask = tmp_path / "mask.png"
    _color_video(video, "blue", 4.0)
    _solid_png(still, (255, 0, 0))
    _center_mask(mask)
    source = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="take",
        kind="video",
        filename=video.name,
        path=str(video),
        scope="project",
    )
    repaired = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="inpaint",
        kind="image",
        filename=still.name,
        path=str(still),
        scope="project",
    )
    db.add(source)
    db.add(repaired)
    db.commit()
    batch_id, repair_id = _seed_batch(db, pid, sid, asset_id=source.id)
    from app.image_product.masks import save_mask

    mask_rec = save_mask(pid, source_asset_id=repaired.id, path=str(mask), role="include")
    job = Job(
        id=str(uuid.uuid4()),
        project_id=pid,
        scene_id=sid,
        kind="imagegen_edit",
        status="done",
        params_json=json.dumps({"output_asset_id": repaired.id}),
    )
    db.add(job)
    db.commit()
    from app.director_timeline_w46.inpaint_repair import _save_repair_metadata

    _save_repair_metadata(
        db,
        pid,
        sid,
        batch_id,
        repair_id,
        {"maskId": mask_rec["maskId"], "prompt": "clean the wall", "jobId": job.id},
    )
    result = apply_inpaint_repair(db, pid, sid, batch_id, repair_id, job_id=job.id)
    assert result.get("ok") is True, result
    assert result.get("autoApproved") is False
    assert result.get("candidate")
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    assert batch.approvedClip and batch.approvedClip.assetId == source.id
    assert batch.status == "Approved"
    assert any(c.assetId == result["assetId"] for c in batch.candidateVersions)


def test_keyframe_repair_listed_for_timeline_engines():
    rows = {row.id: row for row in timeline_generator_snapshot()}
    assert "keyframe_repair" in rows["ltx-local"].inPaintStrategies
    assert NATIVE_DISCLOSURE


def test_extract_cut_in_frame_writes_png(db_scene, tmp_path):
    db, pid, sid = db_scene
    video = tmp_path / "take.mp4"
    _color_video(video, "gray", 2.0)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="take",
        kind="video",
        filename=video.name,
        path=str(video),
        scope="project",
    )
    db.add(asset)
    db.commit()
    result = extract_cut_in_frame_asset(db, project_id=pid, source_asset_id=asset.id, at_seconds=0.4)
    assert result.get("ok") is True, result
    frame = db.get(Asset, result["assetId"])
    assert frame is not None
    assert Path(frame.path).is_file()


def test_submit_video_retake_requires_instruction(db_scene, tmp_path):
    db, pid, sid = db_scene
    video = tmp_path / "take.mp4"
    _color_video(video, "green", 3.0)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="take",
        kind="video",
        filename=video.name,
        path=str(video),
        scope="project",
    )
    db.add(asset)
    db.commit()
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    master.batchBlocks[0].generatorId = "ltx-local"
    master.batchBlocks[0].status = "Approved"
    master.batchBlocks[0].approvedClip = ApprovedClip(assetId=asset.id, executionSnapshotId="snap_seed")
    store.save_master(db, pid, sid, master)
    blocked = submit_video_retake(db, pid, sid, batch_id, start=0.5, length=1.0, prompt="  ")
    assert blocked.get("ok") is False
    assert blocked.get("error") == "REPAIR_PROMPT_REQUIRED"

