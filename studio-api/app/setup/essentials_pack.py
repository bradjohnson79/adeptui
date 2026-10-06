"""Adept UI Essentials Pack — reads catalog.py. Not a second component registry."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from .catalog import get_component
from .diagnostics import verify_component
from .license_metadata import inspect_split_license, is_model_access_gated

PackLevel = Literal["essential", "recommended", "optional", "excluded"]
PackChannel = Literal["local_essentials", "cloud", "premium", "optional_local", "developer"]

PACK_ID = "adept_ui_essentials"
PACK_CHANNEL: PackChannel = "local_essentials"

ESSENTIAL_IDS = (
    "videochat3_4b",
    "sam21_hiera_tiny",
    "grounding_dino_tiny",
    "moge2_geometry",
    "vggt_1b_commercial",
)
RECOMMENDED_IDS = (
    "vjepa2_world_intelligence",
    "internvideo3_8b",
    "depth_anything_v2_small",
    "qwen2_5_omni_7b",
)

CAPABILITY_GROUPS = (
    {
        "id": "video_intelligence",
        "label": "Video Intelligence",
        "componentIds": ["videochat3_4b", "internvideo3_8b"],
    },
    {
        "id": "world_intelligence",
        "label": "World Intelligence",
        "componentIds": ["vjepa2_world_intelligence"],
    },
    {
        "id": "intelligent_selection",
        "label": "Intelligent Selection",
        "componentIds": ["sam21_hiera_tiny", "grounding_dino_tiny"],
    },
    {
        "id": "spatial_intelligence",
        "label": "Spatial Intelligence",
        "componentIds": ["moge2_geometry", "vggt_1b_commercial", "depth_anything_v2_small"],
        "note": "VGGT commercial access is gated and independent. It does not block MoGe-2.",
    },
    {
        "id": "timeline_continuity_review",
        "label": "Timeline continuity review",
        "componentIds": ["qwen2_5_omni_7b"],
        "note": "Required for full Timeline continuity review. Generate and Continue do not wait on it.",
    },
)

LEVEL_BY_ID: dict[str, PackLevel] = {
    **{cid: "essential" for cid in ESSENTIAL_IDS},
    **{cid: "recommended" for cid in RECOMMENDED_IDS},
}


def _pack_state(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    verification = verify_component(component_id)
    license = inspect_split_license(component_id)
    installed = bool(verification.healthy)
    if verification.issue_code == "not_installed" or verification.absent:
        state = "not_installed"
    elif verification.issue_code:
        state = "corrupt" if "corrupt" in str(verification.issue_code) else "unavailable"
        if verification.issue_code == "worker_unhealthy":
            state = "installed"
    elif installed:
        state = "installed"
    else:
        state = "not_installed"
    return {
        "id": component_id,
        "displayName": component.name,
        "level": LEVEL_BY_ID.get(component_id, "optional"),
        "revision": _revision_for(component_id),
        "capability": component.category,
        "downloadBytes": component.download_bytes,
        "installedBytes": component.installed_bytes,
        "license": license.get("license") or "",
        "codeLicense": license.get("code_license") or "",
        "weightsLicense": license.get("weights_license") or "",
        "licenseStatus": license.get("license_status") or "",
        "licenseStatusSecondary": license.get("license_status_secondary") or "",
        "ownerPolicy": license.get("owner_policy") or "",
        "productClass": license.get("product_class") or LEVEL_BY_ID.get(component_id, "optional").upper(),
        "accessGated": is_model_access_gated(component_id),
        "state": state,
        "installed": installed,
        "issueCode": verification.issue_code,
        "message": verification.summary,
        "installPath": verification.path or "",
        "required": component.required,
    }


def _revision_for(component_id: str) -> str:
    if component_id in {"videochat3_4b", "internvideo3_8b"}:
        return "A"
    if component_id in {"grounding_dino_tiny", "sam21_hiera_tiny", "depth_anything_v2_small"}:
        return "B"
    if component_id == "vjepa2_world_intelligence":
        return "C"
    if component_id in {"moge2_geometry", "vggt_1b_commercial"}:
        return "E"
    return "D"


def _preferred_root() -> str:
    try:
        from ..model_storage.store import load_model_storage

        storage = load_model_storage()
        root = str((storage or {}).get("preferredRoot") or "").strip()
        if root and Path(root).exists():
            return root
    except Exception:
        pass
    return ""


def _disk_gb(path: str) -> float | None:
    try:
        target = Path(path) if path else Path.cwd()
        if not target.exists():
            target = target.parent if target.parent.exists() else Path.cwd()
        usage = shutil.disk_usage(target)
        return round(usage.free / (1024**3), 2)
    except Exception:
        return None


def pack_status() -> dict[str, Any]:
    rows = [_pack_state(cid) for cid in (*ESSENTIAL_IDS, *RECOMMENDED_IDS)]
    essentials = [row for row in rows if row["level"] == "essential"]
    recommended = [row for row in rows if row["level"] == "recommended"]
    essential_installed = sum(1 for row in essentials if row["installed"])
    missing = [row for row in essentials if not row["installed"]]
    missing_bytes = sum(int(row["downloadBytes"] or 0) for row in missing)
    preferred = _preferred_root()
    groups = []
    by_id = {row["id"]: row for row in rows}
    for group in CAPABILITY_GROUPS:
        members = [by_id[cid] for cid in group["componentIds"] if cid in by_id]
        essential_members = [item for item in members if LEVEL_BY_ID.get(item["id"]) == "essential"]
        installable_essentials = [item for item in essential_members if not item.get("accessGated")]
        if installable_essentials:
            group_installed = all(item["installed"] for item in installable_essentials)
        elif essential_members:
            group_installed = False
        else:
            group_installed = bool(members) and all(item["installed"] for item in members)
        groups.append(
            {
                **group,
                "installed": group_installed,
                "members": [{"id": item["id"], "installed": item["installed"], "level": item["level"]} for item in members],
            }
        )
    return {
        "id": PACK_ID,
        "channel": PACK_CHANNEL,
        "title": "Adept UI Essentials Pack",
        "summary": "Install the Adept UI Essentials Pack to enable Co-Director's video understanding, world intelligence, intelligent selection, tracking, and spatial perception.",
        "essentialInstalled": essential_installed,
        "essentialTotal": len(essentials),
        "recommendedInstalled": sum(1 for row in recommended if row["installed"]),
        "recommendedTotal": len(recommended),
        "missingEssentialCount": len(missing),
        "estimatedAdditionalBytes": missing_bytes,
        "estimatedDiskBytes": sum(int(row["installedBytes"] or 0) for row in rows),
        "preferredRoot": preferred,
        "availableGb": _disk_gb(preferred),
        "requiredGb": round(missing_bytes / (1024**3), 2),
        "groups": groups,
        "components": rows,
        "generationBlockedByPack": False,
    }


def preflight_install(*, include_recommended: bool = False, destination_root: str | None = None) -> dict[str, Any]:
    status = pack_status()
    wanted = [row for row in status["components"] if not row["installed"] and (row["level"] == "essential" or include_recommended)]
    required_bytes = sum(int(row["downloadBytes"] or 0) for row in wanted)
    root = (destination_root or status["preferredRoot"] or "").strip()
    available_gb = _disk_gb(root)
    required_gb = round(required_bytes / (1024**3), 2)
    enough = available_gb is None or available_gb >= required_gb + 1
    return {
        "ok": enough,
        "modelsMissing": len(wanted),
        "requiredBytes": required_bytes,
        "requiredGb": required_gb,
        "availableGb": available_gb,
        "destinationRoot": root,
        "componentIds": [row["id"] for row in wanted],
        "message": (
            None
            if enough
            else "Not enough space on the model drive. Choose another location or free space before installing."
        ),
    }


def health_report() -> dict[str, Any]:
    """Sequential lightweight checks. Do not load every model at once."""
    checks: list[dict[str, Any]] = []
    for component_id in (*ESSENTIAL_IDS, *RECOMMENDED_IDS):
        verification = verify_component(component_id)
        runtime_ok = None
        if component_id in {"videochat3_4b", "internvideo3_8b"} and verification.healthy:
            try:
                from ..codirector.video_intelligence.health import probe_component

                runtime_ok = bool(probe_component(component_id).get("ok"))
            except Exception:
                runtime_ok = False
        elif component_id == "vjepa2_world_intelligence" and verification.healthy:
            try:
                from ..codirector.world_intelligence.health import world_intelligence_status

                runtime_ok = bool(world_intelligence_status(probe=False).get("available"))
            except Exception:
                runtime_ok = False
        elif component_id in {"sam21_hiera_tiny", "grounding_dino_tiny"} and verification.healthy:
            try:
                from ..codirector.perception.worker_client import probe_selection_health

                runtime_ok = bool(probe_selection_health().get("ok"))
            except Exception:
                runtime_ok = False
        elif component_id == "depth_anything_v2_small":
            runtime_ok = verification.healthy
        elif component_id in {"moge2_geometry", "vggt_1b_commercial"}:
            runtime_ok = False
        checks.append(
            {
                "id": component_id,
                "installed": bool(verification.healthy),
                "runtime": runtime_ok,
                "message": verification.summary,
            }
        )
    return {"ok": True, "sequential": True, "checks": checks}
