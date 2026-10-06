"""QueueWorker passes turbo_lora into build_leaf_graph for LTX 2.5. The signature must accept it."""

from app.config import settings
from app.video_runtime.workflow_execute import build_leaf_graph
from app.video_runtime.workflow_resolver import resolve_from_scene_params


def test_ltx_25_i2v_accepts_turbo_lora_kwargs() -> None:
    contract = resolve_from_scene_params(
        engine="ltx-2.5",
        start_asset_id="asset-start-frame",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
    )
    assert contract.leaf_workflow_key == "ltx_25.i2v"
    graph = build_leaf_graph(
        contract,
        settings=settings,
        positive="a still camera",
        negative="",
        width=1280,
        height=704,
        length=121,
        fps=24,
        seed=11,
        start_image="start.png",
        steps=8,
        filename_prefix="studio/ltx_i2v_test",
        turbo_lora=True,
    )
    classes = {n["class_type"] for n in graph.values()}
    assert "LTXVImgToVideo" in classes
    assert "LoraLoaderModelOnly" in classes
