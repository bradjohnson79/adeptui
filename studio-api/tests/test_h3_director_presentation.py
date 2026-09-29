"""Presentation-scope tests: H3 Director label + execution-plan Film dims."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.film_timeline.availability import list_generator_status
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import (
    MiniMaxH3I2VLocalAdapter,
)
from app.video_runtime.legal_canvas import resolve_generation_dimensions


def test_h3_local_filmmaker_label_is_director_not_r2v() -> None:
    caps = MiniMaxH3I2VLocalAdapter.capabilities
    assert caps.id == "minimax-h3-i2v-local"
    assert caps.label == "MiniMax H3 Director — Local"
    assert "Reference to Video" not in caps.label
    assert "Reference-to-Video" not in caps.label


def test_availability_overrides_h3_local_label_to_director() -> None:
    fake_caps = MagicMock()
    fake_caps.model_dump.return_value = {
        "id": "minimax-h3-i2v-local",
        "label": "SHOULD_BE_OVERRIDDEN",
        "executionType": "local",
        "executable": True,
    }
    registry = MagicMock()
    registry.list_capabilities.return_value = [fake_caps]
    with (
        patch("app.film_timeline.availability.get_registry", return_value=registry),
        patch("app.film_timeline.availability._comfy_reachable", return_value=True),
        patch("app.film_timeline.availability._secret_present", return_value=False),
    ):
        rows = list_generator_status()
    h3 = next(r for r in rows if r["id"] == "minimax-h3-i2v-local")
    assert h3["label"] == "MiniMax H3 Director — Local"
    assert "Reference to Video" not in h3["label"]


def test_h3_auto_quality_dims_are_1152x640() -> None:
    dims = resolve_generation_dimensions(model="minimax-h3-i2v-local", draft_mode=False)
    assert dims["width"] == 1152
    assert dims["height"] == 640
