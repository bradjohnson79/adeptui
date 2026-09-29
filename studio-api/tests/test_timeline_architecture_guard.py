"""Timeline architecture pins after the Film Timeline cutover.

Owner unlock: timeline
Owner unlock: API multi-window pipeline
Owner unlock: timeline-reference-identity

The previous batch-window pins described SceneTimelineMaster as the production
authority. That runtime is retired. Live pins are in test_film_timeline.py.
"""

from __future__ import annotations

from pathlib import Path

API = Path(__file__).resolve().parents[1]


def test_film_timeline_is_the_production_owner():
    contracts = (API / "app" / "film_timeline" / "contracts.py").read_text(encoding="utf-8")
    assert "class FilmTimeline" in contracts
    assert "class ShotState" in contracts
    router = (API / "app" / "director_timeline_w46" / "router.py").read_text(encoding="utf-8")
    generate = router.split("def generate_scene", 1)[1].split("def list_scene_takes", 1)[0]
    assert "_film_timeline_only()" in generate
    assert "orchestrator.generate_scene" not in generate


def test_motion_context_is_not_imported():
    strategies = (API / "app" / "film_timeline" / "strategies.py").read_text(encoding="utf-8")
    assert "MOTION_CONTEXT_AVAILABLE = False" in strategies
    assert "ComfyUI-H3-Motion-Context" in strategies
