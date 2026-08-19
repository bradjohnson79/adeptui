"""Reusable @/# entity resolver and shot-request compiler for Co-Director.

Not Spatial-Map-only: this module resolves character @-references and prop
#-references for any Co-Director capability handler that needs structured
entity IDs from free-form creator text (Scene Creator, Image Generate,
Storyboard Generate, etc.).

Amendment #5 (ENTITY TAGS):
- ``@CharacterName`` supports real names with spaces/apostrophes/hyphens/digits
  (e.g. ``@Agent Shadow``, ``@Anga'q'uay``, ``@Mieke-2``).
- ``#prop-tag`` uses normalized tags (``#coffee-cup``, ``#espresso-machine``,
  ``#cup2``). Tags resolve to stable entity IDs; the human-readable tag is
  the friendly reference, not the database identity.

Amendment #3 (SPATIAL AUTHORITY):
- ``compile_shot_prompt`` only *reads* placement state from a snapshot of the
  ERS package. It never writes back to the spatial map.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..character_identity.service import (
    resolve_approved_reference,
    resolve_character_by_name,
)
from ..spatial_map.ers_contracts import (
    EnvironmentReferencePackage,
    PropEntity,
    ShotRequest,
    normalize_prop_tag,
)
from ..spatial_map.ers_persistence import (
    list_prop_entities,
    load_ers_package,
    load_prop_entity,
)

# Amendment #5 — character @-reference parser.
# Allows multi-word capitalized names: "@Agent Shadow", "@Anga'q'uay", "@Mieke-2".
_CHARACTER_TAG_RE = re.compile(r"@([A-Z][A-Za-z'\-0-9]+(?:\s+[A-Z][A-Za-z'\-0-9]+)*)")

# Amendment #5 — prop #-reference parser. Normalized lowercase tags only.
_PROP_TAG_RE = re.compile(r"#([a-z][a-z0-9\-]*)")

# Framing keywords (creator language, not technical jargon).
_FRAMING_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("close-up", "close-up"),
    ("closeup", "close-up"),
    ("close up", "close-up"),
    ("medium shot", "medium"),
    ("medium", "medium"),
    ("wide shot", "wide"),
    ("wide", "wide"),
    ("ots", "over-the-shoulder"),
    ("over-the-shoulder", "over-the-shoulder"),
    ("over the shoulder", "over-the-shoulder"),
    ("high angle", "high angle"),
    ("low angle", "low angle"),
    ("bird's eye", "bird's eye"),
    ("birds eye", "bird's eye"),
    ("birds-eye", "bird's eye"),
    ("extreme close-up", "extreme close-up"),
    ("extreme closeup", "extreme close-up"),
    ("two-shot", "two-shot"),
    ("two shot", "two-shot"),
)

# Orientation keywords (scene-relative — amendment #4). "facing north" etc.
_ORIENTATION_RE = re.compile(
    r"\b(?:facing\s+|looking\s+|view\s+(?:to|towards|toward)\s+)?"
    r"(north|east|south|west)(?:\s+(?:facing|view|direction))?\b",
    re.IGNORECASE,
)

# Angle keywords like "15 degrees right", "30 degrees left of center".
_ANGLE_RE = re.compile(
    r"\b(\d{1,3})\s*°?\s*degrees?\s+(right|left|clockwise|counter-?clockwise)\b",
    re.IGNORECASE,
)


def find_character_names(text: str) -> list[str]:
    """Return all unique ``@CharacterName`` strings (without the leading ``@``)."""
    seen: dict[str, None] = {}
    for match in _CHARACTER_TAG_RE.finditer(text or ""):
        name = match.group(1).strip()
        if name and name not in seen:
            seen[name] = None
    return list(seen.keys())


def find_prop_tags(text: str) -> list[str]:
    """Return all unique ``#prop-tag`` strings (without the leading ``#``)."""
    seen: dict[str, None] = {}
    for match in _PROP_TAG_RE.finditer(text or ""):
        tag = match.group(1).strip()
        if tag and tag not in seen:
            seen[tag] = None
    return list(seen.keys())


def resolve_character(
    db: Session, project_id: str, name: str
) -> dict[str, Any] | None:
    """Resolve a single ``@CharacterName`` to a character profile + casting ref.

    Returns ``{character_id, name, approved_casting_asset_id}`` or ``None`` if
    the character is unknown to this project. Never raises — unknown
    references degrade gracefully so creators can keep typing.
    """
    if not name or not name.strip():
        return None
    profile = resolve_character_by_name(db, project_id, name)
    if profile is None:
        return None
    casting_asset_id = resolve_approved_reference(db, profile.id, "hero_identity")
    persisted: dict[str, Any] = {}
    try:
        from ..character_identity.crs_service import load_persisted_crs

        persisted = load_persisted_crs(db, profile.id)
    except Exception:
        persisted = {}
    sheet_id = persisted.get("approved_sheet_asset_id") or casting_asset_id
    result: dict[str, Any] = {
        "character_id": profile.id,
        "name": profile.name,
        "approved_casting_asset_id": sheet_id,
        "crs_revision": int(persisted.get("crs_revision") or 0),
        "approved_sheet_asset_id": sheet_id,
        "production_ready": (profile.approval_status or "").lower() == "approved",
    }
    try:
        from ..character_identity.crs_service import get_crs_summary
        summary = get_crs_summary(db, project_id, profile.id)
        if summary:
            result["crs_revision"] = summary.crs_revision
            result["has_approved_reference"] = summary.has_approved_reference
            result["approved_reference_asset_id"] = summary.approved_reference_asset_id
            result["reference_coverage"] = summary.reference_coverage
            result["visual_canon_ready"] = summary.canon_status.visual_canon_ready if summary.canon_status else False
            result["render_domain"] = summary.render_domain.model_dump() if summary.render_domain else {}
    except Exception:
        pass
    return result


def resolve_prop(
    db: Session, project_id: str, tag: str
) -> PropEntity | None:
    """Resolve a single ``#prop-tag`` to a ``PropEntity`` (registry or spatial map).

    Lookup order:
    1. ``ProjectTraitRow`` category ``prop_entity`` (project prop registry).
    2. Returns ``None`` if no entity exists — callers may auto-register a
       placeholder when a creator approves a Library asset for the tag.
    """
    if not tag:
        return None
    normalized = normalize_prop_tag(tag) if not _is_normalized(tag) else tag
    return load_prop_entity(db, project_id, normalized)


def _is_normalized(tag: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9\-]+", tag or ""))


def list_known_prop_tags(db: Session, project_id: str) -> list[str]:
    """List the normalized tags of all registered prop entities for a project."""
    return [prop.tag for prop in list_prop_entities(db, project_id)]


# ---------------------------------------------------------------------------
# Shot request parsing
# ---------------------------------------------------------------------------


def _detect_framing(text: str) -> str:
    lowered = (text or "").lower()
    # Longest-match first to avoid "close" shadowing "close-up".
    for needle, framing in sorted(_FRAMING_KEYWORDS, key=lambda kv: -len(kv[0])):
        if needle in lowered:
            return framing
    return ""


def _detect_angle(text: str) -> str:
    match = _ANGLE_RE.search(text or "")
    if not match:
        return ""
    degrees = match.group(1)
    direction = match.group(2).lower().replace("-", "")
    return f"{degrees} degrees {direction}"


def _detect_orientation(text: str) -> str:
    match = _ORIENTATION_RE.search(text or "")
    if not match:
        return ""
    return match.group(1).lower()


def _split_shot_text(raw_text: str) -> list[str]:
    """Split comma- or newline-separated shot text into individual shot strings.

    Splits on top-level commas and newlines. Does not split inside
    parentheses (so "close-up (high angle), wide" is two shots).
    """
    if not raw_text:
        return []
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in raw_text:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif depth == 0 and (char == "," or char == "\n"):
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [piece for piece in parts if piece]


def parse_shot_requests(raw_text: str) -> list[ShotRequest]:
    """Parse free-form creator shot text into a list of ``ShotRequest``.

    Entity IDs (``characters`` / ``prop_entities``) are NOT populated here —
    use ``resolve_shot_request_entities`` after parsing (requires db + project).
    The raw substring is preserved verbatim as ``raw_text`` so the creator
    can see exactly what they typed.
    """
    shots: list[ShotRequest] = []
    for index, piece in enumerate(_split_shot_text(raw_text)):
        char_names = find_character_names(piece)
        prop_tags = find_prop_tags(piece)
        framing = _detect_framing(piece)
        angle = _detect_angle(piece)
        orientation = _detect_orientation(piece)
        # Strip the leading @/# tokens from "additional_instructions" so the
        # compiled prompt reads as natural prose, not tag soup.
        cleaned = _CHARACTER_TAG_RE.sub("", piece)
        cleaned = _PROP_TAG_RE.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
        shots.append(
            ShotRequest(
                index=index,
                raw_text=piece,
                characters=char_names,  # names for now; resolved to IDs later
                prop_entities=prop_tags,  # tags for now; resolved to IDs later
                framing=framing,
                angle=angle,
                orientation=orientation,
                additional_instructions=cleaned,
            )
        )
    return shots


def resolve_shot_request_entities(
    db: Session, project_id: str, shot: ShotRequest
) -> ShotRequest:
    """Resolve ``characters`` (names) and ``prop_entities`` (tags) to stable IDs.

    Returns a NEW ``ShotRequest`` — the input is never mutated. Character
    names that cannot be resolved are dropped from the ``characters`` list
    (the creator is told elsewhere that the @-reference was unknown). Prop
    tags that have no registered entity are dropped from ``prop_entities``
    but remain in ``additional_instructions`` so the prompt still mentions
    the prop semantically.
    """
    resolved_chars: list[str] = []
    for name in shot.characters:
        ref = resolve_character(db, project_id, name)
        if ref and ref.get("character_id"):
            resolved_chars.append(ref["character_id"])

    resolved_props: list[str] = []
    for tag in shot.prop_entities:
        prop = resolve_prop(db, project_id, tag)
        if prop:
            resolved_props.append(prop.id)

    return shot.model_copy(
        update={
            "characters": resolved_chars,
            "prop_entities": resolved_props,
        }
    )


# ---------------------------------------------------------------------------
# Shot prompt compilation
# ---------------------------------------------------------------------------


def _character_metadata(db: Session, project_id: str, character_ids: list[str]) -> list[dict[str, Any]]:
    """Pull concise, production-relevant metadata for each resolved character."""
    from ..character_identity.service import get_profile, list_references

    out: list[dict[str, Any]] = []
    for character_id in character_ids:
        try:
            profile = get_profile(db, project_id, character_id)
        except Exception:
            continue
        casting = resolve_approved_reference(db, character_id, "hero_identity")
        refs = list_references(db, project_id, character_id)
        out.append(
            {
                "character_id": profile.id,
                "name": profile.name,
                "description": profile.description or "",
                "visual_description": profile.visual_description or "",
                "visual_style": profile.visual_style or "",
                "approved_casting_asset_id": casting,
                "reference_asset_ids": [r["asset_id"] for r in refs if r.get("asset_id")],
            }
        )
    return out


def _prop_metadata(db: Session, project_id: str, prop_ids: list[str]) -> list[dict[str, Any]]:
    """Pull concise metadata for each resolved prop entity."""
    out: list[dict[str, Any]] = []
    for prop_id in prop_ids:
        # ``prop_entities`` are stored by tag in the registry; resolve by id.
        for prop in list_prop_entities(db, project_id):
            if prop.id == prop_id:
                out.append(
                    {
                        "id": prop.id,
                        "prop_id": prop.id,
                        "tag": prop.tag,
                        "display_label": prop.display_label,
                        "approved_asset_id": (prop.approved_asset_id or "").strip() or None,
                        "library_asset_id": (prop.approved_asset_id or "").strip()
                        or (prop.library_asset_id or "").strip(),
                        "description": (prop.description or prop.notes or "").strip(),
                        "notes": prop.notes,
                    }
                )
                break
    return out


def identity_reference_ids(
    char_meta: list[dict[str, Any]],
    prop_meta: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Approved character casting + prop library ids, in that order."""
    ids: list[str] = []
    for char in char_meta or []:
        aid = str(char.get("approved_casting_asset_id") or "").strip()
        if aid and aid not in ids:
            ids.append(aid)
    for prop in prop_meta or []:
        aid = str(prop.get("approved_asset_id") or "").strip()
        if aid and aid not in ids:
            ids.append(aid)
    return ids


def place_ers_composite_in_refs(
    reference_image_ids: list[str],
    composite_id: str,
    identity_ids: list[str],
) -> list[str]:
    """Keep identity refs first. ERS composite is environment context, never the lead when casting exists."""
    refs = [str(x).strip() for x in reference_image_ids if str(x).strip()]
    composite = (composite_id or "").strip()
    identity = [str(i).strip() for i in identity_ids if str(i).strip()]
    if composite:
        refs = [r for r in refs if r != composite]
    ordered: list[str] = []
    for iid in identity:
        if iid in refs and iid not in ordered:
            ordered.append(iid)
    for ref in refs:
        if ref not in ordered:
            ordered.append(ref)
    if composite:
        if identity:
            ordered.append(composite)
        else:
            ordered.insert(0, composite)
    return ordered


def primary_reference_image(
    refs: list[str],
    identity_ids: list[str],
    composite_id: str = "",
) -> str:
    """Provider ``referenceImage`` is the first identity asset when one exists."""
    identity = [str(i).strip() for i in identity_ids if str(i).strip()]
    for iid in identity:
        if iid in refs:
            return iid
    if refs:
        return refs[0]
    return (composite_id or "").strip()


def compile_shot_prompt(
    db: Session,
    project_id: str,
    shot: ShotRequest,
    ers_package: EnvironmentReferencePackage | None = None,
) -> dict[str, Any]:
    """Build the imagegen request context for one resolved ``ShotRequest``.

    Returns a dict suitable for passing to ``enqueue_imagegen_job`` body
    construction (prompt, referenceImage, creativeContext, etc.). Style
    resolution is layered (project + character + environment + user) and NOT
    flattened into a single global style string.

    Amendment #3: only reads ERS/spatial state — never writes back.
    """
    char_meta = _character_metadata(db, project_id, shot.characters)
    prop_meta = _prop_metadata(db, project_id, shot.prop_entities)

    from ..spatial_map.ers_projection import compile_structured_blocking

    approved_map = {
        str(prop.get("id") or prop.get("prop_id") or "").strip(): bool(
            (prop.get("approved_asset_id") or "").strip()
        )
        for prop in prop_meta
        if str(prop.get("id") or prop.get("prop_id") or "").strip()
    }
    name_map = {
        str(char.get("character_id") or "").strip(): str(char.get("name") or "")
        for char in char_meta
        if str(char.get("character_id") or "").strip() and char.get("name")
    }
    structured_blocking = compile_structured_blocking(
        list(ers_package.placements or []) if ers_package else [],
        prop_approved=approved_map,
        character_names=name_map,
    )

    # Style layering: project > environment (ERS) > character > user (visual_style).
    # We pass these as discrete keys in creativeContext so downstream consumers
    # can apply them independently (no flattening into one global string).
    project_style = _project_visual_style(db, project_id)
    from ..aspect_fps import normalize_production_aspect, production_pixels
    from ..db import Scene

    aspect = None
    scene_id = str(getattr(shot, "scene_id", "") or "")
    if scene_id:
        try:
            scene_row = db.get(Scene, scene_id)
            aspect = getattr(scene_row, "aspect_ratio", None) if scene_row else None
        except Exception:
            aspect = None
    aspect = normalize_production_aspect(aspect)
    width, height = production_pixels(aspect, "final")
    environment_style = ""
    if ers_package:
        environment_style = (
            ers_package.style_context.get("visual_style") if ers_package.style_context else ""
        ) or ""
    character_styles = [c.get("visual_style") for c in char_meta if c.get("visual_style")]
    user_style = ""  # caller may set ``visual_style`` on the resulting body

    # Canonical approved identity only — do not dump every character-sheet frame
    # into the provider array (those extras are never loaded by a one-slot graph).
    reference_image_ids: list[str] = []
    for char in char_meta:
        if char.get("approved_casting_asset_id"):
            reference_image_ids.append(char["approved_casting_asset_id"])
    for prop in prop_meta:
        visual = (prop.get("approved_asset_id") or prop.get("library_asset_id") or "").strip()
        if visual and visual not in reference_image_ids:
            reference_image_ids.append(visual)

    directional_ref: dict[str, Any] = {}
    if ers_package and shot.orientation in {"north", "east", "south", "west"}:
        asset_id = ers_package.directional_assets.get(shot.orientation)  # type: ignore[arg-type]
        if asset_id:
            directional_ref = {
                "direction": shot.orientation,
                "asset_id": asset_id,
            }
            if asset_id not in reference_image_ids:
                reference_image_ids.append(asset_id)

    composite_id = ""
    if ers_package:
        composite_id = str(getattr(ers_package, "ers_composite_asset_id", None) or "").strip()
    directional_present = bool(
        (directional_ref.get("asset_id") if directional_ref else "")
        or any(
            str(v or "").strip()
            for v in ((ers_package.directional_assets or {}).values() if ers_package else [])
        )
    )
    identity_ids = identity_reference_ids(char_meta, prop_meta)
    # When N/E/S/W views are empty, the sheet composite IS the ERS environment.
    # Keep it on the request, but never ahead of approved character/prop identity.
    if ers_package and composite_id and not directional_present:
        reference_image_ids = place_ers_composite_in_refs(
            reference_image_ids, composite_id, identity_ids
        )

    # Compose the visible prompt: additional instructions + framing/angle/orientation
    # modifiers + named entities (already-resolved names for clarity in the model).
    char_names = [c.get("name") for c in char_meta if c.get("name")]
    prop_labels = [p.get("display_label") for p in prop_meta if p.get("display_label")]
    prompt_parts: list[str] = []
    if structured_blocking.get("lines"):
        prompt_parts.extend(structured_blocking["lines"])
        if structured_blocking.get("conceptual_prose"):
            prompt_parts.append(structured_blocking["conceptual_prose"])
    else:
        if char_names:
            prompt_parts.append("Characters: " + ", ".join(char_names))
        if prop_labels:
            prompt_parts.append("Props: " + ", ".join(prop_labels))
    prop_facts = [p.get("description") for p in prop_meta if p.get("description")]
    if prop_facts:
        prompt_parts.append("Prop details: " + " ".join(prop_facts))
    if shot.framing:
        prompt_parts.append(f"Framing: {shot.framing}")
    if shot.angle:
        prompt_parts.append(f"Camera angle: {shot.angle}")
    if shot.orientation:
        prompt_parts.append(f"View direction: {shot.orientation} (scene-relative)")
    if shot.additional_instructions:
        prompt_parts.append(shot.additional_instructions)
    prompt = ". ".join(part for part in prompt_parts if part).strip()

    # Style-aware model selection for scene shots. Scene shots frequently carry
    # approved casting / ERS directional reference images — when a reference is
    # attached we keep the reference-capable default (zimage) so reference-
    # conditioned generation is never downgraded to a text-only engine
    # (Reference Law). When no reference is attached, consult the style→engine
    # recommender using the layered visual style (project > environment) so
    # anime/animation scenes prefer Illustrious XL while photoreal scenes keep
    # the realism engine.
    routing_style = project_style or environment_style or (character_styles[0] if character_styles else "")
    # Do not silently switch the selected family to zimage because references exist.
    # Enqueue locks the filmmaker's generator; Image Core picks a Certified path.
    try:
        from ..image_product.recommend import recommend_image_family

        rec = recommend_image_family(
            prompt=prompt,
            purpose="scene_shot",
            operation="image.generate",
            style=routing_style or None,
        )
        scene_model_family = rec.get("executionFamily") or "zimage"
    except Exception:
        scene_model_family = "zimage"
    scene_workflow_key = f"{scene_model_family}.txt2img"

    creative_context: dict[str, Any] = {
        "objective": "scene_shot",
        "shot_index": shot.index,
        "shot_raw_text": shot.raw_text,
        "characters": char_meta,
        "prop_entities": prop_meta,
        "framing": shot.framing,
        "angle": shot.angle,
        "orientation": shot.orientation,
        "ers_package_id": ers_package.id if ers_package else "",
        "ers_composite_asset_id": composite_id or None,
        "ers_directional_ref": directional_ref,
        "structured_blocking": structured_blocking,
        # Layered styles — NOT flattened.
        "style_layers": {
            "project": project_style,
            "environment": environment_style,
            "characters": character_styles,
            "user": user_style,
        },
        "workflowKey": scene_workflow_key,
    }

    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": "",
        "width": width,
        "height": height,
        "tag": f"scene_shot_{shot.index}",
        "modelFamilyPreference": scene_model_family,
        "purpose": "scene_shot",
        "aspectRatio": aspect,
        "batchCount": 1,
        "creativeContext": creative_context,
    }

    if reference_image_ids:
        # ``enqueue_imagegen_job`` accepts either ``referenceImage`` or
        # ``reference_image``; provide both for parity with image_generate.py.
        primary = primary_reference_image(reference_image_ids, identity_ids, composite_id)
        body["referenceImage"] = primary
        body["reference_image"] = primary
        body["creativeContext"]["reference_image_ids"] = reference_image_ids

    return body


def _project_visual_style(db: Session, project_id: str) -> str:
    """Best-effort read of the project-level visual style (never raises)."""
    try:
        from ..db import Project

        project = db.get(Project, project_id)
        if not project:
            return ""
        # Project visual style may live in settings_json or a dedicated column;
        # use whatever exists without inventing new state.
        for attr in ("visual_style", "style"):
            value = getattr(project, attr, None)
            if value:
                return str(value)
        settings_raw = getattr(project, "settings_json", None) or "{}"
        if isinstance(settings_raw, str):
            import json

            try:
                settings = json.loads(settings_raw)
            except Exception:
                settings = {}
            else:
                if isinstance(settings, dict):
                    for key in ("visual_style", "style", "globalStyle"):
                        value = settings.get(key)
                        if value:
                            return str(value)
    except Exception:
        return ""
    return ""


# ---------------------------------------------------------------------------
# Optional: load ERS package by id (helper for handlers)
# ---------------------------------------------------------------------------


def get_ers_package(db: Session, project_id: str, ers_package_id: str) -> EnvironmentReferencePackage | None:
    """Convenience wrapper so handlers don't import ers_persistence directly."""
    if not ers_package_id:
        return None
    return load_ers_package(db, project_id, ers_package_id)
