"""Overlay composition validation — plain text only, bounded shapes/fonts."""

from __future__ import annotations

import re
from typing import Any

from .fonts import font_ids, resolve_font

MAX_TEXT = 100
MAX_VECTOR = 200
MAX_TEXT_LEN = 5000
MAX_GROUP_DEPTH = 8
SHAPES = {
    "rectangle",
    "rounded_rectangle",
    "line",
    "circle",
    "ellipse",
    "triangle",
    "chevron",
    "accent_bar",
    "divider",
}
ANIM = {"none", "fade", "slide_left", "slide_right", "slide_up", "slide_down", "scale_in", "wipe", None}
COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$|^rgba?\([^)]+\)$|^transparent$")
HTML_RE = re.compile(r"[<>]|javascript:|data:text/html", re.I)
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _err(msg: str) -> dict[str, Any]:
    return {"ok": False, "errors": [msg]}


def validate_composition(comp: dict[str, Any], *, project_id: str) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(comp, dict):
        return _err("Composition must be an object")
    if comp.get("schemaVersion") != 1:
        errors.append("Unsupported schemaVersion")
    if comp.get("projectId") != project_id:
        errors.append("projectId mismatch / cross-project access denied")
    cw = int(comp.get("canvasWidth") or 0)
    ch = int(comp.get("canvasHeight") or 0)
    if cw < 16 or ch < 16 or cw > 16384 or ch > 16384:
        errors.append("Invalid canvas dimensions")
    overlays = comp.get("overlays")
    if not isinstance(overlays, list):
        errors.append("overlays must be a list")
        return {"ok": False, "errors": errors}
    ids: set[str] = set()
    text_n = vec_n = 0
    known = font_ids()

    def walk(els: list[Any], depth: int) -> None:
        nonlocal text_n, vec_n
        if depth > MAX_GROUP_DEPTH:
            errors.append("Maximum nested group depth exceeded")
            return
        for el in els:
            if not isinstance(el, dict):
                errors.append("Invalid overlay element")
                continue
            eid = el.get("id")
            if not eid or not isinstance(eid, str):
                errors.append("Overlay missing id")
                continue
            if eid in ids:
                errors.append(f"Duplicate overlay id {eid}")
            ids.add(eid)
            t = el.get("type")
            if t == "text":
                text_n += 1
                text = str(el.get("text") or "")
                if len(text) > MAX_TEXT_LEN:
                    errors.append(f"Text too long on {eid}")
                if HTML_RE.search(text) or CTRL_RE.search(text):
                    errors.append(f"Unsupported markup/control sequences in text {eid}")
                style = el.get("textStyle") or {}
                fid = style.get("fontFamily") or style.get("fontId")
                if fid and fid not in known and not resolve_font(str(fid)).get("font"):
                    errors.append(f"Unknown font {fid}")
                for key in ("color", "strokeColor"):
                    c = style.get(key)
                    if c and not COLOR_RE.match(str(c)):
                        errors.append(f"Invalid colour {key} on {eid}")
                anim = el.get("animationPreset")
                if anim not in ANIM and anim is not None:
                    errors.append(f"Invalid animation preset on {eid}")
                fs = float(style.get("fontSize") or 24)
                if fs < 4 or fs > 600:
                    errors.append(f"Font size out of range on {eid}")
            elif t == "vector":
                vec_n += 1
                if el.get("shape") not in SHAPES:
                    errors.append(f"Unsupported shape on {eid}")
                if el.get("rawSvg") or el.get("svg"):
                    errors.append(f"Raw SVG forbidden on {eid}")
            elif t == "group":
                children = el.get("children") or []
                if not isinstance(children, list):
                    errors.append(f"Group {eid} children invalid")
                else:
                    walk(children, depth + 1)
            else:
                errors.append(f"Unknown overlay type on {eid}")
            for num_key, lo, hi in (
                ("opacity", 0, 1),
                ("rotation", -360, 360),
                ("x", -2, 2),
                ("y", -2, 2),
                ("width", 0, 2),
                ("height", 0, 2),
            ):
                if num_key in el and el[num_key] is not None:
                    try:
                        v = float(el[num_key])
                    except (TypeError, ValueError):
                        errors.append(f"Invalid {num_key} on {eid}")
                        continue
                    if v < lo or v > hi:
                        # x/y/width/height stored normalized 0–1 (allow slight overshoot)
                        if num_key in ("x", "y", "width", "height"):
                            if v < -0.5 or v > 1.5:
                                errors.append(f"{num_key} out of bounds on {eid}")
                        else:
                            errors.append(f"{num_key} out of range on {eid}")

    walk(overlays, 0)
    if text_n > MAX_TEXT:
        errors.append("Too many text elements")
    if vec_n > MAX_VECTOR:
        errors.append("Too many vector elements")
    return {"ok": len(errors) == 0, "errors": errors}
