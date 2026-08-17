"""Panel-task weights and occlusion notes. Runtime stays one whole-sheet I2I job."""

from __future__ import annotations

from typing import Any

from .schema import CanonicalContinuity

# Extra instruction emphasis per panelTask. Whole-sheet still lists all sections.
PANEL_EMPHASIS: dict[str, list[str]] = {
    "whole_sheet": [
        "Required sections in one image: Hero, Spatial/Top-Down, Structural/3D if supported, "
        "Directional N/E/S/W, Materials, Lighting, Environment DNA, Continuity. "
        "Add occupied-scale only when placed subjects are listed."
    ],
    "hero": [
        "Emphasize architecture, furniture, materials, lighting, and composition in the Hero panel.",
        "Hero is environment-only. No characters. No hero props.",
    ],
    "top_down": [
        "Emphasize geometry, object positions, doors, windows, counter, and circulation in the top-down panel.",
        "Do not add cinematic occupied-scale storytelling to the floor plan.",
    ],
    "greybox": [
        "Emphasize geometry, structure, scale, and fixed landmarks in the structural / 3D panel.",
        "Skip rather than fake a second hero render.",
    ],
    "elevation": [
        "Emphasize wall features, counter, windows, doors, and fixed furniture for the requested elevation.",
        "Environment-only. No characters.",
    ],
    "east_elevation": [
        "Generate the east-facing elevation of this same physical set.",
        "Only change the camera viewpoint.",
    ],
    "occupied_scale": [
        "Emphasize character placement, prop placement, scale, spatial relationship, and side-of-barrier logic.",
        "Occupied scale is the only panel that may show placed subjects.",
    ],
    "materials": [
        "Emphasize surfaces, finishes, color, and texture swatches that belong to this place.",
    ],
}


def emphasis_lines(panel_task: str) -> list[str]:
    key = str(panel_task or "whole_sheet").strip() or "whole_sheet"
    return list(PANEL_EMPHASIS.get(key) or PANEL_EMPHASIS["whole_sheet"])


def panel_includes_occupied(panel_task: str) -> bool:
    """Occupied-scale actor prose belongs on whole_sheet and occupied_scale only."""
    key = str(panel_task or "whole_sheet").strip() or "whole_sheet"
    return key in {"whole_sheet", "occupied_scale"}


def occlusion_notes(facts: CanonicalContinuity, panel_task: str) -> list[str]:
    """An object not visible from a viewpoint is not absent from canon."""
    task = str(panel_task or "").lower()
    notes: list[str] = []
    furniture = facts.persistentFurniture or {}
    couch = furniture.get("couch") if isinstance(furniture.get("couch"), dict) else {}
    present = couch.get("present")
    if present is True or (isinstance(present, str) and present.lower() in {"true", "yes"}):
        loc = str(couch.get("location") or "lounge").strip()
        if "east" in task or task == "elevation":
            notes.append(
                f"The lounge couch exists ({loc}) but may be occluded from this viewpoint. "
                "Do not remove it from the environment canon."
            )
        else:
            notes.append(f"Keep the lounge couch present ({loc}).")
    bar = (facts.fixedArchitecture or {}).get("serviceCounterOrBar")
    if isinstance(bar, dict) and (bar.get("location") or bar.get("shape")):
        if "east" in task:
            notes.append(
                "The service counter exists even if a given elevation hides part of it. "
                "Do not delete it from canon."
            )
    return notes


def furniture_present(facts: CanonicalContinuity, key: str) -> bool:
    block = facts.persistentFurniture or {}
    item = block.get(key)
    if isinstance(item, dict):
        return bool(item.get("present") is True or item.get("location"))
    return bool(item)
