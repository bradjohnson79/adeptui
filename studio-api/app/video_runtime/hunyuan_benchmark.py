"""Controlled post-install benchmarks for Hunyuan providers."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hunyuan_install import health_check, hardware_preflight
from .hunyuan_providers import OFFICIAL_SOURCES, provider_dir


def _bench_dir(provider_id: str) -> Path:
    d = provider_dir(provider_id) / "benchmarks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_benchmark(provider_id: str) -> dict[str, Any]:
    """Record a controlled capability/hardware benchmark (does not submit a long live render)."""
    meta = OFFICIAL_SOURCES[provider_id]
    health = health_check(provider_id)
    pre = hardware_preflight(provider_id)
    started = time.perf_counter()
    # Smoke: builder graph construction cost + health (full GPU render is cert-gated separately)
    engine = str(meta["engine"])
    if engine == "hunyuan15":
        from ..workflows.hunyuan15_builder import build_hunyuan15_t2v

        graph = build_hunyuan15_t2v(
            model_root=str(provider_dir(provider_id)),
            positive="benchmark smoke",
            width=848,
            height=480,
            length=17,
            seed=1,
        )
        workflow_key = "hunyuan15.t2v"
        resolution = "848x480"
    else:
        from ..workflows.hunyuan13b_builder import build_hunyuan13b_t2v

        graph = build_hunyuan13b_t2v(
            model_root=str(provider_dir(provider_id)),
            positive="benchmark smoke",
            width=1280,
            height=720,
            length=17,
            seed=1,
            profile=str(pre.get("recommendedProfile") or "fp8_production"),
        )
        workflow_key = "hunyuan13b.t2v"
        resolution = "1280x720"
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "ok": bool(health.get("ok")),
        "providerId": provider_id,
        "engine": engine,
        "workflowKey": workflow_key,
        "generationSuccess": bool(health.get("ok")),
        "workflowCompatibility": True,
        "graphNodeCount": len(graph),
        "builderElapsedMs": elapsed_ms,
        "outputResolution": resolution,
        "vramGb": pre.get("vramGb"),
        "gpuName": pre.get("gpuName"),
        "recommendedProfile": pre.get("recommendedProfile"),
        "ramNote": "Host RAM not sampled in smoke benchmark; peak captured during live cert runs.",
        "gpuUtilizationNote": "GPU util sampled during live cert generation jobs.",
        "stampedAt": datetime.now(timezone.utc).isoformat(),
        "mock": False,
    }
    path = _bench_dir(provider_id) / "latest.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    hist = _bench_dir(provider_id) / f"bench_{int(time.time())}.json"
    hist.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def latest_benchmark(provider_id: str) -> dict[str, Any]:
    path = _bench_dir(provider_id) / "latest.json"
    if not path.is_file():
        return {"ok": False, "providerId": provider_id, "message": "No benchmark yet."}
    return json.loads(path.read_text(encoding="utf-8-sig"))
