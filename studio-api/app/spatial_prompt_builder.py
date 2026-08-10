from __future__ import annotations

"""Assemble editable spatial prompt layers from Scene Avatars."""

from typing import Any, Optional

from .spatial_scene import PromptLayers, SceneAvatar, SceneState, SpatialSceneDoc, resolve_avatars_for_state


def _label(a: SceneAvatar) -> str:
    return a.label or a.initials or a.entity_type


def _active_state(doc: SpatialSceneDoc, state_id: str | None = None) -> SceneState | None:
    sid = state_id or doc.active_state_id
    return next((s for s in doc.states if s.id == sid), None)


def build_lighting_layer(
    doc: SpatialSceneDoc,
    *,
    state_id: str | None = None,
    avatars: list[SceneAvatar] | None = None,
) -> str:
    """Aggregate SceneState.lighting + light avatar prompts into the lighting layer."""
    resolved = avatars if avatars is not None else resolve_avatars_for_state(doc, state_id)
    bits: list[str] = []
    state = _active_state(doc, state_id)
    if state and (state.lighting or "").strip():
        bits.append(state.lighting.strip())
    for a in resolved:
        if a.entity_type != "light":
            continue
        label = _label(a)
        detail = (a.spatial_prompt or "").strip()
        if detail:
            bits.append(f"{label}: {detail}")
        else:
            bits.append(f"{label} at map position ({a.x:.0f}, {a.y:.0f}).")
    return "\n".join(bits)


def _facing_text(a: SceneAvatar, by_id: dict[str, SceneAvatar]) -> str:
    mode = a.facing.mode
    if mode == "face_avatar" and a.facing.target_avatar_id:
        other = by_id.get(a.facing.target_avatar_id)
        return f"faces {_label(other) if other else 'another avatar'}"
    if mode == "face_camera":
        return "faces the camera"
    if mode == "face_object" and a.facing.target_avatar_id:
        other = by_id.get(a.facing.target_avatar_id)
        return f"faces {_label(other) if other else 'an object'}"
    if mode == "look_left":
        return "looks left"
    if mode == "look_right":
        return "looks right"
    if mode == "over_shoulder":
        return "looks over the shoulder"
    if mode == "back_to_camera":
        return "has back to camera"
    if mode == "three_quarter_camera":
        return "is three-quarters toward the camera"
    if a.facing.compass:
        return f"faces {a.facing.compass}"
    return f"oriented at {a.rotation:.0f}°"


def _relation_text(a: SceneAvatar, by_id: dict[str, SceneAvatar]) -> list[str]:
    out = []
    for r in a.relationships or []:
        other = by_id.get(r.to_id)
        out.append(f"{_label(a)} {r.type.replace('_', ' ')} {_label(other) if other else r.to_id}")
    return out


def build_spatial_composition(doc: SpatialSceneDoc, state_id: str | None = None) -> str:
    avatars = resolve_avatars_for_state(doc, state_id)
    by_id = {a.id: a for a in avatars}
    chars = [a for a in avatars if a.entity_type == "character"]
    cams = [a for a in avatars if a.entity_type == "camera"]
    props = [a for a in avatars if a.entity_type in ("prop", "architecture", "vehicle")]
    lines: list[str] = ["SPATIAL COMPOSITION"]

    for a in chars:
        pos = f"at map position ({a.x:.0f}, {a.y:.0f})"
        face = _facing_text(a, by_id)
        extra = []
        if a.wardrobe:
            extra.append(f"wardrobe: {a.wardrobe}")
        if a.pose:
            extra.append(f"pose: {a.pose}")
        if a.expression:
            extra.append(f"expression: {a.expression}")
        if a.continuity == "locked":
            extra.append("continuity locked")
        line = f"{_label(a)} stands {pos}, {face}."
        if extra:
            line += " (" + "; ".join(extra) + ")"
        lines.append(line)
        lines.extend(_relation_text(a, by_id))

    for a in props:
        st = a.door_state or a.prop_state
        lines.append(
            f"{_label(a)} ({a.entity_type}) at ({a.x:.0f}, {a.y:.0f})"
            + (f", state: {st}" if st else "")
            + "."
        )

    for a in cams:
        cam = a.camera
        if not cam:
            lines.append(f"Camera {_label(a)} at ({a.x:.0f}, {a.y:.0f}).")
            continue
        focus = ", ".join(_label(by_id[t]) for t in cam.focus_targets if t in by_id) or "scene"
        lines.append(
            f"Camera {_label(a)} is at ({a.x:.0f}, {a.y:.0f}), height {cam.height_m} m, "
            f"{cam.lens_mm:g} mm lens, FOV {cam.fov_deg:g}°, {cam.shot_size} shot, focus on {focus}, "
            f"rig {cam.rig}, movement {cam.movement}, aspect {cam.aspect}."
        )

    if doc.notes.strip():
        lines.append(f"Set notes: {doc.notes.strip()}")

    return "\n".join(lines)


def default_negative_spatial(avatars: list[SceneAvatar]) -> str:
    chars = [a for a in avatars if a.entity_type == "character"]
    bits = [
        "Do not reverse character screen positions.",
        "Do not duplicate characters.",
        "Do not relocate architecture or doors without cause.",
    ]
    if len(chars) >= 2:
        bits.append(
            f"Do not reverse {_label(chars[0])} and {_label(chars[1])}."
        )
        bits.append(f"Do not place {_label(chars[0])} behind {_label(chars[1])} unless staged.")
    return " ".join(bits)


def assemble_prompt_layers(
    doc: SpatialSceneDoc,
    *,
    state_id: str | None = None,
    profile_blurbs: dict[str, str] | None = None,
    style: str = "",
) -> PromptLayers:
    avatars = resolve_avatars_for_state(doc, state_id)
    by_id = {a.id: a for a in avatars}
    profile_blurbs = profile_blurbs or {}

    identity_bits = []
    perf_bits = []
    for a in avatars:
        if a.entity_type != "character":
            continue
        blurb = profile_blurbs.get(a.profile_id or "", "")
        identity_bits.append(f"{_label(a)}: {blurb or a.spatial_prompt or 'character identity from profile'}")
        if a.expression or a.pose:
            perf_bits.append(f"{_label(a)} performance: {a.expression or ''} {a.pose or ''}".strip())

    props = [a for a in avatars if a.entity_type in ("prop", "architecture", "vehicle")]
    prop_text = "; ".join(
        f"{_label(a)}" + (f" ({a.door_state or a.prop_state})" if (a.door_state or a.prop_state) else "")
        for a in props
    )

    cams = [a for a in avatars if a.entity_type == "camera"]
    cam_text = build_spatial_composition(doc, state_id)
    # Prefer camera-only subset for camera layer
    cam_lines = [ln for ln in cam_text.splitlines() if ln.lower().startswith("camera")]
    spatial = build_spatial_composition(doc, state_id)
    lighting = build_lighting_layer(doc, state_id=state_id, avatars=avatars)

    layers = doc.prompt_layers.model_copy(deep=True)
    if not layers.spatial.strip():
        layers.spatial = spatial
    if not layers.identity.strip():
        layers.identity = "\n".join(identity_bits)
    if not layers.performance.strip():
        layers.performance = "\n".join(perf_bits)
    if not layers.camera.strip():
        layers.camera = "\n".join(cam_lines) if cam_lines else (cams[0].spatial_prompt if cams else "")
    if not layers.props.strip():
        layers.props = prop_text
    if not layers.environment.strip() and doc.notes:
        layers.environment = doc.notes
    if not layers.lighting.strip() and lighting.strip():
        layers.lighting = lighting
    if style and not layers.style.strip():
        layers.style = style
    if not layers.negative_spatial.strip():
        layers.negative_spatial = default_negative_spatial(avatars)
    if not layers.scene.strip():
        layers.scene = doc.notes or "Cinematic scene staged from spatial map."
    return layers


def flatten_layers(layers: PromptLayers) -> tuple[str, str]:
    positive = "\n\n".join(
        block
        for block in [
            layers.scene,
            layers.identity,
            layers.performance,
            layers.spatial,
            layers.camera,
            layers.environment,
            layers.props,
            layers.lighting,
            layers.style,
        ]
        if block and block.strip()
    )
    negative = "\n".join(
        b for b in [layers.negative_identity, layers.negative_spatial] if b and b.strip()
    )
    return positive.strip(), negative.strip()


def guidance_hint(level: str) -> str:
    if level == "strict":
        return (
            "STRICT spatial guidance: preserve character positions, facing, camera side, "
            "relative distances, and prop/door placement."
        )
    if level == "loose":
        return "LOOSE spatial guidance: use the map as compositional inspiration only."
    return (
        "BALANCED spatial guidance: preserve major character positions, orientation, "
        "camera direction, and key background elements."
    )
