"""Fill arguments the existing tool contracts already store.

The model chooses the tool. These bindings only copy duration, ratio, reference,
and brief from the creator's own words onto parameters that sanitize would
otherwise drop. They do not pick a different tool.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

_RATIO = re.compile(r"\b(\d{1,2}:\d{1,2})\b")
_SECONDS = re.compile(r"\b(\d+(?:\.\d+)?)\s*-?\s*seconds?\b", re.I)
_NAMED = re.compile(r"\bnamed\s+((?:[A-Z][\w'-]+)(?:\s+[A-Z][\w'-]+)*)")
_REFERENCE = re.compile(
    r"\b([A-Z][\w'-]+)'s existing\b|\bexisting\s+([A-Z][\w'-]+)\s+(?:prop\s+)?reference\b",
)
_PROP_OBJECT = re.compile(
    r"\b(?:create|make|generate)\s+(?:(?:a|an|the)\s+)?(.+?)\s+as a prop\b",
    re.I,
)
_SHEET_NAME = re.compile(
    r"\b(?:named|for)\s+((?:[A-Z][\w'-]+)(?:\s+[A-Z][\w'-]+)*)",
)
_USE_CHARACTER = re.compile(
    r"\b(use|using|with|featuring|include|including)\s+([A-Za-z][\w'-]+)",
    re.I,
)
_EXPLICIT_CHARACTER = frozenset({"use", "using", "named"})
_NOT_A_CHARACTER = frozenset(
    {
        "timeline",
        "scene",
        "video",
        "image",
        "studio",
        "creator",
        "reference",
        "prompt",
        "format",
        "character",
        "prop",
        "environment",
        "audio",
        "voice",
        "the",
        "a",
        "an",
        "this",
        "that",
        "my",
        "our",
        "minimax",
        "ltx",
        "seedance",
        "kling",
        "veo",
        "wan",
        "hailuo",
        "h3",
    }
)
_TIMELINE_CHARACTER_TOOLS = frozenset(
    {
        "create_scene",
        "references.attach",
        "timeline.propose_add_prompt_segment",
    }
)
_SHEET_MARKERS = (
    "reference sheet",
    "visual sheet",
    "character sheet",
    "multi-view",
    "multiview",
    "multi view",
)

# Same payload the Prop Creator Generate button sends when Local Identity Engine
# is on, Cloud Generators are off, and Auto Select is on. Resolution stays in
# build_prop_candidate_plans.
PROP_CREATOR_BUTTON_SOURCES: dict[str, Any] = {
    "local": [{"family": "auto", "enabled": True, "batchCount": 1}],
    "api": None,
    "stage2Enabled": False,
    "styleEngine": {"enabled": False},
}
QWEN_EXPRESS_SOURCES: dict[str, Any] = {
    "local": [{"family": "qwen2512", "enabled": True, "batchCount": 1}],
    "api": None,
    "stage2Enabled": False,
    "styleEngine": {"enabled": False},
}


def is_reference_sheet_request(text: str) -> bool:
    """Creator asked for a Character Reference Sheet, not a new character."""

    folded = " ".join(_plain(text).lower().split())
    return any(marker in folded for marker in _SHEET_MARKERS)


def is_new_character_request(text: str) -> bool:
    """Creator asked Character Creator to persist a new profile."""

    if is_reference_sheet_request(text):
        return False
    folded = " ".join(_plain(text).lower().split())
    if "new character" in folded:
        return True
    return "create " in folded and "character" in folded and "named " in folded


def sheet_character_name(text: str) -> str | None:
    match = _SHEET_NAME.search(_plain(text))
    if not match:
        return None
    name = match.group(1).strip()
    if name.casefold() in {"the", "a", "an", "this", "that", "current"}:
        return None
    return name


def is_environment_generation_request(text: str) -> bool:
    """Creator asked for an environment image, not a shelved Spatial Map tool."""

    folded = " ".join(_plain(text).lower().split())
    if any(phrase in folded for phrase in ("do not generate", "don't generate", "do not create", "don't create")):
        return False
    mentions_environment = any(
        marker in folded
        for marker in (
            "environment reference",
            "environment sheet",
            "environment creator",
            "an environment",
            "new environment",
        )
    )
    return mentions_environment and any(phrase in folded for phrase in ("create ", "generate ", "make "))


def timeline_execution_plan(text: str) -> list[dict[str, Any]] | None:
    """One ordered plan of existing Timeline tools. Duration stays on create_scene."""

    folded = " ".join(_plain(text).lower().split())
    creating = any(phrase in folded for phrase in ("create a scene", "create a new scene", "new scene"))
    if not creating:
        return None
    seconds = requested_seconds(text)
    attaching = "attach" in folded and "reference" in folded
    if not attaching:
        return None
    first: dict[str, Any] = {"toolId": "create_scene", "arguments": {}}
    if seconds is not None:
        first["arguments"]["durationSec"] = seconds
    return [first, {"toolId": "references.attach", "arguments": {}}]


def ordered_execution_plan(text: str) -> list[dict[str, Any]] | None:
    """The only tools a compound request may store. The model cannot add more."""

    timeline = timeline_execution_plan(text)
    if timeline:
        return timeline
    folded = " ".join(_plain(text).lower().split())
    if is_prop_generation_request(text) and "reference sheet" in folded:
        return [
            {"toolId": "prop_creator.generate_view", "arguments": {}},
            {"toolId": "prop_creator.generate_reference_sheet", "arguments": {}},
        ]
    return None


def is_prop_generation_request(text: str) -> bool:
    """Creator asked Prop Creator to make a prop image, not only to talk about one."""

    folded = " ".join(_plain(text).lower().split())
    if "prop creator" not in folded:
        return False
    if any(phrase in folded for phrase in ("do not generate", "don't generate", "do not create", "don't create")):
        return False
    return any(phrase in folded for phrase in ("create ", "generate ", "make "))


def _plain(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')


def requested_seconds(text: str) -> float | None:
    match = _SECONDS.search(text or "")
    if not match:
        return None
    value = float(match.group(1))
    if value < 0.5 or value > 20:
        return None
    return value


def requested_ratio(text: str) -> str | None:
    match = _RATIO.search(text or "")
    return match.group(1) if match else None


_CALLED_SCENE = re.compile(r"\bcalled\s+([^.!\n]{1,120})", re.I)


_ENGINE_PHRASES = (
    ("base optimized", "minimax-h3-base-optimized"),
    ("faster local h3", "minimax-h3-base-optimized"),
    ("standard h3", "minimax-h3"),
    ("hunyuanvideo 1.5", "hunyuan-video-1.5-distilled"),
    ("hunyuan video 1.5", "hunyuan-video-1.5-distilled"),
    ("minimax", "minimax-h3"),
    ("ltx", "ltx-2.5"),
    ("seedance", "fal_seedance"),
    ("kling", "fal_kling"),
    ("veo", "fal_veo"),
    ("runway", "fal_runway"),
)
_LEGAL_SCENE_ENGINES = frozenset(
    {
        "auto",
        "minimax-h3",
        "minimax-h3-base-optimized",
        "ltx-2.5",
        "hunyuan-video-1.5-distilled",
        "fal_seedance",
        "fal_kling",
        "fal_veo",
        "fal_runway",
    }
)


_MEGAPIXELS = re.compile(r"\b(\d+(?:\.\d+)?)\s*-?\s*megapixels?\b", re.I)


def requested_megapixels(text: str) -> float | None:
    match = _MEGAPIXELS.search(text or "")
    if not match:
        return None
    value = float(match.group(1))
    if value <= 0 or value > 4:
        return None
    return value


def requested_engine(text: str) -> str | None:
    """Legal scene engine named in the creator's words. MiniMax H3 Local is minimax-h3."""

    folded = (text or "").casefold()
    for needle, engine in _ENGINE_PHRASES:
        if needle in folded:
            return engine
    return None


def requested_scene_name(text: str) -> str | None:
    """The scene title after 'called'. Generator and shot instructions stay out of the title."""

    match = _CALLED_SCENE.search(text or "")
    if not match:
        return None
    name = match.group(1).strip(" \t-—")
    return name or None


def _reference_name(text: str) -> str | None:
    match = _REFERENCE.search(text or "")
    if not match:
        return None
    return next(group for group in match.groups() if group)


def _approved_reference_id(db: Session, project_id: str, name: str) -> str | None:
    from ...project_library.codirector import search_library_assets

    found = search_library_assets(db, project_id, query=name, limit=8)
    items = list(found.get("items") or [])
    approved = [item for item in items if str(item.get("approvalState") or "") == "approved"]
    if not approved:
        return None
    return str(approved[0].get("id") or "") or None


def _names_equal(left: str, right: str) -> bool:
    from ...creator_scope.contract import normalize_profile_name

    return normalize_profile_name(left) == normalize_profile_name(right) and bool(normalize_profile_name(left))


def _named_profiles(db: Session, project_id: str, name: str) -> tuple[list[Any], list[Any]]:
    """Exact display-name matches: profiles in this project, then other global profiles."""

    from sqlalchemy import or_

    from ...character_identity.models import CharacterProfileRow

    visible = (
        db.query(CharacterProfileRow)
        .filter(
            or_(
                CharacterProfileRow.project_id == project_id,
                CharacterProfileRow.is_global.is_(True),
            )
        )
        .all()
    )
    owned = [
        row
        for row in visible
        if row.project_id == project_id and row.name and _names_equal(row.name, name)
    ]
    others = [
        row
        for row in visible
        if row.project_id != project_id and row.name and _names_equal(row.name, name)
    ]
    return owned, others


def _not_found_character(name: str = "") -> str:
    who = (name or "that character").strip() or "that character"
    return f"I couldn't find {who} in the current project or available global characters."


def visible_character_matches(payload: Any) -> list[dict[str, str]]:
    """Read a character.search result. A null source name does not reject a match.

    The canonical envelope stores matches at data.matches. A bare handler dict
    stores them at matches. Either shape is the same search.
    """

    node: Any = payload
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except json.JSONDecodeError:
            return []
    if not isinstance(node, dict):
        return []
    read = node.get("evidence")
    if isinstance(read, dict) and isinstance(read.get("read"), dict):
        inner = read["read"]
        if isinstance(inner.get("result"), dict):
            node = inner["result"]
    data = node.get("data") if isinstance(node.get("data"), dict) else node
    raw_matches = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(raw_matches, list):
        return []
    found: list[dict[str, str]] = []
    for item in raw_matches:
        if not isinstance(item, dict):
            continue
        name = str(item.get("displayName") or item.get("name") or "").strip()
        character_id = str(item.get("characterId") or "").strip()
        if not name or not character_id:
            continue
        found.append({"displayName": name, "characterId": character_id})
    return found


def _ambiguous_character(name: str) -> str:
    return f"I found more than one character named {name}. Which one would you like me to use?"


def _intended_character_names(db: Session, project_id: str, text: str) -> list[str]:
    """Names the creator asked to use, plus known names already written in the request."""

    from ...character_identity.service import list_profiles
    from ...director_timeline_w46.generation.character_identity_bind import mentioned_character_names

    known: list[str] = []
    try:
        known = [str(profile.name).strip() for profile in list_profiles(db, project_id) if str(profile.name or "").strip()]
    except Exception:
        known = []
    found = mentioned_character_names(text, known)
    seen = {name.casefold() for name in found}
    known_by_fold = {name.casefold(): name for name in known}
    for match in _USE_CHARACTER.finditer(text or ""):
        introducer = match.group(1).strip().casefold()
        token = match.group(2).strip()
        folded = token.casefold()
        if folded in _NOT_A_CHARACTER or folded in seen:
            continue
        known_name = known_by_fold.get(folded)
        if known_name:
            seen.add(folded)
            found.append(known_name)
            continue
        if introducer in _EXPLICIT_CHARACTER:
            seen.add(folded)
            found.append(token)
    return found


_GENERIC_ENTITY_WORDS = frozenset(
    {
        "coffee",
        "house",
        "shop",
        "metal",
        "silver",
        "scene",
        "table",
        "window",
        "character",
        "inside",
        "filled",
        "green",
        "liquid",
    }
)


def _entity_tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", value or "")
        if token.casefold() not in _GENERIC_ENTITY_WORDS
    }


def _best_visible_label(text: str, labels: list[str]) -> str:
    """One visible name, or nothing when the text fits more than one."""

    exact = _matching_label(text, labels)
    if exact:
        same = [label for label in labels if label.casefold() == exact.casefold()]
        return exact if len(same) == 1 else ""
    text_tokens = _entity_tokens(text)
    scored: list[tuple[int, str]] = []
    for label in labels:
        overlap = _entity_tokens(label) & text_tokens
        distinctive = {token for token in overlap if len(token) >= 6}
        if not distinctive:
            continue
        scored.append((len(distinctive), label))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1].casefold()))
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return ""
    return scored[0][1]


def _matching_label(text: str, labels: list[str]) -> str:
    best = ""
    for label in labels:
        token = str(label or "").strip()
        if len(token) < 3:
            continue
        if re.search(rf"\b{re.escape(token)}\b", text or "", flags=re.I) and len(token) > len(best):
            best = token
    return best


def _remember_scene_entities(db: Session, project_id: str, text: str, args: dict[str, Any]) -> None:
    """Copy creator-facing prop and environment names onto the stored proposal."""

    if not str(args.get("propName") or "").strip():
        labels: list[str] = []
        try:
            from ...prop_creator.service import list_props

            labels = [
                str(getattr(prop, "display_label", "") or getattr(prop, "name", "") or "").strip()
                for prop in list_props(db, project_id)
            ]
        except Exception:
            labels = []
        prop_name = _best_visible_label(text, labels)
        if prop_name:
            args["propName"] = prop_name
    if not str(args.get("environmentName") or "").strip():
        labels = []
        try:
            from ...environment_reference_sheet.store import (
                list_visible_sheets,
                sheet_is_project_reference,
            )

            labels = [
                str(getattr(sheet, "name", "") or "").strip()
                for sheet in list_visible_sheets(db, project_id)
                if sheet_is_project_reference(sheet)
            ]
        except Exception:
            labels = []
        environment_name = _best_visible_label(text, labels)
        if environment_name:
            args["environmentName"] = environment_name


def _bind_timeline_character(
    db: Session,
    project_id: str,
    text: str,
    args: dict[str, Any],
    *,
    tool_id: str,
) -> str | None:
    """Resolve a named character onto the existing reference attachment fields.

    A model-supplied id is discarded. The persisted profile id is stored only
    after an exact name match.
    """

    args.pop("characterId", None)
    named = _intended_character_names(db, project_id, text)
    explicit = str(args.get("characterName") or "").strip()
    if explicit and explicit.casefold() not in {name.casefold() for name in named}:
        named.insert(0, explicit)
    _remember_scene_entities(db, project_id, text, args)
    if not named:
        return None
    from ..entity_resolver import resolve_character

    bound: list[Any] = []
    for name in named:
        owned, others = _named_profiles(db, project_id, name)
        matches = owned if owned else others
        if len(matches) > 1:
            return _ambiguous_character(str(getattr(matches[0], "name", "") or name))
        if len(matches) == 1:
            bound.append(matches[0])
            continue
        if name.casefold() in _NOT_A_CHARACTER:
            continue
        return _not_found_character(name)
    unique: list[Any] = []
    seen: set[str] = set()
    for profile in bound:
        token = str(getattr(profile, "id", "") or "")
        if token and token not in seen:
            seen.add(token)
            unique.append(profile)
    if not unique:
        return None
    profile = unique[0]
    args["characterId"] = str(profile.id)
    args["characterName"] = str(getattr(profile, "name", "") or "")
    hit = resolve_character(db, project_id, args["characterName"]) or {}
    asset_id = str(
        hit.get("approved_casting_asset_id")
        or hit.get("approved_sheet_asset_id")
        or ""
    ).strip()
    if asset_id:
        args["assetId"] = asset_id
    args["identityId"] = str(profile.id)
    if tool_id == "references.attach":
        args["referenceType"] = "character"
        args.setdefault("scopeType", "scene")
        args["usageModes"] = ["informational", "generation"]
        args["referenceRoles"] = ["character"]
    return None


def _remember_profile(args: dict[str, Any], profile: Any, db: Session) -> None:
    from ...character_identity import service as ci

    args["characterId"] = str(profile.id)
    args["characterName"] = str(getattr(profile, "name", "") or "")
    description = str(getattr(profile, "description", "") or "").strip()
    if description:
        args["profileSummary"] = description[:400]
    hero = ci.resolve_approved_reference(db, str(profile.id), "hero_identity")
    if hero and not str(args.get("heroAssetId") or "").strip():
        args["heroAssetId"] = hero


def _bind_visual_sheet(
    db: Session,
    args: dict[str, Any],
    text: str,
    project_id: str,
    selected_character_id: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Store the persisted profile id. Do not keep an id the model invented."""

    from ...character_identity import service as ci

    args.pop("characterId", None)
    named = sheet_character_name(text)
    selected = str(selected_character_id or "").strip()
    if selected:
        try:
            profile = ci.get_profile(db, project_id, selected)
        except Exception:
            profile = None
        if profile is not None and (not named or _names_equal(str(getattr(profile, "name", "") or ""), named)):
            _remember_profile(args, profile, db)
            return args, None
    if not named:
        return args, (
            "Name the character whose reference sheet to create, "
            "or open that character in Character Creator. I did not guess an id."
        )
    owned, others = _named_profiles(db, project_id, named)
    matches = owned if owned else others
    if len(matches) == 1:
        _remember_profile(args, matches[0], db)
        return args, None
    if len(matches) > 1:
        return args, (
            f"More than one character is named {named}. Tell me which one to use. I did not guess."
        )
    return args, (
        f"I couldn't find a character named {named}. "
        "I did not create a reference sheet or invent a character id."
    )


def _prop_has_reference(db: Session, project_id: str, args: dict[str, Any]) -> bool:
    """An approved prop image stays the identity. A new prop has none."""

    if str(args.get("referenceAssetId") or args.get("reference_asset_id") or "").strip():
        return True
    if db is None:
        return False
    name = str(args.get("name") or args.get("propName") or "").strip().lower()
    if not name:
        return False
    from ...prop_creator.service import list_props

    for prop in list_props(db, project_id):
        label = str(getattr(prop, "display_label", "") or getattr(prop, "name", "") or "").strip().lower()
        if label == name and str(getattr(prop, "reference_asset_id", "") or "").strip():
            return True
    return False


_SPOKEN_LINE = re.compile(r"[\"“](.+?)[\"”]")
_TONE = re.compile(r"\bin an?\s+(.{3,160}?)\s+tone\b", re.I)
_GIVE_VOICE = re.compile(r"\bgive\s+[A-Za-z][\w'-]*\s+(?:an?\s+)?(.+?)\s+voice\b", re.I)
_VOICE_CHARACTER_TOOLS = {
    "character_creator.get_voice_status",
    "character_creator.get_voice_profile",
    "character_creator.get_voice_candidates",
    "character_creator.open_voice_creator",
    "character_creator.preview_voice_design",
    "character_creator.generate_voice_candidates",
    "character_creator.approve_voice_candidate",
}
_AUDIO_GENERATE = {
    "audio.generate_sfx": "sfx",
    "audio.generate_ambience": "ambience",
    "audio.generate_music": "music",
}


def _bind_voice(
    db: Session,
    project_id: str,
    text: str,
    args: dict[str, Any],
    *,
    tool_id: str,
) -> tuple[dict[str, Any], str | None]:
    refusal = _bind_timeline_character(db, project_id, text, args, tool_id=tool_id)
    if refusal:
        return args, refusal
    if tool_id not in {"character_creator.generate_voice_candidates", "character_creator.preview_voice_design"}:
        return args, None
    spoken = _SPOKEN_LINE.search(text)
    if spoken:
        args["testLine"] = spoken.group(1).strip().strip(",").strip()[:500]
    else:
        supplied = str(args.get("testLine") or "").strip()
        if supplied and supplied.casefold() not in text.casefold():
            args.pop("testLine", None)
    performance = ""
    tone = _TONE.search(text)
    if tone:
        performance = tone.group(1).strip()
    else:
        given = _GIVE_VOICE.search(text)
        if given:
            performance = given.group(1).strip().strip(",")
    if performance:
        args["performance"] = performance[:180]
    if not str(args.get("designBriefJson") or "").strip():
        brief: dict[str, Any] = {"additionalDirection": text.strip()[:2000], "language": "English"}
        folded = text.lower()
        if "masculine" in folded:
            brief["gender"] = "masculine"
        elif "feminine" in folded:
            brief["gender"] = "feminine"
        if "deep" in folded:
            brief["pitchRange"] = "low"
            brief["vocalRegister"] = "low"
        if performance:
            brief["delivery"] = performance[:180]
        args["designBriefJson"] = json.dumps(brief)
    elif performance:
        try:
            brief = json.loads(str(args.get("designBriefJson") or ""))
        except json.JSONDecodeError:
            brief = None
        if isinstance(brief, dict) and not str(brief.get("delivery") or brief.get("tone") or "").strip():
            brief["delivery"] = performance[:180]
            args["designBriefJson"] = json.dumps(brief)
    if args.get("characterName") and not str(args.get("name") or "").strip():
        args["name"] = str(args["characterName"])[:120]
    if not re.search(r"\b(?:two|three|four|five|\d+)\s+(?:voice|candidate)", text, re.I):
        args["candidateCount"] = 1
    return args, None


def _bind_audio(
    text: str,
    args: dict[str, Any],
    *,
    tool_id: str,
    scene_id: str | None,
) -> tuple[dict[str, Any], str | None]:
    if text.strip() and len(text.strip()) >= len(str(args.get("prompt") or "").strip()):
        args["prompt"] = text.strip()[:4000]
    if scene_id and not str(args.get("sceneId") or "").strip():
        args["sceneId"] = scene_id
    kind = _AUDIO_GENERATE[tool_id]
    minimum = 1 if kind in {"ambience", "music"} else 0.5
    try:
        duration = float(args.get("durationSec"))
    except (TypeError, ValueError):
        duration = None
    if duration is None or duration < minimum:
        args.pop("durationSec", None)
    if kind == "sfx" and not args.get("durationSec"):
        args["durationSec"] = 2
    if kind == "ambience" and args.get("loopRequired") is None:
        args["loopRequired"] = True
    return args, None


_AT_SECONDS = re.compile(
    r"\bat\s+(\d+(?:\.\d+)?)\s*(?:seconds|second|secs|sec|s)\b",
    re.I,
)


def _bind_magi_recipe(text: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    from ...magi.recipes import canonical_recipe_id

    current = canonical_recipe_id(str(args.get("recipeId") or ""))
    if not current:
        folded = text.lower()
        for name in (
            "music video",
            "commercial",
            "interview",
            "podcast",
            "narrative",
            "trailer",
            "documentary",
            "anime",
            "cinematic",
            "social",
        ):
            if name in folded:
                current = canonical_recipe_id(name)
                break
    if not current:
        return args, "Say which MAGI recipe to apply."
    args["recipeId"] = current
    return args, None


def _bind_magi_lighting(text: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    folded = text.lower()
    if any(word in folded for word in ("slightly", "a little", "little")):
        if "warm" in folded:
            args["temperatureDelta"] = 0.08
        elif "cool" in folded:
            args["temperatureDelta"] = -0.08
        if "bright" in folded:
            args["brightnessDelta"] = 0.06
    elif "warm" in folded and not args.get("lightingPresetId"):
        args["lightingPresetId"] = "warm"
    elif "cool" in folded and not args.get("lightingPresetId"):
        args["lightingPresetId"] = "cool"
    if "brightness" in folded and args.get("brightness") is None and args.get("brightnessDelta") is None:
        args["brightnessDelta"] = 0.06
    return args, None


def _bind_magi_transition(text: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    from ...magi.transitions import canonical_transition

    folded = text.lower()
    kind = canonical_transition(str(args.get("kind") or ""))
    if not kind:
        for name in ("dissolve", "wipe", "fade", "none"):
            if name in folded:
                kind = name
                break
    if not kind:
        return args, "Say dissolve, fade, wipe, or none."
    args["kind"] = kind
    if args.get("durationSeconds") is None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*seconds?", folded)
        if match:
            args["durationSeconds"] = float(match.group(1))
        elif "one-second" in folded or "one second" in folded:
            args["durationSeconds"] = 1.0
    return args, None


def _bind_magi_compare(text: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    folded = text.lower()
    args["mode"] = "split" if "split" in folded else str(args.get("mode") or "compare")
    if "original" in folded or not str(args.get("assetId") or "").strip():
        args["assetId"] = "original"
    return args, None


def _bind_magi_audio(text: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Bind the MAGI music/SFX owner from the creator sentence. Empty model args are expected."""

    from .admission import audio_operation

    kind = audio_operation(text)
    if kind in {"music", "sfx"}:
        args["kind"] = kind
    elif str(args.get("kind") or "") not in {"music", "sfx", "all"}:
        args["kind"] = "music"
    if text.strip() and len(text.strip()) >= len(str(args.get("prompt") or "").strip()):
        args["prompt"] = text.strip()[:2000]
    if str(args.get("range") or "") not in {"entire", "clip"}:
        args["range"] = "clip" if str(args.get("clipId") or "").strip() else "entire"
    found = _AT_SECONDS.search(text or "")
    if found:
        args["startSeconds"] = float(found.group(1))
        if args.get("kind") == "sfx" and args.get("duration") is None:
            args["duration"] = 2.0
    return args, None


def bind_request_arguments(
    db: Session,
    *,
    tool_id: str,
    arguments: dict[str, Any] | None,
    user_text: str,
    project_id: str,
    selected_character_id: str | None = None,
    scene_id: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Return arguments plus a refusal when a requested existing reference is missing."""

    args = dict(arguments or {})
    text = _plain(user_text or "")
    if tool_id == "timeline.propose_add_prompt_segment":
        seconds = requested_seconds(text)
        ratio = requested_ratio(text)
        if seconds is not None:
            args["sceneDurationSec"] = seconds
            args["length"] = seconds
            args["start"] = 0
            shaped = f"[0s-{seconds:g}s] {text.strip()}"
            current = str(args.get("text") or "")
            if "[0s-" not in current.lower() or len(current) < len(shaped):
                args["text"] = shaped
        revision = args.get("timelineRevision")
        try:
            if revision is None or int(revision) < 1:
                args.pop("timelineRevision", None)
        except (TypeError, ValueError):
            args.pop("timelineRevision", None)
        if ratio:
            args["aspectRatio"] = ratio
        refusal = _bind_timeline_character(db, project_id, text, args, tool_id=tool_id)
        if refusal:
            return args, refusal
    elif tool_id in {"timeline.continue_shot", "timeline.prepend_shot"}:
        seconds = requested_seconds(text)
        if seconds is not None and args.get("durationSec") is None:
            args["durationSec"] = seconds
        if text.strip() and not str(args.get("prompt") or "").strip():
            args["prompt"] = text.strip()
    elif tool_id == "timeline.generate_shot":
        megapixels = requested_megapixels(text)
        if megapixels is not None and args.get("megapixels") is None:
            args["megapixels"] = megapixels
    elif tool_id == "create_scene":
        seconds = requested_seconds(text)
        ratio = requested_ratio(text)
        if seconds is not None and args.get("durationSec") is None:
            args["durationSec"] = seconds
        if ratio and not args.get("aspectRatio"):
            args["aspectRatio"] = ratio
        if text.strip() and not str(args.get("prompt") or "").strip():
            args["prompt"] = text.strip()
        if not str(args.get("name") or "").strip():
            scene_name = requested_scene_name(text)
            if scene_name:
                args["name"] = scene_name
        named_engine = requested_engine(text)
        current_engine = str(args.get("engine") or "").strip()
        if named_engine:
            args["engine"] = named_engine
        elif current_engine not in _LEGAL_SCENE_ENGINES:
            args.pop("engine", None)
        refusal = _bind_timeline_character(db, project_id, text, args, tool_id=tool_id)
        if refusal:
            return args, refusal
    elif tool_id == "references.attach":
        refusal = _bind_timeline_character(db, project_id, text, args, tool_id=tool_id)
        if refusal:
            return args, refusal
    elif tool_id == "propose_image_generate":
        ratio = requested_ratio(text)
        if ratio and not args.get("aspectRatio"):
            args["aspectRatio"] = ratio
        if text.strip() and not str(args.get("prompt") or "").strip():
            args["prompt"] = text.strip()[:4000]
        if str(args.get("qualityProfile") or "") not in {"draft", "standard", "high"}:
            args.pop("qualityProfile", None)
        if str(args.get("modelFamilyPreference") or "") not in {"zimage", "flux", "qwen", "imagen"}:
            args.pop("modelFamilyPreference", None)
        reference_name = _reference_name(text)
        if reference_name and not args.get("referenceAssetId"):
            asset_id = _approved_reference_id(db, project_id, reference_name)
            if not asset_id:
                return args, (
                    f"No approved {reference_name} reference is in this project. "
                    "I did not invent one or generate a still from the description alone."
                )
            args["referenceAssetId"] = asset_id
    elif tool_id == "character_creator.create_from_brief":
        named = _NAMED.search(text)
        if named and not str(args.get("name") or "").strip():
            args["name"] = named.group(1).strip()
        brief = text.strip()
        if brief and len(brief) >= len(str(args.get("brief") or "")):
            args["brief"] = brief[:8000]
        if args.get("brief") and not str(args.get("description") or "").strip():
            args["description"] = str(args["brief"])[:4000]
        folded = " ".join(text.lower().split())
        if "new character" in folded or "do not modify" in folded or "don't modify" in folded:
            args["requireNew"] = True
    elif tool_id == "character_creator.propose_visual_sheet":
        return _bind_visual_sheet(db, args, text, project_id, selected_character_id)
    elif tool_id == "ers.generate":
        if text.strip() and not str(args.get("description") or args.get("prompt") or "").strip():
            args["description"] = text.strip()[:4000]
            args["prompt"] = text.strip()[:4000]
            args["environmentPrompt"] = text.strip()[:4000]
        named = _reference_name(text)
        if named and not str(args.get("sourceAssetId") or "").strip():
            asset_id = _approved_reference_id(db, project_id, named)
            if not asset_id:
                return args, (
                    f"No approved {named} reference is in this project. "
                    "I did not invent one."
                )
            args["sourceAssetId"] = asset_id
        if not str(args.get("sourceAssetId") or "").strip():
            args["model"] = "qwen2512"
            args["modelFamilyPreference"] = "qwen2512"
            args["forceWorkflowKey"] = "qwen2512.txt2img"
            args["lockModelFamily"] = True
    elif tool_id == "prop_creator.generate_view":
        if not str(args.get("name") or args.get("propName") or "").strip():
            found = _PROP_OBJECT.search(text)
            if found:
                args["name"] = found.group(1).strip()[:200]
        if text.strip() and not str(args.get("description") or "").strip():
            args["description"] = text.strip()[:4000]
        if not isinstance(args.get("generatorSources"), dict):
            args["generatorSources"] = dict(PROP_CREATOR_BUTTON_SOURCES)
        args["local_enabled"] = True
        args["api_enabled"] = False
        if _prop_has_reference(db, project_id, args):
            if not str(args.get("local_family") or "").strip():
                args["local_family"] = "auto"
        else:
            args["local_family"] = "qwen2512"
            args["generatorSources"] = dict(QWEN_EXPRESS_SOURCES)
            args["api_enabled"] = False
        if args.get("candidate_count") is None:
            args["candidate_count"] = 1
        if not str(args.get("view") or "").strip():
            args["view"] = "primary"
    elif tool_id in _VOICE_CHARACTER_TOOLS:
        return _bind_voice(db, project_id, text, args, tool_id=tool_id)
    elif tool_id in _AUDIO_GENERATE:
        return _bind_audio(text, args, tool_id=tool_id, scene_id=scene_id)
    elif tool_id == "magi.audio.generate":
        return _bind_magi_audio(text, args)
    elif tool_id == "magi.recipe.apply":
        return _bind_magi_recipe(text, args)
    elif tool_id == "magi.color.apply":
        return _bind_magi_lighting(text, args)
    elif tool_id == "magi.transition.apply":
        return _bind_magi_transition(text, args)
    elif tool_id == "magi.compare":
        return _bind_magi_compare(text, args)
    elif tool_id == "magi.render":
        args["profile"] = "final"
        args.pop("upscale", None)
    elif tool_id == "film_timeline.send_to_magi":
        from ..tools.handlers.scenes import _usable_id, latest_ready_published_scene

        named = _usable_id(args.get("sceneId"))
        if named and named.lower() not in text.lower():
            named = ""
        if named:
            args["sceneId"] = named
        else:
            found = latest_ready_published_scene(db, project_id)
            if found:
                args["sceneId"] = found[0]
                if found[1]:
                    args["shotId"] = found[1]
            else:
                args.pop("sceneId", None)
                args.pop("shotId", None)
    return args, None
