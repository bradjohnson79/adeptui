"""One-shot live verification of MiniMax H3 Route A T2VA/I2VA graphs against :8192.

Read-only: fetches /object_info once, validates class_types + required inputs.
Does not queue prompts, does not touch runtime lifecycle.
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, "studio-api")

from app.minimax_h3.route_a_adapter import build_t2va_graph, build_i2va_graph  # noqa: E402

BASE = "http://127.0.0.1:8192"


def fetch_object_info() -> dict:
    with urllib.request.urlopen(f"{BASE}/object_info", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def validate_graph(name: str, wf: dict, obj: dict) -> list[str]:
    problems: list[str] = []
    for nid, node in wf.items():
        ct = node.get("class_type")
        if ct not in obj:
            problems.append(f"{name}:{nid} class_type {ct!r} NOT INSTALLED on :8192")
            continue
        spec = obj[ct]
        required = (spec.get("input") or {}).get("required") or {}
        inputs = node.get("inputs") or {}
        for req_key in required:
            if req_key not in inputs:
                problems.append(f"{name}:{nid} ({ct}) missing required input {req_key!r}")
        for k, v in inputs.items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                if v[0] not in wf:
                    problems.append(f"{name}:{nid}.{k} links to missing node {v[0]!r}")
    return problems


def main() -> int:
    try:
        obj = fetch_object_info()
    except Exception as e:
        print(f"BLOCKED — :8192 object_info unreachable: {e}")
        return 2
    print(f":8192 object_info nodes available: {len(obj)}")

    t2va = build_t2va_graph("verify", seed=1, filename_prefix="verify", duration_sec=15.0, width=768, height=512, fps=24.0, steps=20)
    i2va = build_i2va_graph("verify", seed=1, filename_prefix="verify", first_frame_comfy_name="ref.png", duration_sec=15.0, width=768, height=512, fps=24.0, steps=20)

    # Report the duration math for the 15s request
    t2va_len = t2va["5"]["inputs"]["length"]
    print(f"15s @ 24fps -> H3 length frames: {t2va_len} (~{t2va_len / 24.0:.2f}s)")

    all_problems = validate_graph("t2va", t2va, obj) + validate_graph("i2va", i2va, obj)
    if all_problems:
        print("PROBLEMS:")
        for p in all_problems:
            print(" -", p)
        return 1
    print("VERIFIED — MiniMax T2VA + I2VA graphs structurally valid against live :8192")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
