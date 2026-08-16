"""Deterministic Scene Creator production readiness (Layer A). Code verifies IDs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from .reference_packet import compile_reference_packet, family_pixel_slots, packet_ticks


def _pass_fail(ok: bool) -> str:
    return "pass" if ok else "fail"


def build_scene_creator_readiness(
    *,
    production_context: dict[str, Any] | None,
    selected_profile: Any = None,
    packet: dict[str, Any] | None = None,
    family: str = "",
    camera_hash: str = "",
    scene_id: str = "",
) -> dict[str, Any]:
    """Compact readiness object. Recomputed; not a source of truth."""
    ctx = production_context if isinstance(production_context, dict) else None
    pkt = packet if isinstance(packet, dict) else {}
    profile_id = ""
    if selected_profile is not None:
        profile_id = str(getattr(selected_profile, "handoffId", "") or "").strip()
    if not profile_id and ctx:
        profile_id = str(ctx.get("handoffId") or "").strip()

    checks = {
        "handoff": "idle",
        "character": "idle",
        "prop": "idle",
        "environment": "idle",
        "spatial": "idle",
        "camera": "idle",
        "provider": "idle",
    }
    issues: list[dict[str, str]] = []

    if not profile_id:
        return {
            "ready": False,
            "status": "idle",
            "sceneId": scene_id,
            "profileId": "",
            "fingerprint": "",
            "checks": checks,
            "issues": [],
            "ticks": packet_ticks(pkt),
            "llm": None,
        }

    loaded = bool(ctx and ctx.get("loaded") is True)
    checks["handoff"] = _pass_fail(loaded and bool(ctx.get("handoffId")))
    if checks["handoff"] != "pass":
        issues.append({"type": "blocking", "code": "handoff", "message": "Co-Director production data is not loaded."})

    chars = list(pkt.get("characters") or [])
    props = list(pkt.get("props") or [])
    env = pkt.get("environment") if isinstance(pkt.get("environment"), dict) else {}
    if chars:
        char_ok = all(str(c.get("assetId") or "").strip() for c in chars)
        checks["character"] = _pass_fail(char_ok)
        if not char_ok:
            issues.append({"type": "blocking", "code": "character", "message": "An approved character picture is missing."})
    if props:
        prop_ok = all(str(p.get("assetId") or "").strip() for p in props)
        checks["prop"] = _pass_fail(prop_ok)
        if not prop_ok:
            issues.append({"type": "blocking", "code": "prop", "message": "An approved prop picture is missing."})
    env_id = str(env.get("assetId") or ctx.get("ersLibraryAssetId") or "").strip() if ctx else str(env.get("assetId") or "").strip()
    map_id = str((ctx or {}).get("spatialMapId") or env.get("spatialMapId") or "").strip()
    checks["environment"] = _pass_fail(bool(env_id))
    if not env_id:
        issues.append({"type": "blocking", "code": "environment", "message": "The environment picture is missing."})
    checks["spatial"] = _pass_fail(bool(map_id) and (bool(pkt.get("spatialConsumed")) or bool((pkt.get("spatial") or {}).get("lines")) or True))
    if map_id:
        checks["spatial"] = "pass"
    else:
        checks["spatial"] = "fail"
        issues.append({"type": "blocking", "code": "spatial", "message": "Spatial Map is not connected."})

    hash_val = str(camera_hash or (pkt.get("cinematography") or {}).get("cameraStateHash") or "").strip()
    checks["camera"] = _pass_fail(bool(hash_val))
    if hash_val:
        checks["camera"] = "pass"
    else:
        checks["camera"] = "idle"

    slots = family_pixel_slots(family)
    visual_assets = [str(r.get("assetId") or "").strip() for r in (pkt.get("roles") or chars + props + ([env] if env else [])) if str(r.get("assetId") or "").strip()]
    if visual_assets and slots <= 0:
        checks["provider"] = "fail"
        issues.append(
            {
                "type": "blocking",
                "code": "provider",
                "message": "This generator cannot use the character and prop pictures already chosen.",
            }
        )
    elif any(str(r.get("consumption") or "") == "semantic_only" for r in (pkt.get("roles") or [])):
        checks["provider"] = "pass"
        issues.append(
            {
                "type": "advisory",
                "code": "provider_slot",
                "message": "This generator can load only one picture. Extra pictures stay as production notes.",
            }
        )
    else:
        checks["provider"] = "pass"

    blocking = any(i.get("type") == "blocking" for i in issues)
    advisory = any(i.get("type") == "advisory" for i in issues) and not blocking
    if blocking or not loaded:
        status = "blocked"
        ready = False
    elif advisory:
        status = "advisory"
        ready = True
    else:
        status = "pass"
        ready = True

    fingerprint_src = {
        "profile": profile_id,
        "revision": (ctx or {}).get("revision"),
        "fp": (ctx or {}).get("fingerprint"),
        "family": family,
        "camera": hash_val,
        "consumed": pkt.get("consumedAssetIds") or [],
        "prompt": (pkt.get("shot") or {}).get("prompt") or "",
    }
    digest = hashlib.sha256(json.dumps(fingerprint_src, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return {
        "ready": ready,
        "status": status,
        "sceneId": scene_id or str((ctx or {}).get("sceneId") or ""),
        "profileId": profile_id,
        "fingerprint": digest,
        "checks": checks,
        "issues": issues,
        "ticks": packet_ticks(pkt),
        "llm": None,
    }


def readiness_from_workspace(
    db: Session,
    project_id: str,
    *,
    production_context: dict[str, Any] | None,
    selected_profile: Any,
    shot: Any = None,
    family: str = "",
    camera_hash: str = "",
    scene_id: str = "",
) -> dict[str, Any]:
    """Build a packet snapshot from the current shot without enqueueing."""
    from ..codirector.entity_resolver import _character_metadata, _prop_metadata

    char_meta: list[dict[str, Any]] = []
    prop_meta: list[dict[str, Any]] = []
    ers = ""
    pkg = ""
    blocking: dict[str, Any] = {}
    cine: dict[str, Any] = {}
    prompt = ""
    if shot is not None:
        prompt = str(getattr(shot, "prompt", "") or getattr(shot, "intent", "") or "")
        try:
            char_meta = _character_metadata(db, project_id, list(getattr(shot, "character_ids", None) or []))
        except Exception:
            char_meta = []
        try:
            prop_meta = _prop_metadata(db, project_id, list(getattr(shot, "prop_entity_ids", None) or []))
        except Exception:
            prop_meta = []
        pkg = str(getattr(shot, "ers_package_id", "") or "")
        cine = {
            "cameraId": str(getattr(getattr(shot, "camera", None), "camera_id", "") or ""),
            "cameraStateHash": camera_hash,
        }
    if isinstance(production_context, dict):
        ers = str(production_context.get("ersLibraryAssetId") or "")
        if not pkg:
            pkg = str(production_context.get("ersPackageId") or "")
    packet = compile_reference_packet(
        char_meta=char_meta,
        prop_meta=prop_meta,
        ers_composite_asset_id=ers,
        ers_package_id=pkg,
        spatial_map_id=str((production_context or {}).get("spatialMapId") or "") if production_context else "",
        structured_blocking=blocking,
        cinematographer=cine,
        aspect_ratio=str((production_context or {}).get("aspectRatio") or "") if production_context else "",
        prompt=prompt,
    )
    fam = family or (str(getattr(getattr(shot, "generator", None), "local_family", "") or "") if shot is not None else "")
    # Hydrate snapshot has no consumption yet — apply family slots without mutating a job.
    slots = family_pixel_slots(fam)
    consumed: list[str] = []
    roles: list[dict[str, Any]] = []
    for char in packet["characters"]:
        asset = str(char.get("assetId") or "").strip()
        if asset and slots > 0 and len(consumed) < slots:
            char["consumption"] = "consumed"
            consumed.append(asset)
        elif asset and slots <= 0:
            char["consumption"] = "unsupported"
        elif asset:
            char["consumption"] = "semantic_only"
        elif char.get("entityId"):
            char["consumption"] = "missing"
        roles.append(char)
    for prop in packet["props"]:
        asset = str(prop.get("assetId") or "").strip()
        if asset and slots > 0 and len(consumed) < slots:
            prop["consumption"] = "consumed"
            consumed.append(asset)
        elif asset and slots <= 0:
            prop["consumption"] = "unsupported"
        elif asset:
            prop["consumption"] = "semantic_only"
        elif prop.get("entityId"):
            prop["consumption"] = "missing"
        roles.append(prop)
    env = packet["environment"]
    easset = str(env.get("assetId") or "").strip()
    if easset and slots > 0 and len(consumed) < slots:
        env["consumption"] = "consumed"
        consumed.append(easset)
    elif easset and slots <= 0:
        env["consumption"] = "unsupported"
    elif easset:
        env["consumption"] = "semantic_only"
    packet["roles"] = roles + [env]
    packet["consumedAssetIds"] = consumed
    packet["spatialConsumed"] = bool(str((production_context or {}).get("spatialMapId") or "").strip())
    packet["cameraConsumed"] = bool(str(camera_hash or "").strip())
    ready = build_scene_creator_readiness(
        production_context=production_context,
        selected_profile=selected_profile,
        packet=packet,
        family=fam,
        camera_hash=camera_hash,
        scene_id=scene_id,
    )
    from .integrity import assess_production_integrity

    return assess_production_integrity(
        ready,
        packet,
        invoke_llm=False,
    )
