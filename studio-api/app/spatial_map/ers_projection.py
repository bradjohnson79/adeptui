"""ERS / Scene Creator projection of Spatial Map placements.

Reads Spatial Map attachment fields. Does not invent a second relationship store.
Attached props have no independent grid and no fake x/y.
Independent props keep their grid.

Amendment #3: this is a read-only snapshot transform. It never writes back
to the Spatial Map.
"""

from __future__ import annotations

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
