"""One-shot live verification of LTX 2.5 T2V/I2V graphs against Comfy :8188.

Builds the graphs from the canonical builder, fetches /object_info ONCE,
and validates every class_type + required input wiring. Read-only: does not
queue prompts, does not touch Comfy lifecycle.
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, "studio-api")

from app.workflows.ltx_25_builder import build_ltx_25_t2v, build_ltx_25_i2v  # noqa: E402


def fetch_object_info() -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def validate_graph(name: str, wf: dict, obj: dict) -> list[str]:
    problems: list[str] = []
    for nid, node in wf.items():
        ct = node.get("class_type")
        if ct not in obj:
            problems.append(f"{name}:{nid} class_type {ct!r} NOT INSTALLED")
            continue
        spec = obj[ct]
        required = (spec.get("input") or {}).get("required") or {}
        inputs = node.get("inputs") or {}
        for req_key in required:
            if req_key not in inputs:
                problems.append(f"{name}:{nid} ({ct}) missing required input {req_key!r}")
        # validate link targets exist
        for k, v in inputs.items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                if v[0] not in wf:
                    problems.append(f"{name}:{nid}.{k} links to missing node {v[0]!r}")
    return problems


def accelerator_profile(name: str, wf: dict) -> dict:
    types = [n.get("class_type") for n in wf.values()]
    return {
        "graph": name,
        "nodes": len(wf),
        "easy_cache": "EasyCache" in types,
        "stg": "LTXVApplySTG" in types and "STGGuiderNode" in types,
        "tiled_vae_decode": "LTXVTiledVAEDecode" in types,
        "audio_chain": "LTXVSeparateAVLatent" in types and "LTXVAudioVAEDecode" in types,
        "save_video": "SaveVideo" in types or "CreateVideo" in types,
    }


class FakeSettings:
    ltx_2_5_checkpoint = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    ltx_2_5_video_vae = "ltx-2.5-video-vae-bf16.safetensors"
    ltx_2_5_audio_vae = "ltx-2.5-audio-vae-bf16.safetensors"
    ltx_2_5_text_encoder = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"


def main() -> int:
    obj = fetch_object_info()
    print(f"object_info nodes available: {len(obj)}")

    t2v = build_ltx_25_t2v(FakeSettings(), "verify-t2v", "verify", generate_audio=True)
    i2v = build_ltx_25_i2v(FakeSettings(), "verify-i2v", "verify", start_image_path="ref.png", generate_audio=True)

    all_problems = validate_graph("t2v", t2v, obj) + validate_graph("i2v", i2v, obj)
    profiles = [accelerator_profile("t2v", t2v), accelerator_profile("i2v", i2v)]
    for p in profiles:
        print(json.dumps(p, indent=2))

    if all_problems:
        print("PROBLEMS:")
        for p in all_problems:
            print(" -", p)
        return 1
    print("VERIFIED — both graphs structurally valid against live Comfy :8188")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
