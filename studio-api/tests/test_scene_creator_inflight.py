"""Interrupted / failed jobs are not in-flight and must not be reused."""

from __future__ import annotations

from types import SimpleNamespace

from app.scene_creator.service import _in_flight_candidate, _job_is_live


def test_interrupted_job_is_not_live() -> None:
    db = SimpleNamespace(get=lambda model, jid: SimpleNamespace(status="interrupted"))
    assert _job_is_live(db, "9503b212-7639-42a0-a887-6a5380e805db") is False


def test_failed_job_is_not_live() -> None:
    db = SimpleNamespace(get=lambda model, jid: SimpleNamespace(status="failed"))
    assert _job_is_live(db, "9503b212-7639-42a0-a887-6a5380e805db") is False


def test_running_job_is_live() -> None:
    db = SimpleNamespace(get=lambda model, jid: SimpleNamespace(status="running"))
    assert _job_is_live(db, "job-live") is True


def test_in_flight_skips_interrupted_candidate() -> None:
    dead = SimpleNamespace(
        id="cand-dead",
        status="generating",
        kind="",
        quality_profile="draft",
        camera_state_hash="55a4a8a32562f3a7",
        job_id="9503b212-7639-42a0-a887-6a5380e805db",
        parent_candidate_id="",
        approved_edited_preview_asset_id="",
        source_preview_asset_id="",
        mask_id="",
        edit_operation="",
    )
    shot = SimpleNamespace(candidates=[dead])
    db = SimpleNamespace(get=lambda model, jid: SimpleNamespace(status="interrupted"))
    reuse = _in_flight_candidate(
        shot,
        quality_profile="draft",
        camera_hash="55a4a8a32562f3a7",
        db=db,
    )
    assert reuse is None
