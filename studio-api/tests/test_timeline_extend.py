"""Long-form Timeline Extend service tests — no live GPU, no real H3 job.

Covers:
- Legal H3 duration: honest snap to the generator grid, never above max (8s).
- H3 mode selection: R2V when recurring identity/environment matter, I2V otherwise.
- Current-playable-video resolution: sceneStitch -> approved take -> latest
  batch output, same project only.
- review_and_extend flow: analyze -> compile continuity -> add_batch -> persist
  ExtendSegment + longFormContinuity -> generate ONLY the new batch.
- Honest failure / cancel handling (no fake success).
- Downstream invalidation on earlier-segment take replacement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.db import Asset, Project, Scene, SessionLocal, init_db
from app.director_timeline_w46 import extend_service
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    CandidateVersion,
    DurationState,
    SceneStitch,
    SceneTimelineMaster,
)
from app.director_timeline_w46.longform_continuity import (
    compile_longform_continuity,
    select_h3_mode,
)
from app.director_timeline_w46.store import load_master, save_master
from app.codirector.video_intelligence.contracts import CoDirectorContinuityPolicy
from app.codirector.video_intelligence.media_packet import CharacterAction, MediaIntelligencePacket

init_db()

_PROJECT_ID = "p-extend"
_SCENE_ID = "sc-extend"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ensure_project_scene(db) -> None:
    if db.get(Project, _PROJECT_ID) is None:
        db.add(Project(id=_PROJECT_ID, name="extend-proj"))
    if db.get(Scene, _SCENE_ID) is None:
        db.add(Scene(id=_SCENE_ID, project_id=_PROJECT_ID, name="extend-scene"))
    db.commit()


def _write_bytes(name: str, content: bytes = b"\x89PNG\r\n\x1a\nfake") -> str:
    dest = Path(settings.data_dir) / "extend-test" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return str(dest)


def _add_asset(db, asset_id: str, project_id: str = _PROJECT_ID, kind: str = "video") -> Asset:
    # The session DB is shared across tests — get-or-create by stable ID.
    if db.get(Project, project_id) is None:
        db.add(Project(id=project_id, name=f"proj-{project_id}"))
        db.commit()
    path = _write_bytes(f"{asset_id}.mp4")
    existing = db.get(Asset, asset_id)
    if existing is not None:
        existing.project_id = project_id
        existing.path = path
        existing.kind = kind
        db.add(existing)
        db.commit()
        return existing
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=f"test-{asset_id}",
        kind=kind,
        filename=f"{asset_id}.mp4",
        path=path,
    )
    db.add(asset)
    db.commit()
    return asset


def _approved_batch(batch_id: str, order: int, asset_id: str, **kw) -> BatchBlock:
    return BatchBlock(
        id=batch_id,
        sceneId=_SCENE_ID,
        order=order,
        label=f"Batch {order + 1}",
        status="Approved",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0),
        approvedClip=ApprovedClip(assetId=asset_id, executionSnapshotId=f"snap_{batch_id}"),
        **kw,
    )


def _master(*batches: BatchBlock) -> SceneTimelineMaster:
    master = SceneTimelineMaster(batchBlocks=list(batches))
    # Keep the Co-Director temporal review out of unit tests (no Qwen worker).
    master.coDirectorContinuityPolicy = CoDirectorContinuityPolicy(enabled=False)
    return master


def _save(db, master: SceneTimelineMaster) -> None:
    _ensure_project_scene(db)
    save_master(db, _PROJECT_ID, _SCENE_ID, master)


def _reload(db) -> SceneTimelineMaster:
    payload = load_master(db, _PROJECT_ID, _SCENE_ID)
    assert payload.get("ok"), payload
    return SceneTimelineMaster.model_validate(payload["master"])


def _fake_packet(*, characters: list[tuple[str | None, str]] | None = None) -> MediaIntelligencePacket:
    return MediaIntelligencePacket(
        projectId=_PROJECT_ID,
        assetId="asset_b1",
        mode="full",
        availability="ready",
        summary="Korri stands on the bridge as the cruiser hums.",
        characterActions=[
            CharacterAction(characterId=cid, characterLabel=label, action="standing", movementDirection=None)
            for cid, label in (characters or [])
        ],
    )


@pytest.fixture()
def fake_perception(monkeypatch: pytest.MonkeyPatch):
    """Stub the perception call (never a real Qwen job in unit tests)."""
    calls: list[dict] = []

    def fake_analyze(db, project_id, asset_id, **kw):
        calls.append({"asset_id": asset_id, **kw})
        return _fake_packet()

    monkeypatch.setattr(extend_service.media_analyze, "analyze_asset", fake_analyze)
    return calls


@pytest.fixture()
def fake_anchor(monkeypatch: pytest.MonkeyPatch):
    """Stub only the pixel extract; the real Asset row is still written."""

    def fake_extract(video_path: str, dest_path: str, *, at_seconds=None, at_frame=None) -> None:
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"\x89PNG\r\n\x1a\nfake-frame")

    monkeypatch.setattr(extend_service, "extract_last_frame_png", fake_extract)


@pytest.fixture()
def fake_generate(monkeypatch: pytest.MonkeyPatch):
    """Capture generate_scene calls; never submits a real H3 job."""
    calls: list[dict] = []

    def fake_generate_scene(db, project_id, scene_id, *, scope="full", batch_ids=None, draft_mode=None):
        calls.append({"scope": scope, "batch_ids": list(batch_ids or []), "draft_mode": draft_mode})
        return {
            "ok": True,
            "jobs": [{"jobId": "job_fake_1", "batchBlockId": (batch_ids or [None])[0], "status": "queued"}],
            "errors": [],
            "mock": False,
        }

    monkeypatch.setattr(extend_service.orchestrator, "generate_scene", fake_generate_scene)
    return calls


# ---------------------------------------------------------------------------
# Legal duration — Inspector request, 15s max, 17k+5 snap (8s is not the max)
# ---------------------------------------------------------------------------


def test_legal_duration_defaults_to_five_seconds_clean():
    out = extend_service.legal_extend_duration("minimax-h3-t2v-local", None)
    assert out["ok"] is True
    assert out["maxDurationSec"] == 15.0
    # Extend product default remains 5s; creator durationSec stays clean (not 124/24).
    assert out["durationSec"] == 5.0
    assert abs(out["legalDurationSec"] - (124 / 24)) < 1e-6
    assert out["snapped"] is True


def test_legal_duration_twelve_seconds_is_legal():
    out = extend_service.legal_extend_duration("minimax-h3-t2v-local", 12.0)
    assert out["ok"] is True
    assert out["requestedDurationSec"] == 12.0
    assert out["maxDurationSec"] == 15.0
    assert out["durationSec"] == 12.0  # creator request stays clean
    assert abs(out["legalDurationSec"] - (294 / 24)) < 1e-6  # 12s → 294 frames
    assert out["snapped"] is True


def test_legal_duration_blocks_above_fifteen():
    out = extend_service.legal_extend_duration("minimax-h3-t2v-local", 16.0)
    assert out["ok"] is False
    assert out["durationSec"] is None
    assert out["maxDurationSec"] == 15.0
    assert "15" in (out.get("message") or "")


def test_legal_duration_eight_seconds_is_on_grid():
    exact = extend_service.legal_extend_duration("minimax-h3-t2v-local", 8.0)
    assert exact["ok"] is True
    assert exact["durationSec"] == 8.0
    assert exact["snapped"] is False


def test_legal_duration_i2v_row_same_grid():
    out = extend_service.legal_extend_duration("minimax-h3-i2v-local", 100.0)
    assert out["ok"] is False
    assert out["maxDurationSec"] == 15.0


# ---------------------------------------------------------------------------
# H3 mode selection — R2V when Korri/Anadriya + ERS matter
# ---------------------------------------------------------------------------


def test_select_h3_mode_truth_table():
    assert select_h3_mode(multi_character=False, has_ers=False, identity_risk=False) == "i2v"
    assert select_h3_mode(multi_character=True, has_ers=False, identity_risk=False) == "r2v"
    assert select_h3_mode(multi_character=False, has_ers=True, identity_risk=False) == "r2v"
    assert select_h3_mode(multi_character=False, has_ers=False, identity_risk=True) == "r2v"


def test_service_mode_selection_r2v_for_two_characters_and_ers():
    state = compile_longform_continuity(
        project_id=_PROJECT_ID,
        scene_id=_SCENE_ID,
        master=None,
        media_packet=None,
        temporal=None,
        reference_bindings=[
            {"kind": "crs", "assetId": "crs_korri", "characterId": "char_korri", "name": "Korri"},
            {"kind": "crs", "assetId": "crs_anadriya", "characterId": "char_anadriya", "name": "Anadriya"},
            {"kind": "ers", "assetId": "ers_bridge", "name": "Bridge"},
        ],
    )
    mode, generator_id = extend_service._select_mode(state)
    assert mode == "r2v"
    assert generator_id == extend_service.H3_R2V_GENERATOR_ID


def test_service_mode_selection_i2v_when_last_frame_is_enough():
    state = compile_longform_continuity(
        project_id=_PROJECT_ID,
        scene_id=_SCENE_ID,
        master=None,
        media_packet=_fake_packet(characters=[(None, "Korri")]),
        temporal=None,
    )
    mode, generator_id = extend_service._select_mode(state)
    assert mode == "i2v"
    assert generator_id == extend_service.H3_I2V_GENERATOR_ID


# ---------------------------------------------------------------------------
# Current playable scene video resolution (same project only)
# ---------------------------------------------------------------------------


def test_resolve_prefers_current_stitch():
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _add_asset(db, "asset_b2")
        _add_asset(db, "asset_stitch")
        master = _master(_approved_batch("b1", 0, "asset_b1"), _approved_batch("b2", 1, "asset_b2"))
        master.sceneStitch = SceneStitch(
            assetId="asset_stitch", sourceBatchIds=["b1", "b2"], sourceAssetIds=["asset_b1", "asset_b2"]
        )
        resolved = extend_service._resolve_current_playable(db, _PROJECT_ID, master)
        assert resolved is not None
        assert resolved["kind"] == "sceneStitch"
        assert resolved["assetId"] == "asset_stitch"
    finally:
        db.close()


def test_resolve_falls_back_to_last_approved_take_when_stitch_stale():
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _add_asset(db, "asset_b2")
        _add_asset(db, "asset_stitch_old")
        master = _master(_approved_batch("b1", 0, "asset_b1"), _approved_batch("b2", 1, "asset_b2"))
        master.sceneStitch = SceneStitch(
            assetId="asset_stitch_old", sourceBatchIds=["b1"], sourceAssetIds=["asset_b1"]
        )
        resolved = extend_service._resolve_current_playable(db, _PROJECT_ID, master)
        assert resolved is not None
        assert resolved["kind"] == "approvedTake"
        assert resolved["assetId"] == "asset_b2"
        assert resolved["batch"] is not None and resolved["batch"].id == "b2"
    finally:
        db.close()


def test_resolve_falls_back_to_latest_batch_output():
    db = SessionLocal()
    try:
        _add_asset(db, "asset_cand")
        batch = BatchBlock(
            id="b1",
            sceneId=_SCENE_ID,
            order=0,
            status="CandidateReady",
            duration=DurationState(plannedDuration=5.0),
            candidateVersions=[CandidateVersion(executionSnapshotId="snap", assetId="asset_cand")],
        )
        resolved = extend_service._resolve_current_playable(db, _PROJECT_ID, _master(batch))
        assert resolved is not None
        assert resolved["kind"] == "batchOutput"
        assert resolved["assetId"] == "asset_cand"
    finally:
        db.close()


def test_resolve_never_crosses_project_boundary():
    db = SessionLocal()
    try:
        _add_asset(db, "asset_foreign", project_id="p-other")
        master = _master(_approved_batch("b1", 0, "asset_foreign"))
        assert extend_service._resolve_current_playable(db, _PROJECT_ID, master) is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# review_and_extend flow
# ---------------------------------------------------------------------------


def test_review_and_extend_happy_path(fake_perception, fake_anchor, fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _save(db, _master(_approved_batch("b1", 0, "asset_b1")))

        result = extend_service.review_and_extend(
            db, _PROJECT_ID, _SCENE_ID, prompt="Korri turns toward the alarm."
        )

        assert result["ok"] is True, json.dumps(result, default=str)[:800]
        assert result["mock"] is False
        # Perception ran against the current playable video, full clip mode.
        assert fake_perception and fake_perception[0]["asset_id"] == "asset_b1"
        assert fake_perception[0]["mode"] == "full"
        # Exactly one new batch; generation scoped to it and nothing else.
        assert len(fake_generate) == 1
        assert fake_generate[0]["scope"] == "selected"
        new_batch_id = result["batchId"]
        assert new_batch_id != "b1"
        assert fake_generate[0]["batch_ids"] == [new_batch_id]

        master = _reload(db)
        assert len(master.batchBlocks) == 2
        new_batch = next(b for b in master.batchBlocks if b.id == new_batch_id)
        assert new_batch.generatorId in {
            extend_service.H3_R2V_GENERATOR_ID,
            extend_service.H3_I2V_GENERATOR_ID,
        }
        assert new_batch.duration.plannedDuration == 5.0  # creator request, not frames/24
        # Prior batch untouched.
        assert next(b for b in master.batchBlocks if b.id == "b1").status == "Approved"

        # ExtendSegment + Continuity Packet persisted on the master.
        assert len(master.extendSegments) == 1
        segment = master.extendSegments[0]
        assert segment.batchBlockId == new_batch_id
        assert segment.prompt == "Korri turns toward the alarm."
        assert segment.status == "generating"
        assert segment.durationSec == 5.0  # creator request, not frames/24
        assert segment.h3Mode in ("i2v", "r2v")
        assert master.longFormContinuity is not None
        assert master.longFormContinuity.revision == 1
        assert master.longFormContinuity.nextIntent == "Korri turns toward the alarm."
        assert master.longFormContinuity.mediaIntelligencePacketId
        assert master.lastMediaIntelligencePacketId == master.longFormContinuity.mediaIntelligencePacketId

        # Ending anchor registered as a project asset and bound to the batch.
        assert result["endingAnchor"] and result["endingAnchor"]["assetId"]
        anchor_asset = db.get(Asset, result["endingAnchor"]["assetId"])
        assert anchor_asset is not None and anchor_asset.project_id == _PROJECT_ID
        assert segment.inputAnchors == [result["endingAnchor"]["assetId"]]
        assert any(a.assetId == result["endingAnchor"]["assetId"] for a in new_batch.sourceAnchors)
        assert master.longFormContinuity.endingAnchors[-1]["assetId"] == result["endingAnchor"]["assetId"]
    finally:
        db.close()


def test_review_and_extend_snaps_duration_honestly(fake_perception, fake_anchor, fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _save(db, _master(_approved_batch("b1", 0, "asset_b1")))
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="more", duration_sec=12.0)
        assert result["ok"] is True
        snap = result["durationSnap"]
        assert snap["requestedDurationSec"] == 12.0
        assert snap["durationSec"] == 12.0  # creator request stays clean
        assert abs(snap["legalDurationSec"] - (294 / 24)) < 1e-6  # 12s snaps to 294 frames, not 8s
        assert snap["snapped"] is True
        master = _reload(db)
        assert master.extendSegments[0].durationSec == 12.0
        new_batch = next(b for b in master.batchBlocks if b.id == result["batchId"])
        assert new_batch.duration.plannedDuration == 12.0
    finally:
        db.close()


def test_review_and_extend_r2v_when_scene_bindings_carry_identity(
    monkeypatch, fake_perception, fake_anchor, fake_generate
):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _save(db, _master(_approved_batch("b1", 0, "asset_b1")))
        monkeypatch.setattr(
            extend_service,
            "_scene_reference_bindings",
            lambda db, project_id, scene_id: (
                [
                    {"bindingId": "bind_korri", "kind": "crs", "assetId": "crs_korri", "characterId": "char_korri", "name": "Korri"},
                    {"bindingId": "bind_anadriya", "kind": "crs", "assetId": "crs_anadriya", "characterId": "char_anadriya", "name": "Anadriya"},
                    {"bindingId": "bind_bridge", "kind": "ers", "assetId": "ers_bridge", "characterId": None, "name": "Bridge"},
                ],
                None,
            ),
        )
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="continue")
        assert result["ok"] is True
        assert result["h3Mode"] == "r2v"
        assert result["generatorId"] == extend_service.H3_R2V_GENERATOR_ID
        master = _reload(db)
        segment = master.extendSegments[0]
        assert segment.h3Mode == "r2v"
        assert set(segment.referenceAssetIds) == {"crs_korri", "crs_anadriya", "ers_bridge"}
        # Canonical binding IDs reached the batch prompt segment (not chat names).
        new_batch = next(b for b in master.batchBlocks if b.id == result["batchId"])
        assert set(new_batch.promptSegments[0].referenceBindingIds) == {"bind_korri", "bind_anadriya", "bind_bridge"}
        # Continuity Packet carries CRS/ERS by canonical asset IDs.
        state = master.longFormContinuity
        assert state.environment.get("ersAssetId") == "ers_bridge"
        assert {c.crsAssetId for c in state.characters} >= {"crs_korri", "crs_anadriya"}
    finally:
        db.close()


def test_review_and_extend_requires_playable_video(fake_perception, fake_anchor, fake_generate):
    db = SessionLocal()
    try:
        _save(db, _master(BatchBlock(id="b1", sceneId=_SCENE_ID, order=0, status="Draft")))
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="continue")
        assert result["ok"] is False
        assert result["error"] == "NO_PLAYABLE_SCENE_VIDEO"
        assert result["message"]
        assert fake_generate == []
        master = _reload(db)
        assert len(master.batchBlocks) == 1  # nothing created
    finally:
        db.close()


def test_review_and_extend_refuses_while_generation_in_flight(fake_perception, fake_anchor, fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        master = _master(_approved_batch("b1", 0, "asset_b1"))
        master.batchBlocks.append(
            BatchBlock(id="b2", sceneId=_SCENE_ID, order=1, status="Generating", duration=DurationState())
        )
        _save(db, master)
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="continue")
        assert result["ok"] is False
        assert result["error"] == "EXTEND_GENERATION_IN_FLIGHT"
        assert fake_generate == []
        assert fake_perception == []  # refused before any analysis spend
        assert len(_reload(db).batchBlocks) == 2
    finally:
        db.close()


def test_review_and_extend_generate_failure_is_honest(monkeypatch, fake_perception, fake_anchor):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _save(db, _master(_approved_batch("b1", 0, "asset_b1")))

        def failing_generate(db, project_id, scene_id, *, scope="full", batch_ids=None, draft_mode=None):
            return {"ok": False, "error": "CAPABILITY_VALIDATION_FAILED", "message": "Prompt is required.", "mock": False}

        monkeypatch.setattr(extend_service.orchestrator, "generate_scene", failing_generate)
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="continue")
        assert result["ok"] is False
        assert result["error"] == "EXTEND_GENERATION_FAILED"
        assert result["detail"] == "CAPABILITY_VALIDATION_FAILED"
        assert result["message"]  # timelineActionError-style creator message
        master = _reload(db)
        assert master.extendSegments[0].status == "failed"
        # Prior batch untouched.
        assert next(b for b in master.batchBlocks if b.id == "b1").status == "Approved"
    finally:
        db.close()


def test_review_and_extend_cancel_marks_segment_cancelled(monkeypatch, fake_perception, fake_anchor):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        _save(db, _master(_approved_batch("b1", 0, "asset_b1")))

        def cancelled_generate(db, project_id, scene_id, *, scope="full", batch_ids=None, draft_mode=None):
            return {"ok": False, "error": "CANCELLED_BY_USER", "message": "Generation cancelled.", "mock": False}

        monkeypatch.setattr(extend_service.orchestrator, "generate_scene", cancelled_generate)
        result = extend_service.review_and_extend(db, _PROJECT_ID, _SCENE_ID, prompt="continue")
        assert result["ok"] is False
        assert result["error"] == "EXTEND_CANCELLED"
        master = _reload(db)
        assert master.extendSegments[0].status == "cancelled"
        assert next(b for b in master.batchBlocks if b.id == "b1").status == "Approved"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Downstream invalidation — replacing an earlier segment take
# ---------------------------------------------------------------------------


def _master_with_two_segments() -> tuple[SceneTimelineMaster, str, str]:
    b1 = _approved_batch("b1", 0, "asset_b1")
    e1 = BatchBlock(id="bb_e1", sceneId=_SCENE_ID, order=1, status="Approved", generatorId="minimax-h3-t2v-local",
                    duration=DurationState(plannedDuration=5.0),
                    approvedClip=ApprovedClip(assetId="asset_b1", executionSnapshotId="snap_e1"))
    e2 = BatchBlock(id="bb_e2", sceneId=_SCENE_ID, order=2, status="Approved", generatorId="minimax-h3-t2v-local",
                    duration=DurationState(plannedDuration=5.0),
                    approvedClip=ApprovedClip(assetId="asset_b1", executionSnapshotId="snap_e2"))
    master = _master(b1, e1, e2)
    state = compile_longform_continuity(
        project_id=_PROJECT_ID, scene_id=_SCENE_ID, master=master, media_packet=None, temporal=None
    )
    master.longFormContinuity = state
    from app.director_timeline_w46.contracts import ExtendSegment

    seg1 = ExtendSegment(batchBlockId="bb_e1", prompt="first", status="approved")
    seg2 = ExtendSegment(batchBlockId="bb_e2", prompt="second", status="approved")
    master.extendSegments = [seg1, seg2]
    return master, seg1.segmentId, seg2.segmentId


def test_retake_segment_marks_downstream_stale(fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        master, seg1_id, seg2_id = _master_with_two_segments()
        _save(db, master)

        result = extend_service.retake_extend_segment(db, _PROJECT_ID, _SCENE_ID, seg1_id)
        assert result["ok"] is True, json.dumps(result, default=str)[:800]
        assert result["downstreamStale"] is True
        assert result["staleFromSegmentId"] == seg1_id
        # Only the replaced segment's batch is regenerated.
        assert len(fake_generate) == 1
        assert fake_generate[0]["scope"] == "selected"
        assert fake_generate[0]["batch_ids"] == ["bb_e1"]

        master = _reload(db)
        assert master.longFormContinuity is not None
        assert master.longFormContinuity.stale is True
        assert master.longFormContinuity.staleFromSegmentId == seg1_id
        segments = {s.segmentId: s for s in master.extendSegments}
        assert segments[seg1_id].status == "generating"
        assert segments[seg2_id].status == "planned"  # downstream invalidated
        batches = {b.id: b for b in master.batchBlocks}
        assert batches["bb_e2"].downstreamStale is True
    finally:
        db.close()


def test_retake_segment_unknown_id_returns_not_found(fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        master, _seg1, _seg2 = _master_with_two_segments()
        _save(db, master)
        result = extend_service.retake_extend_segment(db, _PROJECT_ID, _SCENE_ID, "ext_missing")
        assert result["ok"] is False
        assert result["error"] == "SEGMENT_NOT_FOUND"
        assert fake_generate == []
    finally:
        db.close()


def test_retake_segment_prompt_update_projects_to_legacy_lane(fake_generate):
    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        master, seg1_id, _seg2_id = _master_with_two_segments()
        _save(db, master)
        result = extend_service.retake_extend_segment(
            db, _PROJECT_ID, _SCENE_ID, seg1_id, prompt="Korri dives for cover.", duration_sec=8.0
        )
        assert result["ok"] is True
        master = _reload(db)
        batch = next(b for b in master.batchBlocks if b.id == "bb_e1")
        assert batch.promptSegments[0].text == "Korri dives for cover."
        assert batch.promptSegments[0].userDirection == "Korri dives for cover."
        assert batch.duration.plannedDuration == 8.0
        segment = next(s for s in master.extendSegments if s.segmentId == seg1_id)
        assert segment.prompt == "Korri dives for cover."
        assert segment.durationSec == 8.0
    finally:
        db.close()


def test_retake_segment_h3_non_grid_duration_persists_requested_not_snapped(fake_generate):
    """H3 17k+5 snap is request-scoped: a 7.0s retake must persist 7.0, never 7.2917."""

    db = SessionLocal()
    try:
        _add_asset(db, "asset_b1")
        master, seg1_id, _seg2_id = _master_with_two_segments()
        _save(db, master)
        result = extend_service.retake_extend_segment(
            db, _PROJECT_ID, _SCENE_ID, seg1_id, duration_sec=7.0
        )
        assert result["ok"] is True, json.dumps(result, default=str)[:800]
        master = _reload(db)
        batch = next(b for b in master.batchBlocks if b.id == "bb_e1")
        assert batch.duration.plannedDuration == 7.0
        assert batch.promptSegments[0].length == 7.0
        segment = next(s for s in master.extendSegments if s.segmentId == seg1_id)
        assert segment.durationSec == 7.0
        # Guard the exact regression value (175 frames / 24 fps).
        assert batch.duration.plannedDuration != 7.291666666666667
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Router surface (mocked service — no runtime touched)
# ---------------------------------------------------------------------------


def test_extend_route_registered_and_maps_errors(client, monkeypatch):
    import app.director_timeline_w46.extend_service as ext

    def fake_review(db, project_id, scene_id, *, prompt=None, duration_sec=None, force=False):
        return {
            "ok": True,
            "segment": {"segmentId": "ext_1"},
            "batchId": "bb_1",
            "generatorId": ext.H3_R2V_GENERATOR_ID,
            "h3Mode": "r2v",
            "mock": False,
        }

    monkeypatch.setattr(ext, "review_and_extend", fake_review)
    resp = client.post(
        f"/api/director-timeline/projects/{_PROJECT_ID}/scenes/{_SCENE_ID}/extend",
        json={"prompt": "continue", "durationSec": 5.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["batchId"] == "bb_1"

    def missing(db, project_id, scene_id, *, prompt=None, duration_sec=None, force=False):
        return {"ok": False, "error": "SCENE_NOT_FOUND", "message": "This scene could not be found.", "mock": False}

    monkeypatch.setattr(ext, "review_and_extend", missing)
    resp = client.post(
        "/api/director-timeline/projects/p-nope/scenes/sc-nope/extend",
        json={"prompt": "continue"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "SCENE_NOT_FOUND"
