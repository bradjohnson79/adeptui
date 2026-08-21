"""CameraShotPacket — deterministic per-camera production shot packet.

Scene Creator Mini compiler input. Compiled ONLY from saved production state
(Spatial Map document + authoritative ERS reference) at enqueue time. The
Co-Director intelligence layer may format and creatively enrich this packet
for presentation; it may not change the facts.

Governing rule:

    DETERMINISTIC PRODUCTION FACTS -> LOCKED
    CREATIVE PRESENTATION          -> FLEXIBLE

Locked examples: the character exists, is behind the service counter, is on
the employee side; camera C2 is at N12 facing NW; counter position is fixed;
north orientation is fixed. Flexible: expression nuance, lighting nuance,
depth of field, pose variation, subtle framing within the same camera.

Never writes back to the Spatial Map (read-only snapshot transform).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, Field

from .ers_projection import (
    _as_dict,
    _region_east_west,
    _region_north_south,
    _spatial_map_relation,
    camera_production_label,
    compile_camera_viewpoint_facts,
    compile_structured_cameras,
    grid_cell_label,
)

_REGION_PHRASE = {
    ("east", "north"): "northeastern area",
    ("east", "south"): "southeastern area",
    ("west", "north"): "northwestern area",
    ("west", "south"): "southwestern area",
    ("east", "center"): "eastern side",
    ("west", "center"): "western side",
    ("center", "north"): "northern side",
    ("center", "south"): "southern side",
    ("center", "center"): "central area",
}

FIXTURE_LABEL_HINTS = ("counter", "bar", "desk", "table", "island", "stand", "station")


def _region_phrase(region_x: str, region_y: str) -> str:
    return _REGION_PHRASE.get((region_x, region_y), f"{region_x}-{region_y} region")


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _finite_world_xz(item: Mapping[str, Any]) -> tuple[float, float] | None:
    from .capture_intelligence import _finite_world_xz as _impl

    return _impl(item.get("x"), item.get("z"))


def _character_side_relations(
    character: Mapping[str, Any],
    camera_xz: tuple[float, float] | None,
    anchors: Iterable[Any] | None,
) -> list[str]:
    """Derive fixture-side placement relations from map geometry only.

    "Korri is behind the service counter from this camera" style facts come
    from world coordinates, never from hardcoded per-project prose.
    """
    if camera_xz is None:
        return []
    char_xz = _finite_world_xz(character)
    if char_xz is None:
        return []
    name = str(
        character.get("label")
        or character.get("name")
        or character.get("characterId")
        or "the character"
    ).strip()
    cx, cz = camera_xz
    hx, hz = char_xz
    out: list[str] = []
    for raw in anchors or []:
        anchor = _as_dict(raw)
        label = str(anchor.get("label") or "").strip()
        fx = _optional_float(anchor.get("x"))
        fz = _optional_float(anchor.get("z"))
        if not label or fx is None or fz is None:
            continue
        # Aligned when the character is roughly on the camera->fixture line.
        v1 = (fx - cx, fz - cz)
        v2 = (hx - cx, hz - cz)
        v1_len = math.hypot(v1[0], v1[1])
        v2_len = math.hypot(v2[0], v2[1])
        if v1_len <= 1e-6 or v2_len <= 1e-6:
            continue
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        align = abs(cross) / (v1_len * v2_len)
        if align < 0.35 and v2_len > v1_len:
            out.append(
                f"{name} is behind the {label} from this camera "
                f"(far side, away from the camera)."
            )
            out.append(
                f"{name} remains on the far side of the {label}; "
                f"must not move to the near side in front of the {label}."
            )
        elif align < 0.35:
            out.append(
                f"{name} is on the near side of the {label} "
                f"(between this camera and the {label})."
            )
    return out


def _identity_for_character(db: Any, project_id: str, character_id: str) -> dict[str, Any]:
    """Approved identity as text + asset id stamp. Best-effort; never raises."""
    result: dict[str, Any] = {"name": "", "facts": [], "approvedAssetId": None}
    if db is None or not character_id:
        return result
    try:
        from ..character_identity.models import CharacterProfileRow, CharacterWardrobeRow
        from ..character_identity.service import resolve_approved_reference

        row = db.get(CharacterProfileRow, character_id)
        if row is None or str(row.project_id) != str(project_id):
            return result
        result["name"] = str(row.name or "").strip()
        facts: list[str] = []
        for label, value in (
            ("species", row.species_or_type),
            ("appearance", row.visual_description),
            ("height", row.height_description),
            ("build", row.body_type),
            ("age", row.apparent_age),
        ):
            text_value = str(value or "").strip()
            if text_value and text_value.lower() not in {"human", ""}:
                facts.append(f"{label}: {text_value}")
            elif text_value and label == "species":
                facts.append(f"{label}: {text_value}")
        wardrobe_id = str(getattr(row, "active_wardrobe_id", "") or "").strip()
        if wardrobe_id:
            wardrobe = db.get(CharacterWardrobeRow, wardrobe_id)
            if wardrobe is not None:
                wardrobe_bits = [
                    str(getattr(wardrobe, key, "") or "").strip()
                    for key in ("name", "description", "materials", "colors")
                ]
                wardrobe_text = ", ".join(bit for bit in wardrobe_bits if bit)
                if wardrobe_text:
                    facts.append(f"wardrobe: {wardrobe_text}")
        result["facts"] = facts
        result["approvedAssetId"] = resolve_approved_reference(db, character_id, "hero_identity")
    except Exception:
        pass
    return result


def _prop_identity(db: Any, project_id: str, prop_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {"name": "", "approvedAssetId": None}
    if db is None or not prop_id:
        return result
    try:
        from ..spatial_map.ers_persistence import load_prop_entity_by_id

        entity = load_prop_entity_by_id(db, project_id, prop_id)
        if entity is None:
            return result
        result["name"] = str(entity.display_label or entity.tag or "").strip()
        result["approvedAssetId"] = str(entity.approved_asset_id or "").strip() or None
    except Exception:
        pass
    return result


class PacketEnvironment(BaseModel):
    projectId: str = ""
    sceneId: str | None = None
    spatialMapId: str = ""
    mapVersion: str = ""
    savedVersion: str | None = None
    spatialProfileId: str = ""
    ersSheetId: str = ""
    ersCompositeAssetId: str = ""
    ersRevision: str = ""
    northLock: str = "north"
    environmentIdentity: str = ""
    anchors: list[dict[str, Any]] = Field(default_factory=list)
    continuityRules: list[str] = Field(default_factory=list)


class PacketCamera(BaseModel):
    id: str = ""
    label: str = ""
    cameraSlot: int = -1
    normalizedX: float | None = None
    normalizedY: float | None = None
    gridRow: int = -1
    gridColumn: int = -1
    cell: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    orientation: str = "N"
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    fovPreset: str = "medium"
    shotSize: str = "auto"
    region: str = ""
    facing: str = ""
    look: str = ""
    relationalFacts: list[str] = Field(default_factory=list)
    antiSubstitutionRules: list[str] = Field(default_factory=list)


class PacketCharacter(BaseModel):
    placementId: str = ""
    characterId: str = ""
    name: str = ""
    label: str = ""
    tag: str = ""
    approvedAssetId: str | None = None
    identityFacts: list[str] = Field(default_factory=list)
    cell: str = ""
    region: str = ""
    gridRow: int = -1
    gridColumn: int = -1
    normalizedX: float | None = None
    normalizedY: float | None = None
    x: float | None = None
    z: float | None = None
    yawDegrees: float = 0.0
    visible: bool = True
    mandatoryForCamera: bool = False
    primarySubject: bool = False
    cameraRelation: str = ""
    sideRelations: list[str] = Field(default_factory=list)


class PacketProp(BaseModel):
    placementId: str = ""
    propId: str = ""
    label: str = ""
    approvedAssetId: str | None = None
    cell: str = ""
    gridRow: int = -1
    gridColumn: int = -1
    x: float | None = None
    z: float | None = None
    visible: bool = True
    placementMode: str = "independent"
    relationship: str | None = None
    attachmentPoint: str | None = None
    attachedCharacterId: str | None = None
    mandatoryForCamera: bool = False


class PacketSceneIntent(BaseModel):
    userSceneDirection: str = ""
    productionIntent: str = ""
    summary: str = ""
    action: str = ""
    dialogue: str = ""
    performanceDirection: str = ""
    continuityConstraints: list[str] = Field(default_factory=list)


class CameraShotPacket(BaseModel):
    environment: PacketEnvironment = Field(default_factory=PacketEnvironment)
    camera: PacketCamera = Field(default_factory=PacketCamera)
    characters: list[PacketCharacter] = Field(default_factory=list)
    props: list[PacketProp] = Field(default_factory=list)
    sceneIntent: PacketSceneIntent = Field(default_factory=PacketSceneIntent)
    requiredCharacterIds: list[str] = Field(default_factory=list)
    primarySubject: dict[str, str] = Field(default_factory=dict)
    lockedFacts: list[str] = Field(default_factory=list)
    flexibleNotes: list[str] = Field(default_factory=list)


def _profile_id_for_map(db: Any, project_id: str, map_id: str) -> str:
    if db is None or not project_id or not map_id:
        return ""
    try:
        from ..scene_creator.production_handoff import list_profiles

        for profile in list_profiles(db, project_id):
            if str(profile.spatialMapId or "") == str(map_id):
                return str(profile.handoffId or "")
    except Exception:
        pass
    return ""


def _coerce_scene_intent(raw: Any) -> dict[str, Any]:
    try:
        from .scene_intent import coerce_scene_intent

        intent = coerce_scene_intent(raw)
        if intent is None:
            return {}
        return intent.model_dump()
    except Exception:
        return {}


def _is_character_placement(data: Mapping[str, Any]) -> bool:
    return bool(data.get("characterId") or data.get("character_id"))


def _placed(data: Mapping[str, Any]) -> bool:
    try:
        row = int(data.get("gridRow", -1))
        col = int(data.get("gridColumn", -1))
    except (TypeError, ValueError):
        return False
    return row >= 0 and col >= 0


def compile_camera_shot_packet(
    db: Any,
    project_id: str,
    document: Any,
    camera: Any,
    *,
    ers_sheet_id: str = "",
    ers_composite_asset_id: str = "",
    ers_revision: str = "",
) -> CameraShotPacket:
    """Compile the deterministic production packet for one Mini camera.

    All facts come from the saved Spatial Map document (plus authoritative
    ERS reference ids). This function never infers creative interpretation.
    """
    map_id = str(getattr(document, "id", "") or "")
    cameras_raw = getattr(document, "cameras", None) or []
    characters_raw = getattr(document, "characters", None) or []
    props_raw = getattr(document, "props", None) or []
    anchors_raw = getattr(document, "anchors", None) or []

    camera_data = _as_dict(camera)
    compiled_cameras = compile_structured_cameras([camera_data]).get("cameras") or []
    rec = compiled_cameras[0] if compiled_cameras else {
        "id": camera_data.get("id"),
        "label": camera_production_label(camera_data),
        "cameraSlot": camera_data.get("cameraSlot"),
        "normalizedX": _optional_float(camera_data.get("normalizedX")),
        "normalizedY": _optional_float(camera_data.get("normalizedY")),
        "gridColumn": camera_data.get("gridColumn"),
        "gridRow": camera_data.get("gridRow"),
        "cell": grid_cell_label(camera_data.get("gridColumn"), camera_data.get("gridRow")),
        "orientation": str(camera_data.get("orientation") or "N").strip().upper() or "N",
        "yawDegrees": _optional_float(camera_data.get("yawDegrees")) or 0.0,
        "fovPreset": str(camera_data.get("fovPreset") or "medium"),
        "x": camera_data.get("x"),
        "y": camera_data.get("y"),
        "z": camera_data.get("z"),
        "targetCharacterIds": list(camera_data.get("targetCharacterIds") or []),
        "visible": True,
    }

    viewpoint = compile_camera_viewpoint_facts(
        camera_data,
        cameras=cameras_raw,
        characters=characters_raw,
        props=props_raw,
        anchors=anchors_raw,
    )
    viewpoint_lines = list(viewpoint.get("lines") or [])
    contradictions = list(viewpoint.get("contradictions") or [])
    relational_facts = [line for line in viewpoint_lines if line not in contradictions]

    nx = rec.get("normalizedX")
    ny = rec.get("normalizedY")
    if not isinstance(nx, float):
        nx = _optional_float(nx)
    if not isinstance(ny, float):
        ny = _optional_float(ny)
    region_x = _region_east_west(nx)
    region_y = _region_north_south(ny)
    region = _region_phrase(region_x, region_y)
    shot_size = str(camera_data.get("shotSize") or "auto").strip().lower() or "auto"

    cam_xz = _finite_world_xz(rec)
    if cam_xz is None:
        cam_xz = _finite_world_xz(camera_data)

    # ---- characters -------------------------------------------------------
    target_ids = {str(cid) for cid in (rec.get("targetCharacterIds") or [])}
    packet_characters: list[PacketCharacter] = []
    for raw in characters_raw or []:
        data = _as_dict(raw)
        if not _is_character_placement(data):
            continue
        character_id = str(data.get("characterId") or data.get("character_id") or "").strip()
        label = str(data.get("label") or data.get("tag") or "").lstrip("@").strip()
        identity = _identity_for_character(db, project_id, character_id) if character_id else {}
        name = str(identity.get("name") or "").strip() or label or character_id
        cell = grid_cell_label(data.get("gridColumn"), data.get("gridRow"))
        c_nx = _optional_float(data.get("normalizedX"))
        c_ny = _optional_float(data.get("normalizedY"))
        char_region = _region_phrase(_region_east_west(c_nx), _region_north_south(c_ny)) if c_nx is not None and c_ny is not None else ""
        c_xz = _finite_world_xz(data)
        relation_note = ""
        if cam_xz is not None and c_xz is not None:
            relation_note = str(
                _spatial_map_relation(
                    yaw_degrees=float(rec.get("yawDegrees") or 0.0),
                    camera_x=cam_xz[0],
                    camera_z=cam_xz[1],
                    object_x=c_xz[0],
                    object_z=c_xz[1],
                    label=name,
                )
                or ""
            )
        side_relations = _character_side_relations(data, cam_xz, anchors_raw)
        visible = data.get("visible", True) is not False
        placed = _placed(data)
        in_view = bool(relation_note) and (
            "visible ahead" in relation_note or "partially visible" in relation_note
        )
        is_primary = str(camera_data.get("primarySubject") or "").strip() == character_id
        mandatory = bool(visible and placed and (in_view or character_id in target_ids or is_primary))
        packet_characters.append(
            PacketCharacter(
                placementId=str(data.get("id") or ""),
                characterId=character_id,
                name=name,
                label=label,
                tag=str(data.get("tag") or ""),
                approvedAssetId=identity.get("approvedAssetId"),
                identityFacts=list(identity.get("facts") or []),
                cell=cell,
                region=char_region,
                gridRow=int(data.get("gridRow", -1) or -1),
                gridColumn=int(data.get("gridColumn", -1) or -1),
                normalizedX=c_nx,
                normalizedY=c_ny,
                x=_optional_float(data.get("x")),
                z=_optional_float(data.get("z")),
                yawDegrees=_optional_float(data.get("yawDegrees")) or 0.0,
                visible=visible,
                mandatoryForCamera=mandatory,
                primarySubject=is_primary,
                cameraRelation=relation_note,
                sideRelations=side_relations,
            )
        )

    # ---- props ------------------------------------------------------------
    packet_props: list[PacketProp] = []
    for raw in props_raw or []:
        data = _as_dict(raw)
        if _is_character_placement(data):
            continue
        prop_id = str(data.get("propId") or data.get("prop_id") or "").strip()
        label = str(
            data.get("label")
            or data.get("tag")
            or _prop_identity(db, project_id, prop_id).get("name")
            or "Prop"
        ).strip() or "Prop"
        identity = _prop_identity(db, project_id, prop_id) if prop_id else {}
        visible = data.get("visible", True) is not False
        attached = str(data.get("placementMode") or "") == "attached"
        packet_props.append(
            PacketProp(
                placementId=str(data.get("id") or ""),
                propId=prop_id or None,
                label=label,
                approvedAssetId=identity.get("approvedAssetId"),
                cell=grid_cell_label(data.get("gridColumn"), data.get("gridRow")),
                gridRow=int(data.get("gridRow", -1) or -1),
                gridColumn=int(data.get("gridColumn", -1) or -1),
                x=_optional_float(data.get("x")),
                z=_optional_float(data.get("z")),
                visible=visible,
                placementMode=str(data.get("placementMode") or "independent"),
                relationship=data.get("relationship"),
                attachmentPoint=data.get("attachmentPoint"),
                attachedCharacterId=data.get("attachedCharacterId"),
                mandatoryForCamera=bool(visible and (prop_id or attached)),
            )
        )

    # ---- scene intent -----------------------------------------------------
    intent_data = _coerce_scene_intent(getattr(document, "sceneIntent", None))
    scene_intent = PacketSceneIntent(
        userSceneDirection=str(intent_data.get("sourcePromptSummary") or ""),
        productionIntent=str(intent_data.get("productionIntent") or ""),
        summary=str(intent_data.get("summary") or ""),
        action=str(intent_data.get("action") or ""),
        dialogue=str(intent_data.get("dialogue") or ""),
        performanceDirection=str(intent_data.get("performanceDirection") or ""),
        continuityConstraints=[str(s) for s in (intent_data.get("environmentTraits") or [])],
    )

    # ---- primary subject --------------------------------------------------
    primary_raw = str(camera_data.get("primarySubject") or "auto").strip().lower() or "auto"
    primary_subject: dict[str, str] = {"type": "auto", "characterId": "", "name": ""}
    if primary_raw == "environment":
        primary_subject = {"type": "environment", "characterId": "", "name": "Environment"}
    elif primary_raw not in {"auto", "environment"}:
        match = next((c for c in packet_characters if c.characterId == primary_raw), None)
        if match is not None:
            primary_subject = {"type": "character", "characterId": match.characterId, "name": match.name}
        else:
            primary_subject = {"type": "auto", "characterId": "", "name": ""}
    elif primary_raw == "auto" and len(target_ids) == 1:
        match = next((c for c in packet_characters if c.characterId in target_ids), None)
        if match is not None:
            primary_subject = {"type": "character", "characterId": match.characterId, "name": match.name}

    required_ids = [c.characterId for c in packet_characters if c.mandatoryForCamera and c.characterId]

    # ---- locked facts -----------------------------------------------------
    env_identity = str(
        getattr(document, "masterEnvironmentPrompt", "") or getattr(document, "title", "") or ""
    ).strip()
    anchors_snapshot: list[dict[str, Any]] = []
    for raw in anchors_raw or []:
        anchor = _as_dict(raw)
        anchors_snapshot.append(
            {
                "id": str(anchor.get("id") or ""),
                "label": str(anchor.get("label") or ""),
                "x": _optional_float(anchor.get("x")),
                "z": _optional_float(anchor.get("z")),
            }
        )

    locked: list[str] = [
        f"Environment: {env_identity}",
        f"North lock: {_north_lock_for(document, ers_sheet_id)}",
    ]
    try:
        from .metric import compile_metric_lines

        locked.extend(compile_metric_lines(document))
    except Exception:
        pass
    if rec.get("cell"):
        locked.append(f"Camera {rec['label']} is at grid cell {rec['cell']}.")
    if nx is not None and ny is not None:
        locked.append(f"Camera {rec['label']} normalized position ({float(nx):.4f}, {float(ny):.4f}).")
    locked.append(f"Camera {rec['label']} region: {region}.")
    locked.append(f"Camera {rec['label']} faces {rec['orientation']} (yaw {float(rec.get('yawDegrees') or 0.0):g}).")
    locked.append(f"Camera {rec['label']} FOV: {rec['fovPreset']}.")
    if shot_size != "auto":
        locked.append(
            f"Shot size: {shot_size.replace('_', ' ')}. Shot size changes framing, "
            f"crop and composition only — it does NOT move the camera."
        )
    else:
        locked.append("Shot size: AUTO (framing inferred within this camera geography).")
    for character in packet_characters:
        if character.mandatoryForCamera:
            locked.append(
                f"{str(character.name).upper()} MUST BE PRESENT."
                if character.name
                else "THE REQUIRED CHARACTER MUST BE PRESENT."
            )
            locked.append(f"{character.name} is placed at {character.cell}." if character.cell else "")
            if character.cameraRelation:
                locked.append(f"From this camera: {character.cameraRelation}.")
            identity_text = "; ".join(str(f) for f in character.identityFacts if f).strip()
            if identity_text:
                locked.append(f"Character identity ({character.name}): {identity_text}")
        for side in character.sideRelations:
            locked.append(side)
    for prop in packet_props:
        if prop.mandatoryForCamera:
            cell_part = f" at {prop.cell}" if prop.cell else ""
            locked.append(f"Prop {prop.label} is present{cell_part}.")
    locked.extend(contradictions)

    flexible: list[str] = [
        "Expression nuance, lighting nuance, depth of field, and subtle pose variation are flexible.",
        "Composition may vary only within this exact camera geography.",
    ]

    packet = CameraShotPacket(
        environment=PacketEnvironment(
            projectId=project_id,
            sceneId=getattr(document, "sceneId", None),
            spatialMapId=map_id,
            mapVersion=str(getattr(document, "version", "") or ""),
            savedVersion=getattr(document, "savedVersion", None),
            spatialProfileId=_profile_id_for_map(db, project_id, map_id),
            ersSheetId=ers_sheet_id,
            ersCompositeAssetId=ers_composite_asset_id,
            ersRevision=ers_revision or str(getattr(document, "groundingFingerprint", "") or ""),
            northLock=_north_lock_for(document, ers_sheet_id),
            environmentIdentity=env_identity,
            anchors=anchors_snapshot,
        ),
        camera=PacketCamera(
            id=str(rec.get("id") or ""),
            label=str(rec.get("label") or ""),
            cameraSlot=int(rec.get("cameraSlot", -1) or -1),
            normalizedX=nx,
            normalizedY=ny,
            gridRow=int(rec.get("gridRow", -1) or -1),
            gridColumn=int(rec.get("gridColumn", -1) or -1),
            cell=str(rec.get("cell") or ""),
            x=_optional_float(rec.get("x")),
            y=_optional_float(rec.get("y")),
            z=_optional_float(rec.get("z")),
            orientation=str(rec.get("orientation") or "N"),
            yawDegrees=float(rec.get("yawDegrees") or 0.0),
            pitchDegrees=_optional_float(camera_data.get("pitchDegrees")) or 0.0,
            fovPreset=str(rec.get("fovPreset") or "medium"),
            shotSize=shot_size,
            region=region,
            facing=str(rec.get("orientation") or "N"),
            look=str(viewpoint.get("look") or ""),
            relationalFacts=relational_facts,
            antiSubstitutionRules=contradictions,
        ),
        characters=packet_characters,
        props=packet_props,
        sceneIntent=scene_intent,
        requiredCharacterIds=required_ids,
        primarySubject=primary_subject,
        lockedFacts=locked,
        flexibleNotes=flexible,
    )
    return packet


def _north_lock_for(document: Any, ers_sheet_id: str) -> str:
    return "north"
