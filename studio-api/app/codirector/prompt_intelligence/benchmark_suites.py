"""Load benchmark suites and build strategy matrices."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from .benchmark_models import (
    BenchmarkPlan,
    BenchmarkStrategy,
    BenchmarkSuite,
    ControlSettings,
    MatrixCell,
)

FULL_STRATEGIES: list[BenchmarkStrategy] = [
    "creator",
    "refined-english",
    "bilingual-subtle",
    "bilingual-balanced",
    "bilingual-strong",
]

# Rough disk estimates per successful output (MB)
_DISK_ESTIMATE_MB = {
    "image": 4.0,
    "video": 18.0,
    "audio": 2.0,
    "voice": 1.0,
    "music": 2.0,
    "sfx": 1.0,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def suites_config_dir() -> Path:
    return _repo_root() / "config" / "codirector" / "prompt-benchmark-suites"


def load_suite(suite_id: str) -> BenchmarkSuite:
    path = suites_config_dir() / f"{suite_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark suite not found: {suite_id}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return BenchmarkSuite.model_validate(data)


def list_suites() -> list[BenchmarkSuite]:
    root = suites_config_dir()
    if not root.is_dir():
        return []
    out: list[BenchmarkSuite] = []
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        out.append(BenchmarkSuite.model_validate(data))
    return out


def provider_eligible(case_providers: list[str], provider_id: str) -> bool:
    if not case_providers:
        return True
    return provider_id in case_providers


def build_matrix_plan(
    suite: BenchmarkSuite,
    *,
    provider_id: str,
    model_revision: str = "default",
    samples_per_strategy: Optional[int] = None,
    strategies: Optional[list[BenchmarkStrategy]] = None,
) -> BenchmarkPlan:
    samples = max(1, int(samples_per_strategy if samples_per_strategy is not None else suite.samplesPerStrategy))
    strat_list: list[BenchmarkStrategy] = list(strategies or suite.strategies or FULL_STRATEGIES)
    cells: list[MatrixCell] = []
    for case in suite.cases:
        if not provider_eligible(case.providerEligibility, provider_id):
            continue
        for strategy in strat_list:
            for sample_index in range(samples):
                cell_id = f"{suite.suiteId}:{case.benchmarkId}:{strategy}:s{sample_index}:{uuid.uuid4().hex[:8]}"
                cells.append(
                    MatrixCell(
                        cellId=cell_id,
                        suiteId=suite.suiteId,
                        benchmarkId=case.benchmarkId,
                        category=case.category,
                        domain=suite.domain,
                        strategy=strategy,
                        sampleIndex=sample_index,
                        providerId=provider_id,
                        modelRevision=model_revision,
                        creatorPrompt=case.creatorPrompt,
                        negativePrompt=case.negativePrompt,
                        lockedTerms=list(case.lockedTerms),
                        continuityContext=case.continuityContext,
                        controlSettings=case.controlSettings or ControlSettings(),
                        evaluationCriteria=list(case.evaluationCriteria),
                    )
                )
    disk = _DISK_ESTIMATE_MB.get(suite.domain, 5.0) * len(cells)
    return BenchmarkPlan(
        planId=f"plan_{uuid.uuid4().hex[:12]}",
        suiteId=suite.suiteId,
        providerId=provider_id,
        modelRevision=model_revision,
        domain=suite.domain,
        cells=cells,
        estimatedJobs=len(cells),
        estimatedDiskMb=round(disk, 1),
        matrixMode=suite.matrixMode,
    )


def resolve_live_video_provider() -> dict:
    """Probe canonical local video providers in priority order: MiniMax H3 → LTX 2.5."""
    order = [
        "minimax-h3",
        "ltx-2.5-distilled",
    ]
    results: list[dict] = []
    for pid in order:
        health = _probe_video_provider(pid)
        results.append(health)
        if health.get("healthy"):
            return {"selected": pid, "healthy": True, "probes": results}
    return {"selected": None, "healthy": False, "probes": results, "pending": "no healthy video provider"}


def _probe_video_provider(provider_id: str) -> dict:
    if provider_id == "minimax-h3":
        try:
            from ...minimax_h3.route_a_adapter import RouteARuntimeAdapter

            h = RouteARuntimeAdapter().health()
            ok = bool(h.get("ok"))
            return {
                "providerId": provider_id,
                "healthy": ok,
                "status": "ready" if ok else "pending",
                "detail": h,
            }
        except Exception as exc:
            return {"providerId": provider_id, "healthy": False, "status": "pending", "error": str(exc)}
    if provider_id.startswith("ltx-2.5"):
        try:
            from ...setup.diagnostics import verify_component

            required = ["ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"]
            missing = [cid for cid in required if not verify_component(cid).healthy]
            ok = not missing
            return {
                "providerId": provider_id,
                "healthy": ok,
                "status": "ready" if ok else "pending",
                "missingComponents": missing,
            }
        except Exception as exc:
            return {"providerId": provider_id, "healthy": False, "status": "pending", "error": str(exc)}
    return {"providerId": provider_id, "healthy": False, "status": "unknown"}
