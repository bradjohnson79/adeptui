from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _synthetic_corridor(height: int = 80, width: int = 120) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:height, 0:width]
    points = np.zeros((height, width, 3), dtype=np.float64)
    points[:, :, 0] = (xs / max(width - 1, 1)) * 8.0 - 4.0
    points[:, :, 2] = (ys / max(height - 1, 1)) * 16.0
    points[:, :, 1] = 0.0
    points[:8, :, 1] = 2.4
    points[-8:, :, 1] = 2.4
    colors = np.zeros((height, width, 3), dtype=np.uint8)
    colors[:, :] = (120, 90, 70)
    colors[:8, :] = (40, 40, 48)
    colors[-8:, :] = (40, 40, 48)
    return points, colors


def test_top_down_is_repeatable(tmp_path: Path):
    from app.spatial_map.geometry.renderer import MANDATORY_VIEW, render_views

    points, colors = _synthetic_corridor()
    first = render_views(points=points, colors=colors, output_dir=tmp_path / "a", engine="fixture")
    second = render_views(points=points, colors=colors, output_dir=tmp_path / "b", engine="fixture")
    assert first["ok"] is True
    assert MANDATORY_VIEW in first["views"]
    a = np.asarray(Image.open(first["mandatoryPlate"]))
    b = np.asarray(Image.open(second["mandatoryPlate"]))
    assert a.shape == b.shape
    assert np.array_equal(a, b)
    assert first["provenance"]["diffusion"] is False
    assert first["provenance"]["styleKnobs"] is None


def test_unknown_samples_stay_muted(tmp_path: Path):
    from app.spatial_map.geometry.renderer import render_views

    points, colors = _synthetic_corridor()
    points[:, 60:] = np.nan
    result = render_views(points=points, colors=colors, output_dir=tmp_path, engine="fixture")
    plate = np.asarray(Image.open(result["mandatoryPlate"]))
    assert plate.shape[2] == 4
    assert int((plate[:, :, 3] < 255).sum()) > 100


def test_vggt_forbids_noncommercial_model():
    from app.spatial_map.geometry.vggt_runtime import assert_commercial_model_only

    try:
        assert_commercial_model_only("facebook/VGGT-1B")
        raise AssertionError("non-commercial VGGT must be forbidden")
    except ValueError as exc:
        assert "VGGT-1B-Commercial" in str(exc)


def test_vggt_clone_is_never_ready(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import vggt_runtime

    root = tmp_path / "vggt"
    (root / "src" / "vggt" / "models").mkdir(parents=True)
    (root / "src" / "vggt" / "models" / "vggt.py").write_text("# clone only\n", encoding="utf-8")
    monkeypatch.setattr(vggt_runtime, "runtime_root", lambda: root)
    status = vggt_runtime.runtime_status()
    assert vggt_runtime.source_present() is True
    assert vggt_runtime.commercial_weights_present() is False
    assert status["sourceInstalled"] is True
    assert status["runtimeReady"] is False
    assert status["modelReady"] is False
    assert status["available"] is False
    assert status["status"] == "model_access_gated"
    assert status["modelSource"] == "facebook/VGGT-1B-Commercial"


def test_vggt_plate_stays_gated_without_commercial_weights(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import infer, vggt_runtime

    monkeypatch.setattr(vggt_runtime, "commercial_weights_present", lambda: False)
    monkeypatch.setattr(infer, "require_essential_agreement", lambda *args, **kwargs: None)
    result = infer.run_vggt_plate([tmp_path / "a.png", tmp_path / "b.png"], tmp_path)
    assert result["ok"] is False
    assert result["code"] == "MODEL_ACCESS_GATED"
    assert "MoGe-2" in result["message"]


def test_vggt_single_observed_image_falls_back_to_moge(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import infer

    monkeypatch.setattr(infer, "require_essential_agreement", lambda *args, **kwargs: None)
    result = infer.run_vggt_plate([tmp_path / "only.png"], tmp_path)
    assert result["ok"] is False
    assert result["code"] == "VGGT_REQUIRES_TWO_OBSERVED_IMAGES"
    assert result["fallback"] == "moge2"


def test_vggt_rejects_inferred_qwen_views(tmp_path: Path, monkeypatch):
    from app.spatial_map.geometry import infer

    monkeypatch.setattr(infer, "require_essential_agreement", lambda *args, **kwargs: None)
    result = infer.run_vggt_plate(
        [tmp_path / "a.png", tmp_path / "b.png"],
        tmp_path,
        inferred_image_paths=[tmp_path / "qwen_edit.png"],
    )
    assert result["ok"] is False
    assert result["code"] == "INFERRED_NOT_VGGT_EVIDENCE"


def test_assemble_bakeoff_records_matched_renderer(tmp_path: Path, monkeypatch):
    from PIL import Image

    from app.spatial_map.geometry import bakeoff

    src = tmp_path / "source.png"
    Image.new("RGB", (64, 36), (80, 80, 80)).save(src)
    plate_dir = tmp_path / "moge2" / "plates"
    plate_dir.mkdir(parents=True)
    Image.new("RGB", (64, 64), (40, 40, 40)).save(plate_dir / "top_down_orthographic.png")
    monkeypatch.setattr(bakeoff, "run_vggt_plate", lambda *args, **kwargs: {"ok": False, "code": "VGGT_REQUIRES_TWO_OBSERVED_IMAGES"})
    report = bakeoff.assemble_existing_bakeoff(source_path=src, output_dir=tmp_path)
    assert report["matchedRenderer"] == "adept.atlas.deterministic.v1"
    assert report["viewportBuilt"] is False
    assert report["enginePromoted"] is False


def test_install_rejects_noncommercial_vggt(monkeypatch):
    from app.spatial_map.geometry import install

    monkeypatch.setattr(install, "require_essential_agreement", lambda *args, **kwargs: None)
    try:
        install.install_vggt_source(model_id="facebook/VGGT-1B")
        raise AssertionError("non-commercial VGGT install must be rejected")
    except ValueError as exc:
        assert "VGGT-1B-Commercial" in str(exc)
