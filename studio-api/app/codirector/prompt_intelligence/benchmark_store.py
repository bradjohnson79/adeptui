"""File-backed store for Prompt Intelligence V2 benchmarks."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from .benchmark_models import (
    BlindComparison,
    CategoryEvidence,
    FeedbackItem,
    PromptBenchmarkRun,
    SuiteRun,
)
from .models import utc_now_iso

_LOCK = threading.RLock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def data_root() -> Path:
    env = os.environ.get("PROMPT_INTELLIGENCE_DATA_ROOT")
    if env:
        root = Path(env)
    else:
        root = _repo_root() / "data" / "prompt_intelligence"
    for sub in ("suites", "runs", "reviews", "evidence", "feedback/queue"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def evidence_overlay_root() -> Path:
    root = _repo_root() / "config" / "codirector" / "prompt-profiles" / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_run(run: PromptBenchmarkRun) -> PromptBenchmarkRun:
    with _LOCK:
        run.updatedAt = utc_now_iso()
        if not run.createdAt:
            run.createdAt = run.updatedAt
        path = data_root() / "runs" / f"{run.runId}.json"
        _write_json(path, run.model_dump(mode="json"))
        return run


def load_run(run_id: str) -> Optional[PromptBenchmarkRun]:
    data = _read_json(data_root() / "runs" / f"{run_id}.json")
    return PromptBenchmarkRun.model_validate(data) if data else None


def list_runs(*, suite_run_id: Optional[str] = None, suite_id: Optional[str] = None) -> list[PromptBenchmarkRun]:
    root = data_root() / "runs"
    out: list[PromptBenchmarkRun] = []
    for path in sorted(root.glob("*.json")):
        data = _read_json(path)
        if not data:
            continue
        run = PromptBenchmarkRun.model_validate(data)
        if suite_run_id and run.suiteRunId != suite_run_id:
            continue
        if suite_id and run.suiteId != suite_id:
            continue
        out.append(run)
    return out


def save_suite_run(suite_run: SuiteRun) -> SuiteRun:
    with _LOCK:
        suite_run.updatedAt = utc_now_iso()
        if not suite_run.createdAt:
            suite_run.createdAt = suite_run.updatedAt
        path = data_root() / "suites" / f"{suite_run.suiteRunId}.json"
        _write_json(path, suite_run.model_dump(mode="json"))
        return suite_run


def load_suite_run(suite_run_id: str) -> Optional[SuiteRun]:
    data = _read_json(data_root() / "suites" / f"{suite_run_id}.json")
    return SuiteRun.model_validate(data) if data else None


def list_suite_runs() -> list[SuiteRun]:
    root = data_root() / "suites"
    out: list[SuiteRun] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = _read_json(path)
        if data:
            out.append(SuiteRun.model_validate(data))
    return out


def save_review(comparison: BlindComparison) -> BlindComparison:
    with _LOCK:
        comparison.updatedAt = utc_now_iso()
        if not comparison.createdAt:
            comparison.createdAt = comparison.updatedAt
        path = data_root() / "reviews" / f"{comparison.comparisonId}.json"
        _write_json(path, comparison.model_dump(mode="json"))
        return comparison


def load_review(comparison_id: str) -> Optional[BlindComparison]:
    data = _read_json(data_root() / "reviews" / f"{comparison_id}.json")
    return BlindComparison.model_validate(data) if data else None


def list_reviews() -> list[BlindComparison]:
    root = data_root() / "reviews"
    out: list[BlindComparison] = []
    for path in sorted(root.glob("*.json")):
        data = _read_json(path)
        if data:
            out.append(BlindComparison.model_validate(data))
    return out


def evidence_path(provider_id: str, model_revision: str, domain: str, category: str) -> Path:
    safe = lambda s: "".join(c if c.isalnum() or c in "-_." else "_" for c in s)
    return (
        data_root()
        / "evidence"
        / safe(provider_id)
        / safe(model_revision)
        / safe(domain)
        / f"{safe(category)}.json"
    )


def save_evidence(evidence: CategoryEvidence) -> CategoryEvidence:
    with _LOCK:
        evidence.updatedAt = utc_now_iso()
        path = evidence_path(
            evidence.providerId,
            evidence.modelRevision,
            evidence.domain,
            evidence.category,
        )
        _write_json(path, evidence.model_dump(mode="json"))
        return evidence


def load_evidence(
    provider_id: str,
    model_revision: str,
    domain: str,
    category: str,
) -> Optional[CategoryEvidence]:
    data = _read_json(evidence_path(provider_id, model_revision, domain, category))
    return CategoryEvidence.model_validate(data) if data else None


def list_evidence() -> list[CategoryEvidence]:
    root = data_root() / "evidence"
    out: list[CategoryEvidence] = []
    for path in root.rglob("*.json"):
        data = _read_json(path)
        if data:
            out.append(CategoryEvidence.model_validate(data))
    return out


def overlay_path(profile_id: str, profile_version: str) -> Path:
    safe = lambda s: "".join(c if c.isalnum() or c in "-_@." else "_" for c in s)
    return evidence_overlay_root() / f"{safe(profile_id)}@{safe(profile_version)}.json"


def save_overlay(overlay: dict[str, Any]) -> Path:
    with _LOCK:
        profile_id = str(overlay.get("profileId") or "unknown")
        profile_version = str(overlay.get("profileVersion") or "1")
        path = overlay_path(profile_id, profile_version)
        overlay = {**overlay, "updatedAt": utc_now_iso()}
        _write_json(path, overlay)
        return path


def load_overlay(profile_id: str, profile_version: str) -> Optional[dict[str, Any]]:
    return _read_json(overlay_path(profile_id, profile_version))


def enqueue_feedback(item: FeedbackItem) -> FeedbackItem:
    with _LOCK:
        if not item.createdAt:
            item.createdAt = utc_now_iso()
        path = data_root() / "feedback" / "queue" / f"{item.feedbackId}.json"
        _write_json(path, item.model_dump(mode="json"))
        return item


def list_feedback() -> list[FeedbackItem]:
    root = data_root() / "feedback" / "queue"
    out: list[FeedbackItem] = []
    for path in sorted(root.glob("*.json")):
        data = _read_json(path)
        if data:
            out.append(FeedbackItem.model_validate(data))
    return out
