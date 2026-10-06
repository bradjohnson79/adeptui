from __future__ import annotations

import json

import pytest

from app.video_runtime.local_t2v import (
    i2v_only_blocker,
    is_local_ltx25_t2v_engine,
    is_local_minimax_t2v_engine,
    is_local_t2v_engine,
    resolve_txt2vid_engine,
)
from app.video_runtime.workflow_resolver import resolve_workflow


def test_engine_tokens():
    assert is_local_ltx25_t2v_engine("ltx-2.5")
    assert is_local_ltx25_t2v_engine("ltx-2.5-distilled")
    assert not is_local_ltx25_t2v_engine("ltx")
    assert is_local_minimax_t2v_engine("minimax-h3")
    assert not is_local_minimax_t2v_engine("wan")


def test_allow_local_t2v_for_ltx25_and_minimax():
    assert is_local_t2v_engine("ltx-2.5") is True
    assert is_local_t2v_engine("ltx-2.5-distilled") is True
    assert is_local_t2v_engine("minimax-h3") is True
    assert is_local_t2v_engine("ltx") is False
    assert is_local_t2v_engine("wan") is False


def test_auto_prefers_ltx25_then_minimax_never_hosted():
    assert resolve_txt2vid_engine("auto", ltx25_ready=True, minimax_ready=True) == "ltx-2.5"
    assert resolve_txt2vid_engine("auto", ltx25_ready=False, minimax_ready=True) == "minimax-h3"
    assert (
        resolve_txt2vid_engine(
            "auto",
            ltx25_ready=False,
            minimax_ready=False,
            paid_fal_approved=True,
        )
        == "auto"
    )
    assert resolve_txt2vid_engine("auto", ltx25_ready=False, minimax_ready=False) == "auto"
    assert resolve_txt2vid_engine("minimax-h3", ltx25_ready=True) == "minimax-h3"


def test_resolver_txt2vid_ltx25_empty_latent():
    contract = resolve_workflow("txt2vid", engine="ltx-2.5", present_inputs={})
    assert contract.leaf_workflow_key == "ltx_25.t2v"


def test_resolver_txt2vid_minimax_does_not_use_ltx():
    with pytest.raises(RuntimeError, match="LOCAL_T2V_UNSUPPORTED|MINIMAX_MODE_REQUIRED"):
        resolve_workflow("txt2vid", engine="minimax-h3", present_inputs={})


def test_resolver_scene_minimax_does_not_silent_swap_to_ltx():
    with pytest.raises(RuntimeError, match="MINIMAX_MODE_REQUIRED"):
        resolve_workflow(
            "scene_render",
            engine="minimax-h3",
            present_inputs={"start_asset_id": "still-1"},
        )


def test_i2v_only_blocker_message():
    body = i2v_only_blocker(engine="wan")
    assert body["code"] == "WRONG_SURFACE_FOR_ENGINE"
    assert "1 Frame" in str(body["message"])
    json.dumps(body)


def test_catalog_ltx25_and_minimax_advertise_t2v():
    from app.production_control.model_registry import list_models

    by_id = {m.id: m for m in list_models("video")}
    assert "text_to_video" in (by_id["ltx-2.5-distilled"].supports or [])
    assert "image_to_video" in (by_id["ltx-2.5-distilled"].supports or [])
    assert "text_to_video" in (by_id["minimax-h3"].supports or [])
