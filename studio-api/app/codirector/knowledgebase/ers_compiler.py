"""Dedicated Environment Reference Sheet prompt compiler.

MUST NOT go through the character-sheet / four-view / generic reference_sheet
compiler. Purpose is always environment_reference_sheet. Layout is production_ers.
"""

from __future__ import annotations

import re
from typing import Any

from ...spatial_map.scene_intent import coerce_scene_intent, environment_intent_summary
from .ers_loader import load_ers_knowledgebase

ERS_PURPOSE = "environment_reference_sheet"
ERS_LAYOUT = "production_ers"
ERS_COMPILER_ID = "environment_reference_sheet"

# Character-sheet sheet-layout language. Never emit these as ERS views.
_CHARACTER_SHEET_LAYOUT_RE = re.compile(
    r"(?is)("
    r"front\s*/\s*side\s*/\s*back(?:\s*/\s*close[- ]?up)?"
    r"|full[- ]body\s+front"
    r"|full[- ]body\s+side"
    r"|full[- ]body\s+back"
    r"|head[- ]and[- ]shoulders\s+close[- ]?up"
    r"|four[- ]panel\s+character"
    r"|character\s+turnaround"
    r"|four[- ]view\s+character"
    r"|professional four-panel character"
    r")"
)

_VARIATION_GRID_RE = re.compile(
    r"(?is)(four[- ]image variation|four variations of the same|variation grid|"
    r"mood board|four different looks|four cinematic povs?)"
)

_BANNED_CONTENT_LEAK = re.compile(
    r"(?is)(venture main observation corridor|mother sphere|korri'?s domocile|"
    r"the adept chronicles|aiya'?s broom)"
)


def strip_character_sheet_layout_language(text: str) -> str:
    """Remove Front/Side/Back/Close-Up character-sheet layout phrasing."""
    cleaned = _CHARACTER_SHEET_LAYOUT_RE.sub("", str(text or ""))
    cleaned = _VARIATION_GRID_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _names(items: Any, *, limit: int = 6) -> list[str]:
    out: list[str] = []
    if not items:
        return out
    if isinstance(items, dict):
        items = items.values()
    for item in items:
        if len(out) >= limit:
            break
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue
        if isinstance(item, dict):
            name = _text(item.get("name") or item.get("displayName") or item.get("id"))
            if name:
                out.append(name)
            continue
        name = _text(getattr(item, "name", None) or getattr(item, "displayName", None))
        if name:
            out.append(name)
    return out


def _spatial_facts(spatial_map: dict[str, Any] | None) -> list[str]:
    """Only facts the Spatial Map / project actually provided. Never invent."""
    src = _as_dict(spatial_map)
    facts: list[str] = []
    for key, label in (
        ("mapId", "Spatial Map id"),
        ("id", "Spatial Map id"),
        ("northLockDirection", "North lock"),
        ("compass", "Compass"),
        ("dimensions", "Dimensions"),
        ("widthMeters", "Width (m)"),
        ("lengthMeters", "Length (m)"),
        ("heightMeters", "Height (m)"),
        ("scale", "Scale"),
        ("summary", "Spatial summary"),
        ("masterEnvironmentPrompt", "Master environment"),
    ):
        val = src.get(key)
        if val in (None, "", [], {}):
            continue
        text = val if isinstance(val, str) else str(val)
        text = text.strip()
        if text:
            facts.append(f"{label}: {text}")
    return facts


def _model_supports_layout_refs(body: dict[str, Any] | None) -> bool:
    """GPT Image 2 (explicit) can consume layout exemplars. Qwen is T2I-only."""
    src = _as_dict(body)
    blob = " ".join(
        _text(src.get(k))
        for k in (
            "hostedModelId",
            "kieImageModelId",
            "falImageModelId",
            "model",
            "modelId",
            "modelFamilyPreference",
        )
    ).lower()
    if "gpt-image-2" in blob or "gpt_image_2" in blob:
        return True
    return False


def should_attach_ers_exemplars(body: dict[str, Any] | None = None) -> bool:
    """Attach exemplar pixels only when the model path supports refs AND it is useful.

    First implementation is one prompt + one image. Qwen (default) is T2I-only.
    Explicit GPT Image 2 may attach exemplars as layout conditioning, never I2I
    source pixels, and never as content to copy.
    """
    src = _as_dict(body)
    if src.get("attachErsExemplars") is False:
        return False
    if not _model_supports_layout_refs(src):
        return False
    return bool(src.get("attachErsExemplars"))


def _source_grounding_preamble(
    intent: Any,
    *,
    has_source_image: bool = False,
) -> list[str]:
    """§13 source-grounding preamble. Identity authority BEFORE layout spec."""
    scene = coerce_scene_intent(intent)
    if scene is None:
        return []
    title = _text(scene.sceneTitle) or "the recorded environment"
    location = _text(scene.locationType).replace("_", " ")
    lines = [
        "SOURCE ENVIRONMENT — AUTHORITATIVE GROUNDING (highest priority):",
        f"PRIMARY ENVIRONMENT IDENTITY: this sheet depicts {title}"
        + (f", a {location}." if location else "."),
    ]
    summary = environment_intent_summary(scene)
    if summary:
        lines.append("Authoritative environment intent (from the creator / project record):")
        lines.append(summary)
    if has_source_image:
        lines.append(
            "The attached source environment image is the VISUAL AUTHORITY for "
            "architecture, materials, color palette, and mood."
        )
    lines.append(
        "Do not replace this place with a generic living room, bedroom, office, "
        "sci-fi corridor, or any other environment."
    )
    lines.append(
        "If any other instruction conflicts with the scene intent above, the scene intent wins."
    )
    lines.append(
        "Exemplar sheets (if attached) show LAYOUT STRUCTURE ONLY — do not copy "
        "their content, architecture, props, lighting, or text."
    )
    return lines


def compile_environment_reference_sheet_prompt(
    *,
    environment_name: str = "",
    environment_description: str = "",
    creator_prompt: str = "",
    project_context: dict[str, Any] | None = None,
    spatial_map: dict[str, Any] | None = None,
    environment_intent: dict[str, Any] | None = None,
    characters: list[Any] | None = None,
    props: list[Any] | None = None,
    cameras: list[Any] | None = None,
    visual_style: str = "",
    atlas_note: str = "",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one canonical ERS prompt. Never a character-sheet layout."""
    kb = load_ers_knowledgebase()
    project = _as_dict(project_context)
    spatial = _as_dict(spatial_map) or _as_dict(project.get("spatial"))
    scene = coerce_scene_intent(environment_intent)
    name = (
        _text(environment_name)
        or _text(project.get("environmentName"))
        or _text(project.get("name"))
        or (_text(scene.sceneTitle) if scene is not None else "")
        or _text(creator_prompt)
        or "this environment"
    )
    description = (
        _text(environment_description)
        or _text(project.get("environmentDescription"))
        or _text(project.get("description"))
        or _text(creator_prompt)
    )
    style = _text(visual_style) or _text(project.get("visualStyle"))
    atlas = _text(atlas_note) or _text(spatial.get("backgroundAssetId") or spatial.get("atlasAssetId"))

    char_names = _names(characters if characters is not None else project.get("characters"))
    prop_names = _names(props if props is not None else project.get("props"))
    camera_names = _names(cameras if cameras is not None else project.get("cameras") or spatial.get("cameras"))
    spatial_facts = _spatial_facts(spatial)

    preamble = _source_grounding_preamble(
        scene,
        has_source_image=bool(_model_supports_layout_refs(body)),
    )

    lines = [
        f"Create ONE unified Environment Reference Sheet (production-design document) for {name}.",
        "Purpose: environment_reference_sheet. Layout: production_ers.",
        "This is a production-design document for one locked place. It is not a person turnaround, not an object catalog, not a storyboard, and not four similar beauty shots.",
        "Directional panels are North, East, South, West elevations of the room. Do not emit person-view turnaround panels.",
        "Every panel is a different kind of information about the SAME locked environment.",
    ]
    # §13: the source-grounding authority clause leads — before the layout spec.
    if preamble:
        lines.extend(["", *preamble])
    lines.extend(
        [
            "",
            "Required sections (all in one image):",
        f"1. Hero Environment — canonical look of {name}.",
        "2. Spatial / Top-Down — floor plan of this place. Include scale, compass, IDs, or dimensions ONLY if Spatial Map / project data below provides them. Do not invent any of those.",
        "3. Structural / 3D — greybox / untextured mesh if the model can. Skip rather than fake a second hero render.",
        "4. Directional / Orthographic views — N / E / S / W of the same environment (North, East, South, West elevations). Architectural, not cinematic POVs.",
        "5. Materials — surface swatches for floors, walls, counters, furniture, and equipment that belong to this place.",
        "6. Lighting — primary / secondary / accent sources that belong to this place.",
        "7. Environment DNA — era, visual language, condition, emotional register taken from the scene. Do not invent lore, dates, or environment IDs.",
        "8. Continuity Rules — Always / Never for this environment. Concrete and checkable.",
        "",
        "Continuity: same architecture, materials, lighting, and time of day in every panel. Do not redesign the world.",
        ]
    )
    if description:
        lines.extend(["", f"Environment: {description}"])
    if style:
        lines.append(f"Visual language: {style}")
    if spatial_facts:
        lines.extend(["", "Spatial Map facts (use only these; do not invent more):"])
        lines.extend(f"- {fact}" for fact in spatial_facts)
    else:
        lines.append("No Spatial Map dimensions, dates, environment IDs, or compass were provided. Do not invent them.")
    if char_names:
        lines.append("Characters (scale / occupancy only, not portraits): " + ", ".join(char_names))
    if prop_names:
        lines.append("Props (scale / set dressing only, not a prop sheet): " + ", ".join(prop_names))
    if camera_names:
        lines.append("Cameras (scale / blocking on the map only if listed): " + ", ".join(camera_names))
    if atlas:
        lines.append(
            "Atlas / environment plate is architecture and identity conditioning only "
            f"(ref {atlas}). Not a character reference. Not pixel image-to-image."
        )
    lines.extend(
        [
            "",
            "Spec (structural guidance only — do not copy exemplar architecture or text):",
            "Unified production-design document for ONE environment. Required: Hero, Spatial/Top-Down, Structural/3D if supported, Directional N/E/S/W, Materials, Lighting, Environment DNA, Continuity.",
            "Exemplars are layout and density references only. Do not reproduce exemplar architecture, names, or text.",
        ]
    )
    if creator_prompt and _text(creator_prompt).lower() not in description.lower():
        lines.extend(["", f"Creator note: {strip_character_sheet_layout_language(creator_prompt)}"])

    prompt = strip_character_sheet_layout_language("\n".join(lines))
    prompt = _BANNED_CONTENT_LEAK.sub("", prompt)
    prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip()

    attach = should_attach_ers_exemplars(body)
    return {
        "prompt": prompt,
        "purpose": ERS_PURPOSE,
        "layout": ERS_LAYOUT,
        "compiler": ERS_COMPILER_ID,
        "specSummary": kb.spec_summary,
        "exemplarPaths": [str(path) for path in kb.exemplar_paths],
        "attachExemplars": attach,
        "environmentName": name,
    }


def compile_ers_prompt_from_body(
    body: dict[str, Any] | None,
    *,
    project_id: str = "",
) -> dict[str, Any]:
    """Compile from an image-product / ers.generate request body."""
    src = _as_dict(body)
    existing = _text(src.get("prompt") or src.get("acceptedPrompt"))
    if "layout: production_ers" in existing.lower() and "hero environment" in existing.lower():
        kb = load_ers_knowledgebase()
        return {
            "prompt": existing,
            "purpose": ERS_PURPOSE,
            "layout": ERS_LAYOUT,
            "compiler": ERS_COMPILER_ID,
            "specSummary": kb.spec_summary,
            "exemplarPaths": [str(path) for path in kb.exemplar_paths],
            "attachExemplars": should_attach_ers_exemplars(src),
            "environmentName": _text(src.get("environmentName") or src.get("name")),
        }
    ctx = _as_dict(src.get("creativeContext"))
    spatial = _as_dict(src.get("spatialReferenceBundle")) or _as_dict(ctx.get("spatial"))
    if src.get("spatialMapId") and "mapId" not in spatial:
        spatial = {**spatial, "mapId": src.get("spatialMapId")}
    name = _text(ctx.get("environmentName") or src.get("environmentName") or src.get("name"))
    description = _text(
        ctx.get("environmentDescription")
        or src.get("environmentDescription")
        or src.get("description")
        or src.get("prompt")
    )
    return compile_environment_reference_sheet_prompt(
        environment_name=name,
        environment_description=description,
        creator_prompt=_text(src.get("prompt") or src.get("acceptedPrompt")),
        project_context={
            "projectId": project_id or ctx.get("projectId"),
            "name": name,
            "description": description,
            "visualStyle": ctx.get("visualStyle") or src.get("visualStyle"),
            "characters": src.get("characters") or ctx.get("characters"),
            "props": src.get("props") or ctx.get("props"),
            "cameras": src.get("cameras") or ctx.get("cameras"),
            "spatial": spatial,
        },
        spatial_map=spatial,
        environment_intent=ctx.get("sceneIntent") or src.get("sceneIntent"),
        visual_style=_text(ctx.get("visualStyle") or src.get("visualStyle")),
        atlas_note=_text(ctx.get("atlasAssetId") or spatial.get("backgroundAssetId")),
        body=src,
    )


def apply_ers_compile_to_body(body: dict[str, Any], *, project_id: str = "") -> dict[str, Any]:
    """Stamp the dedicated ERS compile onto an image-product body. Never four-view."""
    compiled = compile_ers_prompt_from_body(body, project_id=project_id)
    body["prompt"] = compiled["prompt"]
    body["acceptedPrompt"] = compiled["prompt"]
    body["purpose"] = ERS_PURPOSE
    body["layout"] = ERS_LAYOUT
    body["useExpandedPrompt"] = False
    ctx = body.get("creativeContext")
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    ctx["objective"] = ERS_PURPOSE
    ctx["layout"] = ERS_LAYOUT
    ctx["ersCompiler"] = ERS_COMPILER_ID
    ctx["ersExemplarPaths"] = compiled["exemplarPaths"]
    ctx["ersAttachExemplars"] = compiled["attachExemplars"]
    return compiled
