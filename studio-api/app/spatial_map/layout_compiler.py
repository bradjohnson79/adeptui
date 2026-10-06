"""Deterministic Interior / Exterior Spatial Layout Compiler.

The Environment Design Packet is semantic authority. This module compiles
that packet into a shared layout IR and paints a top-down structural guide.
No diffusion model is used. Maker.js is not added — the backend is Python
and an internal PIL renderer is already the product path.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from .scene_intent import (
    EnvironmentDesignPacket,
    compile_environment_design,
    normalize_environment_class,
)


class LayoutPrimitive(BaseModel):
    kind: Literal["region", "path", "opening", "landmark", "wall", "label"]
    type: str = ""
    label: str = ""
    x: float = 0.5
    y: float = 0.5
    w: float = 0.2
    h: float = 0.2
    x2: float | None = None
    y2: float | None = None
    r: float | None = None
    side: str = ""
    along: float = 0.5
    color: str = ""


class SpatialLayout(BaseModel):
    environmentClass: Literal["interior", "exterior"]
    subtype: str = ""
    widthMeters: float | None = None
    depthMeters: float | None = None
    north: Literal["top"] = "top"
    primitives: list[LayoutPrimitive] = Field(default_factory=list)
    cacheKey: str = ""


def compile_spatial_layout(
    packet: EnvironmentDesignPacket | dict[str, Any] | None,
    *,
    description: str = "",
    environment_class: str = "",
) -> SpatialLayout:
    """Compile a deterministic layout IR. Does not invent unmentioned rooms."""
    if packet is None:
        packet = compile_environment_design(
            description,
            environment_class=environment_class,
        )
    elif isinstance(packet, dict):
        packet = EnvironmentDesignPacket.model_validate(packet)
    env_class = normalize_environment_class(environment_class or packet.environmentClass)
    if env_class == "exterior":
        layout = _compile_exterior(packet, description)
    else:
        layout = _compile_interior(packet, description)
    payload = layout.model_dump(exclude={"cacheKey"})
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    layout.cacheKey = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return layout


def _compile_interior(packet: EnvironmentDesignPacket, description: str) -> SpatialLayout:
    types = {str(z.type or "").lower() for z in packet.zones}
    blob = f"{description} {packet.environmentSubtype} {packet.environmentType}".lower()
    is_corridor = "corridor" in types or "hallway" in blob or packet.environmentSubtype == "corridor"
    primitives: list[LayoutPrimitive] = []
    if is_corridor:
        primitives.append(
            LayoutPrimitive(
                kind="region",
                type="corridor",
                label="corridor",
                x=0.33,
                y=0.08,
                w=0.34,
                h=0.84,
                color="floor",
            )
        )
        primitives.append(
            LayoutPrimitive(kind="wall", type="wall", x=0.33, y=0.08, w=0.34, h=0.84, color="wall")
        )
    else:
        primitives.append(
            LayoutPrimitive(
                kind="region",
                type="room",
                label=packet.environmentSubtype or "room",
                x=0.10,
                y=0.10,
                w=0.80,
                h=0.80,
                color="floor",
            )
        )
        primitives.append(
            LayoutPrimitive(kind="wall", type="wall", x=0.10, y=0.10, w=0.80, h=0.80, color="wall")
        )
    for zone in packet.zones:
        ztype = (zone.type or "").lower()
        if ztype in {"corridor", "hallway"}:
            continue
        if ztype in {"room", "chamber"}:
            side = "right" if "right" in (zone.orientation or "").lower() or "combat" in (zone.label or "").lower() else "right"
            primitives.append(
                LayoutPrimitive(
                    kind="region",
                    type="room",
                    label=zone.label or zone.type,
                    x=0.67 if side == "right" else 0.08,
                    y=0.38,
                    w=0.22,
                    h=0.24,
                    color="room",
                )
            )
    for anchor in packet.anchors:
        kind = (anchor.type or "").lower()
        label = (anchor.label or "").lower()
        wall = (anchor.wall or "").lower()
        location = (anchor.location or "").lower()
        if kind == "elevator" or "elevator" in label:
            primitives.append(
                LayoutPrimitive(
                    kind="opening",
                    type="elevator",
                    label=anchor.label or "elevator",
                    side="end",
                    along=0.08,
                    color="opening",
                )
            )
        elif kind in {"door", "entrance", "opening", "doorway"} or "door" in label or "chamber" in label:
            side = "right" if wall in {"right", "east"} else "left" if wall in {"left", "west"} else "right"
            along = 0.50 if location in {"midpoint", "middle"} else 0.55
            primitives.append(
                LayoutPrimitive(
                    kind="opening",
                    type="doorway",
                    label=anchor.label or "door",
                    side=side,
                    along=along,
                    color="opening",
                )
            )
        elif kind in {"stairs", "stair"}:
            primitives.append(
                LayoutPrimitive(
                    kind="landmark",
                    type="stairs",
                    label=anchor.label or "stairs",
                    x=0.42,
                    y=0.78,
                    w=0.16,
                    h=0.08,
                    color="stairs",
                )
            )
        elif kind == "guidance" or "yellow" in label or "strip" in label:
            primitives.append(
                LayoutPrimitive(
                    kind="path",
                    type="guidance_strip",
                    label=anchor.label or "yellow guidance strip",
                    side="right",
                    along=0.5,
                    color="yellow",
                )
            )
    for path in packet.paths:
        if (path.type or "").lower() in {"guidance", "guidance_strip"} or "yellow" in (path.label or "").lower():
            if not any(p.type == "guidance_strip" for p in primitives):
                primitives.append(
                    LayoutPrimitive(
                        kind="path",
                        type="guidance_strip",
                        label=path.label or "yellow guidance strip",
                        side="right",
                        along=0.5,
                        color="yellow",
                    )
                )
    if is_corridor and "yellow" in blob and not any(p.type == "guidance_strip" for p in primitives):
        primitives.append(
            LayoutPrimitive(
                kind="path",
                type="guidance_strip",
                label="yellow guidance strip",
                side="right",
                along=0.5,
                color="yellow",
            )
        )
    return SpatialLayout(
        environmentClass="interior",
        subtype=packet.environmentSubtype or ("corridor" if is_corridor else "room"),
        widthMeters=packet.dimensions.widthMeters,
        depthMeters=packet.dimensions.depthMeters,
        primitives=primitives,
    )


def _compile_exterior(packet: EnvironmentDesignPacket, description: str) -> SpatialLayout:
    blob = f"{description} {packet.environmentSubtype} {packet.environmentType}".lower()
    primitives: list[LayoutPrimitive] = [
        LayoutPrimitive(
            kind="region",
            type="vegetation",
            label="forest",
            x=0.04,
            y=0.04,
            w=0.92,
            h=0.92,
            color="forest",
        )
    ]
    zone_types = {str(z.type or "").lower() for z in packet.zones}
    if "clearing" in zone_types or "clearing" in blob:
        primitives.append(
            LayoutPrimitive(
                kind="region",
                type="clearing",
                label="clearing",
                x=0.38,
                y=0.36,
                w=0.24,
                h=0.24,
                r=0.13,
                color="clearing",
            )
        )
    if "water" in zone_types or any(t in blob for t in ("river", "stream", "lake")):
        west = "west" in blob or any("west" in (z.orientation or "") for z in packet.zones)
        primitives.append(
            LayoutPrimitive(
                kind="path",
                type="river",
                label="river",
                x=0.14 if west else 0.82,
                y=0.08,
                x2=0.16 if west else 0.84,
                y2=0.92,
                color="water",
            )
        )
    if "elevation" in zone_types or "hill" in blob:
        primitives.append(
            LayoutPrimitive(
                kind="region",
                type="elevation",
                label="rocky hill",
                x=0.28,
                y=0.06,
                w=0.44,
                h=0.16,
                color="hill",
            )
        )
    if "field" in zone_types:
        primitives.append(
            LayoutPrimitive(
                kind="region",
                type="field",
                label="open field",
                x=0.22,
                y=0.28,
                w=0.56,
                h=0.40,
                color="field",
            )
        )
    for path in packet.paths:
        ptype = (path.type or "").lower()
        if ptype in {"trail", "path", "road"} or "trail" in (path.label or "").lower():
            orientation = (path.orientation or path.from_ or "").lower()
            start = (0.78, 0.86) if "south" in orientation or "east" in orientation else (0.20, 0.86)
            primitives.append(
                LayoutPrimitive(
                    kind="path",
                    type="trail",
                    label=path.label or "trail",
                    x=start[0],
                    y=start[1],
                    x2=0.50,
                    y2=0.50,
                    color="trail",
                )
            )
    if ("trail" in blob or "path" in blob) and not any(p.type == "trail" for p in primitives):
        primitives.append(
            LayoutPrimitive(
                kind="path",
                type="trail",
                label="dirt trail",
                x=0.78,
                y=0.86,
                x2=0.50,
                y2=0.50,
                color="trail",
            )
        )
    for anchor in packet.anchors:
        kind = (anchor.type or "").lower()
        loc = (anchor.location or "").lower()
        x, y = 0.66, 0.28
        if "northeast" in loc or loc == "ne":
            x, y = 0.68, 0.24
        elif "northwest" in loc:
            x, y = 0.28, 0.24
        elif "southeast" in loc:
            x, y = 0.70, 0.72
        elif "southwest" in loc:
            x, y = 0.26, 0.72
        elif loc == "north":
            x, y = 0.50, 0.18
        primitives.append(
            LayoutPrimitive(
                kind="landmark",
                type=kind or "landmark",
                label=anchor.label or kind,
                x=x,
                y=y,
                w=0.10,
                h=0.08,
                color="landmark",
            )
        )
    return SpatialLayout(
        environmentClass="exterior",
        subtype=packet.environmentSubtype or "landscape",
        widthMeters=packet.dimensions.widthMeters,
        depthMeters=packet.dimensions.depthMeters,
        primitives=primitives,
    )


def render_spatial_layout(
    layout: SpatialLayout,
    *,
    width: int = 1024,
    height: int = 1024,
) -> bytes:
    """Shared deterministic raster renderer for Interior and Exterior IR."""
    import io

    from PIL import Image, ImageDraw

    palette = {
        "floor": (52, 56, 62),
        "wall": (196, 200, 208),
        "opening": (64, 168, 96),
        "yellow": (232, 196, 48),
        "elevator": (88, 96, 112),
        "room": (70, 76, 86),
        "stairs": (140, 132, 118),
        "forest": (28, 72, 36),
        "clearing": (168, 150, 96),
        "water": (48, 92, 148),
        "hill": (110, 104, 92),
        "field": (120, 140, 72),
        "trail": (150, 112, 64),
        "landmark": (92, 64, 40),
        "bg_interior": (28, 30, 34),
        "bg_exterior": (18, 36, 22),
    }
    bg = palette["bg_exterior"] if layout.environmentClass == "exterior" else palette["bg_interior"]
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    footprint = next((p for p in layout.primitives if p.kind == "region" and p.type in {"corridor", "room"}), None)
    wall_px = max(10, int(min(width, height) * 0.028))

    for prim in layout.primitives:
        color = palette.get(prim.color) or palette["floor"]
        if prim.kind == "region":
            if prim.r:
                cx = int(prim.x * width + prim.w * width / 2)
                cy = int(prim.y * height + prim.h * height / 2)
                rx = int((prim.r or 0.12) * min(width, height))
                draw.ellipse([cx - rx, cy - rx, cx + rx, cy + rx], fill=color)
            else:
                box = _box(prim, width, height)
                draw.rectangle(box, fill=color)
        elif prim.kind == "wall" and footprint:
            box = _box(prim, width, height)
            draw.rectangle(box, outline=color, width=wall_px)
        elif prim.kind == "path":
            if prim.type == "guidance_strip" and footprint:
                fx0, fy0, fx1, fy1 = _box(footprint, width, height)
                pad = wall_px + 10
                if prim.side == "right":
                    draw.rectangle(
                        [fx1 - pad - 10, fy0 + int((fy1 - fy0) * 0.18), fx1 - pad, fy0 + int((fy1 - fy0) * 0.62)],
                        fill=color,
                    )
                else:
                    draw.rectangle(
                        [fx0 + pad, fy0 + int((fy1 - fy0) * 0.18), fx0 + pad + 10, fy0 + int((fy1 - fy0) * 0.62)],
                        fill=color,
                    )
            elif prim.x2 is not None and prim.y2 is not None:
                stroke = 18 if prim.type == "river" else 10
                draw.line(
                    [int(prim.x * width), int(prim.y * height), int(prim.x2 * width), int(prim.y2 * height)],
                    fill=color,
                    width=stroke,
                )
        elif prim.kind == "opening" and footprint:
            fx0, fy0, fx1, fy1 = _box(footprint, width, height)
            _paint_opening(draw, fx0, fy0, fx1, fy1, wall_px, side=prim.side or "right", along=prim.along, color=color)
        elif prim.kind == "landmark":
            box = _box(prim, width, height)
            draw.ellipse(box, fill=color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _box(prim: LayoutPrimitive, width: int, height: int) -> tuple[int, int, int, int]:
    x0 = int(prim.x * width)
    y0 = int(prim.y * height)
    x1 = int((prim.x + prim.w) * width)
    y1 = int((prim.y + prim.h) * height)
    return x0, y0, x1, y1


def _paint_opening(draw: Any, x0: int, y0: int, x1: int, y1: int, wall: int, *, side: str, along: float, color) -> None:
    span = max(28, int((x1 - x0) * 0.42))
    depth = wall + 8
    if side == "end":
        cx = (x0 + x1) // 2
        draw.rectangle([cx - span // 2, y0 - 2, cx + span // 2, y0 + depth], fill=color)
    elif side == "right":
        cy = int(y0 + (y1 - y0) * along)
        draw.rectangle([x1 - depth, cy - span // 2, x1 + 2, cy + span // 2], fill=color)
    else:
        cy = int(y0 + (y1 - y0) * along)
        draw.rectangle([x0 - 2, cy - span // 2, x0 + depth, cy + span // 2], fill=color)


def layout_cache_key(
    *,
    description: str,
    environment_class: str,
    reference_asset_id: str = "",
) -> str:
    raw = json.dumps(
        {
            "description": (description or "").strip(),
            "environmentClass": normalize_environment_class(environment_class),
            "reference": (reference_asset_id or "").strip(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def render_appearance_prior(
    packet: EnvironmentDesignPacket | dict[str, Any] | None,
    *,
    environment_class: str = "",
    width: int = 1024,
    height: int = 1024,
) -> bytes:
    """PIL material swatch from the packet. Not a photograph and not a floorplan."""
    import io

    from PIL import Image, ImageDraw, ImageFilter

    if isinstance(packet, dict):
        packet = EnvironmentDesignPacket.model_validate(packet)
    env_class = normalize_environment_class(
        environment_class or (packet.environmentClass if packet is not None else "interior")
    )
    materials = " ".join((packet.appearance.materials if packet is not None else []) or []).lower()
    width = max(64, int(width or 1024))
    height = max(64, int(height or 1024))
    if env_class == "exterior":
        img = Image.new("RGB", (width, height), (34, 72, 38))
        draw = ImageDraw.Draw(img)
        for i in range(0, height, 18):
            shade = 28 + (i % 40)
            draw.rectangle([0, i, width, i + 10], fill=(shade, shade + 36, shade + 8))
        for i in range(0, width, 28):
            draw.ellipse([i, height // 3, i + 36, height // 3 + 40], fill=(58, 96, 46))
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
    else:
        base = (168, 176, 186) if "silver" in materials or "metal" in materials else (128, 124, 118)
        img = Image.new("RGB", (width, height), base)
        draw = ImageDraw.Draw(img)
        for i in range(0, height, 6):
            tone = 8 if i % 12 == 0 else -6
            color = tuple(max(0, min(255, c + tone)) for c in base)
            draw.line([0, i, width, i], fill=color, width=2)
        draw.rectangle([width // 8, height // 8, width * 7 // 8, height * 7 // 8], outline=(210, 214, 220), width=3)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
