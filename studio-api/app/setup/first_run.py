"""First-run completion on the existing setup record.

The baseline is not a second catalog. System essentials are the catalog
``required`` rows. The image and video baselines are the component ids already
owned by ``models.image.ready`` and ``models.video.ready``, checked against the
workflow model map for ``image.txt2img`` and ``ltx_25.t2v``.
"""

from __future__ import annotations

import json
import logging
import shutil
import urllib.request
from typing import Any

from .state import load_state, state_path, update_state

logger = logging.getLogger(__name__)

FIRST_RUN_KEY = "first_run_setup_complete"
MIGRATION_LOG = "first-run state migrated: required components already ready"
INVARIANT_LOG = "first-run invariant: essential blockers remain, completion withheld"
IMAGE_WORKFLOW_ID = "image.txt2img"
VIDEO_WORKFLOW_ID = "ltx_25.t2v"
_READY = "ready"


class FirstRunNotReady(Exception):
    """Essential baseline is not ready, so the flag must stay incomplete."""


def baseline_component_ids() -> tuple[str, ...]:
    """System essentials plus the image and video components the capability registry already requires."""
    from ..capabilities.registry import CAPABILITIES
    from .catalog import public_components

    ordered: list[str] = [item.id for item in public_components() if item.required]
    for capability in CAPABILITIES:
        if capability.id in ("models.image.ready", "models.video.ready"):
            ordered.extend(capability.component_ids)
    seen: list[str] = []
    for component_id in ordered:
        if component_id not in seen:
            seen.append(component_id)
    return tuple(seen)


def _by_id(components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in components:
        if not isinstance(item, dict):
            continue
        key = item.get("id") or item.get("component_id")
        if key:
            found[str(key)] = item
    return found


def _is_ready(row: dict[str, Any] | None) -> bool:
    return isinstance(row, dict) and row.get("status") == _READY


def _node_types() -> set[str] | None:
    """Read ComfyUI's node catalogue. Failure stays unknown; nothing is installed."""
    from ..config import settings

    url = str(getattr(settings, "comfy_url", "") or "").rstrip("/")
    if not url:
        return None
    try:
        with urllib.request.urlopen(f"{url}/object_info", timeout=4) as response:
            payload = json.load(response)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {str(name) for name in payload.keys()}


def assess_first_run(
    components: list[dict[str, Any]],
    *,
    node_types: set[str] | None = None,
    fetch_nodes: bool = False,
) -> dict[str, Any]:
    """Read-only baseline assessment from component rows the setup scanner already produced."""
    from ..workflows.readiness import workflow_readiness

    from .installation_profile import (
        active_profile,
        provider_blockers,
        required_ids_for,
        verified_providers,
    )

    rows = _by_id(components)
    state = load_state()
    profile = active_profile(state)
    baseline_ids = required_ids_for(profile, state) if profile else baseline_component_ids()
    if fetch_nodes and node_types is None and _is_ready(rows.get("comfyui")):
        node_types = _node_types()

    model_states = {component_id: _is_ready(rows.get(component_id)) for component_id in baseline_ids}
    image_required = profile in (None, "local") or (profile == "hybrid" and "zimage_models" in baseline_ids)
    video_required = profile in (None, "local") or (profile == "hybrid" and "ltx_2_5_checkpoint" in baseline_ids)
    image_workflow = (
        workflow_readiness(IMAGE_WORKFLOW_ID, node_types=node_types, model_states=model_states)
        if image_required
        else {"id": IMAGE_WORKFLOW_ID, "status": "not_required"}
    )
    video_workflow = (
        workflow_readiness(VIDEO_WORKFLOW_ID, node_types=node_types, model_states=model_states)
        if video_required
        else {"id": VIDEO_WORKFLOW_ID, "status": "not_required"}
    )

    blockers: list[dict[str, str]] = []
    ready_items: list[dict[str, str]] = []
    for component_id in baseline_ids:
        row = rows.get(component_id)
        name = str((row or {}).get("name") or component_id)
        if _is_ready(row):
            ready_items.append({"id": component_id, "name": name})
        else:
            blockers.append({"id": component_id, "name": name, "status": str((row or {}).get("status") or "missing")})

    for workflow, label, required in (
        (image_workflow, "Baseline image workflow", image_required),
        (video_workflow, "Baseline video workflow", video_required),
    ):
        if required and workflow.get("status") != _READY:
            blockers.append(
                {
                    "id": f"workflow:{workflow.get('id')}",
                    "name": label,
                    "status": str(workflow.get("status") or "unknown"),
                }
            )
    if profile in ("api", "hybrid"):
        blockers.extend(provider_blockers(profile, state))

    optional_absent = 0
    download_bytes = 0
    install_bytes = 0
    for component_id, row in rows.items():
        if component_id in baseline_ids:
            if not _is_ready(row):
                download_bytes += int(row.get("download_bytes") or 0)
                install_bytes += int(row.get("installed_bytes") or row.get("estimated_installed_bytes") or 0)
            continue
        if row.get("required") is True:
            continue
        if not _is_ready(row):
            optional_absent += 1

    free_bytes = None
    try:
        from ..config import settings

        free_bytes = int(shutil.disk_usage(settings.data_dir).free)
    except OSError:
        free_bytes = None

    storage_shortfall = bool(free_bytes is not None and install_bytes > 0 and free_bytes < install_bytes)
    return {
        "baselineIds": list(baseline_ids),
        "alreadyReady": ready_items,
        "essentialNeeded": [item for item in blockers if not str(item["id"]).startswith("workflow:")],
        "essentialBlockers": blockers,
        "essentialBlockerCount": len(blockers),
        "optionalAbsentCount": optional_absent,
        "baselineImageWorkflow": (
            "not_required" if not image_required else "ready" if image_workflow.get("status") == _READY else "blocked"
        ),
        "baselineVideoWorkflow": (
            "not_required" if not video_required else "ready" if video_workflow.get("status") == _READY else "blocked"
        ),
        "installationProfile": profile,
        "connectedProviders": verified_providers(),
        "imageWorkflowStatus": image_workflow.get("status"),
        "videoWorkflowStatus": video_workflow.get("status"),
        "estimatedDownloadBytes": download_bytes,
        "estimatedInstallBytes": install_bytes,
        "freeBytes": free_bytes,
        "storageShortfall": storage_shortfall,
        "nodeCatalogChecked": node_types is not None,
        "ready": len(blockers) == 0,
    }


def required_first_run_ready(components: list[dict[str, Any]], **kwargs: Any) -> bool:
    return bool(assess_first_run(components, **kwargs)["ready"])


def _stored_flag() -> str:
    """Return true, false, missing, or unreadable. Does not write."""
    path = state_path()
    if not path.exists():
        return "missing"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "unreadable"
    if not isinstance(raw, dict) or FIRST_RUN_KEY not in raw:
        return "missing"
    return "true" if raw.get(FIRST_RUN_KEY) is True else "false"


def apply_first_run_flag(report: dict[str, Any]) -> bool:
    """Persist the flag from one assessment. True is allowed only when the blocker count is zero."""
    ready = bool(report.get("ready")) and int(report.get("essentialBlockerCount") or 0) == 0
    stored = _stored_flag()
    if stored == "unreadable":
        return True
    if stored == "true" and ready:
        return True
    if stored == "false" and not ready:
        return False

    migrated = False
    cleared = False

    def mutate(latest: dict[str, Any]) -> None:
        nonlocal migrated, cleared
        current = latest.get(FIRST_RUN_KEY)
        if current is True and ready:
            return
        if current is False and not ready:
            return
        if current is True and not ready:
            latest[FIRST_RUN_KEY] = False
            cleared = True
            return
        if current is True or current is False:
            return
        latest[FIRST_RUN_KEY] = ready
        if ready and not latest.get("installation_profile"):
            latest["installation_profile"] = "local"
        migrated = ready

    update_state(mutate)
    if migrated:
        logger.info(MIGRATION_LOG)
    if cleared:
        logger.info(INVARIANT_LOG)
    final = _stored_flag()
    if final == "unreadable":
        return True
    return final == "true"


def resolve_first_run(components: list[dict[str, Any]], **kwargs: Any) -> bool:
    return apply_first_run_flag(assess_first_run(components, **kwargs))


def complete_first_run(components: list[dict[str, Any]], **kwargs: Any) -> bool:
    """Set the flag only after the essential baseline has zero blockers. A true flag is not rewritten."""
    from .status import invalidate_status_cache

    report = assess_first_run(components, **kwargs)
    stored = _stored_flag()
    if stored == "unreadable":
        return True
    if stored == "true":
        if report["ready"]:
            return True
        apply_first_run_flag(report)
        raise FirstRunNotReady
    if not report["ready"]:
        raise FirstRunNotReady
    def mark_complete(latest: dict[str, Any]) -> None:
        latest[FIRST_RUN_KEY] = True
        if not latest.get("installation_profile"):
            latest["installation_profile"] = "local"

    update_state(mark_complete)
    invalidate_status_cache()
    return True
