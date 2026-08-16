"""Runtime Scene Creator Reference Packet — consumption, not a second database.

Canonical facts are compiled from Character Creator, Prop Creator, ERS, Spatial Map,
and cinematography at generation time. Provider compile records what the Certified
graph will actually load. Unused IDs must not pretend to be consumed.
"""

from __future__ import annotations

from typing import Any

from ..image_core.capability import certified_visual_edit_path, normalize_family

GROUNDING_BLOCKED_QWEN = (
    "This generator cannot use the character and prop pictures already chosen. "
    "Choose Z-Image to keep those pictures."
)
GROUNDING_BLOCKED_PROFILE = (
    "Co-Director production data is not loaded. Select a Spatial Profile and wait "
    "until it finishes loading before generating."
)
GROUNDING_BLOCKED_CHARACTER = "Korri's approved character picture is missing."
GROUNDING_BLOCKED_PROP = "The approved prop picture is missing."
GROUNDING_BLOCKED_ERS = "The environment picture is missing."


class GroundingBlocked(ValueError):
    """Preview/Final must not run as a grounded generation."""


def family_pixel_slots(family: str) -> int:
    """Certified pixel-reference capacity. Draft multi-ref graphs do not count."""
    key = normalize_family(family)
    if key in {"qwen", "qwen2512", "illustrious"}:
        return 0
    if certified_visual_edit_path(key):
        return 1
    return 0


def _aid(value: Any) -> str:
    return str(value or "").strip()


def compile_reference_packet(
    *,
    char_meta: list[dict[str, Any]] | None = None,
    prop_meta: list[dict[str, Any]] | None = None,
    ers_composite_asset_id: str = "",
    ers_package_id: str = "",
    spatial_map_id: str = "",
    structured_blocking: dict[str, Any] | None = None,
    cinematographer: dict[str, Any] | None = None,
    aspect_ratio: str = "",
    prompt: str = "",
    diagnostic_mode: str = "",
) -> dict[str, Any]:
    """Canonical roles. Does not decide consumption — apply_reference_packet does."""
    characters: list[dict[str, Any]] = []
    for char in char_meta or []:
        asset = _aid(char.get("approved_casting_asset_id"))
        cid = _aid(char.get("character_id"))
        if not cid and not asset:
            continue
        characters.append(
            {
                "role": "character_reference",
                "entityId": cid,
                "name": str(char.get("name") or ""),
                "assetId": asset or None,
            }
        )
    props: list[dict[str, Any]] = []
    for prop in prop_meta or []:
        asset = _aid(prop.get("approved_asset_id") or prop.get("library_asset_id"))
        pid = _aid(prop.get("id") or prop.get("prop_id"))
        if not pid and not asset:
            continue
        props.append(
            {
                "role": "prop_reference",
                "entityId": pid,
                "name": str(prop.get("display_label") or prop.get("tag") or ""),
                "assetId": asset or None,
                "relationship": str(prop.get("relationship") or ""),
            }
        )
    ers = _aid(ers_composite_asset_id)
    blocking = structured_blocking if isinstance(structured_blocking, dict) else {}
    cine = cinematographer if isinstance(cinematographer, dict) else {}
    mode = (diagnostic_mode or "").strip().lower()
    if mode == "prompt_only":
        characters, props, ers = [], [], ""
    elif mode == "ers_only":
        characters, props = [], []
    elif mode == "character":
        props, ers = [], ers  # keep ERS as semantic environment id; pixels decided in apply
    return {
        "characters": characters,
        "props": props,
        "environment": {
            "role": "environment_reference",
            "assetId": ers or None,
            "ersPackageId": _aid(ers_package_id) or None,
            "spatialMapId": _aid(spatial_map_id) or None,
        },
        "spatial": {
            "lines": list(blocking.get("lines") or []),
            "placements": blocking.get("placements") or blocking.get("items") or [],
        },
        "cinematography": {
            "cameraId": _aid(cine.get("cameraId") or cine.get("camera_id")),
            "cameraStateHash": _aid(cine.get("cameraStateHash") or cine.get("camera_state_hash")),
            "framing": _aid(cine.get("framing") or cine.get("shotSize") or cine.get("shot_size")),
            "angle": _aid(cine.get("angle")),
            "aspectRatio": _aid(aspect_ratio),
        },
        "shot": {"prompt": str(prompt or "")},
        "diagnosticMode": mode,
    }


def apply_reference_packet(
    body: dict[str, Any],
    *,
    family: str,
    profile_grounded: bool = False,
    production_loaded: bool = False,
    diagnostic_mode: str = "",
) -> dict[str, Any]:
    """Stamp consumption onto the enqueue body. Collapse graph refs to loaded files only."""
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    packet = compile_reference_packet(
        char_meta=list(ctx.get("characters") or []),
        prop_meta=list(ctx.get("prop_entities") or []),
        ers_composite_asset_id=_aid(ctx.get("ers_composite_asset_id")),
        ers_package_id=_aid(ctx.get("ers_package_id") or ctx.get("ersPackageId")),
        spatial_map_id=_aid(body.get("spatialMapId") or ctx.get("spatialMapId")),
        structured_blocking=ctx.get("structured_blocking") if isinstance(ctx.get("structured_blocking"), dict) else {},
        cinematographer=ctx.get("cinematographer") if isinstance(ctx.get("cinematographer"), dict) else {},
        aspect_ratio=_aid(body.get("aspectRatio") or body.get("aspect")),
        prompt=_aid(ctx.get("shot_raw_text") or body.get("prompt")),
        diagnostic_mode=diagnostic_mode or _aid(ctx.get("diagnosticMode")),
    )
    slots = family_pixel_slots(family)
    mode = packet.get("diagnosticMode") or ""
    consumed: list[str] = []
    roles: list[dict[str, Any]] = []

    def _assign(item: dict[str, Any], *, prefer_slot: bool) -> dict[str, Any]:
        asset = _aid(item.get("assetId"))
        row = dict(item)
        if not asset:
            row["consumption"] = "missing"
            return row
        if prefer_slot and slots > 0 and len(consumed) < slots:
            row["consumption"] = "consumed"
            consumed.append(asset)
            return row
        if slots <= 0:
            row["consumption"] = "unsupported"
            return row
        row["consumption"] = "semantic_only"
        return row

    if mode == "ers_only":
        env = _assign(packet["environment"], prefer_slot=True)
        packet["environment"] = env
        roles.append(env)
        for char in packet["characters"]:
            char["consumption"] = "omitted"
        for prop in packet["props"]:
            prop["consumption"] = "omitted"
    else:
        prefer_char = mode != "prompt_only"
        for char in packet["characters"]:
            row = _assign(char, prefer_slot=prefer_char)
            char.clear()
            char.update(row)
            roles.append(char)
        for prop in packet["props"]:
            row = _assign(prop, prefer_slot=False)
            prop.clear()
            prop.update(row)
            roles.append(prop)
        env = _assign(packet["environment"], prefer_slot=mode == "ers_only")
        packet["environment"] = env
        roles.append(env)

    spatial_ok = bool((packet.get("spatial") or {}).get("lines")) or bool(
        (packet.get("spatial") or {}).get("placements")
    )
    camera_hash = _aid((packet.get("cinematography") or {}).get("cameraStateHash"))
    packet["roles"] = roles
    packet["consumedAssetIds"] = list(consumed)
    packet["family"] = normalize_family(family)
    packet["pixelSlots"] = slots
    packet["spatialConsumed"] = bool(spatial_ok)
    packet["cameraConsumed"] = bool(camera_hash)

    issues: list[dict[str, str]] = []
    blocking = False
    if profile_grounded and not production_loaded and mode not in {"prompt_only"}:
        issues.append({"type": "blocking", "code": "profile", "message": GROUNDING_BLOCKED_PROFILE})
        blocking = True
    if profile_grounded and mode not in {"prompt_only", "ers_only"}:
        for char in packet["characters"]:
            if char.get("entityId") and char.get("consumption") == "missing":
                issues.append({"type": "blocking", "code": "character", "message": GROUNDING_BLOCKED_CHARACTER})
                blocking = True
        for prop in packet["props"]:
            if prop.get("entityId") and prop.get("consumption") == "missing":
                issues.append({"type": "blocking", "code": "prop", "message": GROUNDING_BLOCKED_PROP})
                blocking = True
        env_asset = _aid(packet["environment"].get("assetId"))
        if profile_grounded and not env_asset:
            issues.append({"type": "blocking", "code": "environment", "message": GROUNDING_BLOCKED_ERS})
            blocking = True
        visual_needed = any(_aid(r.get("assetId")) for r in roles)
        if visual_needed and slots <= 0:
            issues.append({"type": "blocking", "code": "provider", "message": GROUNDING_BLOCKED_QWEN})
            blocking = True
        for row in roles:
            if row.get("consumption") == "semantic_only":
                name = str(row.get("name") or row.get("role") or "reference")
                issues.append(
                    {
                        "type": "advisory",
                        "code": "provider_slot",
                        "message": f"{name} picture will not be loaded by this generator.",
                    }
                )
            if row.get("consumption") == "unsupported" and _aid(row.get("assetId")):
                issues.append(
                    {
                        "type": "blocking",
                        "code": "provider",
                        "message": GROUNDING_BLOCKED_QWEN,
                    }
                )
                blocking = True

    packet["issues"] = issues
    packet["blocking"] = blocking
    ctx["referencePacket"] = packet
    ctx["reference_image_ids"] = list(consumed)
    ctx["diagnosticMode"] = mode

    for key in ("referenceImage", "reference_image", "sourceAssetId", "source_asset_id"):
        body.pop(key, None)
    if consumed:
        primary = consumed[0]
        body["referenceImage"] = primary
        body["reference_image"] = primary
        body["sourceAssetId"] = primary
        body["source_asset_id"] = primary
        body["referenceIds"] = [primary]
    else:
        body["referenceIds"] = []
        ctx.pop("reference_image_ids", None)
        ctx["reference_image_ids"] = []

    if blocking and mode not in {"prompt_only"}:
        raise GroundingBlocked(issues[0]["message"] if issues else GROUNDING_BLOCKED_QWEN)
    return body


def packet_ticks(packet: dict[str, Any] | None) -> dict[str, str]:
    """Creator-facing ticks: ok only when that role is actually consumed (pixels or structured)."""
    pkt = packet if isinstance(packet, dict) else {}
    chars = list(pkt.get("characters") or [])
    props = list(pkt.get("props") or [])
    env = pkt.get("environment") if isinstance(pkt.get("environment"), dict) else {}

    def _tick(rows: list[dict[str, Any]], empty: str = "idle") -> str:
        if not rows:
            return empty
        states = [str(r.get("consumption") or "") for r in rows]
        if any(s == "consumed" for s in states):
            if any(s in {"missing", "unsupported", "dropped"} for s in states):
                return "warn"
            return "ok"
        if any(s == "semantic_only" for s in states):
            return "warn"
        if any(s in {"missing", "unsupported", "dropped"} for s in states):
            return "fail"
        return empty

    env_state = str(env.get("consumption") or "")
    env_tick = "idle"
    if env.get("assetId") or env_state:
        if env_state == "consumed":
            env_tick = "ok"
        elif env_state == "semantic_only":
            env_tick = "warn"
        elif env_state in {"missing", "unsupported", "dropped"}:
            env_tick = "fail"
    spatial_tick = "ok" if pkt.get("spatialConsumed") else "idle"
    camera_tick = "ok" if pkt.get("cameraConsumed") else "idle"
    return {
        "character": _tick(chars),
        "prop": _tick(props),
        "environment": env_tick,
        "spatial": spatial_tick,
        "camera": camera_tick,
    }
