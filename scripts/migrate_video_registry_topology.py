#!/usr/bin/env python3
"""Migrate certified-registry.json: additively compute fingerprints.topologyHash.

The legacy graphHash conflated topology with per-job geometry scalars
(width/height/length/frame_rate/steps), so Timeline batches drifted whenever
their bindings differed from the single certification-time reference build.
The canonical contract splits the two: topologyHash (structure only) is the
drift gate; dynamic bindings are validated separately.

This script builds a reference graph for every registry entry whose builder is
reachable offline (via the production build_leaf_graph dispatch), computes
topology_hash, and writes `fingerprints.topologyHash` into the registry JSON.
Legacy graphHash values are left untouched. Entries that cannot be built
offline (no builder, asset-dependent compilers) are reported and skipped.

Usage (repo root, studio-api venv):
  python scripts/migrate_video_registry_topology.py            # dry-run report
  python scripts/migrate_video_registry_topology.py --write    # apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "studio-api"))

REGISTRY_PATH = REPO_ROOT / "config" / "video-workflows" / "certified-registry.json"

# Reference bindings — values are irrelevant to topology (scalars excluded),
# they only need to be valid for the builders.
REFERENCE = dict(
    positive="reference prompt",
    negative="",
    width=768,
    height=512,
    length=121,
    fps=24,
    seed=1,
    start_image="ref_start.png",
    middle_image="ref_mid.png",
    end_image="ref_end.png",
    audio_file="ref_audio.wav",
    steps=8,
    filename_prefix="studio/ref_topology",
    video_path="ref_video.mp4",
    audio_path="ref_audio.wav",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply changes to the registry JSON")
    args = ap.parse_args()

    from app.config import settings  # noqa: WPS433 — deferred for sys.path setup
    from app.video_runtime.fingerprints import topology_hash, validate_dynamic_bindings
    from app.video_runtime.workflow_execute import build_leaf_graph

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    results: list[dict] = []
    changed = 0

    for entry in data.get("entries", []):
        key = entry.get("workflowKey")
        builder_path = entry.get("builderPath")
        if not builder_path:
            results.append({"workflowKey": key, "result": "SKIP — no builderPath"})
            continue
        contract = SimpleNamespace(leaf_workflow_key=key)
        try:
            graph = build_leaf_graph(contract, settings=settings, **REFERENCE)
        except Exception as exc:  # noqa: BLE001 — report and continue
            results.append({"workflowKey": key, "result": f"SKIP — offline build failed: {type(exc).__name__}: {exc}"})
            continue
        bindings = validate_dynamic_bindings(graph)
        thash = topology_hash(graph)
        fps = entry.setdefault("fingerprints", {})
        previous = fps.get("topologyHash")
        if previous != thash:
            fps["topologyHash"] = thash
            changed += 1
        results.append(
            {
                "workflowKey": key,
                "result": "OK",
                "topologyHash": thash,
                "previous": previous,
                "bindingsOk": bindings["ok"],
                "bindingsErrors": bindings["errors"],
            }
        )

    if args.write and changed:
        REGISTRY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"write": args.write, "changed": changed, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
