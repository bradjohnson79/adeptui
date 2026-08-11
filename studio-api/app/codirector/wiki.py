"""Creator-facing Project Wiki derived from persisted conversation + confirmed project facts.

Authoritative UI source: projectIntelligence.knowledgeEntries (+ decisions),
built via build_project_wiki. Conversation events are the message source of truth
(not legacy messages_json alone).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, CoDirectorConversation, Project, Scene
from .errors import PROJECT_NOT_FOUND, CoDirectorError
from .m211.decisions import DecisionRecordStore

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_SPACE_RE = re.compile(r"\s+")

# Canonical UI section keys used by ProjectWikiPanel.
SECTION_KEYS = (
    "knownDetails",
    "creativeFoundation",
    "characters",
    "worldAndSetting",
    "storyAndEpisodes",
    "visualIdentity",
    "productionDecisions",
    "openQuestions",
    "references",
)

# Map deferred/discovery section aliases → UI section keys.
_SECTION_ALIASES: dict[str, str] = {
    "knownDetails": "knownDetails",
    "creativeFoundation": "creativeFoundation",
    "characters": "characters",
    "character": "characters",
    "worldAndSetting": "worldAndSetting",
    "world": "worldAndSetting",
    "world_and_setting": "worldAndSetting",
    "location": "worldAndSetting",
    "storyAndEpisodes": "storyAndEpisodes",
    "story": "storyAndEpisodes",
    "timeline": "storyAndEpisodes",
    "event": "storyAndEpisodes",
    "visualIdentity": "visualIdentity",
    "visual": "visualIdentity",
    "productionDecisions": "productionDecisions",
    "openQuestions": "openQuestions",
    "references": "references",
    "themes": "creativeFoundation",
    "theme": "creativeFoundation",
    "story_principle": "creativeFoundation",
    "world_rule": "worldAndSetting",
    "entity": "worldAndSetting",
    "organization": "worldAndSetting",
    "org": "worldAndSetting",
    "project": "knownDetails",
    "tone": "creativeFoundation",
    "visual_language": "visualIdentity",
    "production_constraint": "productionDecisions",
    "research_note": "references",
    "anti_reference": "references",
    "relationship": "characters",
}


def normalize_wiki_section(section: str | None, text: str = "") -> str:
    """Map any section/category alias onto a ProjectWikiPanel section key."""
    raw = str(section or "").strip()
    if raw in SECTION_KEYS:
        return raw
    mapped = _SECTION_ALIASES.get(raw) or _SECTION_ALIASES.get(raw.lower())
    if mapped:
        return mapped
    return _section_key_for_message(text)


def _sanitize_text(value: str, *, limit: int = 320) -> str:
    text = _UUID_RE.sub("", str(value or ""))
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:limit].strip()


def _empty_section(empty_state: str) -> dict[str, Any]:
    return {"summary": "", "entries": [], "emptyState": empty_state}


def _wiki_entry(
    entry_id: str,
    text: str,
    state: str,
    source_message_id: str | None = None,
    *,
    inferred: bool | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"id": entry_id, "text": _sanitize_text(text), "state": state}
    if source_message_id:
        out["sourceMessageId"] = source_message_id
    if inferred is not None:
        out["inferred"] = inferred
    elif state in {"proposed", "unresolved", "reference-only"}:
        out["inferred"] = True
    elif state in {"confirmed", "approved"}:
        out["inferred"] = False
    return out


def _load_messages(db: Session, project_id: str) -> list[dict[str, Any]]:
    """Prefer conversation events; fall back to legacy messages_json."""
    try:
        from .conversation_events import fold_events

        folded = fold_events(db, project_id)
        if folded:
            return folded
    except Exception:
        pass
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        return []
    try:
        payload = json.loads(row.messages_json or "[]")
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


_QUESTION_RE = re.compile(
    r"^(what|why|how|when|where|who|which|should|could|would|can|do|does|did|is|are|am)\b",
    re.IGNORECASE,
)
_COMMAND_RE = re.compile(
    r"^(please\s+)?(create|make|build|generate|open|go to|navigate|show|start|run|save|approve|reject|delete|rename|update|set)\b",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|got it|cool|great|yes|no|yep|nope)[.!]?\s*$",
    re.IGNORECASE,
)
_CORRECTION_RE = re.compile(r"^(correction|actually|instead|not\b)", re.IGNORECASE)


def _is_conversation_residue(text: str) -> bool:
    """Questions, greetings, and bare commands must not become Wiki canon."""
    cleaned = text.strip()
    if not cleaned:
        return True
    if _GREETING_RE.match(cleaned):
        return True
    if cleaned.endswith("?") or _QUESTION_RE.match(cleaned):
        return True
    if _COMMAND_RE.match(cleaned) and not _CORRECTION_RE.match(cleaned):
        if len(cleaned) < 80:
            return True
    return False


def _meaningful_user_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in messages:
        if str(item.get("role") or "").lower() != "user":
            continue
        text = _sanitize_text(str(item.get("content") or ""), limit=1200)
        if len(text) < 3:
            continue
        if _is_conversation_residue(text):
            continue
        out.append(
            {
                "id": str(item.get("id") or ""),
                "content": text,
                "createdAt": str(item.get("created_at") or item.get("createdAt") or ""),
            }
        )
    return out


def _section_key_for_message(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("character", "hero", "villain", "voice", "cast", "protagonist")):
        return "characters"
    if any(
        token in lower
        for token in ("world", "setting", "city", "planet", "kingdom", "forest", "town", "facility", "location")
    ):
        return "worldAndSetting"
    if any(
        token in lower
        for token in ("episode", "story", "plot", "arc", "scene", "chapter", "timeline", "season", "interview")
    ):
        return "storyAndEpisodes"
    if any(token in lower for token in ("look", "visual", "style", "color", "cinematic", "lighting", "storyboard")):
        return "visualIdentity"
    if any(
        token in lower
        for token in ("decision", "approved", "we chose", "we decided", "call this project", "name it", "title")
    ):
        return "knownDetails"
    if any(token in lower for token in ("script", "treatment", "storyboard", "footage", "audio", "music", "reference")):
        return "references"
    return "creativeFoundation"


def _build_overview(project: Project, user_messages: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> str:
    title = (project.name or "Untitled Project").strip()
    if user_messages:
        seed = user_messages[0]["content"]
        if title and title.lower() != "untitled project" and title.lower() not in seed.lower():
            return _sanitize_text(f"{title} is taking shape. Latest direction: {seed}", limit=400)
        return _sanitize_text(seed, limit=400)
    if decisions:
        return _sanitize_text(str(decisions[0].get("rationale") or decisions[0].get("recommendation") or ""), limit=400)
    return ""


def _project_status(project: Project, *, has_content: bool, decision_count: int) -> str:
    if not has_content and decision_count == 0:
        return "initialized"
    if bool(getattr(project, "archived", 0)) or decision_count >= 3:
        return "production"
    scene_count = len(getattr(project, "scenes", []) or [])
    if scene_count > 1:
        return "production"
    return "developing"


def _section_entry_count(sections: dict[str, dict[str, Any]]) -> int:
    return sum(len(s.get("entries") or []) for s in sections.values())


def _merge_discovery_candidates(db: Session, project_id: str, sections: dict[str, dict[str, Any]], knowledge_ids: set[str]) -> None:
    """Bridge discovery wiki_candidates into UI sections when not already present."""
    try:
        from .conversation.discovery.persistence import load_discovery_bundle

        bundle = load_discovery_bundle(db, project_id)
        candidates = getattr(bundle, "wiki_candidates", None) or []
        for c in candidates:
            cid = str(getattr(c, "id", "") or "")
            title = str(getattr(c, "title", "") or "").strip()
            body = str(getattr(c, "content", "") or getattr(c, "text", "") or getattr(c, "summary", "") or "").strip()
            text = f"{title}: {body}".strip(": ").strip() if title else body
            if not text:
                continue
            if cid and cid in knowledge_ids:
                continue
            cat = getattr(getattr(c, "category", None), "value", None) or getattr(c, "category", None) or ""
            section_key = normalize_wiki_section(str(cat), text)
            if section_key not in sections:
                section_key = _section_key_for_message(text)
            entry_id = cid or f"discovery-{len(knowledge_ids)+1}"
            if any(e.get("id") == entry_id or e.get("text") == text for e in sections[section_key]["entries"]):
                continue
            status = str(getattr(c, "status", "") or "")
            state = "confirmed" if status.upper() in {"CONFIRMED", "APPROVED"} else "proposed"
            sections[section_key]["entries"].append(_wiki_entry(entry_id, text, state))
            knowledge_ids.add(entry_id)
    except Exception:
        pass


def _attach_project_references(
    db: Session,
    project_id: str,
    sections: dict[str, dict[str, Any]],
    knowledge_ids: set[str],
) -> None:
    """Link library assets (images, video, audio) and production notes into References."""
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.created_at.desc())
            .limit(48)
            .all()
        )
    except Exception:
        return
    kind_labels = {
        "image": "Image",
        "video": "Video",
        "audio": "Audio",
        "storyboard": "Storyboard",
        "script": "Script",
        "treatment": "Treatment",
    }
    for asset in assets:
        aid = str(getattr(asset, "id", "") or "")
        if not aid or aid in knowledge_ids:
            continue
        kind = str(getattr(asset, "kind", "") or "asset").strip().lower() or "asset"
        filename = str(getattr(asset, "filename", "") or "").strip() or aid[:8]
        tag = str(getattr(asset, "tag", "") or "").strip()
        approval = str(getattr(asset, "production_approval", "") or "none").strip().lower()
        label = kind_labels.get(kind, kind.replace("_", " ").title())
        # Infer storyboard / script from tags or filename when kind is generic.
        lower_name = f"{tag} {filename}".lower()
        if "storyboard" in lower_name:
            label = "Storyboard"
        elif "treatment" in lower_name:
            label = "Treatment"
        elif "script" in lower_name or "screenplay" in lower_name:
            label = "Script"
        elif "concept" in lower_name:
            label = "Concept art"
        text = f"{label}: {filename}"
        if tag and tag.lower() not in filename.lower():
            text = f"{label}: {tag} ({filename})"
        state = "confirmed" if approval in {"approved", "production_approved", "yes"} else "reference-only"
        if approval in {"rejected", "blocked"}:
            state = "rejected"
        entry = _wiki_entry(f"ref-asset-{aid}", text, state, source_message_id=None)
        entry["referenceKind"] = label
        entry["assetId"] = aid
        sections["references"]["entries"].append(entry)
        knowledge_ids.add(aid)


def build_project_wiki(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        raise CoDirectorError(
            PROJECT_NOT_FOUND,
            "Project not found.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )

    messages = _load_messages(db, project_id)
    user_messages = _meaningful_user_messages(messages)
    decisions = DecisionRecordStore.list_for_project(db, project_id, limit=50)

    sections: dict[str, dict[str, Any]] = {
        "knownDetails": _empty_section("Known details will appear here as the project takes shape."),
        "creativeFoundation": _empty_section("Creative foundation notes appear after your first direction."),
        "characters": _empty_section("Characters will appear here as you define them."),
        "worldAndSetting": _empty_section("World and setting notes will appear here."),
        "storyAndEpisodes": _empty_section("Story beats and episodes will gather here."),
        "visualIdentity": _empty_section("Visual identity notes will appear here."),
        "productionDecisions": _empty_section("Saved production decisions will appear here."),
        "openQuestions": _empty_section("Open questions will stay visible until they are resolved."),
        "references": _empty_section("Scripts, images, storyboards, and other production references appear here."),
    }

    title = (project.name or "Untitled Project").strip()
    project_type = getattr(project, "primary_project_type", None) or ""
    knowledge_ids: set[str] = set()

    # Authoritative story entries from story_entries table.
    story_entry_data: list[dict[str, Any]] = []
    try:
        from app.story_entries.store import list_entries as list_story_entries

        entries = list_story_entries(db, project_id)
        for entry in entries:
            story_entry_data.append({
                "entry_id": entry.id,
                "title": entry.title,
                "entryType": entry.entry_type,
                "logline": entry.logline,
                "shortSummary": entry.short_summary,
                "longSummary": entry.long_summary,
                "sortOrder": entry.sort_order,
            })
    except Exception:
        pass

    # Authoritative character profiles from character_identity table.
    character_profile_data: list[dict[str, Any]] = []
    try:
        from app.character_identity.service import list_profiles as list_char_profiles
        from app.character_identity.models import CharacterReferenceAssetRow

        profiles = list_char_profiles(db, project_id)
        existing_profile_names: set[str] = set()
        for profile in profiles:
            existing_profile_names.add(profile.name.lower())
            refs = (
                db.query(CharacterReferenceAssetRow)
                .filter(CharacterReferenceAssetRow.character_profile_id == profile.id)
                .all()
            )
            hero_portrait = None
            approved_voice = None
            for ref in refs:
                if ref.reference_role == "hero_portrait" and (ref.canonical or ref.approval_status == "approved"):
                    hero_portrait = ref.asset_id
                if ref.reference_role == "voice":
                    approved_voice = ref.asset_id
            character_profile_data.append({
                "profile_id": profile.id,
                "name": profile.name,
                "role": profile.role,
                "description": profile.description,
                "status": str(profile.status),
                "personality": profile.personality if hasattr(profile, 'personality') else {},
                "approvedCastingImageAssetId": hero_portrait,
                "approvedVoiceAssetId": approved_voice,
                "apparentAge": profile.apparent_age,
                "speciesOrType": profile.species_or_type,
                "visualDescription": getattr(profile, 'visual_description', ''),
                "visualStyle": getattr(profile, 'visual_style', ''),
            })
    except Exception:
        existing_profile_names = set()

    # Authoritative knowledge lifecycle entries — always load before empty-state decision.
    try:
        from .conversation.snapshot import load_snapshot

        snapshot = load_snapshot(db, project_id)
        for entry in snapshot.knowledgeEntries:
            state = str(entry.state or "proposed")
            section_key = normalize_wiki_section(getattr(entry, "section", None), entry.text)
            if section_key not in sections:
                section_key = _section_key_for_message(entry.text)
            sections[section_key]["entries"].append(
                _wiki_entry(
                    entry.id,
                    entry.text,
                    state
                    if state
                    in {
                        "confirmed",
                        "proposed",
                        "unresolved",
                        "approved",
                        "rejected",
                        "superseded",
                        "reference-only",
                    }
                    else "proposed",
                    source_message_id=getattr(entry, "sourceMessageId", None),
                )
            )
            knowledge_ids.add(entry.id)
        for question in snapshot.openQuestions[:6]:
            if question and not any(e.get("text") == question for e in sections["openQuestions"]["entries"]):
                sections["openQuestions"]["entries"].append(
                    _wiki_entry(f"open-{len(sections['openQuestions']['entries'])+1}", question, "unresolved")
                )
    except Exception:
        pass

    _merge_discovery_candidates(db, project_id, sections, knowledge_ids)
    _attach_project_references(db, project_id, sections, knowledge_ids)

    # Conversation-derived suggestions — names that don't match existing profiles.
    suggested_characters: list[dict[str, Any]] = []
    try:
        from .conversation.snapshot import load_snapshot as _load_snapshot_suggest

        _snap_suggest = _load_snapshot_suggest(db, project_id)
        for _ke in getattr(_snap_suggest, "knowledgeEntries", None) or []:
            if str(getattr(_ke, "section", "") or "") == "characters":
                _ct = str(getattr(_ke, "text", "") or "")
                _cn = str(getattr(_ke, "title", "") or _ct.split()[0] if _ct else "")
                if _cn and _cn.lower() not in existing_profile_names:
                    suggested_characters.append({
                        "suggestedName": _cn,
                        "source": "conversation",
                        "context": _ct[:200] if _ct else "",
                    })
    except Exception:
        pass

    knowledge_count = _section_entry_count(sections)
    has_authoritative = knowledge_count > 0 or bool(user_messages) or bool(decisions)

    if not has_authoritative:
        updated_at = project.updated_at.isoformat() if project.updated_at else datetime.utcnow().isoformat()
        empty_payload = {
            "projectId": project.id,
            "title": project.name or "Untitled Project",
            "projectType": project_type or None,
            "status": "initialized",
            "overview": "",
            "hasContent": False,
            "emptyState": "Your Project Wiki will begin forming after your first message.",
            "sections": sections,
            "updatedAt": updated_at,
            "toc": [],
            "sourceOfTruth": "projectIntelligence.knowledgeEntries",
            "storyEntries": story_entry_data,
            "characterProfiles": character_profile_data,
            "suggestedCharacters": suggested_characters,
        }
        # Still expose compiled Bible projection so format-agnostic clients see pages/TOC.
        try:
            from .wiki_intelligence.compiled.page_compiler import compile_wiki_bundle, get_compiled_wiki

            compiled = get_compiled_wiki(db, project_id)
            if not compiled.get("pages"):
                compiled = compile_wiki_bundle(db, project_id, force_full=True)
            empty_payload["compiledPages"] = compiled.get("pages") or []
            empty_payload["compiledStorySummary"] = compiled.get("storySummary") or {}
            empty_payload["compiledToc"] = compiled.get("toc") or []
            empty_payload["compiledRevision"] = compiled.get("compiledRevision")
            empty_payload["projection"] = "compiled_bible_v1"
            empty_payload["readabilityOk"] = compiled.get("readabilityOk", True)
        except Exception:
            empty_payload["compiledPages"] = []
            empty_payload["compiledToc"] = []
            empty_payload["projection"] = "compiled_bible_v1"
            empty_payload["readabilityOk"] = True
        return empty_payload

    if title:
        if not any(e.get("id") == "project-title" for e in sections["knownDetails"]["entries"]):
            sections["knownDetails"]["entries"].insert(
                0, _wiki_entry("project-title", f"Project title: {title}", "confirmed")
            )
    if project_type:
        if not any(e.get("id") == "project-type" for e in sections["knownDetails"]["entries"]):
            sections["knownDetails"]["entries"].append(
                _wiki_entry("project-type", f"Project type: {project_type.replace('_', ' ')}", "confirmed")
            )
    scenes = getattr(project, "scenes", []) or []
    if isinstance(scenes, list) and scenes:
        first_scene = scenes[0]
        if isinstance(first_scene, Scene):
            if not any(e.get("id") == "scene-count" for e in sections["knownDetails"]["entries"]):
                sections["knownDetails"]["entries"].append(
                    _wiki_entry(
                        "scene-count",
                        f"Current timeline: {len(scenes)} scene{'s' if len(scenes) != 1 else ''}.",
                        "confirmed",
                    )
                )

    for index, message in enumerate(user_messages[:16], start=1):
        content = message["content"]
        if any(content == e.get("text") for section in sections.values() for e in section.get("entries") or []):
            continue
        key = _section_key_for_message(content)
        sections[key]["entries"].append(
            _wiki_entry(
                f"user-{index}",
                content,
                "proposed",
                source_message_id=message["id"] or None,
            )
        )

    for index, decision in enumerate(decisions[:12], start=1):
        text = str(decision.get("recommendation") or decision.get("rationale") or "").strip()
        if not text:
            text = str((decision.get("explainability") or {}).get("summary") or "").strip()
        if not text:
            continue
        sections["productionDecisions"]["entries"].append(_wiki_entry(f"decision-{index}", text, "confirmed"))

    if not sections["openQuestions"]["entries"]:
        if title.lower() == "untitled project":
            sections["openQuestions"]["entries"].append(
                _wiki_entry("open-title", "What should this project be called?", "unresolved")
            )

    overview = _build_overview(project, user_messages, decisions)
    # Prefer overview from known details / creative foundation when richer.
    if not overview:
        for key in ("knownDetails", "creativeFoundation", "storyAndEpisodes"):
            ents = sections[key]["entries"]
            if ents:
                overview = str(ents[0].get("text") or "")
                break

    updated_candidates = [project.updated_at]
    convo = db.get(CoDirectorConversation, project_id)
    if convo and convo.updated_at:
        updated_candidates.append(convo.updated_at)
    updated_at = max((item for item in updated_candidates if item is not None), default=datetime.utcnow()).isoformat()

    # Strip working preferences and false character fragments from creator surfaces.
    try:
        from .wiki_intelligence.classification import (
            extract_display_name,
            is_false_character_name,
            is_user_preference_not_canon,
        )

        cleaned_chars = []
        for entry in sections["characters"]["entries"]:
            text = str(entry.get("text") or "")
            if is_user_preference_not_canon(text):
                sections["references"]["entries"].append(entry)
                continue
            if is_false_character_name(extract_display_name(text)):
                continue
            cleaned_chars.append(entry)
        sections["characters"]["entries"] = cleaned_chars
        sections["knownDetails"]["entries"] = [
            e
            for e in sections["knownDetails"]["entries"]
            if not is_user_preference_not_canon(str(e.get("text") or ""))
        ]
        if overview and is_user_preference_not_canon(overview):
            overview = ""
    except Exception:
        pass

    has_content = _section_entry_count(sections) > 0
    payload = {
        "projectId": project.id,
        "title": title or "Untitled Project",
        "projectType": project_type or None,
        "status": _project_status(project, has_content=has_content, decision_count=len(decisions)),
        "overview": overview,
        "hasContent": has_content,
        "sections": sections,
        "updatedAt": updated_at,
        "toc": [],
        "sourceOfTruth": "projectIntelligence.knowledgeEntries+bibleProjection",
        "storyEntries": story_entry_data,
        "characterProfiles": character_profile_data,
        "suggestedCharacters": suggested_characters,
    }
    try:
        from .wiki_intelligence.projection import attach_professional_projection

        payload = attach_professional_projection(payload)
    except Exception:
        pass
    # Creator-facing compiled Bible (pages ≠ records). Always attach.
    try:
        from .wiki_intelligence.compiled.page_compiler import compile_wiki_bundle, get_compiled_wiki

        compiled = get_compiled_wiki(db, project_id)
        if not compiled.get("pages"):
            compiled = compile_wiki_bundle(db, project_id, force_full=True)
        payload["compiledPages"] = compiled.get("pages") or []
        payload["compiledStorySummary"] = compiled.get("storySummary") or {}
        payload["compiledToc"] = compiled.get("toc") or payload.get("professionalToc") or []
        payload["compiledRevision"] = compiled.get("compiledRevision")
        payload["projection"] = "compiled_bible_v1"
        payload["readabilityOk"] = compiled.get("readabilityOk", True)
        # Prefer compiled overview prose
        for page in payload["compiledPages"]:
            if page.get("pageType") == "PROJECT" and page.get("summary"):
                payload["overview"] = page.get("summary")
                break
        return payload
    except Exception:
        if not payload.get("toc"):
            payload["toc"] = [
                {"key": key, "label": label, "count": len(sections[key]["entries"])}
                for key, label in (
                    ("knownDetails", "Project Overview"),
                    ("creativeFoundation", "Story"),
                    ("characters", "Characters"),
                    ("worldAndSetting", "World"),
                    ("storyAndEpisodes", "Timeline"),
                    ("visualIdentity", "Visual Identity"),
                    ("productionDecisions", "Production Decisions"),
                    ("openQuestions", "Open Questions"),
                    ("references", "References"),
                )
                if sections[key]["entries"]
            ]
        return payload
