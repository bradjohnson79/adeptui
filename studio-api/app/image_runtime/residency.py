"""VRAM residency for consecutive same-family Co-Director stills.

Does not change generation knobs. Honors unload_after_render and video/WAN handoff.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Optional

from .acceleration_registry import PROTECTED_WORKFLOWS, should_keep_models_resident

logger = logging.getLogger(__name__)

VRAM_PRESSURE_MIB = 2048.0


_last_family: str = ""
_last_workflow: str = ""


def note_still_loaded(family: str, workflow_class: str = "codirector_still") -> None:
    global _last_family, _last_workflow
    _last_family = (family or "").strip().lower()
    _last_workflow = (workflow_class or "").strip().lower()


def last_resident_family() -> str:
    return _last_family


def clear_residency() -> None:
    global _last_family, _last_workflow
    _last_family = ""
    _last_workflow = ""


def vram_pressure(free_mib: float | None, threshold_mib: float = VRAM_PRESSURE_MIB) -> bool:
    if free_mib is None:
        return False
    try:
        return float(free_mib) < float(threshold_mib)
    except (TypeError, ValueError):
        return False


def should_unload_before(
    *,
    next_family: str = "",
    next_workflow: str = "codirector_still",
    unload_after_render: bool = False,
    next_needs_vram: bool = False,
    vram_free_mib: float | None = None,
) -> bool:
    """True when Comfy should free models before the next graph."""

    if unload_after_render or next_needs_vram or vram_pressure(vram_free_mib):
        return True
    nxt = (next_family or "").strip().lower()
    if not _last_family:
        # Nothing resident — do not force a Comfy unload (CC/Prop must not pay
        # per-view eviction when no CD still is loaded).
        return False
    if nxt and nxt != _last_family:
        return True
    nxt_wf = (next_workflow or "").strip().lower()
    # CC/Prop are not keep-resident tuples, but they must not evict a
    # same-family resident. They only evict for incompatibility (above)
    # or VRAM / explicit unload flags (already handled).
    if nxt_wf in PROTECTED_WORKFLOWS:
        return False
    return not should_keep_models_resident(
        family=nxt or _last_family or "*",
        workflow_class=next_workflow or _last_workflow or "codirector_still",
        unload_after_render=unload_after_render,
        next_needs_vram=next_needs_vram,
    )


async def maybe_free_memory(
    comfy: Any,
    *,
    next_family: str = "",
    next_workflow: str = "codirector_still",
    unload_after_render: bool = False,
    next_needs_vram: bool = False,
) -> Optional[dict[str, Any]]:
    free_mib = None
    stats_fn = getattr(comfy, "system_stats", None) or getattr(comfy, "get_system_stats", None)
    if callable(stats_fn):
        try:
            stats = stats_fn()
            if inspect.isawaitable(stats):
                stats = await stats
            devices = (stats or {}).get("devices") or []
            if isinstance(stats, dict) and not devices:
                devices = [stats]
            for device in devices if isinstance(devices, list) else []:
                raw = device.get("vram_free") or device.get("vramFree") or device.get("vram_free_mib")
                if raw is None:
                    continue
                free_mib = float(raw) / (1024 * 1024) if float(raw) > 100_000 else float(raw)
                break
        except Exception:
            logger.exception("Could not read Comfy VRAM for residency")
    if not should_unload_before(
        next_family=next_family,
        next_workflow=next_workflow,
        unload_after_render=unload_after_render,
        next_needs_vram=next_needs_vram,
        vram_free_mib=free_mib,
    ):
        return None
    return await comfy.free_memory(unload_models=True, free_memory=True)
