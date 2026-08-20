"""Certification stub adapter — provider execution boundary replacement.

Registered ONLY when ADEPT_TIMELINE_CERT_STUB=1. Exercises the real request
builder, registry, orchestrator, lineage, APIs, and UI — replacing only the
final provider execution boundary. Never executes GPU/provider code.

Deterministic lifecycle: every submitted job is recorded in a controllable
state store (stub-jobs.json). Tests advance individual jobs through
queued/running/succeeded/failed/cancelled via a test-only control endpoint —
no wall-clock delays or polling timing simulate completion.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    TimelineGenerationResult,
    ValidationResult,
    VideoGeneratorCapabilities,
)

GENERATOR_ID = "cert-stub-local"
ALIASES = frozenset({"cert-stub-local", "cert-stub"})

ENV_FLAG = "ADEPT_TIMELINE_CERT_STUB"

_LOCK = threading.Lock()

# Job lifecycle states the stub can model (test-controlled).
STUB_STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})


def stub_enabled() -> bool:
    return os.environ.get(ENV_FLAG, "").strip().lower() in ("1", "true", "yes")


def _cert_dir() -> Path:
    from ....config import settings

    d = Path(settings.data_dir) / "runtime" / "cert"
    d.mkdir(parents=True, exist_ok=True)
    return d


def request_sink_path() -> Path:
    return _cert_dir() / "timeline-requests.jsonl"


def _state_store_path() -> Path:
    return _cert_dir() / "stub-jobs.json"


def _read_store() -> dict[str, Any]:
    p = _state_store_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_store(store: dict[str, Any]) -> None:
    _state_store_path().write_text(json.dumps(store, indent=2), encoding="utf-8")


def set_stub_job_state(
    job_id: str,
    state: str,
    *,
    output_asset_ids: list[str] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Test-only deterministic state transition. No provider code runs."""
    if state not in STUB_STATES:
        raise ValueError(f"Invalid stub state: {state}")
    with _LOCK:
        store = _read_store()
        entry = store.get(job_id) or {}
        entry["status"] = state
        if output_asset_ids is not None:
            entry["outputAssetIds"] = list(output_asset_ids)
        if error_code is not None:
            entry["errorCode"] = error_code
        if error_message is not None:
            entry["errorMessage"] = error_message
        store[job_id] = entry
        _write_store(store)
    return {"ok": True, "jobId": job_id, "status": state}


def get_stub_job_state(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _read_store().get(job_id)


def read_request_sink() -> list[dict[str, Any]]:
    """Test-only: parse the JSONL request sink."""
    sink = request_sink_path()
    if not sink.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in sink.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def clear_cert_sink() -> None:
    """Test-only: reset the request sink and state store."""
    with _LOCK:
        sink = request_sink_path()
        if sink.exists():
            sink.unlink()
        store = _state_store_path()
        if store.exists():
            store.unlink()


def _capabilities() -> VideoGeneratorCapabilities:
    return VideoGeneratorCapabilities(
        id=GENERATOR_ID,
        label="Cert Stub (wiring certification only)",
        executionType="local",
        supportsTextToVideo=True,
        supportsImageToVideo=True,
        supportsStartFrame=True,
        supportsEndFrame=True,
        supportsMultipleImageReferences=True,
        supportsVideoReferences=False,
        supportsAudioReferences=False,
        maximumReferenceImages=8,
        maximumReferenceVideos=0,
        maximumReferenceAudio=0,
        supportedDurations=[2.0, 5.0, 8.0, 10.0],
        supportedResolutions=["1280x720", "768x512", "480x256"],
        supportedAspectRatios=["16:9", "9:16"],
        supportsSeed=True,
        supportsNegativePrompt=True,
        supportsCameraControls=True,
        executable=True,
        notes=(
            "Certification stub — replaces the provider execution boundary. "
            "Records the real TimelineGenerationRequest and never executes GPU code."
        ),
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        finalRequiresNewGeneration=True,
        draftResolution="768x432",
        finalResolution="1280x720",
        supportsImageAndVideoTogether=False,
    )


class StubCertAdapter:
    id = GENERATOR_ID
    capabilities = _capabilities()

    def validate(self, request: TimelineGenerationRequest) -> ValidationResult:
        return ValidationResult(ok=True)

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        from ..contracts import _nid, _now

        job_id = _nid("stubjob_")
        record = {
            "kind": "timelineGenerationRequest",
            "recordedAt": _now(),
            "jobId": job_id,
            "request": request.model_dump(),
        }
        with _LOCK:
            with request_sink_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
            store = _read_store()
            store[job_id] = {"status": "queued", "outputAssetIds": []}
            _write_store(store)
        return NormalizedJobSubmission(
            internalJobId=job_id,
            providerJobId=job_id,
            queueJobId=job_id,
            generatorId=GENERATOR_ID,
            status="queued",
            apiUsed=False,
            providerMetadata={
                "stub": True,
                "projectId": request.projectId,
                "batchBlockId": request.batchBlockId,
                "executionSnapshotId": request.executionSnapshotId,
                "temporalContinuityPacketId": request.temporalContinuityPacketId,
                "temporalContinuationApplied": bool(
                    (request.providerOptions or {}).get("temporalContinuation", {}).get("applied")
                ),
            },
        )

    def get_status(self, job: NormalizedJobSubmission) -> NormalizedJobStatus:
        job_id = job.queueJobId or job.internalJobId
        entry = get_stub_job_state(job_id) or {"status": "queued"}
        raw = entry.get("status", "queued")
        # Map stub terminal states to watcher lifecycle states.
        mapped = {"succeeded": "completed"}.get(raw, raw)
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            queueJobId=job_id,
            generatorId=GENERATOR_ID,
            status=mapped,  # type: ignore[arg-type]
            progress=1.0 if mapped == "completed" else 0.0,
            errorCode=entry.get("errorCode") if mapped == "failed" else None,
            errorMessage=entry.get("errorMessage") if mapped == "failed" else None,
            apiUsed=False,
            providerMetadata={**(job.providerMetadata or {}), "stub": True},
        )

    def collect_result(self, job: NormalizedJobSubmission) -> TimelineGenerationResult:
        job_id = job.queueJobId or job.internalJobId
        entry = get_stub_job_state(job_id) or {}
        return TimelineGenerationResult(
            internalJobId=job.internalJobId,
            providerJobId=job.providerJobId,
            queueJobId=job_id,
            generatorId=GENERATOR_ID,
            status="completed",
            progress=1.0,
            outputAssetIds=list(entry.get("outputAssetIds") or []),
            apiUsed=False,
            providerMetadata={**(job.providerMetadata or {}), "stub": True},
        )

    def cancel(self, job: NormalizedJobSubmission) -> None:
        job_id = job.queueJobId or job.internalJobId
        try:
            set_stub_job_state(job_id, "cancelled")
        except Exception:
            pass
