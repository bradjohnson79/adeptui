"""Copy Test B and swap only LoadImage 15/16 plus the save prefix."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST_B = ROOT / "Scene5_H3_TestB_SubjectBinding.json"
TEST_B_PREFLIGHT = ROOT / "Scene5_H3_TestB_preflight.json"
TEST_B_HASHES = ROOT / "Scene5_H3_TestB_preserve_hashes.json"
DEST = ROOT / "Scene5_H3_TestE_SingleSubject.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    hashes = json.loads(TEST_B_HASHES.read_text(encoding="utf-8"))
    if _sha256(TEST_B) != hashes["test_b_graph"]["sha256"]:
        raise SystemExit("STOP — Test B graph hash changed before Test E copy")
    graph = json.loads(TEST_B.read_text(encoding="utf-8"))
    test_b = json.loads(TEST_B_PREFLIGHT.read_text(encoding="utf-8"))
    test_e = copy.deepcopy(graph)
    test_e["15"]["inputs"]["image"] = "studio/test_e_addex_front.png"
    test_e["16"]["inputs"]["image"] = "studio/test_e_korri_front.png"
    test_e["14"]["inputs"]["filename_prefix"] = "identity_test/h3_single_subject"

    node5 = test_e["5"]["inputs"]
    node8 = test_e["8"]["inputs"]
    node9 = test_e["9"]["inputs"]
    prompt = node5["prompt"]
    preflight = {
        "hypothesis": "H3 failed Test B because Picture 1 / Picture 2 were multi-panel CRS documents",
        "picture_1": {
            "canonicalTag": "@Addex",
            "socket": "ref_image_0",
            "fixture": "studio/test_e_addex_front.png",
        },
        "picture_2": {
            "canonicalTag": "@Korri40YearsOld",
            "socket": "ref_image_1",
            "fixture": "studio/test_e_korri_front.png",
        },
        "subject_1": "@Addex",
        "subject_2": "@Korri40YearsOld",
        "ref_image_0": test_e["15"]["inputs"]["image"],
        "ref_image_1": test_e["16"]["inputs"]["image"],
        "filename_prefix": test_e["14"]["inputs"]["filename_prefix"],
        "ref_image_size": node5["ref_image_size"],
        "easyCache": "90" in test_e,
        "steps": node8["steps"],
        "sampler": test_e["7"]["inputs"]["sampler_name"],
        "scheduler": node8["scheduler"],
        "seed": test_e["6"]["inputs"]["noise_seed"],
        "length": node5["length"],
        "resolution": f"{node5['width']}x{node5['height']}",
        "schedulerModel": node8["model"],
        "guiderModel": node9["model"],
        "prompt": prompt,
        "testBGraphSha256": hashes["test_b_graph"]["sha256"],
        "testBGraphSha256Now": _sha256(TEST_B),
    }
    checks = {
        "picture1_addex_front": preflight["ref_image_0"] == "studio/test_e_addex_front.png",
        "picture2_korri_front": preflight["ref_image_1"] == "studio/test_e_korri_front.png",
        "prompt_unchanged_from_test_b": prompt == test_b["compiledPrompt"],
        "seed_unchanged": preflight["seed"] == test_b["seed"] == 2248151181,
        "canvas_unchanged": preflight["resolution"] == test_b["resolution"] == "1280x704",
        "length_unchanged": preflight["length"] == test_b["length"] == 124,
        "steps_unchanged": preflight["steps"] == test_b["steps"] == 20,
        "sampler_unchanged": preflight["sampler"] == test_b["sampler"] == "res_multistep",
        "scheduler_unchanged": preflight["scheduler"] == test_b["scheduler"] == "simple",
        "ref_image_size_max": preflight["ref_image_size"] == test_b["ref_image_size"] == "max",
        "easyCache_absent": not preflight["easyCache"] and not any(
            isinstance(node, dict) and node.get("class_type") == "EasyCache" for node in test_e.values()
        ),
        "scheduler_model_raw_unet": node8["model"] == ["1", 0],
        "guider_model_raw_unet": node9["model"] == ["1", 0],
        "save_prefix_test_e": preflight["filename_prefix"] == "identity_test/h3_single_subject",
        "test_b_graph_untouched": preflight["testBGraphSha256"] == preflight["testBGraphSha256Now"],
        "only_intended_edits": _only_intended_edits(graph, test_e),
    }
    preflight["checks"] = checks
    preflight["ok"] = all(checks.values())
    DEST.write_text(json.dumps(test_e, indent=2), encoding="utf-8")
    (ROOT / "Scene5_H3_TestE_preflight.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    print(json.dumps({"ok": preflight["ok"], "checks": checks}, indent=2))
    if not preflight["ok"]:
        raise SystemExit("Test E preflight failed — do not queue")


def _only_intended_edits(original: dict, edited: dict) -> bool:
    left = copy.deepcopy(original)
    right = copy.deepcopy(edited)
    left["15"]["inputs"]["image"] = right["15"]["inputs"]["image"]
    left["16"]["inputs"]["image"] = right["16"]["inputs"]["image"]
    left["14"]["inputs"]["filename_prefix"] = right["14"]["inputs"]["filename_prefix"]
    return left == right


if __name__ == "__main__":
    main()
