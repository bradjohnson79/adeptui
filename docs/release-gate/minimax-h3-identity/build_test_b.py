"""Build Test B from the existing H3 compiler. Do not invent a second compiler."""

from __future__ import annotations

import json
from pathlib import Path

from app.db import SessionLocal
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import SceneTimelineMaster
from app.director_timeline_w46.generation.direct_reference import (
    build_direct_reference_payload,
    payload_to_r2v_slots,
)
from app.director_timeline_w46.generation.r2v import compile_h3_prompt
from app.workflows.h3_ref2v_builder import build_h3_ref2v

ROOT = Path(__file__).resolve().parent
PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
SCENE_ID = "a16515ce-cde8-4786-99fa-091d8bede618"
BATCH_ID = "bb_6226cbbd68b7"
SEED = 2248151181
ADDEX = "91b82df6-6c5a-410a-bdb8-6cd3f79753c7"
KORRI = "a42e77e0-dfe3-4ac9-85af-ab98dfc510e5"


def _authored_prompt() -> str:
    submit = json.loads(
        Path(
            r"C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\direct-reference-route\evidence\scene5_minimax_submit.json"
        ).read_text(encoding="utf-8")
    )
    return str(submit["normalizedRequest"]["providerOptions"]["authoredPrompt"])


def main() -> None:
    authored = _authored_prompt()
    with SessionLocal() as db:
        payload = store.load_master(db, PROJECT_ID, SCENE_ID)
        master = SceneTimelineMaster.model_validate(payload["master"])
        batch = next(item for item in master.batchBlocks if item.id == BATCH_ID)
        direct = build_direct_reference_payload(
            db,
            project_id=PROJECT_ID,
            scene_id=SCENE_ID,
            batch=batch,
            generator_id=batch.generatorId or "minimax-h3",
        )
    slots = payload_to_r2v_slots(direct)
    compiled, _ = compile_h3_prompt(authored, slots, style_key="realistic_anime")
    graph = build_h3_ref2v(
        prompt=compiled,
        ref_comfy_names=[
            f"studio/{ADDEX}.jpeg",
            f"studio/{KORRI}.jpeg",
        ],
        filename_prefix="identity_test/h3_subject_binding",
        seed=SEED,
        width=1280,
        height=704,
        length=124,
        steps=20,
        ref_image_size="max",
        fast=False,
    )
    node5 = graph["5"]["inputs"]
    node8 = graph["8"]["inputs"]
    node9 = graph["9"]["inputs"]
    preflight = {
        "primaryHypothesis": "existing compile_h3_prompt / render_h3 output reaches MiniMaxH3ReferenceToVideo.prompt",
        "secondaryVariables": ["ref_image_size=max", "EasyCache absent"],
        "picture_1": {"canonicalTag": slots[0].label, "assetId": slots[0].assetId, "socket": "ref_image_0"},
        "picture_2": {"canonicalTag": slots[1].label, "assetId": slots[1].assetId, "socket": "ref_image_1"},
        "subject_1": slots[0].label,
        "subject_2": slots[1].label,
        "ref_image_0": graph["15"]["inputs"]["image"],
        "ref_image_1": graph["16"]["inputs"]["image"],
        "ref_image_size": node5["ref_image_size"],
        "easyCache": "90" in graph,
        "steps": node8["steps"],
        "sampler": graph["7"]["inputs"]["sampler_name"],
        "scheduler": node8["scheduler"],
        "seed": graph["6"]["inputs"]["noise_seed"],
        "length": node5["length"],
        "resolution": f"{node5['width']}x{node5['height']}",
        "schedulerModel": node8["model"],
        "guiderModel": node9["model"],
        "compiledPrompt": compiled,
        "authoredPrompt": authored,
    }
    checks = {
        "picture1_addex": slots[0].assetId == ADDEX and slots[0].pictureIndex == 1,
        "picture2_korri": slots[1].assetId == KORRI and slots[1].pictureIndex == 2,
        "ref0_addex": preflight["ref_image_0"] == f"studio/{ADDEX}.jpeg",
        "ref1_korri": preflight["ref_image_1"] == f"studio/{KORRI}.jpeg",
        "ref_image_size_max": node5["ref_image_size"] == "max",
        "easyCache_absent": "90" not in graph and not any(
            isinstance(node, dict) and node.get("class_type") == "EasyCache" for node in graph.values()
        ),
        "steps_20": node8["steps"] == 20,
        "sampler_res_multistep": graph["7"]["inputs"]["sampler_name"] == "res_multistep",
        "scheduler_simple": node8["scheduler"] == "simple",
        "seed_exact": graph["6"]["inputs"]["noise_seed"] == SEED,
        "length_124": node5["length"] == 124,
        "resolution_1280x704": node5["width"] == 1280 and node5["height"] == 704,
        "raw_unet_to_scheduler": node8["model"] == ["1", 0],
        "raw_unet_to_guider": node9["model"] == ["1", 0],
        "subject_tokens_present": "<Subject 1>" in compiled and "<Subject 2>" in compiled,
        "picture_tokens_present": "<Picture 1>" in compiled and "<Picture 2>" in compiled,
        "no_new_compiler": True,
    }
    preflight["checks"] = checks
    preflight["ok"] = all(checks.values())
    (ROOT / "Scene5_H3_TestB_SubjectBinding.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (ROOT / "Scene5_H3_TestB_preflight.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    print(json.dumps({"ok": preflight["ok"], "checks": checks, "easyCache": preflight["easyCache"]}, indent=2))
    if not preflight["ok"]:
        raise SystemExit("Test B preflight failed — do not queue")


if __name__ == "__main__":
    main()
