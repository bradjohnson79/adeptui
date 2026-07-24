"""Environment probes behind the capability service.

Each probe answers one narrow question and is individually failure-tolerant: a probe that
cannot answer records a warning and leaves its slice of the snapshot `None`, so one unhealthy
subsystem degrades a few capabilities to `unknown` instead of failing the whole registry read.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProbeSnapshot:
    """One consistent view of the environment, shared by every capability evaluation."""

    checked_at: str = field(default_factory=_now)
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    warnings: list[str] = field(default_factory=list)

    storage_writable: Optional[bool] = None
    storage_message: str = ""
    database_ok: Optional[bool] = None
    database_message: str = ""

    setup_components: dict[str, dict[str, Any]] = field(default_factory=dict)
    setup_overall: Optional[str] = None

    source_manager_ok: Optional[bool] = None
    active_download_count: int = 0
    provider_available_count: int = 0

    comfy: Optional[dict[str, Any]] = None
    node_types: Optional[set[str]] = None

    codirector: Optional[dict[str, Any]] = None

    workflows: list[dict[str, Any]] = field(default_factory=list)

    project_id: Optional[str] = None
    project_exists: Optional[bool] = None
    project_scene_count: Optional[int] = None
    project_asset_count: Optional[int] = None
    project_reference_count: Optional[int] = None
    project_reference_capabilities: Optional[dict[str, Any]] = None

    def component(self, component_id: str) -> dict[str, Any] | None:
        return self.setup_components.get(component_id)

    def component_ready(self, component_id: str) -> Optional[bool]:
        item = self.setup_components.get(component_id)
        if item is None:
            return None
        return str(item.get("status")) == "ready"

    def model_states(self) -> dict[str, bool]:
        return {
            component_id: str(item.get("status")) == "ready"
            for component_id, item in self.setup_components.items()
        }

    def workflow(self, workflow_id: str) -> dict[str, Any] | None:
        for item in self.workflows:
            if item.get("id") == workflow_id:
                return item
        return None

    def workflows_for_modality(self, modality: str) -> list[dict[str, Any]]:
        return [item for item in self.workflows if item.get("modality") == modality]


def probe_storage(snapshot: ProbeSnapshot) -> None:
    """Confirm the configured data root accepts writes (assets, references, previews)."""
    root: Path = settings.data_dir
    probe_file = root / ".capability_write_probe"
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        snapshot.storage_writable = True
        snapshot.storage_message = "Project data directory is writable."
    except Exception:  # noqa: BLE001
        snapshot.storage_writable = False
        snapshot.storage_message = (
            "The configured project data directory could not be written to. Check permissions "
            "or choose another location."
        )
        snapshot.warnings.append("storage_write_probe_failed")


def probe_database(snapshot: ProbeSnapshot) -> None:
    """Confirm SQLite is reachable and the core tables exist."""
    try:
        from sqlalchemy import inspect

        from ..db import engine

        tables = set(inspect(engine).get_table_names())
        missing = {"projects", "scenes", "assets", "jobs"} - tables
        snapshot.database_ok = not missing
        snapshot.database_message = (
            "Project database is available."
            if not missing
            else "Project database is missing core tables: " + ", ".join(sorted(missing)) + "."
        )
        if missing:
            snapshot.warnings.append("database_missing_tables")
    except Exception:  # noqa: BLE001
        snapshot.database_ok = False
        snapshot.database_message = "Project database could not be opened."
        snapshot.warnings.append("database_probe_failed")


def probe_setup(snapshot: ProbeSnapshot) -> None:
    """Component install/verify state, read without persisting a status write."""
    try:
        from ..setup.status import build_status

        status = build_status(persist=False)
        snapshot.setup_overall = str(status.get("overall_status") or "")
        for item in status.get("components") or []:
            component_id = str(item.get("component_id") or item.get("id") or "")
            if component_id:
                snapshot.setup_components[component_id] = item
    except Exception:  # noqa: BLE001
        snapshot.warnings.append("setup_status_probe_failed")


def probe_source_manager(snapshot: ProbeSnapshot) -> None:
    """Provider availability and active download count from the Source Manager overview."""
    try:
        from ..source_manager.registry import overview_payload

        overview = overview_payload()
        snapshot.source_manager_ok = True
        snapshot.active_download_count = len(overview.get("activeDownloads") or [])
        snapshot.provider_available_count = sum(
            1 for provider in overview.get("providers") or [] if provider.get("available")
        )
    except Exception:  # noqa: BLE001
        snapshot.source_manager_ok = False
        snapshot.warnings.append("source_manager_probe_failed")


async def probe_comfy(snapshot: ProbeSnapshot) -> None:
    """Structured ComfyUI reachability plus the live node catalogue."""
    try:
        from ..comfy_health import comfy_health, node_types

        snapshot.comfy = await comfy_health()
        if snapshot.comfy.get("reachable"):
            snapshot.node_types = await node_types()
        else:
            snapshot.node_types = None
    except Exception:  # noqa: BLE001
        snapshot.comfy = None
        snapshot.node_types = None
        snapshot.warnings.append("comfy_probe_failed")


async def probe_codirector(snapshot: ProbeSnapshot) -> None:
    """Local model provider reachability, reported without endpoints' credentials."""
    try:
        from ..codirector import service as codirector_service

        health = await codirector_service.get_health()
        snapshot.codirector = {
            "providerId": health.provider_id,
            "status": health.status,
            "reachable": bool(health.reachable),
            "selectedModel": health.selected_model,
            "modelAvailable": bool(health.model_available),
            "modelCount": len(health.models or []),
            "message": health.message,
            "code": health.code,
            "recommendedAction": health.recommended_action,
        }
    except Exception:  # noqa: BLE001
        snapshot.codirector = None
        snapshot.warnings.append("codirector_probe_failed")


def probe_workflows(snapshot: ProbeSnapshot) -> None:
    """Workflow readiness, reusing the ComfyUI catalogue and component states already probed."""
    try:
        from ..workflows.readiness import readiness_report

        model_states = snapshot.model_states() if snapshot.setup_components else None
        snapshot.workflows = readiness_report(
            node_types=snapshot.node_types,
            model_states=model_states,
        )
    except Exception:  # noqa: BLE001
        snapshot.workflows = []
        snapshot.warnings.append("workflow_readiness_probe_failed")


def probe_project(snapshot: ProbeSnapshot, project_id: str) -> None:
    """Project-scoped facts: existence, counts, and reference readiness."""
    snapshot.project_id = project_id
    try:
        from ..db import Asset, Project, Scene, SessionLocal

        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            snapshot.project_exists = project is not None
            if project is None:
                return
            snapshot.project_scene_count = (
                db.query(Scene).filter(Scene.project_id == project_id).count()
            )
            snapshot.project_asset_count = (
                db.query(Asset).filter(Asset.project_id == project_id).count()
            )
            vram = getattr(project, "vram_gb", None)
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        snapshot.project_exists = None
        snapshot.warnings.append("project_probe_failed")
        return

    try:
        from ..references import store as reference_store

        snapshot.project_reference_count = len(reference_store.list_ingredients(project_id))
    except Exception:  # noqa: BLE001
        snapshot.warnings.append("reference_store_probe_failed")

    try:
        from ..references.capabilities import reference_capabilities
        from ..setup.state import load_state

        configured = (load_state().get("model_locations") or {}).get("ltx23_ic_lora_ingredients")
        # Reuse the ComfyUI catalogue already fetched instead of issuing another blocking call.
        object_info = {name: {} for name in (snapshot.node_types or set())}
        snapshot.project_reference_capabilities = reference_capabilities(
            configured_model_path=configured,
            object_info=object_info,
            vram_gb=vram,
        )
    except Exception:  # noqa: BLE001
        snapshot.warnings.append("reference_capabilities_probe_failed")


async def build_snapshot(*, project_id: str | None = None) -> ProbeSnapshot:
    """Collect every probe into one snapshot. Blocking probes run in worker threads."""
    snapshot = ProbeSnapshot()

    def _sync_probes() -> None:
        probe_storage(snapshot)
        probe_database(snapshot)
        probe_setup(snapshot)
        probe_source_manager(snapshot)

    await asyncio.gather(
        asyncio.to_thread(_sync_probes),
        probe_comfy(snapshot),
        probe_codirector(snapshot),
    )
    await asyncio.to_thread(probe_workflows, snapshot)
    if project_id:
        await asyncio.to_thread(probe_project, snapshot, project_id)
    snapshot.checked_at = _now()
    return snapshot
