"""MiniMax H3 Timeline megapixel resolution control contract tests.

Pure graph/dict tests — no GPU, no Comfy spend, no live MiniMax job.
"""

from __future__ import annotations

import uuid

import pytest

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.adapters.ltx_25_local import Ltx25LocalAdapter
from app.director_timeline_w46.generation.request_builder import (
    _resolution_for_request,
    build_timeline_generation_request,
)
from app.director_timeline_w46 import orchestrator
from app.video_runtime.legal_canvas import (
    H3_AUTO_MEGAPIXEL_FAST,
    H3_AUTO_MEGAPIXEL_QUALITY,
    H3_MEGAPIXEL_GRID,
    SpecFidelityError,
    resolve_h3_megapixel_canvas,
    resolve_h3_timeline_canvas,
)
from app.workflows.h3_ref2v_builder import build_h3_ref2v


class TestH3MegapixelGrid:
    """Canonical 16:9 /32 grid parity."""

    def test_all_grid_values_resolve_exactly(self):
        for mp, (w, h) in H3_MEGAPIXEL_GRID:
            label, rw, rh = resolve_h3_megapixel_canvas(mp)
            assert (rw, rh) == (w, h)
            assert label.endswith(" MP")
            assert w % 32 == 0 and h % 32 == 0

    def test_unknown_megapixel_raises_with_suggestions(self):
        with pytest.raises(SpecFidelityError, match="not a supported MiniMax H3 canvas") as exc:
            resolve_h3_megapixel_canvas(0.99)
        assert exc.value.suggestions
        assert "0.98 MP" in exc.value.suggestions
        assert "1.0 MP" in exc.value.suggestions

    def test_non_numeric_megapixel_raises(self):
        with pytest.raises(SpecFidelityError, match="must be a number"):
            resolve_h3_megapixel_canvas("large")


class TestH3AutoPolicy:
    """Auto mode follows the documented policy constants."""

    def test_auto_draft_uses_fast_policy(self):
        canvas = resolve_h3_timeline_canvas(None, draft_mode=True)
        assert canvas["mode"] == "auto"
        assert canvas["megapixels"] == H3_AUTO_MEGAPIXEL_FAST
        assert canvas["width"] == 864
        assert canvas["height"] == 480
        assert canvas["label"] == "0.4 MP"
        assert canvas["auto"] is True

    def test_auto_final_uses_quality_policy(self):
        canvas = resolve_h3_timeline_canvas(None, draft_mode=False)
        assert canvas["mode"] == "auto"
        assert canvas["megapixels"] == H3_AUTO_MEGAPIXEL_QUALITY
        assert canvas["width"] == 1152
        assert canvas["height"] == 640
        assert canvas["label"] == "0.7 MP"
        assert canvas["auto"] is True

    def test_absent_h3resolution_is_auto(self):
        canvas = resolve_h3_timeline_canvas(None, draft_mode=False)
        assert canvas["auto"] is True

    def test_auto_mode_ignores_stored_megapixels(self):
        canvas = resolve_h3_timeline_canvas({"mode": "auto", "megapixels": 2.0}, draft_mode=False)
        assert canvas["megapixels"] == H3_AUTO_MEGAPIXEL_QUALITY
        assert canvas["auto"] is True


class TestH3ManualOverride:
    """Manual mode wins over draft_mode."""

    @pytest.mark.parametrize("draft_mode", [True, False])
    def test_manual_04_is_864x480(self, draft_mode: bool):
        canvas = resolve_h3_timeline_canvas({"mode": "manual", "megapixels": 0.4}, draft_mode=draft_mode)
        assert canvas["mode"] == "manual"
        assert canvas["width"] == 864
        assert canvas["height"] == 480
        assert canvas["auto"] is False

    @pytest.mark.parametrize("draft_mode", [True, False])
    def test_manual_10_is_1376x768(self, draft_mode: bool):
        canvas = resolve_h3_timeline_canvas({"mode": "manual", "megapixels": 1.0}, draft_mode=draft_mode)
        assert canvas["mode"] == "manual"
        assert canvas["width"] == 1376
        assert canvas["height"] == 768
        assert canvas["auto"] is False

    @pytest.mark.parametrize("draft_mode", [True, False])
    def test_manual_20_is_1920x1088(self, draft_mode: bool):
        canvas = resolve_h3_timeline_canvas({"mode": "manual", "megapixels": 2.0}, draft_mode=draft_mode)
        assert canvas["mode"] == "manual"
        assert canvas["width"] == 1920
        assert canvas["height"] == 1088
        assert canvas["auto"] is False

    def test_manual_missing_megapixels_raises(self):
        with pytest.raises(SpecFidelityError, match="requires a megapixel value"):
            resolve_h3_timeline_canvas({"mode": "manual"}, draft_mode=False)


class TestH3RequestWiring:
    """request_builder resolves H3 resolution and records provenance."""

    def _h3_batch(self, h3_resolution: dict | None = None, generator_id: str = "minimax-h3-t2v-local") -> BatchBlock:
        return BatchBlock(
            id="b_h3",
            sceneId="s",
            label="Hero",
            generatorId=generator_id,
            h3Resolution=h3_resolution,
            duration=DurationState(plannedDuration=5.0),
            promptSegments=[
                TimelinePromptSegment(
                    id="ps1",
                    start=0,
                    length=5,
                    text="wide shot",
                    role="primary",
                    strength=1,
                    anchorIds=[],
                    executionStrategy="compiled",
                    versionId="psv1",
                )
            ],
        )

    def test_manual_10_request_resolution(self):
        batch = self._h3_batch({"mode": "manual", "megapixels": 1.0})
        snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=snap,
            aspect_ratio="16:9",
            draft_mode=False,
        )
        assert req.resolution == "1376x768"
        assert req.providerOptions.get("h3ResolvedCanvas") == {
            "mode": "manual",
            "megapixels": 1.0,
            "label": "1.0 MP",
            "width": 1376,
            "height": 768,
            "auto": False,
        }

    def test_auto_fast_request_resolution(self):
        batch = self._h3_batch({"mode": "auto", "megapixels": 0.4})
        snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=snap,
            aspect_ratio="16:9",
            draft_mode=True,
        )
        assert req.resolution == "864x480"
        canvas = req.providerOptions.get("h3ResolvedCanvas")
        assert canvas is not None
        assert canvas["mode"] == "auto"
        assert canvas["megapixels"] == H3_AUTO_MEGAPIXEL_FAST
        assert canvas["width"] == 864
        assert canvas["height"] == 480

    def test_auto_quality_request_resolution(self):
        batch = self._h3_batch()
        snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=snap,
            aspect_ratio="16:9",
            draft_mode=False,
        )
        assert req.resolution == "1152x640"
        canvas = req.providerOptions.get("h3ResolvedCanvas")
        assert canvas["megapixels"] == H3_AUTO_MEGAPIXEL_QUALITY


class TestLtxResolutionUnchanged:
    """Non-H3 generators keep byte-identical behavior."""

    def test_ltx_batch_resolution_unchanged(self):
        batch = BatchBlock(
            id="b_ltx",
            sceneId="s",
            label="Hero",
            generatorId="ltx-2.5-distilled",
            duration=DurationState(plannedDuration=5.0),
            promptSegments=[
                TimelinePromptSegment(
                    id="ps1",
                    start=0,
                    length=5,
                    text="wide shot",
                    role="primary",
                    strength=1,
                    anchorIds=[],
                    executionStrategy="compiled",
                    versionId="psv1",
                )
            ],
        )
        snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled")
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=snap,
            aspect_ratio="16:9",
            draft_mode=True,
        )
        assert req.resolution == "1280x704"
        assert req.providerOptions.get("h3ResolvedCanvas") is None

    def test_ltx_direct_resolution_call_unchanged(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = BatchBlock(id="b_ltx", sceneId="s", generatorId="ltx-2.5-distilled")
        assert _resolution_for_request(caps, "16:9", batch, draft_mode=True) == "1280x704"


class TestH3GraphProof:
    """build_h3_ref2v receives the resolved width/height."""

    def test_manual_10_graph_node_has_exact_canvas(self):
        graph = build_h3_ref2v(
            prompt="wide shot",
            ref_comfy_names=["ref.png"],
            filename_prefix="video/test",
            width=1376,
            height=768,
            length=5,
        )
        cond = next(
            n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "MiniMaxH3ReferenceToVideo"
        )
        inputs = cond["inputs"]
        assert inputs["width"] == 1376
        assert inputs["height"] == 768

    def test_auto_fast_graph_node_has_exact_canvas(self):
        graph = build_h3_ref2v(
            prompt="wide shot",
            ref_comfy_names=["ref.png"],
            filename_prefix="video/test",
            width=864,
            height=480,
            length=5,
        )
        cond = next(
            n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "MiniMaxH3ReferenceToVideo"
        )
        inputs = cond["inputs"]
        assert inputs["width"] == 864
        assert inputs["height"] == 480


class TestPreflightFinding:
    """run_preflight discloses the resolved H3 canvas."""

    def test_h3_batch_emits_info_finding(self):
        master = SceneTimelineMaster(
            batchBlocks=[
                BatchBlock(
                    id="b1",
                    sceneId="s",
                    generatorId="minimax-h3-t2v-local",
                    duration=DurationState(plannedDuration=5.0),
                    promptSegments=[TimelinePromptSegment(text="prompt")],
                )
            ]
        )
        findings = orchestrator.run_preflight(master)
        h3_findings = [f for f in findings if f["code"] == "h3_canvas"]
        assert len(h3_findings) == 1
        assert h3_findings[0]["severity"] == "info"
        assert "1152×640" in h3_findings[0]["message"]
        assert "0.7 MP" in h3_findings[0]["message"]
        assert "Auto Quality" in h3_findings[0]["message"]

    def test_corrupt_manual_mp_emits_error_finding(self):
        master = SceneTimelineMaster(
            batchBlocks=[
                BatchBlock(
                    id="b1",
                    sceneId="s",
                    generatorId="minimax-h3-t2v-local",
                    h3Resolution={"mode": "manual", "megapixels": 0.99},
                    duration=DurationState(plannedDuration=5.0),
                    promptSegments=[TimelinePromptSegment(text="prompt")],
                )
            ]
        )
        findings = orchestrator.run_preflight(master)
        h3_findings = [f for f in findings if f["code"] == "h3_canvas"]
        assert len(h3_findings) == 1
        assert h3_findings[0]["severity"] == "error"
        assert "not a supported MiniMax H3 canvas" in h3_findings[0]["message"]

    def test_non_h3_batch_has_no_h3_canvas_finding(self):
        master = SceneTimelineMaster(
            batchBlocks=[
                BatchBlock(
                    id="b1",
                    sceneId="s",
                    generatorId="ltx-2.5-distilled",
                    duration=DurationState(plannedDuration=5.0),
                    promptSegments=[TimelinePromptSegment(text="prompt")],
                )
            ]
        )
        findings = orchestrator.run_preflight(master)
        h3_findings = [f for f in findings if f["code"] == "h3_canvas"]
        assert h3_findings == []


class TestBatchBlockRoundTrip:
    """h3Resolution survives pydantic validation and dump/load."""

    def test_h3resolution_survives_model_validate_and_dump(self):
        payload = {
            "mode": "manual",
            "megapixels": 1.5,
        }
        batch = BatchBlock(
            id="b1",
            sceneId="s",
            h3Resolution=payload,
            duration=DurationState(plannedDuration=5.0),
        )
        dumped = batch.model_dump()
        assert dumped["h3Resolution"] == payload
        restored = BatchBlock.model_validate(dumped)
        assert restored.h3Resolution == payload

    def test_absent_h3resolution_defaults_to_none(self):
        batch = BatchBlock(id="b1", sceneId="s", duration=DurationState(plannedDuration=5.0))
        dumped = batch.model_dump()
        assert dumped.get("h3Resolution") is None
        restored = BatchBlock.model_validate(dumped)
        assert restored.h3Resolution is None


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="H3 Res Control", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


class TestH3ResolutionPersistPath:
    """h3Resolution survives touch_batch_config and store round-trip."""

    def test_touch_batch_config_persists_h3_resolution(self, db_scene):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        updated = orchestrator.touch_batch_config(
            db, pid, sid, batch_id, {"h3Resolution": {"mode": "manual", "megapixels": 1.0}}
        )
        assert updated["ok"] is True
        assert updated["batch"]["h3Resolution"] == {"mode": "manual", "megapixels": 1.0}

        payload = service.workspace(db, pid, sid)
        master = SceneTimelineMaster.model_validate(payload["master"])
        reloaded = next(b for b in master.batchBlocks if b.id == batch_id)
        assert reloaded.h3Resolution == {"mode": "manual", "megapixels": 1.0}

    def test_touch_batch_config_clears_invalid_h3_resolution(self, db_scene):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        updated = orchestrator.touch_batch_config(
            db, pid, sid, batch_id, {"h3Resolution": {"mode": "unsupported", "megapixels": 1.0}}
        )
        assert updated["ok"] is True
        assert updated["batch"]["h3Resolution"] is None


class TestH3ResolutionRouterPatch:
    """HTTP PATCH must carry h3Resolution through PatchBatchBody.

    Regression: PatchBatchBody once omitted h3Resolution, so pydantic silently
    dropped it — 200 OK, nothing persisted (found by live UI verification).
    """

    def test_patch_batch_persists_h3_resolution(self, db_scene, client):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        url = f"/api/director-timeline/projects/{pid}/scenes/{sid}/batches/{batch_id}"
        resp = client.patch(url, json={"h3Resolution": {"mode": "manual", "megapixels": 1.0}})
        assert resp.status_code == 200, resp.text

        payload = service.workspace(db, pid, sid)
        master = SceneTimelineMaster.model_validate(payload["master"])
        reloaded = next(b for b in master.batchBlocks if b.id == batch_id)
        assert reloaded.h3Resolution == {"mode": "manual", "megapixels": 1.0}



class TestLtxTimelineQuality:
    """LTX Timeline QUALITY tier -> legal canvas WxH (no 480p)."""

    def _ltx_batch(self, ltx_quality: str | None = None) -> BatchBlock:
        return BatchBlock(
            id="b_ltx",
            sceneId="s",
            label="Hero",
            generatorId="ltx-2.5-distilled",
            ltxQuality=ltx_quality,
            duration=DurationState(plannedDuration=5.0),
            promptSegments=[
                TimelinePromptSegment(
                    id="ps1",
                    start=0,
                    length=5,
                    text="wide shot",
                    role="primary",
                    strength=1,
                    anchorIds=[],
                    executionStrategy="compiled",
                    versionId="psv1",
                )
            ],
        )

    def test_default_absent_is_720p(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = self._ltx_batch(None)
        assert _resolution_for_request(caps, "16:9", batch, draft_mode=True) == "1280x704"

    def test_720p_tier(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = self._ltx_batch("720p")
        assert _resolution_for_request(caps, "16:9", batch, draft_mode=False) == "1280x704"

    def test_1080p_tier(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = self._ltx_batch("1080p")
        assert _resolution_for_request(caps, "16:9", batch, draft_mode=False) == "1920x1088"

    def test_2k_tier(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = self._ltx_batch("2K")
        assert _resolution_for_request(caps, "16:9", batch, draft_mode=False) == "2560x1440"

    def test_4k_fails_honestly(self):
        caps = Ltx25LocalAdapter().capabilities
        batch = self._ltx_batch("4K")
        with pytest.raises(ValueError, match="UNAVAILABLE|4K|cannot compile"):
            _resolution_for_request(caps, "16:9", batch, draft_mode=False)

    def test_request_builder_emits_tier_provenance(self):
        batch = self._ltx_batch("1080p")
        snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled")
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=snap,
            aspect_ratio="16:9",
            draft_mode=False,
        )
        assert req.resolution == "1920x1088"
        assert req.providerOptions.get("ltxResolvedQuality") == {
            "tier": "1080p",
            "resolution": "1920x1088",
        }
        assert req.providerOptions.get("h3ResolvedCanvas") is None


class TestLtxQualityPersistPath:
    """ltxQuality survives touch_batch_config and store round-trip."""

    def test_touch_batch_config_persists_ltx_quality(self, db_scene):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        updated = orchestrator.touch_batch_config(db, pid, sid, batch_id, {"ltxQuality": "1080p"})
        assert updated["ok"] is True
        assert updated["batch"]["ltxQuality"] == "1080p"

        payload = service.workspace(db, pid, sid)
        master = SceneTimelineMaster.model_validate(payload["master"])
        reloaded = next(b for b in master.batchBlocks if b.id == batch_id)
        assert reloaded.ltxQuality == "1080p"

    def test_patch_batch_persists_ltx_quality(self, db_scene, client):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        url = f"/api/director-timeline/projects/{pid}/scenes/{sid}/batches/{batch_id}"
        resp = client.patch(url, json={"ltxQuality": "2K"})
        assert resp.status_code == 200, resp.text

        payload = service.workspace(db, pid, sid)
        master = SceneTimelineMaster.model_validate(payload["master"])
        reloaded = next(b for b in master.batchBlocks if b.id == batch_id)
        assert reloaded.ltxQuality == "2K"

    def test_independent_h3_and_ltx_memory(self, db_scene):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        orchestrator.touch_batch_config(
            db, pid, sid, batch_id, {"h3Resolution": {"mode": "manual", "megapixels": 1.0}}
        )
        orchestrator.touch_batch_config(db, pid, sid, batch_id, {"ltxQuality": "1080p"})
        payload = service.workspace(db, pid, sid)
        master = SceneTimelineMaster.model_validate(payload["master"])
        reloaded = next(b for b in master.batchBlocks if b.id == batch_id)
        assert reloaded.h3Resolution == {"mode": "manual", "megapixels": 1.0}
        assert reloaded.ltxQuality == "1080p"


class TestMultiBatchQualityInherit:
    """add_batch inherits prior batch h3Resolution + ltxQuality."""

    def test_add_batch_inherits_h3_and_ltx(self, db_scene):
        db, pid, sid = db_scene
        from app.director_timeline_w46 import service

        ws = service.workspace(db, pid, sid)
        batch_id = ws["master"]["batchBlocks"][0]["id"]
        orchestrator.touch_batch_config(
            db,
            pid,
            sid,
            batch_id,
            {
                "h3Resolution": {"mode": "manual", "megapixels": 0.98},
                "ltxQuality": "1080p",
            },
        )
        added = service.add_batch(db, pid, sid, label="Batch 2")
        assert added["ok"] is True
        new_batch = BatchBlock.model_validate(added["batch"])
        assert new_batch.h3Resolution == {"mode": "manual", "megapixels": 0.98}
        assert new_batch.ltxQuality == "1080p"
        # Must not silently reset to Auto / absent (Fast Auto would be 864x480).
        assert new_batch.h3Resolution["mode"] == "manual"
