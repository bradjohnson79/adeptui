"""Composition order is track position. Shot numbers stay put. An order-only stitch waits."""

from __future__ import annotations

from app.codirector.conversation.foundation.speech_act import classify_speech_act, resolve_production_action
from app.film_timeline.contracts import FilmTimeline, Segment, Shot
from app.film_timeline.orchestrator import (
    _order_only_rearrange,
    apply_composition_move,
    composition_units,
    mark_order_stale,
)
from app.film_timeline.retake import plan_replacement_pieces


def _shot() -> Shot:
    return Shot(
        segments=[
            Segment(id="a", order=0, status="completed", assetId="a", durationSec=15, shotNumber=1, origin="generated"),
            Segment(id="b", order=1, status="completed", assetId="b", durationSec=8, shotNumber=2, origin="library"),
            Segment(id="c", order=2, status="completed", assetId="c", durationSec=12, shotNumber=3, origin="generated"),
        ]
    )


def test_move_later_keeps_shot_numbers_and_marks_the_old_order_stale():
    shot = _shot()
    shot.state.stitchStatus = "ready"
    shot.state.stitchAssetId = "stitched"
    shot.state.stitchSegmentIds = ["a", "b", "c"]
    apply_composition_move(shot, segment_id="c", direction="earlier")
    assert [item.id for item in composition_units(shot) for item in item] == ["a", "c", "b"]
    assert [item.shotNumber for item in shot.segments] == [1, 3, 2]
    mark_order_stale(shot)
    assert shot.state.stitchStatus == "stale"
    assert shot.state.stitchAssetId is None
    assert shot.state.stitchSegmentIds == ["a", "b", "c"]
    assert _order_only_rearrange(shot, [item for unit in composition_units(shot) for item in unit]) is True


def test_edges_do_not_wrap_and_a_retake_run_moves_together():
    shot = _shot()
    try:
        apply_composition_move(shot, segment_id="a", direction="earlier")
        raised = False
    except Exception as exc:
        raised = True
        assert "already first" in str(exc)
    assert raised
    source = shot.segments[0]
    pieces = plan_replacement_pieces(source, "new", file_in=7, file_out=10, marked=3, generated_sec=3, prompt="turns")
    for index, piece in enumerate(pieces):
        piece.id = f"p{index}"
        piece.order = index
    shot.segments = pieces + shot.segments[1:]
    for index, item in enumerate(shot.segments):
        item.order = index
    apply_composition_move(shot, segment_id="p1", direction="later")
    ids = [item.id for item in composition_units(shot) for item in item]
    assert ids[:3] == ["b", "p0", "p1"] or ids[1:4] == ["p0", "p1", "p2"]
    assert [item.shotNumber for item in pieces] == [1, 1, 1]


def test_phrases_use_the_timeline_services():
    assert resolve_production_action("Move Shot 4 before Shot 2.") == "timeline.reorder"
    assert resolve_production_action("Put the imported library clip after Shot 1.") == "timeline.reorder"
    assert resolve_production_action("Stitch these clips together.") == "timeline.stitch"
    assert classify_speech_act("Stitch these clips together.") == "COMMAND"
    assert FilmTimeline.__name__ == "FilmTimeline"
