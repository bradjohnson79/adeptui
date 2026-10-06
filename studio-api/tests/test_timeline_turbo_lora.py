"""Turbo LoRA capability, request leak, and Preflight resource fail-close."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.orchestrator import run_preflight
from app.production_control.generator_authority import supports_turbo_lora
from app.workflows.ltx_25_builder import TURBO_LORA_UNAVAILABLE


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Turbo LoRA Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            name="Scene 1",
            index=0,
            prompt="walk",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def test_turbo_capability_is_full_only() -> None:
    assert supports_turbo_lora("ltx-2.5-full") is True
    assert supports_turbo_lora("ltx-2.5-distilled") is False
    assert supports_turbo_lora("ltx-2.5-comfy") is False
    assert supports_turbo_lora("minimax-h3") is False
    assert supports_turbo_lora("minimax-h3-i2v-local") is False
    assert supports_turbo_lora("kling-fal") is False


def test_snapshot_exposes_supports_turbo_lora() -> None:
    from app.production_control.generator_authority import timeline_generator_snapshot

    rows = {row.id: row for row in timeline_generator_snapshot()}
    assert rows["ltx-2.5-full"].supportsTurboLora is True
    assert rows["ltx-2.5-distilled"].supportsTurboLora is False
    assert rows["minimax-h3"].supportsTurboLora is False


def _batch(generator_id: str) -> BatchBlock:
    return BatchBlock(
        id="bb_turbo",
        sceneId="sc_turbo",
        order=0,
        label="Batch 1",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(text="walk", productionPrompt="walk", start=0.0, length=5.0)
        ],
    )


def test_request_omits_turbo_for_unsupported_generator() -> None:
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch("minimax-h3"),
        snapshot=ExecutionSnapshot(batchBlockId="bb_turbo", selectedGenerator="minimax-h3"),
        turbo_lora=True,
    )
    assert "turbo_lora" not in req.providerOptions


def test_request_sets_turbo_only_when_supported() -> None:
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch("ltx-2.5-full"),
        snapshot=ExecutionSnapshot(batchBlockId="bb_turbo", selectedGenerator="ltx-2.5-full"),
        turbo_lora=True,
    )
    assert req.providerOptions.get("turbo_lora") is True
    assert "walk" in req.prompt

    off = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch("ltx-2.5-full"),
        snapshot=ExecutionSnapshot(batchBlockId="bb_turbo", selectedGenerator="ltx-2.5-full"),
        turbo_lora=False,
    )
    assert "turbo_lora" not in off.providerOptions


def test_preflight_fails_when_turbo_on_without_resources() -> None:
    from app.workflows.ltx_25_builder import ltx_25_turbo_resource_gaps

    master = SceneTimelineMaster(
        mode="video_finishing",
        sceneGeneratorId="ltx-2.5-full",
        turboLora=True,
        batchBlocks=[_batch("ltx-2.5-full")],
    )
    findings = run_preflight(master)
    codes = {item.get("code") if isinstance(item, dict) else item.code for item in findings}
    messages = [item.get("message") if isinstance(item, dict) else item.message for item in findings]
    if ltx_25_turbo_resource_gaps():
        assert "turbo_lora_resource_unavailable" in codes
        assert any(TURBO_LORA_UNAVAILABLE in str(msg) for msg in messages)
    else:
        assert "turbo_lora_resource_unavailable" not in codes


def test_preflight_fails_when_turbo_on_unsupported_generator() -> None:
    master = SceneTimelineMaster(
        mode="video_finishing",
        sceneGeneratorId="minimax-h3",
        turboLora=True,
        batchBlocks=[_batch("minimax-h3")],
    )
    findings = run_preflight(master)
    codes = {item.get("code") if isinstance(item, dict) else item.code for item in findings}
    assert "turbo_lora_unsupported" in codes


def test_ltx_adapter_passes_turbo_param(db_scene) -> None:
    import json
    from unittest.mock import MagicMock, patch

    from app.db import Job
    from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    db, pid, sid = db_scene
    adapter = LtxLocalAdapter()
    req = TimelineGenerationRequest(
        projectId=pid,
        sceneId=sid,
        batchBlockId="bb_turbo",
        executionSnapshotId="snap_turbo",
        generatorId="ltx-2.5-full",
        generationMode="text_to_video",
        prompt="walk",
        duration=5.0,
        providerOptions={"originalGeneratorId": "ltx-2.5-full", "turbo_lora": True},
    )
    with patch(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        MagicMock(),
    ):
        sub = adapter.submit(req)
    row = db.get(Job, sub.queueJobId)
    params = json.loads(row.params_json)
    assert params["turbo_lora"] is True
    assert params["variant"] == "ltx-2.5-full"
