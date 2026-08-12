"""M42 W4B overlay domain + render + security unit tests."""

from __future__ import annotations

import uuid

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


def test_wave5_may_begin_symbol_exists():
    g = evaluate_wave5_may_begin()
    assert "Wave5MayBegin" in g
    assert "wave4bGo" in g


def test_gate_includes_overlay_flags():
    g = evaluate_magi_wave4b_gate()
    assert "textOverlayDomainOperational" in g
    assert "CanonicalOverlayRenderOperational" in g
