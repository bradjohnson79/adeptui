"""CRS law-view hard gates: one figure + requested view, fail-close."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.character_identity.crs_law_view_gates import (
    RECOMMEND,
    evaluate_crs_law_view_tile,
    gate_candidate_law_views,
    record_slot_gate,
)


class _MockDetector:
    def __init__(self, figures: int | None, view: str | None) -> None:
        self.figures = figures
        self.view = view

    def count_figures(self, path, *, extras=None):
        return self.figures

    def detect_view(self, path, *, extras=None):
        return self.view


def _collage_png(path: Path) -> Path:
    im = Image.new("RGB", (256, 256), (20, 20, 20))
    draw = ImageDraw.Draw(im)
    colors = [(210, 40, 40), (40, 180, 40), (40, 40, 210), (220, 200, 40)]
    boxes = [(8, 8, 120, 120), (136, 8, 248, 120), (8, 136, 120, 248), (136, 136, 248, 248)]
    for box, color in zip(boxes, colors):
        draw.rectangle(box, fill=color)
    # dark gutters already exist as the background
    im.save(path)
    return path


def _single_png(path: Path) -> Path:
    im = Image.new("RGB", (256, 256), (30, 30, 30))
    draw = ImageDraw.Draw(im)
    draw.ellipse((88, 40, 168, 216), fill=(200, 180, 160))
    im.save(path)
    return path


def test_collage_tile_rejected(tmp_path: Path) -> None:
    tile = _collage_png(tmp_path / "collage.png")
    verdict = evaluate_crs_law_view_tile(path=str(tile), requested_role="hero_identity")
    assert verdict.accepted is False
    assert any(c.name == "one_figure" and c.status == "FAIL" for c in verdict.checks)
    slot: dict = {"role": "hero_identity", "assetId": "a1"}
    record_slot_gate(slot, verdict)
    assert slot["composeEligible"] is False
    assert slot["autoApproved"] is False
    assert slot["gateRejected"] is True


def test_single_matching_view_accepted(tmp_path: Path) -> None:
    tile = _single_png(tmp_path / "front.png")
    verdict = evaluate_crs_law_view_tile(
        path=str(tile),
        requested_role="hero_identity",
        detector=_MockDetector(1, "front"),
    )
    assert verdict.accepted is True
    assert verdict.figure_count == 1
    assert verdict.detected_view == "front"
    soft = [c for c in verdict.checks if c.name in ("identity", "wardrobe", "domain")]
    assert soft and all(c.status == RECOMMEND for c in soft)


def test_wrong_angle_single_rejected(tmp_path: Path) -> None:
    tile = _single_png(tmp_path / "side.png")
    verdict = evaluate_crs_law_view_tile(
        path=str(tile),
        requested_role="hero_identity",
        detector=_MockDetector(1, "side"),
    )
    assert verdict.accepted is False
    assert any(c.name == "requested_view" and c.status == "FAIL" for c in verdict.checks)
    assert "wanted front" in verdict.error


def test_failed_slots_block_compose(tmp_path: Path) -> None:
    collage = _collage_png(tmp_path / "c.png")
    front = _single_png(tmp_path / "f.png")
    jobs = [
        {"role": "hero_identity", "assetId": "1", "gateExtras": {"detectedView": "front"}},
        {
            "role": "full_body_side_left",
            "assetId": "2",
            "gateExtras": {"figureCount": 1, "detectedView": "side"},
        },
    ]
    paths = {"1": str(collage), "2": str(front)}
    result = gate_candidate_law_views(jobs, resolve_path=lambda vj: paths.get(str(vj.get("assetId"))))
    assert result["accepted"] is False
    assert result["kreaInvoked"] is False
    assert result["autoApproved"] is False
    assert jobs[0]["composeEligible"] is False

def test_unknown_detector_does_not_reject_single_figure(tmp_path: Path) -> None:
    """No pose/view scorer: requested_view is RECOMMEND, compose stays eligible."""
    tile = _single_png(tmp_path / "solo.png")
    verdict = evaluate_crs_law_view_tile(
        path=str(tile),
        requested_role="hero_identity",
        detector=_MockDetector(1, None),
    )
    assert verdict.accepted is True
    assert verdict.figure_count == 1
    rv = next(c for c in verdict.checks if c.name == "requested_view")
    assert rv.status == RECOMMEND
    assert rv.fail_closed is False
    assert rv.detail.get("scoringUnavailable") is True
    slot: dict = {"role": "hero_identity"}
    record_slot_gate(slot, verdict)
    assert slot["composeEligible"] is True
    assert slot["gateRejected"] is False
    assert slot["autoApproved"] is False


def test_unavailable_detector_error_is_recommend_not_reject(tmp_path: Path) -> None:
    class _Boom:
        def count_figures(self, path, *, extras=None):
            return 1

        def detect_view(self, path, *, extras=None):
            raise RuntimeError("no pose scorer")

    tile = _single_png(tmp_path / "err.png")
    verdict = evaluate_crs_law_view_tile(
        path=str(tile),
        requested_role="full_body_side_left",
        detector=_Boom(),
    )
    assert verdict.accepted is True
    rv = next(c for c in verdict.checks if c.name == "requested_view")
    assert rv.status == RECOMMEND
    assert "unavailable" in rv.reason


def test_default_detector_without_sidecar_does_not_reject_single(tmp_path: Path) -> None:
    tile = _single_png(tmp_path / "plain.png")
    verdict = evaluate_crs_law_view_tile(path=str(tile), requested_role="hero_identity")
    of = next(c for c in verdict.checks if c.name == "one_figure")
    if of.status == "PASS":
        assert verdict.accepted is True
        rv = next(c for c in verdict.checks if c.name == "requested_view")
        assert rv.status == RECOMMEND
