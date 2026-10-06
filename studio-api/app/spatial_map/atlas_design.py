"""GPT Image 2 Atlas design prompt + packet-alignment checks.

The Environment Design Packet is spatial authority. The generated Atlas is
its visualization. Pixel-perfect geometry is not required.
"""

from __future__ import annotations

from typing import Any

from .scene_intent import EnvironmentDesignPacket, SceneIntent, compile_environment_design, coerce_scene_intent


ATLAS_DESIGN_PREFIX = (
    "Create a roofless orthographic top-down Atlas for spatial planning. "
    "Strict top-down / overhead view. Roof removed. Clear walls. Clear door openings. "
    "Clean navigable floor. No eye-level camera. No cinematic perspective. "
    "No perspective corridor shot. Suitable for a 1-meter Spatial Map grid."
)


def compile_atlas_design_prompt(
    intent: SceneIntent | dict[str, Any] | None,
    *,
    look_suffix: str = "",
    style_reference: bool = False,
) -> str:
    """Compile a specialized Atlas prompt from the live design packet."""
    scene = coerce_scene_intent(intent)
    packet = scene.environmentDesign if scene is not None else None
    if packet is None and scene is not None:
        packet = compile_environment_design(scene.summary)
    if packet is None:
        packet = EnvironmentDesignPacket()

    parts = [ATLAS_DESIGN_PREFIX]
    env = (packet.environmentType or (scene.summary if scene else "") or "").strip()
    if env:
        parts.append(f"Environment: {env}.")
    layout_bits: list[str] = []
    width = packet.dimensions.widthMeters
    depth = packet.dimensions.depthMeters
    if width and depth:
        layout_bits.append(f"main space approximately {width:g} meters wide and {depth:g} meters long")
    elif width:
        layout_bits.append(f"approximately {width:g} meters wide")
    elif depth:
        layout_bits.append(f"approximately {depth:g} meters long")
    for zone in packet.zones:
        label = zone.label or zone.type
        if not label:
            continue
        bit = label
        if zone.orientation:
            bit += f" oriented {zone.orientation.replace('_', '-')}"
        layout_bits.append(bit)
    for anchor in packet.anchors:
        label = anchor.label or anchor.type
        if not label:
            continue
        bit = label
        if anchor.wall:
            bit += f" on the {anchor.wall} wall"
        if anchor.location:
            bit += f" at the {anchor.location.replace('_', ' ')}"
        if anchor.distanceMeters:
            bit += f" approximately {anchor.distanceMeters:g} meters along the space"
        layout_bits.append(bit)
    if layout_bits:
        parts.append("Spatial layout: " + "; ".join(layout_bits) + ".")
    appearance_bits: list[str] = []
    if packet.appearance.materials:
        appearance_bits.extend(packet.appearance.materials)
    if packet.appearance.style:
        appearance_bits.append(packet.appearance.style)
    if scene is not None:
        appearance_bits.extend(scene.environmentTraits)
    if appearance_bits:
        parts.append("Appearance: " + ", ".join(dict.fromkeys(appearance_bits)) + ".")
    if style_reference:
        parts.append(
            "Use the attached image only for materials, colors, architectural style, "
            "and atmosphere. Do not treat it as an authoritative floorplan."
        )
    if look_suffix.strip():
        parts.append(look_suffix.strip())
    return " ".join(parts)


LOCAL_ATLAS_DESIGN_PREFIX = (
    "STRICT ROOFLESS ORTHOGRAPHIC TOP-DOWN SPATIAL ATLAS. "
    "PAINT the supplied top-down spatial layout as a photorealistic "
    "roofless environment Atlas. Replace every flat CAD color with real materials. "
    "The supplied structural guide is topology authority only — keep its shape, "
    "openings, paths, and landmarks, but do not return the diagram itself. "
    "Do not move walls, openings, doors, rooms, paths, or anchors. "
    "STRICT top-down / orthographic. Roofless. Clear floor. Clear walls. "
    "Clean spatial planning view. Photoreal materials. "
    "Do not draw a measurement grid, CAD dimensions, title block, or schematic symbols. "
    "No color-block floorplan. No labeled diagram. "
    "No eye-level view. No first-person corridor view. No cinematic perspective. "
    "No vanishing-point perspective. No exterior camera. "
    "No grid overlay on a perspective photograph."
)

LOCAL_ATLAS_FORBIDDEN = (
    "Forbidden: CAD floorplan, blueprint, schematic line drawing, title block, "
    "dimension arrows, watermarks, eye-level corridor, first-person view, "
    "cinematic perspective, vanishing-point hallway, exterior establishing shot, "
    "original photograph with overlays, point-cloud splat, blueprint treatment "
    "of a perspective photo."
)


def local_atlas_aspect(intent: SceneIntent | dict[str, Any] | None) -> str:
    """Prefer a tall plate for long corridors so Local T2I can draw length."""
    scene = coerce_scene_intent(intent)
    packet = scene.environmentDesign if scene is not None else None
    blob = " ".join(
        [
            (scene.summary if scene else "") or "",
            (packet.environmentType if packet else "") or "",
            " ".join((z.type or "") + " " + (z.label or "") for z in (packet.zones if packet else [])),
        ]
    ).lower()
    if "corridor" in blob or "hallway" in blob:
        return "9:16"
    return "1:1"


def compile_local_atlas_design_prompt(
    intent: SceneIntent | dict[str, Any] | None,
    *,
    look_suffix: str = "",
    style_reference: bool = False,
) -> str:
    """Local Atlas adapter: same packet as GPT, stricter camera-forbidden language.

    Description / packet is layout authority. A reference is appearance only.
    Does not ask a model to rotate an eye-level photograph into a floorplan.
    """
    scene = coerce_scene_intent(intent)
    packet = scene.environmentDesign if scene is not None else None
    if packet is None and scene is not None:
        packet = compile_environment_design(scene.summary)
    if packet is None:
        packet = EnvironmentDesignPacket()

    shared = compile_atlas_design_prompt(
        intent,
        look_suffix="",
        style_reference=False,
    )
    shared_body = shared[len(ATLAS_DESIGN_PREFIX):].strip() if shared.startswith(ATLAS_DESIGN_PREFIX) else shared
    parts = [LOCAL_ATLAS_DESIGN_PREFIX]
    if shared_body:
        parts.append(shared_body)
    creator = ""
    if scene is not None:
        creator = (scene.sourcePromptSummary or scene.summary or "").strip()
    if creator:
        parts.append(f"Layout authority from the creator description: {creator}")
    if style_reference:
        parts.append(
            "Use the appearance reference only for materials and visual identity. "
            "Do not copy the reference camera, eye-level perspective, or vanishing point."
        )
    env_class = (packet.environmentClass or "interior") if packet is not None else "interior"
    if env_class == "exterior":
        parts.append(
            "This is an exterior site-plan Atlas. Preserve terrain zones, water, "
            "paths, clearings, and landmarks exactly as the structural guide shows."
        )
    parts.append(
        "DO NOT: return eye-level perspective, return the reference camera, "
        "redesign the floorplan, mirror the layout, invent major rooms, "
        "or replace the layout with decorative patterns."
    )
    parts.append(LOCAL_ATLAS_FORBIDDEN)
    if look_suffix.strip():
        parts.append(look_suffix.strip())
    return " ".join(parts)


def packet_alignment_report(
    packet: EnvironmentDesignPacket | None,
    *,
    prompt: str = "",
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Practical alignment of the compiled prompt/job with the design packet.

    Does not require pixel-perfect geometry. Catastrophic missing named
    anchors or inverted proportions fail.
    """
    if packet is None:
        return {"ok": True, "failCode": "PASS", "reason": "No structured design packet to compare."}
    reasons: list[str] = []
    haystack = (prompt or "").lower()
    if packet.environmentType and packet.environmentType.lower() not in haystack:
        if not any(token in haystack for token in packet.environmentType.lower().split() if len(token) > 3):
            reasons.append("The Atlas prompt dropped the environment type.")
    named = [a for a in packet.anchors if (a.label or a.type)]
    missing = [a.label or a.type for a in named if (a.label or a.type).lower() not in haystack]
    if missing:
        reasons.append("Named places are missing from the Atlas prompt: " + ", ".join(missing[:4]))
    if packet.dimensions.widthMeters and packet.dimensions.depthMeters and width and height:
        intended = packet.dimensions.widthMeters / max(packet.dimensions.depthMeters, 0.001)
        rendered = float(width) / max(float(height), 1.0)
        if intended > 1.6 and rendered < 0.7:
            reasons.append("The Atlas proportions are rotated relative to the requested corridor.")
        if intended < 0.6 and rendered > 1.5:
            reasons.append("The Atlas proportions are rotated relative to the requested corridor.")
    if reasons:
        return {
            "ok": False,
            "failCode": "FAIL_PACKET_ALIGNMENT",
            "reason": " ".join(reasons),
        }
    return {
        "ok": True,
        "failCode": "PASS",
        "reason": "The Atlas prompt reflects the environment design.",
    }
