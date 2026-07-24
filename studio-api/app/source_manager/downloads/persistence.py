"""Persist download_queue and install_receipts in setup_state."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

from ...setup.state import load_state, update_state
from ..models import strip_secrets
from .models import normalize_operation, utc_now

_LOCK = threading.RLock()
_LAST_PROGRESS_PERSIST: dict[str, float] = {}
PROGRESS_PERSIST_INTERVAL = 0.75


def _queue_root(state: dict[str, Any]) -> dict[str, Any]:
    root = state.setdefault("download_queue", {})
    if not isinstance(root, dict):
        root = {}
        state["download_queue"] = root
    root.setdefault("operations", {})
    root.setdefault("locks", {})
    root.setdefault(
        "settings",
        {"maxActiveLarge": 1, "maxActiveSmall": 2, "largeThresholdBytes": 50 * 1024 * 1024},
    )
    return root


def load_queue() -> dict[str, Any]:
    with _LOCK:
        state = load_state()
        root = _queue_root(state)
        ops = {}
        for key, value in (root.get("operations") or {}).items():
            op = normalize_operation(value if isinstance(value, dict) else None)
            if op:
                ops[key] = op
        return {
            "operations": ops,
            "locks": dict(root.get("locks") or {}),
            "settings": dict(root.get("settings") or {}),
            "updatedAt": root.get("updatedAt"),
        }


def save_operation(op: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    clean = normalize_operation(op)
    if not clean:
        raise ValueError("Invalid download operation")
    op_id = clean["id"]
    now_mono = time.monotonic()
    last = _LAST_PROGRESS_PERSIST.get(op_id)
    if (
        not force
        and clean.get("phase") == "downloading"
        and last is not None
        and (now_mono - last) < PROGRESS_PERSIST_INTERVAL
    ):
        return clean
    _LAST_PROGRESS_PERSIST[op_id] = now_mono
    clean["updatedAt"] = utc_now()

    def mutate(state: dict[str, Any]) -> None:
        root = _queue_root(state)
        ops = root.setdefault("operations", {})
        # Cap history of terminal ops
        ops[op_id] = strip_secrets(clean)
        if len(ops) > 100:
            terminal = [
                (k, v)
                for k, v in ops.items()
                if isinstance(v, dict)
                and v.get("phase") in {"installed", "failed", "cancelled", "rolled_back"}
            ]
            terminal.sort(key=lambda item: str(item[1].get("updatedAt") or ""), reverse=True)
            keep = {k for k, _ in terminal[:40]}
            keep |= {
                k
                for k, v in ops.items()
                if isinstance(v, dict)
                and v.get("phase") not in {"installed", "failed", "cancelled", "rolled_back"}
            }
            for k in list(ops.keys()):
                if k not in keep:
                    ops.pop(k, None)
        root["updatedAt"] = utc_now()

    update_state(mutate)
    return clean


def delete_operation(op_id: str) -> bool:
    existed = {"ok": False}

    def mutate(state: dict[str, Any]) -> None:
        root = _queue_root(state)
        ops = root.setdefault("operations", {})
        if op_id in ops:
            ops.pop(op_id, None)
            existed["ok"] = True
        locks = root.setdefault("locks", {})
        for key, value in list(locks.items()):
            if value == op_id:
                locks.pop(key, None)
        root["updatedAt"] = utc_now()

    update_state(mutate)
    _LAST_PROGRESS_PERSIST.pop(op_id, None)
    return existed["ok"]


def dest_lock_key(destination: str) -> str:
    digest = hashlib.sha256(destination.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"dest:{digest}"


def component_lock_key(component_id: str) -> str:
    return f"component:{component_id}"


def acquire_locks(op_id: str, *, component_id: str, destination: str) -> tuple[bool, str | None]:
    """Persist locks. Returns (ok, conflict_op_id)."""
    ckey = component_lock_key(component_id)
    dkey = dest_lock_key(destination)
    conflict: dict[str, str | None] = {"id": None}

    def mutate(state: dict[str, Any]) -> None:
        root = _queue_root(state)
        locks = root.setdefault("locks", {})
        for key in (ckey, dkey):
            holder = locks.get(key)
            if holder and holder != op_id:
                conflict["id"] = str(holder)
                return
        locks[ckey] = op_id
        locks[dkey] = op_id
        root["updatedAt"] = utc_now()

    update_state(mutate)
    if conflict["id"]:
        return False, conflict["id"]
    return True, None


def release_locks(op_id: str) -> None:
    def mutate(state: dict[str, Any]) -> None:
        root = _queue_root(state)
        locks = root.setdefault("locks", {})
        for key, value in list(locks.items()):
            if value == op_id:
                locks.pop(key, None)
        root["updatedAt"] = utc_now()

    update_state(mutate)


def list_receipts() -> dict[str, dict[str, Any]]:
    state = load_state()
    raw = state.get("install_receipts") or {}
    if not isinstance(raw, dict):
        return {}
    return {k: dict(v) for k, v in raw.items() if isinstance(v, dict)}


def save_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    clean = strip_secrets(dict(receipt))
    rid = str(clean.get("id") or "")
    if not rid:
        raise ValueError("Receipt id required")
    if rid in list_receipts():
        raise ValueError("Receipts are immutable")

    def mutate(state: dict[str, Any]) -> None:
        items = state.setdefault("install_receipts", {})
        if rid in items:
            raise ValueError("Receipts are immutable")
        items[rid] = clean

    update_state(mutate)
    return clean


def get_receipt(install_id: str) -> dict[str, Any] | None:
    return list_receipts().get(install_id)
