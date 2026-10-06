"""Adept Setup planner. Reuses catalog, lifecycle, verifiers, and install jobs.

Simulation walks this same planner. The only substitution is the download
boundary, which the caller injects. This module never marks the live
workstation Ready from a fixture.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from ..source_manager.install_jobs.states import InstallState
from .catalog import get_component, public_components
from .component_contract import contract_for
from .diagnostics import Verification, verify_component
from .lifecycle.service import (
    build_install_plan,
    check_updates,
    create_install_job,
    inspect_hardware,
    recipe_for_component,
)
from .paths import default_models_root
from .status import build_status

_UPDATE_CACHE_HOURS = 6
_ALLOWED_ACTIONS = {"install", "repair", "link_existing", "verify", "update"}
_PRODUCTION_BEFORE_APPROVAL = (
    InstallState.NOT_INSTALLED.value,
    InstallState.SOURCE_REQUIRED.value,
    InstallState.AWAITING_CONFIRMATION.value,
)
_PRODUCTION_AFTER_APPROVAL = (
    InstallState.QUEUED.value,
    InstallState.PREPARING.value,
    InstallState.DOWNLOADING.value,
    InstallState.VERIFYING_DOWNLOAD.value,
    InstallState.INSTALLING.value,
    InstallState.CONFIGURING.value,
    InstallState.VERIFYING_INSTALL.value,
    InstallState.READY.value,
)
_KNOWN_INSTALLERS = {item.installer for item in public_components() if item.installer}
_KNOWN_VERIFIERS = {item.verifier for item in public_components() if item.verifier}
_MODEL_CATEGORIES = {
    "Video Models",
    "Still Image Models",
    "Image Generation",
    "Character Voice Models",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _scan_path() -> Path:
    return Path(settings.data_dir) / "setup" / "machine_scan.json"


def _update_cache_path() -> Path:
    return Path(settings.data_dir) / "setup" / "update_check.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ram_bytes() -> int | None:
    try:
        import psutil  # type: ignore

        return int(psutil.virtual_memory().total)
    except Exception:
        return None


def _gpu_vram_gb(hardware: dict[str, Any]) -> float | None:
    gpu = hardware.get("gpu") if isinstance(hardware.get("gpu"), dict) else {}
    gpus = gpu.get("gpus") if isinstance(gpu, dict) else None
    if not isinstance(gpus, list) or not gpus:
        return None
    first = gpus[0] if isinstance(gpus[0], dict) else {}
    mib = first.get("memory_total_mib")
    if not isinstance(mib, (int, float)) or mib <= 0:
        return None
    return float(mib) / 1024.0


def _services_snapshot() -> dict[str, Any]:
    try:
        from ..runtime_manager.service import _collect

        snap = _collect(assume_local_api=True, include_gpu=False)
        if hasattr(snap, "model_dump"):
            snap = snap.model_dump(mode="json")
        return {"available": True, "status": snap}
    except Exception as exc:
        return {"available": False, "reason": "Service scan unavailable", "detail": str(exc)[:200]}


def resolve_source(component_id: str, *, existing_valid: bool) -> dict[str, Any]:
    """Existing valid local install, then the certified recipe, then the registered owner."""
    component = get_component(component_id)
    contract = contract_for(component_id)
    if existing_valid:
        return {
            "kind": "existing_valid_local",
            "componentId": component_id,
            "priority": "existing_valid_local",
        }
    recipe = recipe_for_component(component_id)
    if recipe and recipe.source:
        return {
            "kind": "certified_recipe",
            "componentId": component_id,
            "recipeId": recipe.recipeId,
            "source": recipe.source,
            "priority": "certified_recipe",
        }
    source = dict(contract.get("source") or {})
    source.setdefault("componentId", component_id)
    source.setdefault("kind", "registered_provider")
    source["priority"] = "registered_provider"
    source["owner"] = source.get("owner") or component.installer
    return source


def classify_component(
    component_id: str,
    verification: Verification | dict[str, Any],
    *,
    update_available: bool = False,
    vram_gb: float | None = None,
) -> dict[str, Any]:
    component = get_component(component_id)
    if isinstance(verification, Verification):
        healthy = bool(verification.healthy)
        absent = bool(verification.absent)
        path = verification.path
    else:
        healthy = bool(verification.get("healthy"))
        absent = bool(verification.get("absent", not healthy and not verification.get("path")))
        path = verification.get("path")
    contract = contract_for(component_id)
    vram_floor = float(contract.get("vramFloorGb") or 0)
    unsupported = vram_gb is not None and vram_floor > 0 and vram_gb + 0.05 < vram_floor and not component.required
    if healthy and update_available:
        classification = "Update Available"
        action = "update"
    elif healthy:
        classification = "Already Installed"
        action = "verify"
    elif component.required:
        classification = "Needs Repair" if (path and not absent) else "Essential"
        action = "repair" if classification == "Needs Repair" else (
            "link_existing" if component.installer in {"detect_only", "manual", "path_link"} else "install"
        )
    elif unsupported:
        classification = "Unsupported"
        action = "verify"
    elif path and not absent and not healthy:
        classification = "Needs Repair"
        action = "repair"
    else:
        classification = "Recommended" if component.category in _MODEL_CATEGORIES else "Optional"
        action = "install" if component.installer not in {"detect_only", "manual"} else "link_existing"
    if action not in _ALLOWED_ACTIONS:
        action = "verify"
    return {
        "componentId": component.id,
        "name": component.name,
        "required": bool(component.required),
        "classification": classification,
        "action": action,
        "healthy": healthy,
        "installer": component.installer,
        "verifier": component.verifier,
        "installedBytes": int(component.installed_bytes or 0),
        "downloadBytes": int(component.download_bytes or 0),
        "contract": contract,
    }


def scan_machine(*, persist: bool = True) -> dict[str, Any]:
    hardware = inspect_hardware()
    status = build_status(persist=False)
    vram_gb = _gpu_vram_gb(hardware)
    rows = []
    by_id = {str(item.get("id")): item for item in status.get("components") or [] if isinstance(item, dict)}
    for component in public_components():
        row = by_id.get(component.id) or {}
        status_name = str(row.get("status") or "")
        healthy = status_name == "ready"
        absent = status_name in {"not_installed", "unknown", "download_unavailable", "source_pending"}
        update = check_updates(component.id)
        rows.append(
            classify_component(
                component.id,
                {"healthy": healthy, "absent": absent, "path": row.get("installation_path")},
                update_available=bool(update.get("updateAvailable")),
                vram_gb=vram_gb,
            )
        )
    payload = {
        "scannedAt": _now(),
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "ramBytes": _ram_bytes(),
        "hardware": hardware,
        "services": _services_snapshot(),
        "readiness": {
            "overall_status": status.get("overall_status"),
            "overall_label": status.get("overall_label"),
            "counts": status.get("counts") or {},
        },
        "components": rows,
    }
    if persist:
        _write_json(_scan_path(), payload)
    return payload


def _selected_rows(
    component_ids: list[str] | None,
    *,
    verifications: dict[str, dict[str, Any]] | None,
    free_bytes: int | None,
    vram_gb: float | None,
) -> list[dict[str, Any]]:
    if verifications is None:
        hardware = inspect_hardware()
        free_bytes = hardware.get("freeBytes") if free_bytes is None else free_bytes
        vram_gb = _gpu_vram_gb(hardware) if vram_gb is None else vram_gb
        wanted = list(component_ids) if component_ids else None
        rows = []
        for component in public_components():
            if wanted is not None and component.id not in wanted:
                continue
            verification = verify_component(component.id)
            update = check_updates(component.id)
            row = classify_component(
                component.id,
                verification,
                update_available=bool(update.get("updateAvailable")),
                vram_gb=vram_gb,
            )
            if wanted is None and row["classification"] not in {"Essential", "Needs Repair", "Recommended"}:
                continue
            if wanted is None and row["healthy"]:
                continue
            rows.append(row)
        return rows
    rows = []
    for component in public_components():
        if component_ids is not None and component.id not in component_ids:
            continue
        fixture = verifications.get(component.id) or {"healthy": False, "absent": True, "path": None}
        row = classify_component(component.id, fixture, update_available=bool(fixture.get("updateAvailable")), vram_gb=vram_gb)
        rows.append(row)
    return rows


def dependency_order(component_ids: list[str]) -> list[str]:
    pending = list(dict.fromkeys(component_ids))
    known = {item.id for item in public_components()}
    resolved: list[str] = []
    guard = 0
    while pending:
        guard += 1
        if guard > len(pending) + len(resolved) + 5:
            raise ValueError(f"orphan or cyclic dependency among {pending}")
        progressed = False
        for component_id in list(pending):
            component = get_component(component_id)
            missing = [dep for dep in component.dependencies if dep not in known]
            if missing:
                raise ValueError(f"{component_id} depends on unknown {missing[0]}")
            if all(dep in resolved or dep not in pending for dep in component.dependencies):
                resolved.append(component_id)
                pending.remove(component_id)
                progressed = True
        if not progressed:
            raise ValueError(f"orphan or cyclic dependency among {pending}")
    return resolved


def build_recommendation_plan(
    component_ids: list[str] | None = None,
    *,
    action: str = "install",
    free_bytes: int | None = None,
    verifications: dict[str, dict[str, Any]] | None = None,
    vram_gb: float | None = None,
    destination_root: str | None = None,
    read_install_plan: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """One review plan. Does not start an install job."""
    if action not in _ALLOWED_ACTIONS:
        action = "install"
    rows = _selected_rows(component_ids, verifications=verifications, free_bytes=free_bytes, vram_gb=vram_gb)
    if free_bytes is None and verifications is None:
        free_bytes = inspect_hardware().get("freeBytes")
    destination = destination_root or str(default_models_root())
    ordered_ids = dependency_order([row["componentId"] for row in rows]) if rows else []
    by_id = {row["componentId"]: row for row in rows}
    items = []
    installed_bytes = 0
    for component_id in ordered_ids:
        row = by_id[component_id]
        if row["healthy"] and action != "update":
            step_action = "verify"
            bytes_needed = 0
        else:
            step_action = row["action"] if action == "install" else action
            bytes_needed = int(row["installedBytes"] or 0)
        installed_bytes += bytes_needed
        source = resolve_source(component_id, existing_valid=bool(row["healthy"]))
        plan_action = step_action if step_action != "verify" else "install"
        if read_install_plan is None:
            install_plan = build_install_plan(component_id, action=plan_action, destination_root=destination).model_dump(mode="json")
        else:
            install_plan = read_install_plan(component_id, action=plan_action, destination_root=destination)
        items.append(
            {
                "componentId": component_id,
                "name": row["name"],
                "classification": row["classification"],
                "action": step_action,
                "installedBytes": bytes_needed,
                "source": source,
                "destination": destination,
                "installer": row["installer"],
                "verifier": row["verifier"],
                "requiresApproval": True,
                "installPlan": install_plan,
            }
        )
    fits = free_bytes is not None and int(free_bytes) >= installed_bytes
    return {
        "action": action,
        "requiresApproval": True,
        "approved": False,
        "jobs": [],
        "destinationRoot": destination,
        "freeBytes": free_bytes,
        "installedBytes": installed_bytes,
        "diskBlocked": not fits,
        "diskMessage": None
        if fits
        else "Not enough free space for this setup."
        if free_bytes is not None
        else "Disk scan unavailable. Install stays blocked until free space is known.",
        "items": items,
        "order": ordered_ids,
    }


def approve_recommendation_plan(
    component_ids: list[str],
    *,
    confirm: bool,
    confirm_download_models: bool = False,
    destination_root: str | None = None,
    action: str = "install",
) -> dict[str, Any]:
    """Existing install jobs start only after confirm. Healthy files are not downloaded again."""
    if not confirm:
        return {
            "approved": False,
            "jobs": [],
            "message": "Approval required before an install job starts.",
        }
    if action not in _ALLOWED_ACTIONS:
        action = "install"
    jobs = []
    destination = destination_root or str(default_models_root())
    for component_id in component_ids:
        verification = verify_component(component_id)
        if verification.healthy and action != "update":
            jobs.append(
                {
                    "componentId": component_id,
                    "skipped": True,
                    "state": "ready",
                    "reason": "Expected file is already verified. Download skipped.",
                }
            )
            continue
        job = create_install_job(
            component_id,
            confirm=True,
            confirm_download_models=confirm_download_models or action == "update",
            destination_root=destination,
        )
        if isinstance(job, dict):
            job = {**job, "requestedAction": action}
        jobs.append(job)
    return {"approved": True, "jobs": jobs, "action": action}


def _update_class(component_id: str, update: dict[str, Any], verification: Verification) -> str:
    component = get_component(component_id)
    if not update.get("updateAvailable"):
        return "Deferred"
    if component.category in _MODEL_CATEGORIES and verification.healthy:
        current = update.get("currentCertifiedVersion")
        latest = update.get("latestCertifiedVersion")
        if current and latest and current == latest:
            return "Deferred"
    if not verification.healthy and component.required:
        return "Blocked"
    if component.required:
        return "Required"
    contract = contract_for(component_id)
    if float(contract.get("vramFloorGb") or 0) > 0:
        return "Recommended"
    return "Optional"


def check_update_plan(*, force: bool = False) -> dict[str, Any]:
    """Metadata only. Optional updates never mark Setup unhealthy. No downloads."""
    cache = _read_json(_update_cache_path())
    cached_at = cache.get("checkedAt")
    if not force and isinstance(cached_at, str):
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(cached_at)
            if age.total_seconds() < _UPDATE_CACHE_HOURS * 3600 and isinstance(cache.get("items"), list):
                return {**cache, "fromCache": True}
        except ValueError:
            pass
    items = []
    try:
        for component in public_components():
            update = check_updates(component.id)
            if not update.get("updateAvailable"):
                continue
            verification = verify_component(component.id)
            classification = _update_class(component.id, update, verification)
            if classification == "Deferred":
                continue
            items.append(
                {
                    "componentId": component.id,
                    "name": component.name,
                    "classification": classification,
                    "channel": "certified",
                    "updateAvailable": bool(update.get("updateAvailable")),
                    "currentCertifiedVersion": update.get("currentCertifiedVersion"),
                    "latestCertifiedVersion": update.get("latestCertifiedVersion"),
                    "reason": update.get("reason"),
                    "rollbackAvailable": False,
                    "action": "update" if update.get("updateAvailable") else "verify",
                }
            )
    except Exception:
        payload = {
            "checkedAt": _now(),
            "fromCache": False,
            "available": False,
            "message": "Update check unavailable",
            "unhealthy": False,
            "rollbackAvailable": False,
            "items": [],
        }
        return payload
    payload = {
        "checkedAt": _now(),
        "fromCache": False,
        "available": True,
        "message": None,
        "unhealthy": False,
        "rollbackAvailable": False,
        "channel": "certified",
        "items": items,
    }
    _write_json(_update_cache_path(), payload)
    return payload


def legal_install_transition(current: str, nxt: str, *, approved: bool) -> bool:
    order = list(_PRODUCTION_BEFORE_APPROVAL)
    if approved:
        order.extend(_PRODUCTION_AFTER_APPROVAL)
    if current not in order or nxt not in order:
        return False
    return order.index(nxt) == order.index(current) + 1


def simulate_clean_machine(
    *,
    free_bytes: int,
    verifier: Callable[[str], dict[str, Any]] | None = None,
    artifact_ready: Callable[[str], None] | None = None,
    extra_ids: tuple[str, ...] = ("minimax_h3_base_optimized",),
) -> dict[str, Any]:
    """Certification harness. Fixture presence never calls the live verifier for Ready."""
    essentials = [component.id for component in public_components() if component.required]
    selected = list(dict.fromkeys([*essentials, *[item for item in extra_ids if item]]))
    verifications = {
        component_id: {"healthy": False, "absent": True, "path": None}
        for component_id in selected
    }
    failures: list[str] = []
    try:
        plan = build_recommendation_plan(
            selected,
            free_bytes=free_bytes,
            verifications=verifications,
            vram_gb=32.0,
        )
    except ValueError as exc:
        return {"ok": False, "failures": [str(exc)], "ready": []}
    if plan["diskBlocked"]:
        failures.append("disk budget cannot cover essential install size")
    if not plan["requiresApproval"] or plan["jobs"]:
        failures.append("plan started a job before approval")
    covered = {item["componentId"] for item in plan["items"]}
    for component_id in essentials:
        if component_id not in covered:
            failures.append(f"{component_id} missing from essential plan")
    destination = str(plan.get("destinationRoot") or "")
    if not destination or not Path(destination).is_absolute():
        failures.append("malformed destination")
    ready: list[str] = []
    transitions: list[dict[str, str]] = []
    for item in plan["items"]:
        component_id = item["componentId"]
        contract = contract_for(component_id)
        if not contract.get("complete"):
            failures.append(f"{component_id} missing required metadata")
        source = item.get("source") or {}
        if not source.get("kind") or not source.get("componentId"):
            failures.append(f"{component_id} unresolved source")
        if item["installer"] not in _KNOWN_INSTALLERS:
            failures.append(f"{component_id} nonexistent installer")
        if item["verifier"] not in _KNOWN_VERIFIERS:
            failures.append(f"{component_id} nonexistent verifier")
        state = InstallState.NOT_INSTALLED.value
        approved = False
        sequence = list(_PRODUCTION_BEFORE_APPROVAL[1:])
        for nxt in sequence:
            if not legal_install_transition(state, nxt, approved=approved):
                failures.append(f"{component_id} illegal transition {state}->{nxt}")
                break
            transitions.append({"componentId": component_id, "from": state, "to": nxt})
            state = nxt
        if state != InstallState.AWAITING_CONFIRMATION.value:
            failures.append(f"{component_id} did not stop for approval")
            continue
        if legal_install_transition(state, InstallState.QUEUED.value, approved=False):
            failures.append(f"{component_id} left approval without confirm")
        approved = True
        for nxt in _PRODUCTION_AFTER_APPROVAL:
            if not legal_install_transition(state, nxt, approved=True):
                failures.append(f"{component_id} illegal transition {state}->{nxt}")
                break
            transitions.append({"componentId": component_id, "from": state, "to": nxt})
            state = nxt
            if nxt == InstallState.DOWNLOADING.value and artifact_ready:
                artifact_ready(component_id)
        if state != InstallState.READY.value:
            continue
        proof = verifier(component_id) if verifier else {"healthy": True, "fixture": True}
        if not proof.get("healthy"):
            failures.append(f"{component_id} verifier fixture did not pass")
            continue
        ready.append(component_id)
    for component_id in essentials:
        if component_id not in ready:
            failures.append(f"{component_id} did not reach Ready")
    return {
        "ok": not failures,
        "failures": failures,
        "ready": ready,
        "plan": plan,
        "transitions": transitions,
        "liveReady": False,
    }
