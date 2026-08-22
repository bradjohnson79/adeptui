"""One-figure hard gate + AUTO FLUX → Qwen fallback. No Korri, no live generation."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.character_identity.crs_single_figure import (
    FAILURE_COLLAGE,
    FAILURE_MULTI,
    CrsSingleFigureResult,
    detect_collage_layout,
    is_crs_single_view_job,
    should_fallback_to_qwen,
    validate_crs_single_figure,
)


def _write_one_figure(path: Path) -> Path:
    im = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(im)
    draw.rectangle((20, 8, 44, 56), fill=20)
    im.save(path)
    return path


def _write_two_figures(path: Path) -> Path:
    im = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(im)
    draw.rectangle((6, 10, 26, 54), fill=20)
    draw.rectangle((38, 10, 58, 54), fill=20)
    im.save(path)
    return path


def _write_collage(path: Path) -> Path:
    im = Image.new("L", (64, 64), 40)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 30, 30), fill=30)
    draw.rectangle((34, 0, 63, 30), fill=80)
    draw.rectangle((0, 34, 30, 63), fill=120)
    draw.rectangle((34, 34, 63, 63), fill=160)
    draw.rectangle((30, 0, 34, 63), fill=255)
    draw.rectangle((0, 30, 63, 34), fill=255)
    im.save(path)
    return path


def test_one_figure_passes(tmp_path: Path) -> None:
    img = _write_one_figure(tmp_path / "one.png")
    result = validate_crs_single_figure(img, detect_people=lambda _p: 1)
    assert result.single_figure_pass is True
    assert result.detected_figures == 1
    assert result.failure_code is None
    assert result.view_angle_pass is None


def test_two_figures_fail(tmp_path: Path) -> None:
    img = _write_two_figures(tmp_path / "two.png")
    result = validate_crs_single_figure(img, detect_people=lambda _p: 2)
    assert result.single_figure_pass is False
    assert result.detected_figures == 2
    assert result.failure_code == FAILURE_MULTI


def test_collage_heuristic_detects_grid_not_single_blob(tmp_path: Path) -> None:
    one = _write_one_figure(tmp_path / "one.png")
    grid = _write_collage(tmp_path / "grid.png")
    assert detect_collage_layout(one) is False
    assert detect_collage_layout(grid) is True


def test_collage_fails(tmp_path: Path) -> None:
    img = _write_collage(tmp_path / "grid.png")
    result = validate_crs_single_figure(img, detect_people=lambda _p: 1)
    assert result.single_figure_pass is False
    assert result.failure_code == FAILURE_COLLAGE


def test_unverified_is_not_a_pass(tmp_path: Path) -> None:
    img = _write_one_figure(tmp_path / "maybe.png")
    result = validate_crs_single_figure(
        img,
        detect_people=lambda _p: None,
        detect_collage=lambda _p: False,
    )
    assert result.single_figure_pass is None
    assert result.failure_code is None


def test_is_crs_single_view_job() -> None:
    assert is_crs_single_view_job({"taskType": "CRS_SINGLE_VIEW"}) is True
    assert is_crs_single_view_job({"layout": "crs_view", "fourViewSingleOutput": False}) is True
    assert is_crs_single_view_job({"layout": "four_view", "fourViewSingleOutput": True}) is False
    assert is_crs_single_view_job({"purpose": "character_sheet"}) is False


def test_fallback_only_for_auto_flux() -> None:
    fail = CrsSingleFigureResult(False, 4, FAILURE_MULTI)
    assert should_fallback_to_qwen({"modelFamilyPreference": "flux", "autoSelect": True}, fail)
    assert not should_fallback_to_qwen({"modelFamilyPreference": "flux", "autoSelect": False}, fail)
    assert not should_fallback_to_qwen(
        {"modelFamilyPreference": "flux", "autoSelect": True, "crsSingleFigureFallback": True},
        fail,
    )
    assert not should_fallback_to_qwen({"modelFamilyPreference": "qwen2512", "autoSelect": True}, fail)
    assert not should_fallback_to_qwen({"modelFamilyPreference": "flux", "autoSelect": True}, CrsSingleFigureResult(True, 1, None))
    assert not should_fallback_to_qwen({"modelFamilyPreference": "flux", "autoSelect": True}, CrsSingleFigureResult(None, None, None))


def test_fallback_enqueues_one_qwen_job(monkeypatch) -> None:
    from app.character_identity import visual_sheet as vs

    captured: list[dict] = []

    class _Job:
        id = "flux-job-1"
        project_id = "proj-patch"
        params_json = (
            '{"taskType":"CRS_SINGLE_VIEW","viewRole":"full_body_front",'
            '"modelFamilyPreference":"flux","autoSelect":true,'
            '"creativeContext":{"characterId":"char-patch","viewRole":"full_body_front"}}'
        )

    class _Profile:
        def model_dump(self):
            return {"name": "PatchSubject", "slug": "patch_subject", "visual_style": ""}

    monkeypatch.setattr(vs.service, "get_profile", lambda *_a, **_k: _Profile())
    monkeypatch.setattr(vs.service, "list_references", lambda *_a, **_k: [])
    monkeypatch.setattr(vs, "_resolve_style_profile", lambda *_a, **_k: {})

    def fake_enqueue(*_a, **kwargs):
        captured.append(kwargs)
        out = type("J", (), {"id": "qwen-fallback-1"})()
        return out

    monkeypatch.setattr(vs, "_enqueue_txt2img", fake_enqueue)
    job = vs.enqueue_crs_qwen_fallback_for_job(None, _Job())
    assert job.id == "qwen-fallback-1"
    assert len(captured) == 1
    assert captured[0]["model_family_preference"] == "qwen2512"
    assert captured[0]["force_workflow_key"] == "qwen2512.txt2img"
    assert captured[0]["sheet_layout"] == "crs_view"
    assert captured[0]["prompt_metadata"]["crsSingleFigureFallback"] is True
    assert captured[0]["prompt_metadata"]["taskType"] == "CRS_SINGLE_VIEW"
    assert "1. Request Intent" in captured[0]["prompt"] or "Request Intent" in captured[0]["prompt"]
