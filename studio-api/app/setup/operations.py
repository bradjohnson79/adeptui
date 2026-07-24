from __future__ import annotations

import logging
import re
import threading
import uuid
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .state import load_state, save_state

logger = logging.getLogger(__name__)

FINAL_STATUSES = {"completed", "failed", "cancelled", "interrupted"}
ACTIVE_STATUSES = {"queued", "running", "awaiting_checkpoint", "downloading", "extracting", "verifying", "configuring"}
GLOBAL_ACTIVE_STATUSES = ACTIVE_STATUSES | {"finalizing"}
STALE_RECOVER_STATUSES = {
    "queued",
    "running",
    "downloading",
    "extracting",
    "verifying",
    "configuring",
    "finalizing",
    "awaiting_checkpoint",
}
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+"
)
_PERSIST_KEYS = (
    "operation_id",
    "kind",
    "global_operation",
    "component_ids",
    "status",
    "phase",
    "progress",
    "stage",
    "result",
    "error",
    "checkpoint",
    "created_at",
    "updated_at",
    "recoverable",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationRegistry:
    def __init__(self, maximum: int = 100) -> None:
        self.maximum = maximum
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            state = load_state()
            stored = state.get("operations") or {}
            if not isinstance(stored, dict):
                return
            dirty = False
            for operation_id, payload in stored.items():
                if not isinstance(payload, dict):
                    continue
                status = payload.get("status") or "failed"
                # Ops loaded from disk cannot still be running in this process.
                if status in STALE_RECOVER_STATUSES:
                    status = "interrupted"
                    payload = {
                        **payload,
                        "status": status,
                        "phase": "failed",
                        "stage": "Interrupted — recoverable",
                        "checkpoint": None,
                        "recoverable": True,
                        "error": payload.get("error")
                        or "Interrupted by API restart. Retry when ready.",
                        "updated_at": _now(),
                    }
                    dirty = True
                item = {
                    "operation_id": operation_id,
                    "id": operation_id,
                    "kind": payload.get("kind") or "component_action",
                    "global_operation": bool(payload.get("global_operation")),
                    "component_ids": list(payload.get("component_ids") or []),
                    "status": status,
                    "phase": payload.get("phase") or "configuring",
                    "progress": float(payload.get("progress") or 0.0),
                    "stage": payload.get("stage") or "",
                    "estimated_remaining_seconds": None,
                    "checkpoint": deepcopy(payload.get("checkpoint")),
                    "checkpoints": [],
                    "logs": [],
                    "result": deepcopy(payload.get("result")),
                    "error": payload.get("error"),
                    "created_at": payload.get("created_at") or _now(),
                    "updated_at": payload.get("updated_at") or _now(),
                    "recoverable": bool(payload.get("recoverable")),
                }
                self._items[operation_id] = item
            if dirty:
                for item in self._items.values():
                    self._persist_summary(item)
        except Exception:  # noqa: BLE001 — never block startup on bad state
            logger.exception("Failed to load persisted setup operations")

    def create(
        self,
        kind: str,
        component_ids: list[str],
        *,
        global_operation: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            if global_operation and any(
                item["global_operation"] and item["status"] in GLOBAL_ACTIVE_STATUSES
                for item in self._items.values()
            ):
                raise RuntimeError("A Prepare My Studio operation is already active.")
            operation_id = str(uuid.uuid4())
            now = _now()
            self._items[operation_id] = {
                "operation_id": operation_id,
                "id": operation_id,
                "kind": kind,
                "global_operation": global_operation,
                "component_ids": list(component_ids),
                "status": "queued",
                "phase": "configuring",
                "progress": 0.0,
                "stage": "Queued",
                "estimated_remaining_seconds": None,
                "checkpoint": None,
                "checkpoints": [],
                "logs": [],
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
                "recoverable": False,
            }
            self._trim()
            self._persist_summary(self._items[operation_id])
            return self.snapshot(operation_id)

    def _trim(self) -> None:
        while len(self._items) > self.maximum:
            removable = next(
                (key for key, value in self._items.items() if value["status"] in FINAL_STATUSES),
                None,
            )
            if removable is None:
                break
            self._items.pop(removable, None)

    def snapshot(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            if operation_id not in self._items:
                raise KeyError(f"Unknown setup operation {operation_id}")
            return deepcopy(self._items[operation_id])

    def update(self, operation_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            item.update(changes)
            item["updated_at"] = _now()
            # Map install phases onto status for recovery detection.
            phase = str(item.get("phase") or "")
            if item.get("status") == "running" and phase in (
                "downloading",
                "extracting",
                "verifying",
                "verifying_download",
                "verifying_install",
                "configuring",
            ):
                # Keep status as running; phase carries detail. Persist for restart recovery.
                pass
            self._persist_summary(item)
            return deepcopy(item)

    def log(self, operation_id: str, message: str) -> None:
        safe = _SECRET_PATTERN.sub(r"\1=[redacted]", str(message))[:500]
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            item["logs"].append({"at": _now(), "message": safe})
            del item["logs"][:-100]
            item["updated_at"] = _now()

    def pause(self, operation_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            checkpoint = dict(checkpoint)
            checkpoint.setdefault("checkpoint_id", str(uuid.uuid4()))
            checkpoint.setdefault("status", "pending")
            item["checkpoint"] = checkpoint
            item["checkpoints"].append(deepcopy(checkpoint))
            del item["checkpoints"][:-20]
            item["status"] = "awaiting_checkpoint"
            item["stage"] = checkpoint.get("summary", "User input required")
            item["updated_at"] = _now()
            self._persist_summary(item)
            return deepcopy(item)

    def respond(self, operation_id: str, response: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            checkpoint = item.get("checkpoint")
            if item["status"] != "awaiting_checkpoint" or not checkpoint:
                raise ValueError("This operation is not waiting for a checkpoint.")
            requested_id = response.get("checkpoint_id")
            if requested_id and requested_id != checkpoint["checkpoint_id"]:
                raise ValueError("Checkpoint ID does not match the pending checkpoint.")
            cancelled = bool(response.get("cancelled") or response.get("accepted") is False)
            for historical in reversed(item["checkpoints"]):
                if historical["checkpoint_id"] == checkpoint["checkpoint_id"]:
                    historical["status"] = "cancelled" if cancelled else "answered"
                    break
            item["checkpoint"] = None
            item["status"] = "running"
            item["stage"] = "Cancelling" if cancelled else "Resuming"
            item["updated_at"] = _now()
            self._persist_summary(item)
            return deepcopy(checkpoint)

    def cancel(self, operation_id: str, *, reason: str = "Cancelled by user") -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            item["status"] = "cancelled"
            item["progress"] = item.get("progress") or 0.0
            item["stage"] = "Cancelled"
            item["phase"] = "configuring"
            item["result"] = None
            item["error"] = reason[:500]
            item["checkpoint"] = None
            item["recoverable"] = False
            item["updated_at"] = _now()
            self._persist_summary(item)
            return deepcopy(item)

    def finish(
        self,
        operation_id: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            item["status"] = "failed" if error else "completed"
            item["progress"] = 1.0
            item["stage"] = "Failed" if error else "Complete"
            item["phase"] = "failed" if error else "completed"
            item["result"] = result
            item["error"] = error[:500] if error else None
            item["checkpoint"] = None
            item["recoverable"] = bool(error)
            item["updated_at"] = _now()
            self._persist_summary(item)
            return deepcopy(item)

    def mark_interrupted(
        self,
        operation_id: str,
        *,
        reason: str = "Interrupted by API restart. Retry when ready.",
    ) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            item = self._items[operation_id]
            item["status"] = "interrupted"
            item["phase"] = "failed"
            item["stage"] = "Interrupted — recoverable"
            item["error"] = reason[:500]
            item["checkpoint"] = None
            item["recoverable"] = True
            item["progress"] = float(item.get("progress") or 0.0)
            item["updated_at"] = _now()
            self._persist_summary(item)
            return deepcopy(item)

    def _persist_summary(self, item: dict[str, Any]) -> None:
        try:
            state = load_state()
            state.setdefault("operations", {})[item["operation_id"]] = {
                key: deepcopy(item.get(key)) for key in _PERSIST_KEYS
            }
            save_state(state)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to persist setup operation %s", item.get("operation_id")
            )

    def active_for_component(self, component_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_loaded()
            for item in reversed(self._items.values()):
                if item["status"] in ACTIVE_STATUSES and component_id in item["component_ids"]:
                    return deepcopy(item)
        return None

    def active_global(self) -> dict[str, Any] | None:
        """Return the newest active Prepare My Studio operation, if any."""
        with self._lock:
            self._ensure_loaded()
            for item in reversed(self._items.values()):
                if (
                    item["global_operation"]
                    and item["status"] in GLOBAL_ACTIVE_STATUSES
                ):
                    return deepcopy(item)
        return None

    def recover_stale_operations(self) -> list[dict[str, Any]]:
        """Mark in-flight ops interrupted/recoverable after API restart. Never resumes downloads blindly."""
        recovered: list[dict[str, Any]] = []
        with self._lock:
            self._ensure_loaded()
            for operation_id, item in list(self._items.items()):
                status = item.get("status")
                phase = str(item.get("phase") or "")
                if status not in STALE_RECOVER_STATUSES and phase not in STALE_RECOVER_STATUSES:
                    continue
                # awaiting_checkpoint: clear stuck UI; user can Retry / Link / Choose location again.
                if status == "awaiting_checkpoint":
                    self.mark_interrupted(
                        operation_id,
                        reason=(
                            "Setup was interrupted while waiting for input. "
                            "Use Retry, Choose Install Location, or Link Existing Folder."
                        ),
                    )
                else:
                    self.mark_interrupted(operation_id)
                recovered.append(deepcopy(self._items[operation_id]))
                logger.warning(
                    "Recovered stale setup operation %s (was status=%s phase=%s)",
                    operation_id,
                    status,
                    phase,
                )
        return recovered


registry = OperationRegistry()


def recover_stale_operations() -> list[dict[str, Any]]:
    return registry.recover_stale_operations()
