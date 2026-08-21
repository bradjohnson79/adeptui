"""Kinematic / contact / plausibility analysis for PoseCraft scenes.

This is not JEPA. Joints, primitives, and SpatialDraft labels produce
balance, support, stance, and contact. Warnings never rewrite poses.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Optional

from .contracts import (
    POSE_ANALYSIS_VERSION,
    BalanceState,
    CharacterPoseState,
    ContactEdge,
    ContactGraph,
    EnvironmentRelationship,
    InteractionState,
    LimbConfiguration,
    MotionInterpretation,
    PoseChange,
    PoseTransition,
    ProductionConstraints,
    StanceType,
    SupportLimb,
    Vec3,
)

ARCHETYPES: dict[str, dict[str, float]] = {
    "adult-male": {
        "height": 1.84, "torsoHeight": 0.72, "shoulderWidth": 0.48, "hipWidth": 0.26,
        "upperArm": 0.31, "lowerArm": 0.29, "upperLeg": 0.46, "lowerLeg": 0.45,
    },
    "adult-female": {
        "height": 1.70, "torsoHeight": 0.66, "shoulderWidth": 0.34, "hipWidth": 0.32,
        "upperArm": 0.27, "lowerArm": 0.25, "upperLeg": 0.43, "lowerLeg": 0.42,
    },
    "child-boy": {
        "height": 1.32, "torsoHeight": 0.48, "shoulderWidth": 0.29, "hipWidth": 0.20,
        "upperArm": 0.21, "lowerArm": 0.20, "upperLeg": 0.30, "lowerLeg": 0.29,
    },
    "child-girl": {
        "height": 1.28, "torsoHeight": 0.47, "shoulderWidth": 0.27, "hipWidth": 0.20,
        "upperArm": 0.20, "lowerArm": 0.19, "upperLeg": 0.29, "lowerLeg": 0.28,
    },
}

FLOOR_EPS = 0.08
CONTACT_XY = 0.38
TELEPORT_M = 0.55
YAW_JUMP_DEG = 75.0


def _deg(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rot(rx: float, ry: float, rz: float) -> list[list[float]]:
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    return [
        [cy * cz, cz * sx * sy - cx * sz, cx * cz * sy + sx * sz],
        [cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - cz * sx],
        [-sy, cy * sx, cx * cy],
    ]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def _apply(m: list[list[float]], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _pose_map(figure: Any) -> dict[str, dict[str, float]]:
    raw = getattr(figure, "pose", None)
    if raw is None and isinstance(figure, dict):
        raw = figure.get("pose") or {}
    out: dict[str, dict[str, float]] = {}
    if isinstance(raw, dict):
        for name, rot in raw.items():
            if hasattr(rot, "x"):
                out[str(name)] = {"x": _deg(rot.x), "y": _deg(rot.y), "z": _deg(rot.z)}
            elif isinstance(rot, dict):
                out[str(name)] = {"x": _deg(rot.get("x")), "y": _deg(rot.get("y")), "z": _deg(rot.get("z"))}
    return out


def _spec(archetype_id: str) -> dict[str, float]:
    return ARCHETYPES.get(archetype_id or "", ARCHETYPES["adult-male"])


def _figure_origin(figure: Any) -> tuple[float, float]:
    pos = getattr(figure, "position", None) if not isinstance(figure, dict) else figure.get("position")
    if isinstance(pos, dict):
        return float(pos.get("x") or 0.0), float(pos.get("z") or 0.0)
    if pos is not None:
        return float(getattr(pos, "x", 0.0) or 0.0), float(getattr(pos, "z", 0.0) or 0.0)
    return 0.0, 0.0


def solve_joints(figure: Any) -> dict[str, tuple[float, float, float]]:
    """Approximate world joint positions from the 17-joint PoseCraft hierarchy."""
    spec = _spec(getattr(figure, "archetypeId", None) or (figure.get("archetypeId") if isinstance(figure, dict) else "adult-male"))
    pose = _pose_map(figure)
    origin_x = float((getattr(figure, "position", None) or (figure.get("position") if isinstance(figure, dict) else {}) or {}).get("x", 0.0))
    origin_z = float((getattr(figure, "position", None) or (figure.get("position") if isinstance(figure, dict) else {}) or {}).get("z", 0.0))
    yaw = float(getattr(figure, "rotationY", None) if not isinstance(figure, dict) else figure.get("rotationY", 0.0) or 0.0)
    scale = float(getattr(figure, "scale", None) if not isinstance(figure, dict) else figure.get("scale", 1.0) or 1.0)

    hip_h = (spec["upperLeg"] + spec["lowerLeg"]) * scale
    lower_torso = spec["torsoHeight"] * 0.42 * scale
    upper_torso = spec["torsoHeight"] * 0.38 * scale
    neck_len = spec["torsoHeight"] * 0.14 * scale
    head_r = spec["height"] * 0.07 * scale
    sh = spec["shoulderWidth"] * 0.5 * scale
    hh = spec["hipWidth"] * 0.5 * scale

    locals_off = {
        "pelvis": (0.0, hip_h, 0.0),
        "spine": (0.0, lower_torso, 0.0),
        "chest": (0.0, upper_torso, 0.0),
        "neck": (0.0, neck_len, 0.0),
        "head": (0.0, head_r * 0.95, 0.0),
        "leftShoulder": (-sh, spec["torsoHeight"] * 0.08 * scale, 0.0),
        "leftElbow": (0.0, -spec["upperArm"] * scale, 0.0),
        "leftWrist": (0.0, -spec["lowerArm"] * scale, 0.0),
        "rightShoulder": (sh, spec["torsoHeight"] * 0.08 * scale, 0.0),
        "rightElbow": (0.0, -spec["upperArm"] * scale, 0.0),
        "rightWrist": (0.0, -spec["lowerArm"] * scale, 0.0),
        "leftHip": (-hh, 0.0, 0.0),
        "leftKnee": (0.0, -spec["upperLeg"] * scale, 0.0),
        "leftAnkle": (0.0, -spec["lowerLeg"] * scale, 0.0),
        "rightHip": (hh, 0.0, 0.0),
        "rightKnee": (0.0, -spec["upperLeg"] * scale, 0.0),
        "rightAnkle": (0.0, -spec["lowerLeg"] * scale, 0.0),
    }
    parents = {
        "pelvis": None,
        "spine": "pelvis",
        "chest": "spine",
        "neck": "chest",
        "head": "neck",
        "leftShoulder": "chest",
        "leftElbow": "leftShoulder",
        "leftWrist": "leftElbow",
        "rightShoulder": "chest",
        "rightElbow": "rightShoulder",
        "rightWrist": "rightElbow",
        "leftHip": "pelvis",
        "leftKnee": "leftHip",
        "leftAnkle": "leftKnee",
        "rightHip": "pelvis",
        "rightKnee": "rightHip",
        "rightAnkle": "rightKnee",
    }

    world: dict[str, tuple[float, float, float]] = {}
    mats: dict[str, list[list[float]]] = {}
    root = _rot(0.0, yaw, 0.0)
    root_pos = (origin_x, 0.0, origin_z)

    order = [
        "pelvis", "spine", "chest", "neck", "head",
        "leftShoulder", "leftElbow", "leftWrist",
        "rightShoulder", "rightElbow", "rightWrist",
        "leftHip", "leftKnee", "leftAnkle",
        "rightHip", "rightKnee", "rightAnkle",
    ]
    for name in order:
        parent = parents[name]
        parent_m = root if parent is None else mats[parent]
        parent_p = root_pos if parent is None else world[parent]
        joint = pose.get(name, {"x": 0.0, "y": 0.0, "z": 0.0})
        local_m = _rot(joint["x"], joint["y"], joint["z"])
        mats[name] = _mul(parent_m, local_m)
        off = _apply(parent_m, locals_off[name])
        world[name] = (parent_p[0] + off[0], parent_p[1] + off[1], parent_p[2] + off[2])
    return world


def _flex(pose: dict[str, dict[str, float]], joint: str) -> float:
    return abs(pose.get(joint, {}).get("x", 0.0))


def infer_stance(world: dict[str, tuple[float, float, float]], pose: dict[str, dict[str, float]]) -> StanceType:
    pelvis_y = world.get("pelvis", (0, 1, 0))[1]
    chest = world.get("chest", (0, 1.4, 0))
    left_knee_y = world.get("leftKnee", (0, 0.5, 0))[1]
    right_knee_y = world.get("rightKnee", (0, 0.5, 0))[1]
    torso_horiz = abs(chest[1] - pelvis_y) < 0.28
    if pelvis_y < 0.28 and torso_horiz:
        return "prone"
    if min(left_knee_y, right_knee_y) < 0.18 and pelvis_y < 0.75:
        return "kneeling"
    if (_flex(pose, "leftHip") > 55 and _flex(pose, "rightHip") > 55) or (
        pelvis_y < 0.85 and (_flex(pose, "leftHip") > 40 or _flex(pose, "rightHip") > 40)
    ):
        return "sitting"
    if pelvis_y < 1.05 and (_flex(pose, "leftKnee") > 50 or _flex(pose, "rightKnee") > 50):
        return "crouching"
    return "standing"


def infer_support(world: dict[str, tuple[float, float, float]]) -> tuple[SupportLimb, SupportLimb, float, float, BalanceState, bool]:
    la = world.get("leftAnkle", (0, 0, 0))
    ra = world.get("rightAnkle", (0, 0, 0))
    pelvis = world.get("pelvis", (0, 1, 0))
    left_down = la[1] <= FLOOR_EPS
    right_down = ra[1] <= FLOOR_EPS
    if left_down and right_down:
        primary: SupportLimb = "both"
        secondary: SupportLimb = "both"
        wl, wr = 0.5, 0.5
    elif left_down:
        primary, secondary, wl, wr = "left_foot", "none", 1.0, 0.0
    elif right_down:
        primary, secondary, wl, wr = "right_foot", "none", 0.0, 1.0
    else:
        primary, secondary, wl, wr = "none", "none", 0.5, 0.5
    mid_x = (la[0] + ra[0]) / 2.0
    mid_z = (la[2] + ra[2]) / 2.0
    offset = math.hypot(pelvis[0] - mid_x, pelvis[2] - mid_z)
    if primary == "none":
        balance: BalanceState = "unsupported"
    elif offset > 0.38:
        balance = "unstable"
    else:
        balance = "stable"
    return primary, secondary, wl, wr, balance, left_down or right_down


def _primitive_aabb(prim: Any) -> tuple[str, str, str, float, float, float, float, float, float]:
    if hasattr(prim, "id"):
        pid = str(prim.id)
        name = str(prim.name or prim.kind or pid)
        kind = str(prim.kind or "block")
        pos = prim.position or {}
        size = prim.size or {}
        scale = float(prim.scale or 1.0)
    else:
        pid = str(prim.get("id") or "")
        name = str(prim.get("name") or prim.get("kind") or pid)
        kind = str(prim.get("kind") or "block")
        pos = prim.get("position") or {}
        size = prim.get("size") or {}
        scale = float(prim.get("scale") or 1.0)
    cx = float(pos.get("x", 0.0))
    cz = float(pos.get("z", 0.0))
    sx = float(size.get("x", 0.6)) * scale
    sy = float(size.get("y", 0.5)) * scale
    sz = float(size.get("z", 0.4)) * scale
    return pid, name, kind, cx, 0.0, cz, sx, sy, sz


def _near_box(point: tuple[float, float, float], box: tuple) -> tuple[bool, float, str]:
    _pid, name, kind, cx, _cy, cz, sx, sy, sz = box
    dx = abs(point[0] - cx) - sx / 2
    dz = abs(point[2] - cz) - sz / 2
    top = sy
    dy = point[1] - top
    planar = math.hypot(max(dx, 0.0), max(dz, 0.0))
    touching_top = planar <= CONTACT_XY and abs(dy) <= 0.22
    touching_side = planar <= 0.16 and 0.05 <= point[1] <= top + 0.15
    if touching_top:
        return True, abs(dy), "top"
    if touching_side:
        return True, planar, "side"
    return False, planar, ""


def build_contacts(
    world: dict[str, tuple[float, float, float]],
    primitives: list[Any],
    spatial_labels: list[str] | None = None,
) -> InteractionState:
    graph = ContactGraph()
    foot: list[str] = []
    hand: list[str] = []
    body: list[str] = []
    held: list[str] = []
    seated = False
    leaning = False
    boxes = [_primitive_aabb(p) for p in primitives or []]

    la, ra = world.get("leftAnkle"), world.get("rightAnkle")
    if la and la[1] <= FLOOR_EPS:
        graph.edges.append(ContactEdge(bodyPart="left_foot", targetId="floor", targetKind="floor", targetLabel="floor", relation="planted", confidence="known", distanceM=max(la[1], 0.0)))
        foot.append("left_foot → floor")
    if ra and ra[1] <= FLOOR_EPS:
        graph.edges.append(ContactEdge(bodyPart="right_foot", targetId="floor", targetKind="floor", targetLabel="floor", relation="planted", confidence="known", distanceM=max(ra[1], 0.0)))
        foot.append("right_foot → floor")

    probes = {
        "left_hand": world.get("leftWrist"),
        "right_hand": world.get("rightWrist"),
        "pelvis": world.get("pelvis"),
        "chest": world.get("chest"),
    }
    for part, point in probes.items():
        if not point:
            continue
        for box in boxes:
            hit, dist, rel = _near_box(point, box)
            if not hit:
                continue
            pid, name, kind, *_ = box
            edge = ContactEdge(
                bodyPart=part,
                targetId=pid,
                targetKind=kind,
                targetLabel=name,
                relation=(
                    "seated"
                    if part == "pelvis" and rel == "top" and point[1] <= 0.78
                    else ("leaning" if part == "chest" and rel == "side" else "contact")
                ),
                confidence="known" if dist < 0.12 else "uncertain",
                distanceM=dist,
            )
            graph.edges.append(edge)
            label = f"{part} → {name}"
            if "hand" in part:
                hand.append(label)
                if kind.startswith(("block", "table")) or "counter" in name.lower():
                    held.append(name)
            elif part == "pelvis" and rel == "top" and point[1] <= 0.78:
                seated = True
                body.append(label)
            elif part == "chest" and rel == "side":
                leaning = True
                body.append(label)
            else:
                body.append(label)

    reach = ""
    lw = world.get("leftWrist")
    rw = world.get("rightWrist")
    chest = world.get("chest")
    if rw and chest and rw[1] > chest[1] + 0.15:
        reach = "right hand raised"
    elif lw and chest and lw[1] > chest[1] + 0.15:
        reach = "left hand raised"
    elif hand:
        reach = "hands in contact"

    phrases = [p for p in (spatial_labels or []) if p]
    if phrases:
        for edge in graph.edges:
            if edge.targetKind == "floor" and any("floor" in p.lower() or "zone" in p.lower() for p in phrases):
                edge.targetLabel = next((p for p in phrases if "zone" in p.lower() or "floor" in p.lower()), edge.targetLabel)

    return InteractionState(
        groundContact=bool(foot),
        footContact=foot,
        handContact=hand,
        bodyToObject=body,
        seatedContact=seated,
        leaningContact=leaning,
        heldObjects=list(dict.fromkeys(held)),
        objectSupport=[e.targetLabel for e in graph.edges if e.relation in {"seated", "leaning"}],
        reachState=reach,
        gripConfidence="known" if hand else "insufficient_reference",
        graph=graph,
    )


def environment_from(
    primitives: list[Any],
    interaction: InteractionState,
    spatial: dict[str, Any] | None,
) -> EnvironmentRelationship:
    names = []
    kinds = []
    for prim in primitives or []:
        name = str(getattr(prim, "name", None) or (prim.get("name") if isinstance(prim, dict) else "") or "")
        kind = str(getattr(prim, "kind", None) or (prim.get("kind") if isinstance(prim, dict) else "") or "")
        if name:
            names.append(name)
        if kind:
            kinds.append(kind)
    walls = [n for n, k in zip(names, kinds) if "wall" in k]
    furniture = [n for n, k in zip(names, kinds) if any(tok in k for tok in ("table", "chair", "block"))]
    loc = ""
    phrases = []
    if spatial:
        loc = str(spatial.get("characterLocation") or "")
        phrases = list(spatial.get("zonePhrases") or [])[:8]
        if not loc and phrases:
            loc = phrases[0]
    floor = "planted" if interaction.groundContact else "off the floor"
    return EnvironmentRelationship(
        nearbyGeometry=names[:12],
        relevantProps=names[:12],
        floorRelationship=floor,
        wallRelationship=", ".join(walls) if walls else "none",
        furnitureRelationship=", ".join(furniture) if furniture else "none",
        obstacles=walls[:6],
        spatialConstraints=phrases[:6],
        characterLocation=loc,
        spatialPhrases=phrases,
    )


def build_character_state(figure: Any, world: dict[str, tuple[float, float, float]], revision: int) -> CharacterPoseState:
    pose = _pose_map(figure)
    pelvis = world.get("pelvis", (0.0, 1.0, 0.0))
    chest = world.get("chest", (0.0, 1.4, 0.0))
    head = world.get("head", (0.0, 1.7, 0.0))
    primary, secondary, wl, wr, balance, _ground = infer_support(world)
    stance = infer_stance(world, pose)
    if stance == "standing" and not _ground:
        balance = "unsupported"
    facing = float(getattr(figure, "rotationY", None) if not isinstance(figure, dict) else figure.get("rotationY", 0.0) or 0.0)
    chest_rot = pose.get("chest", {})
    tension = "extended" if max(_flex(pose, "leftElbow"), _flex(pose, "rightElbow")) < 20 else "flexed"
    return CharacterPoseState(
        characterId=getattr(figure, "characterId", None) if not isinstance(figure, dict) else figure.get("characterId"),
        identityId=getattr(figure, "identityId", None) if not isinstance(figure, dict) else figure.get("identityId"),
        figureId=str(getattr(figure, "id", None) or (figure.get("id") if isinstance(figure, dict) else "") or ""),
        figureName=str(getattr(figure, "name", None) or (figure.get("name") if isinstance(figure, dict) else "") or ""),
        archetypeId=str(getattr(figure, "archetypeId", None) or (figure.get("archetypeId") if isinstance(figure, dict) else "") or ""),
        poseId=getattr(figure, "poseId", None) if not isinstance(figure, dict) else figure.get("poseId"),
        poseLabel=getattr(figure, "poseLabel", None) if not isinstance(figure, dict) else figure.get("poseLabel"),
        poseRevision=revision,
        bodyOrientation=Vec3(x=0.0, y=facing, z=0.0),
        headOrientation=Vec3(x=_deg(pose.get("head", {}).get("x")), y=_deg(pose.get("head", {}).get("y")), z=_deg(pose.get("head", {}).get("z"))),
        torsoOrientation=Vec3(x=_deg(chest_rot.get("x")), y=_deg(chest_rot.get("y")), z=_deg(chest_rot.get("z"))),
        limbConfiguration=LimbConfiguration(
            leftKneeFlex=_flex(pose, "leftKnee"),
            rightKneeFlex=_flex(pose, "rightKnee"),
            leftElbowFlex=_flex(pose, "leftElbow"),
            rightElbowFlex=_flex(pose, "rightElbow"),
            leftHipFlex=_flex(pose, "leftHip"),
            rightHipFlex=_flex(pose, "rightHip"),
            spineBend=_flex(pose, "spine") + _flex(pose, "chest"),
        ),
        facingDirection=facing,
        centerOfMass=Vec3(x=pelvis[0], y=pelvis[1], z=pelvis[2]),
        primarySupport=primary,
        secondarySupport=secondary,
        weightLeft=wl,
        weightRight=wr,
        balance=balance,
        stance=stance,
        tension=tension,
        directionalMomentum="",
        momentumConfidence="insufficient_reference",
        worldOrigin=Vec3(x=_figure_origin(figure)[0], y=0.0, z=_figure_origin(figure)[1]),
    )


def production_constraints(character: CharacterPoseState, interaction: InteractionState, warnings: list[str]) -> ProductionConstraints:
    preserve_contact = list(interaction.handContact) + list(interaction.footContact)
    return ProductionConstraints(
        preserveContact=preserve_contact[:8],
        preserveSupportFoot=character.primarySupport,
        preserveFacing=True,
        preserveHandObject=list(interaction.heldObjects),
        preservePropPosition=list(interaction.heldObjects),
        preserveScenePlacement=True,
        preserveMomentum=False,
        forbiddenDiscontinuity=[
            "support foot teleport",
            "unexpected hand detach",
            "orientation jump",
        ],
        continuityRisk=list(warnings),
        stylizationOverride=False,
        creatorIntentHonored=True,
    )


def summarize(character: CharacterPoseState, interaction: InteractionState, motion: MotionInterpretation, warnings: list[str]) -> tuple[str, str]:
    support = character.primarySupport.replace("_", " ")
    contact = interaction.handContact[0] if interaction.handContact else "no hand contact"
    motion_txt = motion.rotationDirection or motion.outgoingMovement or "static"
    risk = warnings[0] if warnings else "none"
    summary = (
        f"Balance: {character.balance.capitalize()}. "
        f"Primary support: {support}. "
        f"Contact: {contact}. "
        f"Motion: {motion_txt}."
    )
    details = (
        f"Stance {character.stance}. "
        f"Weight L {character.weightLeft:.0%} / R {character.weightRight:.0%}. "
        f"Risk: {risk}."
    )
    return summary, details


def pose_cache_key(
    project_id: str,
    revision: int,
    figure: Any,
    primitives: list[Any],
    spatial_fp: str = "",
    image_asset_id: str = "",
) -> str:
    pose = _pose_map(figure)
    prim_ids = []
    for prim in primitives or []:
        if hasattr(prim, "id"):
            prim_ids.append(f"{prim.id}:{getattr(prim, 'position', {})}:{getattr(prim, 'size', {})}")
        elif isinstance(prim, dict):
            prim_ids.append(f"{prim.get('id')}:{prim.get('position')}:{prim.get('size')}")
    raw = json.dumps(
        {
            "projectId": project_id,
            "revision": revision,
            "figureId": getattr(figure, "id", None) if not isinstance(figure, dict) else figure.get("id"),
            "pose": pose,
            "yaw": getattr(figure, "rotationY", None) if not isinstance(figure, dict) else figure.get("rotationY"),
            "pos": getattr(figure, "position", None) if not isinstance(figure, dict) else figure.get("position"),
            "primitives": prim_ids,
            "spatial": spatial_fp,
            "imageAssetId": image_asset_id,
            "schema": POSE_ANALYSIS_VERSION,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compare_worlds(
    a_world: dict[str, tuple[float, float, float]],
    b_world: dict[str, tuple[float, float, float]],
    a_char: CharacterPoseState,
    b_char: CharacterPoseState,
    a_ix: InteractionState,
    b_ix: InteractionState,
) -> tuple[list[PoseChange], list[str], MotionInterpretation]:
    changes: list[PoseChange] = []
    warnings: list[str] = []

    def _add(kind, summary, src="", dst="", severity="minor"):
        changes.append(PoseChange(kind=kind, summary=summary, fromValue=src, toValue=dst, severity=severity, confidence="known"))

    a_feet = {e.bodyPart for e in a_ix.graph.edges if "foot" in e.bodyPart}
    b_feet = {e.bodyPart for e in b_ix.graph.edges if "foot" in e.bodyPart}
    for part in b_feet - a_feet:
        _add("foot_planted", f"{part} planted")
    for part in a_feet - b_feet:
        _add("foot_released", f"{part} released")

    a_hands = {(e.bodyPart, e.targetId) for e in a_ix.graph.edges if "hand" in e.bodyPart}
    b_hands = {(e.bodyPart, e.targetId) for e in b_ix.graph.edges if "hand" in e.bodyPart}
    for edge in b_hands - a_hands:
        _add("contact_gained", f"{edge[0]} contacted {edge[1]}")
    for edge in a_hands - b_hands:
        _add("contact_lost", f"{edge[0]} left {edge[1]}", severity="moderate")
        warnings.append(f"Potential physical discontinuity: {edge[0]} detached from {edge[1]}")

    if a_char.primarySupport != b_char.primarySupport:
        _add("support_changed", "Primary support changed", a_char.primarySupport, b_char.primarySupport, "moderate")

    yaw_delta = abs(((b_char.facingDirection - a_char.facingDirection + 180) % 360) - 180)
    if yaw_delta >= YAW_JUMP_DEG:
        _add("facing_changed", "Character orientation jumped", str(a_char.facingDirection), str(b_char.facingDirection), "major")
        warnings.append("Potential physical discontinuity: character orientation jumped unexpectedly")
    elif yaw_delta > 8:
        _add("body_rotated", f"Torso turned {yaw_delta:.0f}°", severity="none")

    a_p = a_world.get("pelvis", (0, 0, 0))
    b_p = b_world.get("pelvis", (0, 0, 0))
    travel = math.hypot(b_p[0] - a_p[0], b_p[2] - a_p[2])
    if travel > 0.08:
        _add("character_translated", f"Character moved {travel:.2f}m")

    for side, joint in (("left", "leftAnkle"), ("right", "rightAnkle")):
        a_a = a_world.get(joint)
        b_a = b_world.get(joint)
        if not a_a or not b_a:
            continue
        planted = f"{side}_foot" in {p.replace("left_foot", "left").replace("right_foot", "right") for p in a_feet} or (
            (side == "left" and a_char.primarySupport in {"left_foot", "both"})
            or (side == "right" and a_char.primarySupport in {"right_foot", "both"})
        )
        jump = math.hypot(b_a[0] - a_a[0], b_a[2] - a_a[2])
        if planted and jump > TELEPORT_M:
            _add("discontinuity", f"{side} support foot teleported {jump:.2f}m", severity="major")
            warnings.append(f"Potential physical discontinuity: {side} support foot teleported")

    if a_char.stance in {"standing", "crouching"} and not b_ix.groundContact:
        if b_char.stance in {"sitting", "kneeling", "prone"}:
            _add("support_changed", f"Stance changed to {b_char.stance}", a_char.stance, b_char.stance, "minor")
        else:
            warnings.append("Potential physical discontinuity: standing character lost floor contact")
            _add("discontinuity", "Lost floor contact", severity="major")

    if a_ix.seatedContact and not b_ix.seatedContact and b_char.centerOfMass.y > 1.05:
        warnings.append("Potential physical discontinuity: seated pose left its support")

    chest_yaw = abs(((b_char.torsoOrientation.y - a_char.torsoOrientation.y + 180) % 360) - 180)
    rot_dir = ""
    if chest_yaw > 6 or yaw_delta > 6:
        delta = ((b_char.facingDirection - a_char.facingDirection + 540) % 360) - 180
        rot_dir = "clockwise torso turn" if delta < 0 else "counter-clockwise torso turn"

    a_to_b = (b_p[0] - a_p[0], b_p[2] - a_p[2])
    incoming = ""
    if travel > 0.08:
        incoming = "forward" if a_to_b[1] < 0 else "lateral step"

    planted = b_char.primarySupport.replace("_", " ")
    moving = ""
    if "left" in b_char.primarySupport and b_char.secondarySupport != "right_foot":
        moving = "right leg"
    elif "right" in b_char.primarySupport and b_char.secondarySupport != "left_foot":
        moving = "left leg"

    motion = MotionInterpretation(
        incomingMovement=incoming,
        outgoingMovement=incoming or rot_dir or "hold",
        motionDirection=incoming,
        rotationDirection=rot_dir,
        plantedLimb=planted,
        movingLimb=moving,
        transitionState="turning" if rot_dir else ("stepping" if incoming else "hold"),
        unfinishedAction="" if travel < 0.4 else "travel incomplete",
        likelyContinuation=rot_dir or incoming or "hold pose",
        discontinuityWarnings=list(warnings),
        confidence="known" if changes else "uncertain",
    )
    if a_char.stance == b_char.stance and travel < 0.05 and yaw_delta < 8 and not (b_hands ^ a_hands):
        _add("pose_converged", "Pose remained consistent", severity="none")
    elif warnings:
        _add("pose_diverged", "Pose changed with continuity risk", severity="moderate")
    return changes, warnings, motion


def plausibility_static(character: CharacterPoseState, interaction: InteractionState, primitives: list[Any]) -> list[str]:
    warnings: list[str] = []
    if character.stance == "standing" and not interaction.groundContact:
        warnings.append("Potential physical discontinuity: standing character lost floor contact")
    if character.stance == "sitting" and not interaction.seatedContact and character.centerOfMass.y > 0.95:
        warnings.append("Potential physical discontinuity: seated pose floats above furniture")
    if character.stance == "leaning" and not interaction.leaningContact:
        warnings.append("Potential physical discontinuity: character leans without support")
    if character.balance == "unsupported" and character.stance == "standing":
        warnings.append("Potential physical discontinuity: no support foot on the floor")
    if character.primarySupport == "none" and character.stance in {"standing", "crouching"}:
        warnings.append("Weight shift is inconsistent with stance")
    pelvis = (character.centerOfMass.x, character.centerOfMass.y, character.centerOfMass.z)
    for prim in primitives or []:
        box = _primitive_aabb(prim)
        pid, name, kind, cx, _cy, cz, sx, sy, sz = box
        if "wall" in kind or "table" in kind or "block" in kind:
            inside = abs(pelvis[0] - cx) < sx * 0.25 and abs(pelvis[2] - cz) < sz * 0.25 and 0.15 < pelvis[1] < sy
            if inside:
                warnings.append(f"Potential physical discontinuity: body may pass through {name}")
    return warnings
