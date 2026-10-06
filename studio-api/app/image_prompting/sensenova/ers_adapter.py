"""SenseNova adapter over the existing production_ers compiler.

Uses Adept ERS_SPEC sections. Venture corridor is layout/density only.
"""

from __future__ import annotations

from typing import Any

from ...codirector.knowledgebase.ers_compiler import (
    ERS_LAYOUT,
    compile_environment_reference_sheet_prompt,
    strip_character_sheet_layout_language,
)

_LAYOUT_BANNER = (
    "LAYOUT EXEMPLAR RULES (binding): Copy only sheet structure and information density. "
    "Do NOT copy Venture corridor architecture, Earth-from-orbit windows, Adept Chronicles "
    "titles, environment IDs, dates, or dimensions. The Observatory / Lab environment "
    "described below is the only place on this sheet."
)


def compile_sensenova_ers_prompt(
    *,
    compiled_ers: str | dict[str, Any] | None = None,
    environment_name: str = "",
    spatial_summary: str = "",
    landmarks: list[str] | None = None,
    cameras: list[str] | None = None,
    has_atlas: bool = True,
    has_layout_exemplar: bool = False,
) -> dict[str, str]:
    if isinstance(compiled_ers, dict):
        body = str(compiled_ers.get("prompt") or compiled_ers.get("text") or "").strip()
    elif compiled_ers:
        body = str(compiled_ers).strip()
    else:
        body = ""
    if not body:
        try:
            pkg = compile_environment_reference_sheet_prompt(
                environment_name=environment_name,
                spatial_map={"summary": spatial_summary} if spatial_summary else None,
            )
            body = str(pkg.get("prompt") or pkg.get("text") or "")
        except Exception:
            body = ""
    body = strip_character_sheet_layout_language(body)
    name = (environment_name or "the environment").strip()
    marks = ", ".join(str(m).strip() for m in (landmarks or []) if str(m).strip())
    cams = ", ".join(str(c).strip() for c in (cameras or []) if str(c).strip())
    spatial = (spatial_summary or "").strip()
    banner = f"{_LAYOUT_BANNER}\n" if has_layout_exemplar else ""
    atlas = (
        "CONTENT SOURCE: The attached environment / Atlas image is the authoritative place. "
        "Preserve its architecture, materials, and landmark sides. Expand it into a production "
        "Environment Reference Sheet of the SAME room.\n"
        if has_atlas
        else ""
    )
    prompt = (
        f"{banner}{atlas}"
        f"Create ONE professional production Environment Reference Sheet for {name}. "
        "This is a unified production-design document of one place, not four cinematic POVs "
        "and not a character turnaround.\n"
        f"{body}\n"
        f"Spatial Map facts (do not invent missing numbers): {spatial or 'use only provided map relations'}.\n"
        f"Landmarks to keep in correct left/right/front/back relation: {marks or 'those on the Spatial Map'}.\n"
        f"Cameras if present: {cams or 'omit camera IDs unless the map supplies them'}.\n"
        "Required sections: Hero Environment; Spatial / Top-Down matching the map; "
        "Structural / greybox if possible (skip rather than fake); North East South West of the "
        "SAME room; Materials that exist here; Lighting that belongs here; Environment DNA from "
        "scene data; Continuity Always/Never rules that are checkable.\n"
        "Labels only if readable. Do not invent IDs, dates, or dimensions."
    )
    negative = (
        "character turnaround, Front/Side/Back/Close-Up of a person, Korri, "
        "Venture corridor copy, Earth-from-orbit windows copied from the exemplar, "
        "four unrelated rooms, four cinematic POV beauty shots, single still with a title bar, "
        "invented dimensions, Adept Chronicles masthead"
    )
    return {
        "prompt": strip_character_sheet_layout_language(prompt),
        "negative": negative,
        "layout": ERS_LAYOUT,
    }
