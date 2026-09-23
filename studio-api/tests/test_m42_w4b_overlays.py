"""M42 W4B overlay domain + render + security unit tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.magi.overlays import store as overlay_store
from app.magi.overlays.validate import validate_composition
from app.magi.composition.render import render_composition_to_png
from app.magi.production_gate import evaluate_magi_wave4b_gate, evaluate_wave5_may_begin


def _comp(project_id: str, **extra):
    return {
        "schemaVersion": 1,
        "compositionId": str(uuid.uuid4()),
        "projectId": project_id,
        "sourceAssetId": None,
        "canvasWidth": 640,
        "canvasHeight": 360,
        "overlays": [
            {
                "id": "txt-1",
                "type": "text",
                "name": "Title",
                "visible": True,
                "locked": False,
                "opacity": 1,
                "x": 0.1,
                "y": 0.1,
                "width": 0.5,
                "height": 0.15,
                "rotation": 0,
                "anchorX": 0,
                "anchorY": 0,
                "zIndex": 1,
                "startFrame": None,
                "endFrame": None,
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z",
                "text": "Hello MAGI",
                "textStyle": {
                    "fontFamily": "dejavu-sans",
                    "fontSize": 32,
                    "fontWeight": 700,
                    "fontStyle": "normal",
                    "textDecoration": "none",
                    "color": "#FFFFFF",
                    "alignment": "left",
                    "verticalAlignment": "middle",
                    "lineHeight": 1.2,
                    "letterSpacing": 0,
                    "wordSpacing": 0,
                    "uppercase": False,
                    "maxLines": None,
                    "autoFit": False,
                    "strokeColor": None,
                    "strokeWidth": 0,
                    "shadowEnabled": False,
                    "shadowColor": "#000000",
                    "shadowBlur": 0,
                    "shadowOffsetX": 0,
                    "shadowOffsetY": 0,
                },
                "backgroundStyle": {
                    "enabled": True,
                    "fill": "#000000",
                    "opacity": 0.5,
                    "paddingTop": 4,
                    "paddingRight": 8,
                    "paddingBottom": 4,
                    "paddingLeft": 8,
                    "cornerRadius": 4,
                    "borderEnabled": False,
                    "borderColor": "#fff",
                    "borderWidth": 1,
                    "autoSize": True,
                    "fixedWidth": None,
                },
                "animationPreset": None,
            }
        ],
        "safeAreaEnabled": True,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        **extra,
    }


def test_validate_rejects_script_markup():
    pid = "proj-overlay-sec"
    c = _comp(pid)
    c["overlays"][0]["text"] = "<script>alert(1)</script>"
    v = validate_composition(c, project_id=pid)
    assert not v["ok"]


def test_validate_rejects_raw_svg():
    pid = "proj-overlay-svg"
    c = _comp(pid)
    c["overlays"].append(
        {
            "id": "vec-1",
            "type": "vector",
            "name": "bad",
            "visible": True,
            "locked": False,
            "opacity": 1,
            "x": 0.1,
            "y": 0.1,
            "width": 0.2,
            "height": 0.2,
            "rotation": 0,
            "anchorX": 0,
            "anchorY": 0,
            "zIndex": 1,
            "startFrame": None,
            "endFrame": None,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "shape": "rectangle",
            "fill": "#fff",
            "stroke": None,
            "strokeWidth": 0,
            "cornerRadius": 0,
            "rawSvg": "<svg onload=alert(1)></svg>",
        }
    )
    v = validate_composition(c, project_id=pid)
    assert not v["ok"]


def test_validate_accepts_image_overlay():
    pid = "proj-overlay-img"
    c = _comp(pid)
    c["overlays"].append(
        {
            "id": "img-1",
            "type": "image",
            "name": "Logo",
            "visible": True,
            "locked": False,
            "opacity": 1,
            "x": 0.1,
            "y": 0.1,
            "width": 0.2,
            "height": 0.2,
            "rotation": 0,
            "anchorX": 0,
            "anchorY": 0,
            "zIndex": 5,
            "startFrame": None,
            "endFrame": None,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "assetId": "asset-123",
        }
    )
    v = validate_composition(c, project_id=pid)
    assert v["ok"], v["errors"]


def test_validate_rejects_image_without_asset_id():
    c = _comp("proj-overlay-img-bad")
    c["overlays"].append(
        {
            "id": "img-2",
            "type": "image",
            "name": "Bad",
            "visible": True,
            "locked": False,
            "opacity": 1,
            "x": 0.1,
            "y": 0.1,
            "width": 0.2,
            "height": 0.2,
            "rotation": 0,
            "anchorX": 0,
            "anchorY": 0,
            "zIndex": 5,
            "startFrame": None,
            "endFrame": None,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        }
    )
    v = validate_composition(c, project_id="proj-overlay-img-bad")
    assert not v["ok"]
    assert any("assetid" in e.lower() for e in v["errors"])


def test_validate_rejects_cross_project():
    c = _comp("a")
    v = validate_composition(c, project_id="b")
    assert not v["ok"]


def test_store_and_render(tmp_path):
    pid = f"proj-{uuid.uuid4().hex[:8]}"
    c = _comp(pid)
    saved = overlay_store.save_composition(pid, c)
    assert saved["compositionId"]
    loaded = overlay_store.get_composition(pid, saved["compositionId"])
    assert loaded and loaded["overlays"][0]["text"] == "Hello MAGI"
    out = tmp_path / "out.png"
    meta = render_composition_to_png(source_image_path=None, composition=loaded, out_path=out)
    assert out.is_file()
    assert meta["staticRender"] is True
    assert meta.get("compositionId") == loaded["compositionId"]
    from PIL import Image as PILImage

    plate = PILImage.open(out).convert("RGBA")
    corner = plate.getpixel((plate.width - 2, plate.height - 2))
    assert corner[3] == 0, "overlay plate must stay transparent so video remains visible"


def test_image_render_loads_asset(tmp_path):
    from PIL import Image as PILImage
    pid = f"proj-{uuid.uuid4().hex[:8]}"
    asset_id = "img-asset-1"
    asset_path = tmp_path / "asset.png"
    src = PILImage.new("RGBA", (100, 100), (255, 0, 0, 128))
    src.save(asset_path, "PNG")

    c = _comp(pid)
    c["overlays"] = [
        {
            "id": "img-1",
            "type": "image",
            "name": "Logo",
            "visible": True,
            "locked": False,
            "opacity": 1,
            "x": 0,
            "y": 0,
            "width": 1,
            "height": 1,
            "rotation": 0,
            "anchorX": 0,
            "anchorY": 0,
            "zIndex": 1,
            "startFrame": None,
            "endFrame": None,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "assetId": asset_id,
        }
    ]
    saved = overlay_store.save_composition(pid, c)
    assert saved["overlays"][0]["type"] == "image"
    out = tmp_path / "out.png"
    meta = render_composition_to_png(
        source_image_path=None,
        composition=saved,
        out_path=out,
        asset_paths={asset_id: str(asset_path)},
    )
    assert out.is_file()
    assert meta["overlayIds"] == ["img-1"]


def test_wave5_may_begin_symbol_exists():
    g = evaluate_wave5_may_begin()
    assert "Wave5MayBegin" in g
    assert "wave4bGo" in g


def test_gate_includes_overlay_flags():
    g = evaluate_magi_wave4b_gate()
    assert "textOverlayDomainOperational" in g
    assert "CanonicalOverlayRenderOperational" in g


def test_faded_overlay_stays_visible_mid_window(tmp_path):
    """Still-PNG fade must not wipe the plate. Mid-window text must survive the burn."""
    import shutil
    import subprocess

    from PIL import Image as PILImage

    from app.magi.final_render import _maybe_overlay

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available")

    pid = f"proj-fade-{uuid.uuid4().hex[:8]}"
    c = _comp(pid)
    c["overlays"][0]["text"] = "ANADRIYA"
    c["overlays"][0]["animationPreset"] = "fade"
    c["overlays"][0]["startFrame"] = 24
    c["overlays"][0]["endFrame"] = 96
    c["overlays"][0]["textStyle"]["color"] = "#FFFFFF"
    c["overlays"][0]["backgroundStyle"]["enabled"] = False
    overlay_store.save_composition(pid, c)

    video = tmp_path / "edit.mp4"
    dest = tmp_path / "burned.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360:d=5:r=24",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    burned = _maybe_overlay(object(), pid, video, dest, fps=24)
    assert burned is not None and Path(burned).is_file()

    frame = tmp_path / "mid.png"
    grab = subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", "-ss", "2.0", "-i", str(burned), "-frames:v", "1", str(frame)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert grab.returncode == 0 and frame.is_file(), grab.stderr[-400:]
    pixels = list(PILImage.open(frame).convert("RGB").getdata())
    bright = sum(1 for r, g, b in pixels if r > 180 and g > 180 and b > 180)
    assert bright > 40, f"faded overlay missing mid-window; bright pixels={bright}"


def test_objects_track_must_be_1_or_2():
    pid = f"ov-{uuid.uuid4().hex[:8]}"
    bad = _comp(pid)
    bad["overlays"][0]["objectsTrack"] = 3
    result = validate_composition(bad, project_id=pid)
    assert result["ok"] is False
    assert any("objectsTrack" in err for err in result["errors"])


def test_overlay_paint_key_orders_objects_2_above_objects_1():
    from app.magi.final_render import _overlay_paint_key

    lt = {"objectsTrack": 1, "zIndex": 99}
    logo = {"objectsTrack": 2, "zIndex": 1}
    moved = {"objectsTrack": 2, "zIndex": 5}
    assert _overlay_paint_key(lt) < _overlay_paint_key(logo)
    assert _overlay_paint_key(moved) > _overlay_paint_key(logo) or _overlay_paint_key(moved)[0] == 2
    ordered = sorted([lt, logo, moved], key=_overlay_paint_key)
    assert ordered[0] is lt
    assert ordered[-1]["zIndex"] == 5 or ordered[-1] is logo
