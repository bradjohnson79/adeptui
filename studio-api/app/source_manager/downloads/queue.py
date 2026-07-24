"""Persistent DownloadQueueManager."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from ...config import settings
from ...setup.pack_install import staging_root
from .disk import preflight_disk
from .executors import get_executor
from .executors.base import DownloadExecutionContext
from .models import (
    create_operation,
    empty_capabilities,
    make_failure,
    normalize_operation,
    public_operation,
    utc_now,
)
from .persistence import (
    acquire_locks,
    delete_operation,
    load_queue,
    release_locks,
    save_operation,
)
from .phases import InvalidPhaseTransition, is_terminal, transition
from .progress import ProgressTracker
from .receipts import build_link_record, build_managed_receipt, persist_receipt

logger = logging.getLogger(__name__)


class DownloadQueueManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workers: dict[str, threading.Thread] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._pause: dict[str, threading.Event] = {}
        self._trackers: dict[str, ProgressTracker] = {}
        self._ops: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        data = load_queue()
        self._ops = dict(data.get("operations") or {})
        self._loaded = True

    def _settings(self) -> dict[str, Any]:
        data = load_queue()
        return data.get("settings") or {
            "maxActiveLarge": 1,
            "maxActiveSmall": 2,
            "largeThresholdBytes": 50 * 1024 * 1024,
        }

    def _persist(self, op: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
        clean = save_operation(op, force=force)
        self._ops[clean["id"]] = clean
        return clean

    def _set_phase(self, op: dict[str, Any], phase: str) -> dict[str, Any]:
        current = op.get("phase") or "queued"
        op["phase"] = transition(current, phase)
        op["updatedAt"] = utc_now()
        if phase not in {"queued"} and not op.get("startedAt"):
            op["startedAt"] = utc_now()
        if is_terminal(phase):
            op["completedAt"] = utc_now()
            op["terminal"] = True
        return self._persist(op, force=True)

    def _recompute_positions(self) -> None:
        queued = [
            op
            for op in self._ops.values()
            if op.get("phase") == "queued"
        ]
        queued.sort(key=lambda o: (-int(o.get("priority") or 100), str(o.get("createdAt") or "")))
        for index, op in enumerate(queued, start=1):
            if op.get("queuePosition") != index:
                op["queuePosition"] = index
                self._persist(op, force=True)

    def enqueue(self, plan: dict[str, Any], *, priority: int = 100) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            component_id = str(plan.get("componentId") or "")
            # Prevent duplicate active ops for same component
            for existing in self._ops.values():
                if existing.get("componentId") == component_id and not is_terminal(
                    str(existing.get("phase"))
                ):
                    return public_operation(existing)
            executor = get_executor(str(plan.get("providerId") or "direct_http"))
            caps = executor.get_capabilities(plan).to_dict()
            op = create_operation(plan, priority=priority, capabilities=caps or empty_capabilities())
            dest = str(plan.get("destinationRoot") or "")
            stage = staging_root(component_id, op["id"], destination=dest or None)
            op["paths"]["stagingDirectory"] = str(stage)
            self._ops[op["id"]] = op
            self._persist(op, force=True)
            self._recompute_positions()
            self._pump()
            return public_operation(self._ops[op["id"]])

    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_loaded()
            items = list(self._ops.values())
            if filters:
                phase = filters.get("phase")
                component_id = filters.get("componentId")
                active_only = filters.get("active")
                if phase:
                    items = [o for o in items if o.get("phase") == phase]
                if component_id:
                    items = [o for o in items if o.get("componentId") == component_id]
                if active_only:
                    items = [o for o in items if not is_terminal(str(o.get("phase")))]
            items.sort(
                key=lambda o: (
                    0 if not is_terminal(str(o.get("phase"))) else 1,
                    -int(o.get("priority") or 100),
                    str(o.get("createdAt") or ""),
                )
            )
            self._recompute_positions()
            return [public_operation(o) for o in items]

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            return public_operation(op) if op else None

    def active_for_component(self, component_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_loaded()
            for op in self._ops.values():
                if op.get("componentId") == component_id and not is_terminal(str(op.get("phase"))):
                    return public_operation(op)
            return None

    def cancel(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            if is_terminal(str(op.get("phase"))):
                return public_operation(op)
            op["cancelRequested"] = True
            event = self._cancel.setdefault(operation_id, threading.Event())
            event.set()
            try:
                self._set_phase(op, "cancelling")
            except InvalidPhaseTransition:
                op["phase"] = "cancelling"
                self._persist(op, force=True)
            return public_operation(op)

    def pause(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            caps = op.get("capabilities") or {}
            if not caps.get("canPause"):
                raise ValueError("Pause is not supported by this source. You may cancel and retry.")
            if op.get("phase") != "downloading":
                raise ValueError("Only downloading operations can be paused.")
            op["pauseRequested"] = True
            self._pause.setdefault(operation_id, threading.Event()).set()
            tracker = self._trackers.get(operation_id)
            if tracker:
                tracker.pause()
            return public_operation(self._set_phase(op, "pausing"))

    def resume(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            phase = op.get("phase")
            if phase not in {"paused", "interrupted"}:
                raise ValueError("Operation is not paused or interrupted.")
            caps = op.get("capabilities") or {}
            if phase == "paused" and not caps.get("canResume"):
                raise ValueError("Resume is not supported by this source.")
            op["pauseRequested"] = False
            self._pause.setdefault(operation_id, threading.Event()).clear()
            tracker = self._trackers.get(operation_id)
            if tracker:
                tracker.resume()
            if phase == "interrupted":
                self._set_phase(op, "queued")
            else:
                self._set_phase(op, "resuming")
                self._set_phase(op, "downloading")
            self._pump()
            return public_operation(self._ops[operation_id])

    def retry(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            if op.get("phase") not in {"failed", "interrupted", "cancelled"}:
                raise ValueError("Only failed, interrupted, or cancelled operations can be retried.")
            retry = dict(op.get("retry") or {})
            count = int(retry.get("count") or 0) + 1
            if count > int(retry.get("maxAttempts") or 3):
                raise ValueError("Maximum retry attempts exceeded.")
            attempts = list(op.get("attempts") or [])
            attempts.append(
                {
                    "attempt": count,
                    "previousFailure": op.get("failure"),
                    "retriedAt": utc_now(),
                    "providerId": op.get("providerId"),
                    "sourceFingerprint": (op.get("plan") or {}).get("sourceFingerprint"),
                }
            )
            previous_failure = op.get("failure") or {}
            op["attempts"] = attempts
            op["retry"] = {**retry, "count": count, "lastAttemptAt": utc_now()}
            # Clear corrupt staging on checksum failures before clearing failure record
            if previous_failure.get("category") == "checksum_mismatch":
                stage = (op.get("paths") or {}).get("stagingDirectory")
                if stage:
                    shutil.rmtree(stage, ignore_errors=True)
            op["failure"] = None
            op["cancelRequested"] = False
            op["completedAt"] = None
            op["terminal"] = False
            release_locks(operation_id)
            self._set_phase(op, "queued")
            self._recompute_positions()
            self._pump()
            return public_operation(self._ops[operation_id])

    def reprioritize(self, operation_id: str, priority: int) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            if op.get("phase") != "queued":
                raise ValueError("Only queued operations can be reprioritized.")
            op["priority"] = int(priority)
            self._persist(op, force=True)
            self._recompute_positions()
            self._pump()
            return public_operation(self._ops[operation_id])

    def cleanup(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            op = self._ops.get(operation_id)
            if not op:
                raise KeyError(operation_id)
            stage = (op.get("paths") or {}).get("stagingDirectory")
            if stage:
                shutil.rmtree(stage, ignore_errors=True)
            release_locks(operation_id)
            if not is_terminal(str(op.get("phase"))):
                self._set_phase(op, "cancelled")
            return public_operation(op)

    def recover_interrupted(self) -> dict[str, Any]:
        """Classify and convert unsafe active states after restart."""
        with self._lock:
            self._ensure_loaded()
            summary = {"interrupted": [], "resumable": [], "cleanup_required": []}
            auto = os.environ.get("ADEPT_DOWNLOAD_AUTO_RESUME", "").strip() in {"1", "true", "YES"}
            for op_id, op in list(self._ops.items()):
                phase = str(op.get("phase"))
                if is_terminal(phase):
                    continue
                if op_id in self._workers and self._workers[op_id].is_alive():
                    continue
                # No live worker
                caps = op.get("capabilities") or {}
                stage = (op.get("paths") or {}).get("stagingDirectory")
                has_partial = bool(stage and Path(stage).exists())
                classification = "restart_required"
                if caps.get("canResume") and has_partial:
                    classification = "resumable"
                elif phase in {"finalizing", "extracting", "validating"}:
                    classification = "cleanup_required"
                op["recovery"] = {"classification": classification, "at": utc_now()}
                try:
                    self._set_phase(op, "interrupted")
                except InvalidPhaseTransition:
                    op["phase"] = "interrupted"
                    self._persist(op, force=True)
                release_locks(op_id)
                summary["interrupted"].append(op_id)
                if classification == "resumable":
                    summary["resumable"].append(op_id)
                if classification == "cleanup_required":
                    summary["cleanup_required"].append(op_id)
                if auto and classification == "resumable":
                    try:
                        self._set_phase(op, "queued")
                    except InvalidPhaseTransition:
                        pass
            self._recompute_positions()
            self._pump()
            return summary

    def _active_counts(self) -> tuple[int, int]:
        settings = self._settings()
        large_threshold = int(settings.get("largeThresholdBytes") or 50 * 1024 * 1024)
        large = small = 0
        for op in self._ops.values():
            if op.get("phase") not in {
                "preflighting",
                "resolving",
                "verifying_source",
                "downloading",
                "extracting",
                "validating",
                "finalizing",
                "resuming",
            }:
                continue
            total = (op.get("progress") or {}).get("bytesTotal") or 0
            if int(total) >= large_threshold:
                large += 1
            else:
                small += 1
        return large, small

    def _pump(self) -> None:
        settings = self._settings()
        max_large = int(settings.get("maxActiveLarge") or 1)
        max_small = int(settings.get("maxActiveSmall") or 2)
        queued = [
            op
            for op in self._ops.values()
            if op.get("phase") == "queued"
        ]
        queued.sort(key=lambda o: (-int(o.get("priority") or 100), str(o.get("createdAt") or "")))
        for op in queued:
            large, small = self._active_counts()
            total = (op.get("progress") or {}).get("bytesTotal") or 0
            is_large = int(total or 0) >= int(settings.get("largeThresholdBytes") or 50 * 1024 * 1024)
            if is_large and large >= max_large:
                continue
            if not is_large and small >= max_small:
                continue
            if large >= max_large and is_large:
                continue
            # Prefer single large at a time: if any large active, skip other larges
            self._start_worker(op["id"])

    def _start_worker(self, operation_id: str) -> None:
        if operation_id in self._workers and self._workers[operation_id].is_alive():
            return
        cancel = self._cancel.setdefault(operation_id, threading.Event())
        cancel.clear()
        pause = self._pause.setdefault(operation_id, threading.Event())
        pause.clear()

        def run() -> None:
            try:
                self._execute(operation_id)
            except Exception:  # noqa: BLE001
                logger.exception("Download worker crashed op=%s", operation_id)
                with self._lock:
                    op = self._ops.get(operation_id)
                    if op and not is_terminal(str(op.get("phase"))):
                        op["failure"] = make_failure(
                            "process_crashed",
                            "Download worker crashed.",
                            phase=op.get("phase"),
                        )
                        try:
                            self._set_phase(op, "failed")
                        except InvalidPhaseTransition:
                            op["phase"] = "failed"
                            self._persist(op, force=True)
                        release_locks(operation_id)
            finally:
                with self._lock:
                    self._workers.pop(operation_id, None)
                    self._pump()

        thread = threading.Thread(target=run, name=f"download-{operation_id}", daemon=True)
        self._workers[operation_id] = thread
        thread.start()

    def _execute(self, operation_id: str) -> None:
        with self._lock:
            op = self._ops.get(operation_id)
            if not op:
                return
            plan = dict(op.get("plan") or {})
            component_id = str(op.get("componentId"))
            destination = str((op.get("paths") or {}).get("finalDestination") or plan.get("destinationRoot") or "")
            ok_lock, conflict = acquire_locks(operation_id, component_id=component_id, destination=destination)
            if not ok_lock:
                op["failure"] = make_failure(
                    "destination_unwritable",
                    f"Another operation holds the destination lock ({conflict}).",
                    phase="queued",
                    recommended_action="wait",
                )
                # Stay queued — another pump later
                return
            try:
                self._set_phase(op, "preflighting")
            except InvalidPhaseTransition:
                return

        # Disk preflight
        preflight = preflight_disk(
            destination or str(settings.data_dir),
            download_bytes=plan.get("estimatedDownloadBytes"),
            extracted_bytes=plan.get("estimatedExtractedBytes"),
        )
        with self._lock:
            op = self._ops[operation_id]
            op["diskPreflight"] = preflight
            if preflight.get("block"):
                op["failure"] = make_failure(
                    "disk_full",
                    preflight.get("message") or "Insufficient disk space.",
                    phase="preflighting",
                    details=preflight,
                    recommended_action="change_destination",
                )
                self._set_phase(op, "waiting_for_disk_space")
                release_locks(operation_id)
                return
            self._set_phase(op, "resolving")
            self._set_phase(op, "verifying_source")

        if self._cancel.get(operation_id, threading.Event()).is_set():
            self._finish_cancelled(operation_id)
            return

        with self._lock:
            op = self._ops[operation_id]
            self._set_phase(op, "downloading")
            tracker = ProgressTracker()
            if plan.get("estimatedDownloadBytes"):
                tracker.set_total(int(plan["estimatedDownloadBytes"]))
            self._trackers[operation_id] = tracker

        provider_id = str(plan.get("providerId") or op.get("providerId") or "fixture")
        # Prefer fixture when ADEPT_PACK_PROVIDER=fixture_http
        if os.environ.get("ADEPT_PACK_PROVIDER", "").strip().lower() == "fixture_http":
            if str(plan.get("componentId") or "").startswith("pack_"):
                provider_id = "fixture"
        executor = get_executor(provider_id)
        stage = Path(
            str((op.get("paths") or {}).get("stagingDirectory")
                or staging_root(component_id, operation_id, destination=destination))
        )
        stage.mkdir(parents=True, exist_ok=True)

        def on_progress(done: int, total: int | None) -> None:
            with self._lock:
                op_inner = self._ops.get(operation_id)
                if not op_inner:
                    return
                if total is not None:
                    tracker.set_total(total)
                snap = tracker.update(done)
                progress = dict(op_inner.get("progress") or {})
                progress.update(snap)
                op_inner["progress"] = progress
                self._persist(op_inner, force=False)

        context = DownloadExecutionContext(
            operation_id=operation_id,
            staging_dir=str(stage),
            cancel_event=self._cancel.setdefault(operation_id, threading.Event()),
            pause_event=self._pause.setdefault(operation_id, threading.Event()),
            on_progress=on_progress,
            metadata={"resume": bool((op.get("recovery") or {}).get("classification") == "resumable")},
        )

        # Pause polling during download for capable providers
        result = None
        if context.pause_event.is_set():
            with self._lock:
                op = self._ops[operation_id]
                try:
                    self._set_phase(op, "paused")
                except InvalidPhaseTransition:
                    pass
            return

        with self._lock:
            op = self._ops[operation_id]
            try:
                # mark extracting path after download inside executor for fixture
                pass
            except Exception:
                pass

        result = executor.execute(plan, context)

        with self._lock:
            op = self._ops.get(operation_id)
            if not op:
                return
            if result.ok:
                try:
                    if op.get("phase") == "downloading":
                        self._set_phase(op, "extracting")
                        self._set_phase(op, "validating")
                        self._set_phase(op, "finalizing")
                except InvalidPhaseTransition:
                    pass
                # Receipt
                try:
                    if (plan.get("metadata") or {}).get("mode") == "link_existing":
                        receipt = build_link_record(
                            component_id=component_id,
                            linked_path=destination,
                            observed_files=result.files,
                            source_id=op.get("sourceId"),
                        )
                    else:
                        receipt = build_managed_receipt(
                            operation=op,
                            destination_root=destination,
                            files=result.files,
                            version=(plan.get("metadata") or {}).get("version"),
                        )
                    persist_receipt(receipt)
                    op["installId"] = receipt.get("id")
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to persist install receipt")
                # Cleanup staging
                shutil.rmtree(stage, ignore_errors=True)
                try:
                    self._set_phase(op, "installed")
                except InvalidPhaseTransition:
                    op["phase"] = "installed"
                    op["completedAt"] = utc_now()
                    self._persist(op, force=True)
                release_locks(operation_id)
            else:
                category = result.error_category or "unknown"
                if category == "cancelled" or op.get("cancelRequested"):
                    self._finish_cancelled(operation_id)
                    return
                op["failure"] = make_failure(
                    category,
                    result.message or "Download failed.",
                    phase=op.get("phase"),
                    recommended_action="retry",
                )
                try:
                    self._set_phase(op, "failed")
                except InvalidPhaseTransition:
                    op["phase"] = "failed"
                    self._persist(op, force=True)
                release_locks(operation_id)

    def _finish_cancelled(self, operation_id: str) -> None:
        with self._lock:
            op = self._ops.get(operation_id)
            if not op:
                return
            try:
                if op.get("phase") != "cancelling":
                    self._set_phase(op, "cancelling")
            except InvalidPhaseTransition:
                op["phase"] = "cancelling"
            op["failure"] = make_failure(
                "cancelled", "Cancelled by user.", phase=op.get("phase"), recoverable=True
            )
            stage = (op.get("paths") or {}).get("stagingDirectory")
            # Retain partials only when resumable; otherwise clean
            caps = op.get("capabilities") or {}
            if stage and not caps.get("canResume"):
                shutil.rmtree(stage, ignore_errors=True)
            try:
                self._set_phase(op, "cancelled")
            except InvalidPhaseTransition:
                op["phase"] = "cancelled"
                op["completedAt"] = utc_now()
                self._persist(op, force=True)
            release_locks(operation_id)


_MANAGER: DownloadQueueManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_queue_manager() -> DownloadQueueManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = DownloadQueueManager()
        return _MANAGER
