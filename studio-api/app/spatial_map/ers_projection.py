"""ERS / Scene Creator projection of Spatial Map placements.

Reads Spatial Map attachment fields. Does not invent a second relationship store.
Attached props have no independent grid and no fake x/y.
Independent props keep their grid.

Amendment #3: this is a read-only snapshot transform. It never writes back
to the Spatial Map.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from .attachment import normalize_prop_attachment

_INDEPENDENT_COORD_KEYS = (
    "x",
    "y",
    "z",
    "normalizedX",
    "normalizedY",
)

_RELATIONSHIP_GERUND = {
    "held": "holding",
    "carried": "carrying",
    "worn": "wearing",
    "using": "using",
    "interacting": "interacting with",
    "associated": "associated with",
}

_ATTACHMENT_POINT_PHRASE = {
    "left_hand": " in the left hand",
    "right_hand": " in the right hand",
    "both_hands": " in both hands",
    "head": " on the head",
    "upper_body": " on the upper body",
    "lower_body": " on the lower body",
    "back": " on the back",
    "waist": " at the waist",
    "wrist": " at the wrist",
    "shoulder": " on the shoulder",
    "unspecified": "",
}


def _as_dict(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dump()
    return {
        key: getattr(item, key)
        for key in dir(item)
        if not key.startswith("_") and not callable(getattr(item, key, None))
    }


def grid_cell_label(column: Any, row: Any) -> str:
    """Spreadsheet-style cell label. column 5 + row 5 -> F6."""
    try:
        col = int(column)
        r = int(row)
    except (TypeError, ValueError):
        return ""
    if col < 0 or r < 0:
        return ""
    letters = ""
    n = col
    while True:
        letters = chr(ord("A") + (n % 26)) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return f"{letters}{r + 1}"


def _title_enum(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text.replace("_", " ").title()


def _is_character_placement(data: Mapping[str, Any]) -> bool:
    return bool(data.get("characterId") or data.get("character_id"))


def _is_attached_prop(data: Mapping[str, Any]) -> bool:
    return str(data.get("placementMode") or "") == "attached"


def project_character_placement(character: Any) -> dict[str, Any]:
    """Snapshot a character placement. Grid is kept when present."""
    return _as_dict(character)


def project_prop_placement(prop: Any) -> dict[str, Any]:
    """Snapshot a prop placement with attachment fields when present.

    Attached: attachment fields kept; independent grid / x/y stripped.
    Independent: grid kept; attachment fields already cleared by normalize.
    """
    data = _as_dict(prop)
    normalize_prop_attachment(data)
    if data.get("placementMode") == "attached":
        for key in _INDEPENDENT_COORD_KEYS:
            data[key] = None
        data["gridRow"] = -1
        data["gridColumn"] = -1
    return data


def project_ers_placements(
    characters: Iterable[Any] | None = None,
    props: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build EnvironmentReferencePackage.placements from a Spatial Map document."""
    out: list[dict[str, Any]] = []
    for character in characters or []:
        out.append(project_character_placement(character))
    for prop in props or []:
        out.append(project_prop_placement(prop))
    return out


def project_document_placements(document: Any) -> list[dict[str, Any]]:
    return project_ers_placements(
        characters=getattr(document, "characters", None) or [],
        props=getattr(document, "props", None) or [],
    )


def project_placement_dicts(placements: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Re-project stored ERS placement dicts. Attached props lose leftover x/y."""
    out: list[dict[str, Any]] = []
    for raw in placements or []:
        data = _as_dict(raw)
        if _is_character_placement(data):
            out.append(project_character_placement(data))
        else:
            out.append(project_prop_placement(data))
    return out


def compile_structured_blocking(
    placements: Iterable[Any] | None,
    *,
    prop_approved: Mapping[str, bool] | None = None,
    character_names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Structured Scene Creator / ERS blocking from snapshotted placements.

    Does not infer attachment from overlapping cells. Conceptual prose is
    derived from placementMode / relationship / attachmentPoint only.
    Character identity refs and prop approved_asset_id stay separate.
    """
    approved = dict(prop_approved or {})
    names = dict(character_names or {})
    characters: list[dict[str, Any]] = []
    props: list[dict[str, Any]] = []
    for raw in placements or []:
        data = _as_dict(raw)
        if _is_character_placement(data):
            characters.append(project_character_placement(data))
        else:
            props.append(project_prop_placement(data))

    lines: list[str] = []
    attachments: list[dict[str, Any]] = []
    prose_parts: list[str] = []

    char_by_id: dict[str, dict[str, Any]] = {}
    char_by_slot: dict[int, dict[str, Any]] = {}
    for character in characters:
        cid = str(character.get("characterId") or character.get("character_id") or "").strip()
        label = (
            str(character.get("label") or "").strip()
            or names.get(cid, "")
            or cid
            or "Character"
        )
        cell = grid_cell_label(character.get("gridColumn"), character.get("gridRow"))
        if cell:
            lines.append(f"Character: {label}, Position: {cell}")
        else:
            lines.append(f"Character: {label}")
        if cid:
            char_by_id[cid] = {**character, "_label": label}
        slot_index = character.get("slotIndex")
        try:
            slot_int = int(slot_index) if slot_index is not None else None
        except (TypeError, ValueError):
            slot_int = None
        if slot_int is not None and 0 <= slot_int <= 3:
            char_by_slot[slot_int + 1] = {**character, "_label": label}

    for prop in props:
        label = str(prop.get("label") or prop.get("tag") or prop.get("propId") or "Prop").strip() or "Prop"
        prop_id = str(prop.get("propId") or prop.get("prop_id") or prop.get("id") or "").strip()
        if _is_attached_prop(prop):
            relationship = prop.get("relationship")
            point = prop.get("attachmentPoint")
            rel_label = _title_enum(relationship)
            point_label = _title_enum(point)
            attached_line = f"Attached Prop: {label}"
            if rel_label:
                attached_line += f", Relationship: {rel_label}"
            if point_label:
                attached_line += f", Attachment: {point_label}"
            lines.append(attached_line)

            host = _host_character(prop, char_by_id, char_by_slot)
            host_name = (host or {}).get("_label") or names.get(
                str(prop.get("attachedCharacterId") or "").strip(), ""
            ) or "the character"
            is_approved = bool(approved.get(prop_id))
            prose_parts.append(
                _derive_attachment_prose(
                    host_name=host_name,
                    prop_label=label,
                    relationship=str(relationship or ""),
                    attachment_point=str(point or "") if point else "",
                    approved=is_approved,
                )
            )
            attachments.append(
                {
                    "propId": prop_id or None,
                    "label": label,
                    "placementMode": "attached",
                    "attachedCharacterId": prop.get("attachedCharacterId"),
                    "attachedCharacterSlot": prop.get("attachedCharacterSlot"),
                    "relationship": relationship,
                    "attachmentPoint": point,
                    "hostCharacter": host_name,
                }
            )
            continue

        cell = grid_cell_label(prop.get("gridColumn"), prop.get("gridRow"))
        if cell:
            lines.append(f"Prop: {label}, Position: {cell}")
        else:
            lines.append(f"Prop: {label}")

    return {
        "lines": lines,
        "conceptual_prose": " ".join(part for part in prose_parts if part).strip(),
        "attachments": attachments,
    }


def camera_production_label(camera: Any) -> str:
    """Stable C1–C4 label from cameraSlot. Never renumber from list order."""
    data = _as_dict(camera)
    try:
        slot = int(data.get("cameraSlot"))
    except (TypeError, ValueError):
        slot = -1
    if 0 <= slot <= 3:
        return f"C{slot + 1}"
    label = str(data.get("label") or "").strip()
    return label or "Camera"


def is_active_spatial_camera(camera: Any) -> bool:
    """Placed and visible. Unplaced (grid < 0) or hidden cameras are excluded."""
    data = _as_dict(camera)
    if data.get("visible") is False:
        return False
    try:
        row = int(data.get("gridRow", -1))
        col = int(data.get("gridColumn", -1))
    except (TypeError, ValueError):
        return False
    return row >= 0 and col >= 0


def compile_structured_cameras(cameras: Iterable[Any] | None) -> dict[str, Any]:
    """Canonical Spatial Map cameras for ERS, Co-Director, and Scene Creator Mini.

    Uses existing SpatialCamera fields. Does not invent gridPosition/headingDegrees.
    """
    compiled: list[dict[str, Any]] = []
    for raw in cameras or []:
        if not is_active_spatial_camera(raw):
            continue
        data = _as_dict(raw)
        try:
            slot = int(data.get("cameraSlot", -1))
        except (TypeError, ValueError):
            slot = -1
        nx = data.get("normalizedX")
        ny = data.get("normalizedY")
        try:
            nx_f = float(nx) if nx is not None else None
        except (TypeError, ValueError):
            nx_f = None
        try:
            ny_f = float(ny) if ny is not None else None
        except (TypeError, ValueError):
            ny_f = None
        try:
            yaw = float(data.get("yawDegrees") if data.get("yawDegrees") is not None else 0)
        except (TypeError, ValueError):
            yaw = 0.0
        orientation = str(data.get("orientation") or "N").strip().upper() or "N"
        cell = grid_cell_label(data.get("gridColumn"), data.get("gridRow"))
        rec = {
            "id": str(data.get("id") or ""),
            "label": camera_production_label(data),
            "cameraSlot": slot,
            "normalizedX": nx_f,
            "normalizedY": ny_f,
            "gridColumn": data.get("gridColumn"),
            "gridRow": data.get("gridRow"),
            "cell": cell,
            "orientation": orientation,
            "yawDegrees": yaw,
            "fovPreset": str(data.get("fovPreset") or "medium"),
            "shotSize": str(data.get("shotSize") or "auto").strip().lower() or "auto",
            "primarySubject": str(data.get("primarySubject") or "auto").strip().lower() or "auto",
            "x": data.get("x"),
            "y": data.get("y"),
            "z": data.get("z"),
            "visible": True,
            "targetCharacterIds": list(data.get("targetCharacterIds") or []),
        }
        compiled.append(rec)

    compiled.sort(
        key=lambda item: (
            item["cameraSlot"] if isinstance(item.get("cameraSlot"), int) and int(item["cameraSlot"]) >= 0 else 99,
            str(item.get("label") or ""),
        )
    )
    lines: list[str] = []
    for rec in compiled:
        lines.append(f"CAMERA {rec['label']}")
        cell = str(rec.get("cell") or "")
        lines.append(f"Grid position: {cell}" if cell else "Grid position: unknown")
        nx_f = rec.get("normalizedX")
        ny_f = rec.get("normalizedY")
        if nx_f is not None and ny_f is not None:
            lines.append(f"Normalized: ({float(nx_f):.4f}, {float(ny_f):.4f})")
        lines.append(f"Facing: {rec['orientation']} (yaw {rec['yawDegrees']:g})")
        lines.append(f"FOV: {rec['fovPreset']}")
    return {
        "cameras": compiled,
        "lines": lines,
        "labels": [str(item["label"]) for item in compiled],
        "count": len(compiled),
    }


_FACING_LOOK = {
    "N": "north",
    "NE": "northeast",
    "E": "east",
    "SE": "southeast",
    "S": "south",
    "SW": "southwest",
    "W": "west",
    "NW": "northwest",
}

_REGION_EW_EAST = 0.2
_REGION_EW_WEST = -0.2
_REGION_NS_SOUTH = 0.2
_REGION_NS_NORTH = -0.2
_RELATIVE_DELTA = 0.08


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _region_east_west(normalized_x: float | None) -> str:
    if normalized_x is None:
        return "center"
    if normalized_x > _REGION_EW_EAST:
        return "east"
    if normalized_x < _REGION_EW_WEST:
        return "west"
    return "center"


def _region_north_south(normalized_y: float | None) -> str:
    if normalized_y is None:
        return "center"
    if normalized_y > _REGION_NS_SOUTH:
        return "south"
    if normalized_y < _REGION_NS_NORTH:
        return "north"
    return "center"


def _plant_phrase(region_x: str, region_y: str) -> str:
    parts: list[str] = []
    if region_x == "east":
        parts.append("eastern")
    elif region_x == "west":
        parts.append("western")
    if region_y == "north":
        parts.append("northern")
    elif region_y == "south":
        parts.append("southern")
    if not parts:
        return "central area of the mapped room"
    if len(parts) == 1:
        return f"{parts[0]} side of the mapped room"
    return f"{parts[0]}-{parts[1]} area of the mapped room"


def _named_label(data: Mapping[str, Any]) -> str:
    return str(
        data.get("label")
        or data.get("name")
        or data.get("characterId")
        or data.get("id")
        or ""
    ).strip()


def _placement_world_xz(data: Mapping[str, Any]) -> tuple[float, float] | None:
    from .capture_intelligence import _finite_world_xz

    nx = data.get("normalizedX")
    ny = data.get("normalizedY")
    xz = _finite_world_xz(data.get("x"), data.get("z"))
    if nx is None and ny is None:
        if xz is None or xz == (0.0, 0.0):
            return None
        return xz
    return xz


def _spatial_map_bearing(*, from_x: float, from_z: float, to_x: float, to_z: float) -> float:
    """Yaw 0 = north = −Z. Clockwise toward +X (east). Same north lock as Spatial Map."""
    dx = to_x - from_x
    dz = to_z - from_z
    return (math.degrees(math.atan2(dx, -dz)) + 360.0) % 360.0


def _spatial_map_relation(
    *,
    yaw_degrees: float,
    camera_x: float,
    camera_z: float,
    object_x: float,
    object_z: float,
    label: str,
) -> str | None:
    """Same visibility buckets as capture_intelligence, on Spatial Map north."""
    from .capture_intelligence import _angle_delta

    bearing = _spatial_map_bearing(
        from_x=camera_x, from_z=camera_z, to_x=object_x, to_z=object_z
    )
    delta = _angle_delta(bearing, yaw_degrees)
    if delta <= 35:
        return f"{label} visible ahead"
    if delta <= 70:
        side = "right" if ((bearing - yaw_degrees + 360.0) % 360.0) < 180.0 else "left"
        return f"{label} partially visible at {side} edge"
    if delta <= 110:
        return f"{label} occluded / leaving frame"
    return f"{label} behind the camera"


def compile_camera_viewpoint_facts(
    camera: Any,
    *,
    cameras: Iterable[Any] | None = None,
    characters: Iterable[Any] | None = None,
    props: Iterable[Any] | None = None,
    anchors: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Mini-only relational viewpoint. Do not append these lines to the ERS compiler.

    Deterministic from saved Spatial Map fields. No environment-specific prose.
    """
    from .capture_intelligence import _finite_world_xz

    data = _as_dict(camera)
    compiled = compile_structured_cameras([data]).get("cameras") or []
    rec = compiled[0] if compiled else {
        "id": str(data.get("id") or ""),
        "label": camera_production_label(data),
        "normalizedX": _optional_float(data.get("normalizedX")),
        "normalizedY": _optional_float(data.get("normalizedY")),
        "cell": grid_cell_label(data.get("gridColumn"), data.get("gridRow")),
        "orientation": str(data.get("orientation") or "N").strip().upper() or "N",
        "yawDegrees": _optional_float(data.get("yawDegrees")) or 0.0,
        "fovPreset": str(data.get("fovPreset") or "medium"),
        "x": data.get("x"),
        "z": data.get("z"),
    }
    label = str(rec.get("label") or "Camera")
    cell = str(rec.get("cell") or "")
    nx = rec.get("normalizedX")
    ny = rec.get("normalizedY")
    if not isinstance(nx, float):
        nx = _optional_float(nx)
    if not isinstance(ny, float):
        ny = _optional_float(ny)
    region_x = _region_east_west(nx)
    region_y = _region_north_south(ny)
    orientation = str(rec.get("orientation") or "N").strip().upper() or "N"
    yaw = float(rec.get("yawDegrees") or 0.0)
    look = _FACING_LOOK.get(orientation, orientation.lower())
    fov = str(rec.get("fovPreset") or "medium")
    cam_xz = _finite_world_xz(rec.get("x"), rec.get("z"))
    if cam_xz is None:
        cam_xz = _finite_world_xz(data.get("x"), data.get("z"))

    lines: list[str] = [
        f"CAMERA {label} VIEWPOINT",
        f"Grid position: {cell}" if cell else "Grid position: unknown",
    ]
    if nx is not None and ny is not None:
        lines.append(f"Normalized: ({float(nx):.4f}, {float(ny):.4f})")
    lines.append(f"This camera is planted on the {_plant_phrase(region_x, region_y)}.")
    lines.append(f"Facing: {orientation} (yaw {yaw:g}). Looks {look}.")
    lines.append(f"FOV: {fov}")
    if orientation != "N":
        lines.append(
            "Architecture that sits due north of this plant is seen at an oblique angle, not head-on."
        )

    siblings = compile_structured_cameras(cameras or []).get("cameras") or []
    more_western: list[str] = []
    cam_id = str(rec.get("id") or data.get("id") or "")
    for other in siblings:
        other_id = str(other.get("id") or "")
        if other_id and other_id == cam_id:
            continue
        other_label = str(other.get("label") or "Camera")
        other_nx = other.get("normalizedX")
        other_ny = other.get("normalizedY")
        if isinstance(nx, float) and isinstance(other_nx, (int, float)) and not isinstance(other_nx, bool):
            delta_x = float(nx) - float(other_nx)
            if delta_x > _RELATIVE_DELTA:
                lines.append(f"This camera is east of {other_label}.")
                more_western.append(other_label)
            elif delta_x < -_RELATIVE_DELTA:
                lines.append(f"This camera is west of {other_label}.")
        if isinstance(ny, float) and isinstance(other_ny, (int, float)) and not isinstance(other_ny, bool):
            delta_y = float(ny) - float(other_ny)
            if delta_y > _RELATIVE_DELTA:
                lines.append(f"This camera is south of {other_label}.")
            elif delta_y < -_RELATIVE_DELTA:
                lines.append(f"This camera is north of {other_label}.")

    relation_lines: list[str] = []
    if cam_xz is not None:
        named_items: list[tuple[str, Mapping[str, Any]]] = []
        for raw in characters or []:
            item = _as_dict(raw)
            name = _named_label(item)
            if name:
                named_items.append((name, item))
        for raw in props or []:
            item = _as_dict(raw)
            name = _named_label(item)
            if name:
                named_items.append((name, item))
        for raw in anchors or []:
            item = _as_dict(raw)
            name = _named_label(item)
            if name:
                named_items.append((name, item))
        for name, item in named_items:
            obj_xz = _placement_world_xz(item)
            if obj_xz is None:
                continue
            note = _spatial_map_relation(
                yaw_degrees=yaw,
                camera_x=cam_xz[0],
                camera_z=cam_xz[1],
                object_x=obj_xz[0],
                object_z=obj_xz[1],
                label=name,
            )
            if note:
                relation_lines.append(note)
    if relation_lines:
        lines.append("From this camera: " + "; ".join(relation_lines) + ".")

    contradictions = [
        f"CAMERA {label} IS CANONICAL for this still.",
        "Do not relocate this camera to another region of the room.",
        "Do not mirror the room.",
        "Do not rotate the environment.",
        "Do not substitute another camera's viewpoint.",
    ]
    if region_x == "east":
        contradictions.append(
            "Do not render a centered north-facing hero or front-of-service composition from this camera."
        )
        contradictions.append("Do not plant this camera west of the primary service area.")
        contradictions.append(
            "Keep the nearest guest furniture in the east seating neighborhood. "
            "Do not fill the foreground with lounge seating or an entrance-door composition."
        )
    if orientation != "N":
        contradictions.append(
            "Do not render a straight-on north hero view; this camera is not facing due north."
        )
    if more_western:
        contradictions.append(
            "Do not reuse a more-western camera's viewpoint ("
            + ", ".join(more_western)
            + ")."
        )
    lines.extend(contradictions)

    return {
        "label": label,
        "cell": cell,
        "regionX": region_x,
        "regionY": region_y,
        "facing": orientation,
        "look": look,
        "yawDegrees": yaw,
        "fovPreset": fov,
        "moreWestern": more_western,
        "lines": lines,
        "contradictions": contradictions,
    }


def _host_character(
    prop: Mapping[str, Any],
    char_by_id: Mapping[str, dict[str, Any]],
    char_by_slot: Mapping[int, dict[str, Any]],
) -> dict[str, Any] | None:
    cid = str(prop.get("attachedCharacterId") or "").strip()
    if cid and cid in char_by_id:
        return char_by_id[cid]
    slot = prop.get("attachedCharacterSlot")
    try:
        slot_int = int(slot) if slot is not None else None
    except (TypeError, ValueError):
        slot_int = None
    if slot_int is not None and slot_int in char_by_slot:
        return char_by_slot[slot_int]
    return None


def _derive_attachment_prose(
    *,
    host_name: str,
    prop_label: str,
    relationship: str,
    attachment_point: str,
    approved: bool,
) -> str:
    verb = _RELATIONSHIP_GERUND.get(relationship, "")
    if not verb:
        return ""
    approved_word = "approved " if approved else ""
    point = _ATTACHMENT_POINT_PHRASE.get(attachment_point, "")
    return f"{host_name} is {verb} the {approved_word}{prop_label} prop{point}."
