"""Revision D selection contracts, cache isolation, auto-mask honesty, rembg alpha."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from app.codirector.perception.cache import get_cached_selection, set_cached_selection
from app.codirector.perception.contracts import PerceptionCapability, PROVIDER_LEAK_KEYS
from app.codirector.perception.perception_router import plan_perception
from app.codirector.perception.selection_contracts import PerceptionSelectionPacket
from app.codirector.perception.selection_service import apply_subject_alpha
from app.setup.catalog import BY_ID, get_component


def test_selection_packet_rejects_logits():
    try:
        PerceptionSelectionPacket(provenance={"mask_logits": [1]})
    except ValueError as exc:
        assert "leaked" in str(exc)
        return
    raise AssertionError("expected leak rejection")


def test_selection_packet_strips_are_not_in_dump():
    packet = PerceptionSelectionPacket(projectId="p-a", assetId="a1", semanticLabel="cup")
    dumped = packet.model_dump()
    assert not PROVIDER_LEAK_KEYS.intersection(dumped)
    assert dumped["schemaVersion"] == "selection-v1"


def test_task_router_does_not_always_run_depth():
    simple = plan_perception("remove_background", depth_available=True)
    assert simple["sam"] is True
    assert simple["depth"] is False
    place = plan_perception("spatial_place", depth_available=True)
    assert place["depth"] is True
    place_off = plan_perception("spatial_place", depth_available=False)
    assert place_off["depth"] is False


def test_cache_is_project_isolated(tmp_path, monkeypatch):
    from app.codirector.perception import cache as cache_mod

    monkeypatch.setattr(cache_mod.settings, "data_dir", tmp_path)
    packet_a = {
        "projectId": "proj-a",
        "assetId": "asset-1",
        "frameTimeMs": 0,
        "modelId": "sam21-hiera-tiny",
        "modelVersion": "abc",
        "maskAssetId": "mask-a",
        "selectionId": "sel_a",
    }
    set_cached_selection(packet_a, entity="cup", source="text")
    hit_b = get_cached_selection(
        project_id="proj-b",
        asset_id="asset-1",
        frame_time_ms=0,
        entity="cup",
        model_id="sam21-hiera-tiny",
        model_version="abc",
        source="text",
    )
    assert hit_b is None
    hit_a = get_cached_selection(
        project_id="proj-a",
        asset_id="asset-1",
        frame_time_ms=0,
        entity="cup",
        model_id="sam21-hiera-tiny",
        model_version="abc",
        source="text",
    )
    assert hit_a is not None
    assert hit_a["maskAssetId"] == "mask-a"


def test_background_remove_builds_alpha(tmp_path: Path):
    source = tmp_path / "src.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(source)
    m = Image.new("L", (8, 8), 0)
    for x in range(4):
        for y in range(8):
            m.putpixel((x, y), 255)
    m.save(mask)
    png = apply_subject_alpha(str(source), str(mask))
    out = Image.open(io.BytesIO(png))
    assert out.mode == "RGBA"
    assert out.getpixel((1, 1))[3] == 255
    assert out.getpixel((6, 1))[3] == 0


def test_auto_mask_never_returns_a_box_as_mask():
    from app.codirector.perception import auto_mask as am
    from app.codirector.perception.contracts import ProposedSlotFill, SpatialDraft

    draft = SpatialDraft(
        proposedFills=[
            ProposedSlotFill(id="fill_cup", kind="prop", label="cup", perceptionEntityId="ent_1"),
        ]
    )
    original_cap = am.get_capability
    original_load = am.load_spatial_draft
    am.get_capability = lambda: PerceptionCapability(autoMask="testing")  # type: ignore[arg-type]
    am.load_spatial_draft = lambda *_a, **_k: draft
    try:
        payload = am.resolve_auto_mask(object(), "p1", "m1", "cup")
    finally:
        am.get_capability = original_cap
        am.load_spatial_draft = original_load
    assert payload["ok"] is False
    assert payload["maskAssetId"] == ""
    assert "paint" in payload["message"].lower()


def test_catalog_selection_models_stay_not_required():
    assert get_component("sam21_hiera_tiny").required is False
    assert get_component("grounding_dino_tiny").required is False
    assert get_component("depth_anything_v2_small").required is False
    assert get_component("vjepa2_world_intelligence").required is False
    assert "timelens" not in BY_ID


def test_vggt_noncommercial_ids_stay_out_of_catalog():
    assert "vggt" not in BY_ID
    assert "vggt_1b" not in BY_ID
    assert "vggt_1b_commercial" in BY_ID


def test_select_persists_real_mask(tmp_path, monkeypatch):
    from app.codirector.perception import selection_service as svc
    from app.codirector.perception.selection_contracts import SelectRequest
    from app.image_product import masks as mask_mod

    monkeypatch.setattr(mask_mod, "project_dir", lambda project_id: tmp_path / project_id)
    monkeypatch.setattr(svc, "selection_models_present", lambda: True)
    monkeypatch.setattr(svc, "_asset_path", lambda *_a, **_k: str(tmp_path / "missing.png"))

    img = Image.new("L", (4, 4), 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    def fake_worker(_payload):
        return {"ok": True, "maskPngBase64": b64, "label": "cup", "bounds": {"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5}, "confidence": 0.9}

    result = svc.select(None, "proj-test", SelectRequest(assetId="asset-1", label="cup"), worker=fake_worker)
    assert result["ok"] is True
    assert result["maskAssetId"]
    assert result["selection"]["maskAssetId"] == result["maskAssetId"]
    assert result.get("overlayPngBase64")


def test_sam_point_prompt_is_four_level():
    source = Path(__file__).resolve().parents[1] / "app" / "codirector" / "perception" / "worker.py"
    text = source.read_text(encoding="utf-8")
    assert "input_points = [[[[px, py]]]]" in text
    assert "input_labels = [[[1]]]" in text


def test_resolve_ffmpeg_finds_an_executable():
    from app.codirector.perception.tracking_service import resolve_ffmpeg

    found = resolve_ffmpeg()
    assert found
    assert Path(found).is_file()


def test_track_extracts_frames_not_video_bytes(tmp_path, monkeypatch):
    from app.codirector.perception import tracking_service as ts

    monkeypatch.setattr(ts, "sam_present", lambda: True)
    monkeypatch.setattr(ts, "_asset_path", lambda *_a, **_k: str(tmp_path / "clip.mp4"))
    (tmp_path / "clip.mp4").write_bytes(b"not-a-video")
    called = {}

    def fake_extract(video_path, dest_png, time_sec):
        called["extract"] = True
        dest_png.parent.mkdir(parents=True, exist_ok=True)
        Image.new("L", (4, 4), 255).save(dest_png)
        return True

    img = Image.new("L", (4, 4), 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    def fake_worker(payload):
        called["imagePath"] = payload.get("imagePath")
        called["mode"] = payload.get("mode")
        if payload.get("mode") == "track":
            return {
                "ok": True,
                "frames": [{"frameTimeMs": 0, "maskPngBase64": b64, "bounds": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}}],
            }
        return {"ok": True, "maskPngBase64": b64, "label": "car", "bounds": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}}

    monkeypatch.setattr(ts, "extract_video_frame", fake_extract)
    from app.codirector.perception.selection_contracts import TrackRequest
    from app.image_product import masks as mask_mod
    from app.codirector.perception import cache as cache_mod

    monkeypatch.setattr(mask_mod, "project_dir", lambda project_id: tmp_path / project_id)
    monkeypatch.setattr(cache_mod.settings, "data_dir", tmp_path)
    monkeypatch.setattr(ts.settings, "data_dir", tmp_path)

    result = ts.track(None, "proj-t", TrackRequest(assetId="vid-1", label="car"), worker=fake_worker)
    assert called.get("extract") is True
    assert result["ok"] is True
    assert result["nativeVideoInpaint"] is False
    assert "range replacement" in result["disclosure"].lower() or "unavailable" in result["disclosure"].lower()
