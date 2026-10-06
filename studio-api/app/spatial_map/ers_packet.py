"""Canonical ERS Environment Packet compiled from Spatial Map authority."""

from __future__ import annotations

from typing import Any

from .background_alignment import hydrate_alignment

CARDINAL_YAW: dict[str, int] = {"north": 0, "east": 90, "south": 180, "west": 270}
ERS_COMPONENTS: tuple[str, ...] = ("master", "north", "east", "south", "west", "three_d", "occupied")
COMPONENT_LABELS: dict[str, str] = {
    "master": "MASTER",
    "north": "NORTH",
    "east": "EAST",
    "south": "SOUTH",
    "west": "WEST",
    "three_d": "3D ENVIRONMENT",
    "occupied": "OCCUPIED SCALE",
    "spatial_map": "SPATIAL MAP",
    "json": "SUMMARY",
}


def packet_needs_occupied(packet: dict[str, Any]) -> bool:
    for item in packet.get("characters") or []:
        if item.get("visible") is False:
            continue
        if str(item.get("characterId") or item.get("character_id") or "").strip():
            return True
    return False


def hydrate_ers_character_canon(db: Any, packet: dict[str, Any], *, project_id: str = "") -> dict[str, Any]:
    """Attach Character Creator canon onto packet placements. Mutates a copy."""
    from ..character_identity.crs_service import resolve_character_for_generation

    pid = str(project_id or packet.get("projectId") or "").strip()
    out = dict(packet)
    rows = []
    for item in list(packet.get("characters") or []):
        row = dict(item)
        cid = str(row.get("characterId") or row.get("character_id") or "").strip()
        if cid and db is not None and pid:
            resolved = resolve_character_for_generation(
                db, pid, character_id=cid, purpose="ers_occupied"
            )
            if resolved:
                row["displayName"] = resolved.get("displayName") or row.get("label")
                row["characterId"] = resolved.get("characterId") or cid
                row["approvedRevision"] = resolved.get("approvedRevision")
                row["referenceAssetId"] = resolved.get("referenceAssetId")
                row["characterSheetAssetId"] = resolved.get("characterSheetAssetId")
                row["identityFacts"] = resolved.get("identityFacts") or []
                row["wardrobe"] = resolved.get("wardrobe") or ""
                row["characterJson"] = resolved.get("characterJson") or {}
                row["identityRequired"] = True
                row["hasApprovedReference"] = bool(resolved.get("hasApprovedReference"))
        rows.append(row)
    out["characters"] = rows
    return out


def compile_ers_packet(document: Any, *, project_id: str = "") -> dict[str, Any]:
    intent = getattr(document, "sceneIntent", None)
    summary = ""
    if intent is not None:
        summary = str(getattr(intent, "summary", "") or "")
    description = str(getattr(document, "sceneDescription", "") or summary or "")
    characters = [
        {
            "id": str(getattr(c, "id", "") or ""),
            "characterId": str(getattr(c, "characterId", "") or getattr(c, "character_id", "") or ""),
            "label": str(getattr(c, "label", "") or getattr(c, "name", "") or "Character"),
            "visible": bool(getattr(c, "visible", True)),
            "x": getattr(c, "normalizedX", None),
            "y": getattr(c, "normalizedY", None),
            "yaw": getattr(c, "yawDegrees", None),
        }
        for c in list(getattr(document, "characters", None) or [])
    ]
    props = [
        {
            "id": str(getattr(p, "id", "") or ""),
            "label": str(getattr(p, "label", "") or getattr(p, "name", "") or "Prop"),
            "x": getattr(p, "normalizedX", None),
            "y": getattr(p, "normalizedY", None),
            "yaw": getattr(p, "yawDegrees", None),
        }
        for p in list(getattr(document, "props", None) or [])
    ]
    cameras = [
        {
            "id": str(getattr(cam, "id", "") or ""),
            "label": str(getattr(cam, "label", "") or "Camera"),
            "x": getattr(cam, "normalizedX", None),
            "y": getattr(cam, "normalizedY", None),
            "yaw": getattr(cam, "yawDegrees", None),
            "pitch": getattr(cam, "pitchDegrees", None),
        }
        for cam in list(getattr(document, "cameras", None) or [])
    ]
    anchors = []
    for a in list(getattr(document, "environmentalAnchors", None) or getattr(document, "anchors", None) or []):
        if isinstance(a, dict):
            anchors.append({"type": a.get("type") or a.get("label"), "label": a.get("label") or a.get("type")})
        else:
            anchors.append({
                "type": str(getattr(a, "type", "") or ""),
                "label": str(getattr(a, "label", "") or getattr(a, "type", "") or ""),
            })
    return {
        "projectId": project_id or str(getattr(document, "projectId", "") or ""),
        "environmentId": str(getattr(document, "id", "") or ""),
        "environmentName": str(getattr(document, "title", "") or "Environment"),
        "spatialMapId": str(getattr(document, "id", "") or ""),
        "spatialMapAssetId": str(getattr(document, "backgroundAssetId", "") or ""),
        "environmentDescription": description,
        "dimensions": {
            "widthMeters": getattr(document, "widthMeters", None),
            "depthMeters": getattr(document, "depthMeters", None),
            "metersPerCell": getattr(document, "metersPerCell", None),
        },
        "scale": "1 square = 1 meter",
        "directionConvention": {
            "system": "atlas-north-up",
            "northYaw": 0,
            "eastYaw": 90,
            "southYaw": 180,
            "westYaw": 270,
            "zeroDegrees": "north_negative_y",
        },
        "anchors": anchors,
        "characters": characters,
        "props": props,
        "cameras": cameras,
        "backgroundAlignment": hydrate_alignment(getattr(document, "backgroundAlignment", None)),
        "threeDKind": "representation",
    }


def compile_component_prompt(packet: dict[str, Any], component: str) -> str:
    desc = str(packet.get("environmentDescription") or "this environment").strip()
    name = str(packet.get("environmentName") or "Environment")
    anchors = ", ".join(
        str(a.get("label") or a.get("type") or "")
        for a in list(packet.get("anchors") or [])
        if a.get("label") or a.get("type")
    ) or "the approved Spatial Map landmarks"
    if component == "master":
        return (
            f"Create the MASTER cinematic environment identity shot of {name}. "
            f"SPATIAL AUTHORITY: {desc}. Preserve materials, lighting, and appearance canon. "
            f"Show one single cinematic photograph of the place from the most useful production master angle. "
            f"Do not redesign the floorplan. Do not return a cardinal direction plate. "
            f"Do not return a multi-panel technical sheet. "
            f"Landmarks: {anchors}."
        )
    if component == "three_d":
        return (
            f"Create a 3D ENVIRONMENT REPRESENTATION of {name} — a clear illustrative "
            f"three-quarter spatial view of the same place. This is a visual representation, "
            f"not a downloadable 3D model. SPATIAL AUTHORITY: {desc}. Do not invent rooms or move doors. "
            f"Landmarks: {anchors}."
        )
    if component == "occupied":
        names = []
        for item in packet.get("characters") or []:
            if item.get("visible") is False:
                continue
            names.append(str(item.get("displayName") or item.get("label") or item.get("characterId") or "").strip())
        names = [n for n in names if n]
        who = ", ".join(names) or "the approved saved character"
        canon_bits = []
        for item in packet.get("characters") or []:
            if item.get("visible") is False:
                continue
            facts = "; ".join(str(f) for f in (item.get("identityFacts") or []) if f)
            wardrobe = str(item.get("wardrobe") or "").strip()
            label = str(item.get("displayName") or item.get("label") or "").strip()
            if label and facts:
                canon_bits.append(f"{label}: {facts}")
            elif wardrobe:
                canon_bits.append(f"{label} wardrobe: {wardrobe}")
        canon_line = " ".join(canon_bits)
        return (
            f"Create ONE occupied-scale production still of {name}. "
            f"The visible character is the approved saved character {who}. "
            f"Use the supplied character reference as the authoritative identity. "
            f"Preserve the same face, hair, skin tone, body proportions, wardrobe, and distinguishing features. "
            f"Do not substitute a generic person, anonymous stand-in, alternate actor, or newly invented character. "
            f"{canon_line} "
            f"SPATIAL AUTHORITY: {desc}. Place the character at the Spatial Map blocking. "
            f"This is environment scale, not a character sheet. Landmarks: {anchors}."
        )
    yaw = CARDINAL_YAW[component]
    label = COMPONENT_LABELS[component]
    return (
        f"Render the {label}-facing canonical view of this exact environment. "
        f"SPATIAL AUTHORITY: Use the approved Spatial Map and ERS Environment Packet. "
        f"CAMERA: Direction {label}. Yaw {yaw} degrees (atlas-north-up, 0 = North / -Y). "
        f"Framing: show the environment clearly from this direction. "
        f"EXPECTED STRUCTURE: {desc}. Landmarks: {anchors}. "
        f"Preserve established materials and lighting. "
        f"DO NOT redesign the floorplan, move rooms or doors, mirror the environment, "
        f"return the Master camera, or invent major architecture."
    )


def placement_fingerprint(packet: dict[str, Any]) -> str:
    import hashlib
    import json

    payload = {
        "characters": packet.get("characters") or [],
        "props": packet.get("props") or [],
        "cameras": packet.get("cameras") or [],
        "backgroundAlignment": hydrate_alignment(packet.get("backgroundAlignment")),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def human_readable_summary(packet: dict[str, Any]) -> list[str]:
    dims = packet.get("dimensions") or {}
    lines = [
        f"Environment: {packet.get('environmentName') or 'Environment'}",
        f"Scale: {packet.get('scale') or '1 square = 1 meter'}",
        f"Dimensions: {dims.get('widthMeters') or '—'} m × {dims.get('depthMeters') or '—'} m",
        f"Direction: North=0° East=90° South=180° West=270°",
    ]
    chars = packet.get("characters") or []
    if chars:
        lines.append("Characters:")
        for c in chars[:8]:
            label = c.get("displayName") or c.get("label") or c.get("characterId") or "Character"
            cid = str(c.get("characterId") or "").strip()
            suffix = f"  id {cid}" if cid else ""
            lines.append(f"  {label}{suffix}  facing {c.get('yaw') if c.get('yaw') is not None else '—'}")
    props = packet.get("props") or []
    if props:
        lines.append("Props:")
        for p in props[:8]:
            lines.append(f"  {p.get('label')}  facing {p.get('yaw') if p.get('yaw') is not None else '—'}")
    cams = packet.get("cameras") or []
    if cams:
        lines.append("Cameras:")
        for cam in cams[:8]:
            lines.append(
                f"  {cam.get('label')}  yaw {cam.get('yaw') if cam.get('yaw') is not None else '—'} "
                f"pitch {cam.get('pitch') if cam.get('pitch') is not None else '—'}"
            )
    return lines
