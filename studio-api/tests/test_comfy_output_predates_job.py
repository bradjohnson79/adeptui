import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.video_runtime.output_gate import comfy_output_predates_job


def test_comfy_output_predates_job_detects_leftover(tmp_path: Path) -> None:
    leftover = tmp_path / "old.mp4"
    leftover.write_bytes(b"mp4")
    created = datetime.now(timezone.utc)
    old = (created - timedelta(minutes=6)).timestamp()
    os.utime(leftover, (old, old))
    assert comfy_output_predates_job(leftover, created.replace(tzinfo=None)) is True


def test_comfy_output_predates_job_allows_fresh_file(tmp_path: Path) -> None:
    fresh = tmp_path / "new.mp4"
    created = datetime.now(timezone.utc) - timedelta(seconds=5)
    fresh.write_bytes(b"mp4")
    assert comfy_output_predates_job(fresh, created.replace(tzinfo=None)) is False
