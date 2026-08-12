from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session


@dataclass
class StoryFact:
    value: str
    source: str
    source_ref: str
    provenance: str
    confidence: float = 1.0
    updated_at: Optional[datetime] = None


class StoryEvidenceModel(BaseModel):
    project_id: str
    format: Optional[StoryFact] = None
    title: Optional[StoryFact] = None
    protagonist: Optional[StoryFact] = None
    primary_characters: list[StoryFact] = []
    setting: Optional[StoryFact] = None
    premise: Optional[StoryFact] = None
    objective: Optional[StoryFact] = None
    conflict: Optional[StoryFact] = None
    stakes: Optional[StoryFact] = None
    tone: Optional[StoryFact] = None
    genre: Optional[StoryFact] = None
    relationships: list[StoryFact] = []
    story_beats: list[StoryFact] = []
    ending: Optional[StoryFact] = None
    themes: list[StoryFact] = []
    unresolved_questions: list[StoryFact] = []
    source_refs: list[str] = []


def _now() -> datetime:
    return datetime.utcnow()


def _fact(
    value: str,
    source: str,
    source_ref: str,
    provenance: str,
    confidence: float = 1.0,
) -> StoryFact:
    return StoryFact(
        value=value,
        source=source,
        source_ref=source_ref,
        provenance=provenance,
        confidence=confidence,
        updated_at=_now(),
    )


def build_story_evidence(db: Session, project_id: str) -> StoryEvidenceModel:
    source_refs: list[str] = []
    meta: dict[str, Any] = {}

    # 1. Project info
    try:
        from app.db import Project

        project = db.get(Project, project_id)
        if project:
            fmt = getattr(project, "primary_project_type", None) or ""
            if fmt:
                meta["format"] = _fact(
                    value=fmt,
                    source="creator_stated",
                    source_ref=f"project:{project_id}",
                    provenance="creator-stated",
                )
                source_refs.append(f"project:{project_id}")
            name = getattr(project, "name", "") or ""
            if name:
                meta["title"] = _fact(
                    value=name,
                    source="creator_stated",
                    source_ref=f"project:{project_id}",
                    provenance="creator-stated",
                )
            desc = getattr(project, "description", "") or ""
            if desc:
                meta["objective"] = _fact(
                    value=desc,
                    source="creator_stated",
                    source_ref=f"project:{project_id}",
                    provenance="creator-stated",
                )
    except Exception:
        pass

    # 2. Script Writer (Fountain elements)
    try:
        from app.scriptwriter.store import list_documents

        docs = list_documents(db, project_id)
        if docs:
            doc = docs[0]
            source_refs.append(f"script_document:{doc.id}")
            characters: list[str] = []
            beats: list[str] = []
            for el in getattr(doc, "elements", None) or []:
                etype = getattr(el, "type", "") or ""
                etext = (getattr(el, "text", "") or "").strip()
                if not etext:
                    continue
                if etype == "character" and etext not in characters:
                    characters.append(etext)
                elif etype == "scene_heading":
                    beats.append(etext)
                elif etype == "action" and len(etext) > 10:
                    beats.append(etext[:200])
            for ch in characters:
                meta.setdefault("primary_characters", []).append(
                    _fact(
                        value=ch,
                        source="script_writer",
                        source_ref=f"script_document:{doc.id}",
                        provenance="creator-stated",
                        confidence=0.9,
                    )
                )
            for i, beat in enumerate(beats):
                meta.setdefault("story_beats", []).append(
                    _fact(
                        value=beat,
                        source="script_writer",
                        source_ref=f"script_document:{doc.id}/beat:{i}",
                        provenance="creator-stated",
                        confidence=0.9,
                    )
                )
    except Exception:
        pass

    # 3. Production Bible
    try:
        from app.db import ProductionBible, ProductionBibleEntity

        bible = (
            db.query(ProductionBible)
            .filter(ProductionBible.project_id == project_id)
            .first()
        )
        if bible:
            from app.codirector.bible.operations import entities_for_version

            version_id = getattr(bible, "active_version_id", None)
            if version_id:
                entities = entities_for_version(db, version_id)
                for ent in entities:
                    etype = getattr(ent, "entity_type", "") or ""
                    ename = getattr(ent, "display_name", "") or getattr(ent, "entity_key", "") or ""
                    if not ename:
                        continue
                    data_json = getattr(ent, "data_json", "") or "{}"
                    data = {}
                    try:
                        import json
                        data = json.loads(data_json) if isinstance(data_json, str) else {}
                    except Exception:
                        data = {}
                    ref = f"bible_entity:{getattr(ent, 'stable_id', '') or getattr(ent, 'id', '')}"
                    if ref not in source_refs:
                        source_refs.append(ref)
                    if etype == "character" and ename:
                        meta.setdefault("primary_characters", []).append(
                            _fact(
                                value=ename,
                                source="production_bible",
                                source_ref=ref,
                                provenance="creator-approved",
                                confidence=0.95,
                            )
                        )
                        desc = (data.get("description") or data.get("arcSummary") or "").strip()
                        if desc:
                            meta.setdefault("relationships", []).append(
                                _fact(
                                    value=f"{ename}: {desc}",
                                    source="production_bible",
                                    source_ref=ref,
                                    provenance="creator-approved",
                                    confidence=0.9,
                                )
                            )
                    elif etype == "relationship" and ename:
                        meta.setdefault("relationships", []).append(
                            _fact(
                                value=ename,
                                source="production_bible",
                                source_ref=ref,
                                provenance="creator-approved",
                                confidence=0.95,
                            )
                        )
                    elif etype == "location" and ename:
                        desc = (data.get("description") or "").strip()
                        setting_text = f"{ename}: {desc}" if desc else ename
                        meta["setting"] = _fact(
                            value=setting_text,
                            source="production_bible",
                            source_ref=ref,
                            provenance="creator-approved",
                            confidence=0.95,
                        )
                    elif etype == "story_beat" and ename:
                        meta.setdefault("story_beats", []).append(
                            _fact(
                                value=ename,
                                source="production_bible",
                                source_ref=ref,
                                provenance="creator-approved",
                                confidence=0.9,
                            )
                        )
                    elif etype == "narrative_thread" and ename:
                        meta.setdefault("themes", []).append(
                            _fact(
                                value=ename,
                                source="production_bible",
                                source_ref=ref,
                                provenance="creator-approved",
                                confidence=0.85,
                            )
                        )
    except Exception:
        pass

    # 4. Wiki knowledge entries
    try:
        from app.codirector.conversation.snapshot import load_snapshot

        snapshot = load_snapshot(db, project_id)
        for entry in getattr(snapshot, "knowledgeEntries", None) or []:
            state = str(getattr(entry, "state", "proposed") or "proposed")
            if state in ("rejected", "superseded"):
                continue
            text = (getattr(entry, "text", "") or "").strip()
            if len(text) < 3:
                continue
            provenance_str = getattr(entry, "provenance", None) or ""
            section = str(getattr(entry, "section", "") or "")
            eid = str(getattr(entry, "id", "") or "")
            ref = f"wiki_entry:{eid}" if eid else f"wiki:{project_id}"
            if ref not in source_refs:
                source_refs.append(ref)
            is_confirmed = state in ("confirmed", "approved")
            prov = "creator-approved" if is_confirmed else "ai-inferred"
            confidence = 0.95 if is_confirmed else 0.6
            if section == "storyAndEpisodes":
                meta.setdefault("story_beats", []).append(
                    _fact(
                        value=text,
                        source="wiki",
                        source_ref=ref,
                        provenance=prov,
                        confidence=confidence,
                    )
                )
            elif section == "worldAndSetting":
                meta["setting"] = _fact(
                    value=text,
                    source="wiki",
                    source_ref=ref,
                    provenance=prov,
                    confidence=confidence,
                )
            else:
                lower = text.lower()
                if "character" in section.lower() or any(
                    ch.lower() in lower for ch in ["protagonist", "main character", "hero"]
                ):
                    meta.setdefault("primary_characters", []).append(
                        _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                    )
                elif "theme" in section.lower() or "theme" in lower:
                    meta.setdefault("themes", []).append(
                        _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                    )
                elif "premise" in section.lower() or "logline" in section.lower():
                    meta["premise"] = _fact(
                        value=text,
                        source="wiki",
                        source_ref=ref,
                        provenance=prov,
                        confidence=confidence,
                    )
                elif "conflict" in section.lower():
                    meta["conflict"] = _fact(
                        value=text,
                        source="wiki",
                        source_ref=ref,
                        provenance=prov,
                        confidence=confidence,
                    )
                elif "tone" in section.lower() or "genre" in section.lower():
                    meta.setdefault("tone" if "tone" in section.lower() else "genre", ...)
                    if "tone" in section.lower():
                        meta["tone"] = _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                    else:
                        meta["genre"] = _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                elif "question" in section.lower():
                    meta.setdefault("unresolved_questions", []).append(
                        _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                    )
                else:
                    meta.setdefault("primary_characters", []).append(
                        _fact(
                            value=text,
                            source="wiki",
                            source_ref=ref,
                            provenance=prov,
                            confidence=confidence,
                        )
                    )
    except Exception:
        pass

    # 5. Character identity
    try:
        from app.character_identity.service import list_profiles

        profiles = list_profiles(db, project_id)
        for prof in profiles:
            name = getattr(prof, "name", "") or ""
            if not name:
                continue
            ref = f"character_profile:{getattr(prof, 'id', '')}"
            if ref not in source_refs:
                source_refs.append(ref)
            role = getattr(prof, "role", "") or ""
            desc = getattr(prof, "description", "") or ""
            appr = getattr(prof, "approval_status", "") or ""
            prov = "creator-approved" if appr in ("approved", "locked") else "creator-stated"
            confidence = 0.95 if prov == "creator-approved" else 0.85
            meta.setdefault("primary_characters", []).append(
                _fact(
                    value=f"{name} ({role})" if role else name,
                    source="character_identity",
                    source_ref=ref,
                    provenance=prov,
                    confidence=confidence,
                )
            )
            if desc:
                meta.setdefault("relationships", []).append(
                    _fact(
                        value=f"{name}: {desc}",
                        source="character_identity",
                        source_ref=ref,
                        provenance=prov,
                        confidence=confidence * 0.9,
                    )
                )
    except Exception:
        pass

    # 6. Scene records
    try:
        from app.db import Scene

        scenes = (
            db.query(Scene)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.index)
            .all()
        )
        for scene in scenes:
            name = getattr(scene, "name", "") or ""
            summary = getattr(scene, "summary", "") or ""
            sid = getattr(scene, "id", "") or ""
            ref = f"scene:{sid}" if sid else f"scene:{project_id}"
            if ref not in source_refs:
                source_refs.append(ref)
            label = f"{name}: {summary}" if name and summary else (name or summary)
            if label:
                meta.setdefault("story_beats", []).append(
                    _fact(
                        value=label,
                        source="scene_records",
                        source_ref=ref,
                        provenance="creator-approved",
                        confidence=0.9,
                    )
                )
    except Exception:
        pass

    # 7. Living Project Brief
    try:
        from app.codirector.conversation.discovery.persistence import load_discovery_bundle

        bundle = load_discovery_bundle(db, project_id)
        brief = getattr(bundle, "brief", None)
        if brief:
            fields = getattr(brief, "fields", None) or {}
            for key, val in fields.items():
                if not val or not isinstance(val, str):
                    continue
                ref = f"living_brief:{project_id}"
                if ref not in source_refs:
                    source_refs.append(ref)
                if key == "premise":
                    meta["premise"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key == "tone":
                    meta["tone"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key == "genre":
                    meta["genre"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key in ("main_characters", "protagonist"):
                    meta["protagonist"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key in ("central_conflict", "conflict"):
                    meta["conflict"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key == "setting":
                    meta["setting"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key == "themes":
                    meta["themes"] = _fact(
                        value=val,
                        source="living_brief",
                        source_ref=ref,
                        provenance="ai-inferred",
                        confidence=0.7,
                    )
                elif key == "world_rules":
                    meta.setdefault("themes", []).append(
                        _fact(
                            value=val,
                            source="living_brief",
                            source_ref=ref,
                            provenance="ai-inferred",
                            confidence=0.6,
                        )
                    )
    except Exception:
        pass

    # 8. Partnership story template
    try:
        from app.codirector.conversation.partnership.story_template import build_story_template
        from app.codirector.conversation.partnership.schemas import CollaborationOwnership

        template = build_story_template(
            project_id=project_id,
            user_message="",
            ownership_mode=CollaborationOwnership.CO_CREATE,
        )
        content = getattr(template, "content", "") or ""
        if content:
            ref = f"story_template:{project_id}"
            if ref not in source_refs:
                source_refs.append(ref)
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- **Core premise**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["premise"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
                elif line.startswith("- **Protagonist**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["protagonist"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
                elif line.startswith("- **Central conflict**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["conflict"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
                elif line.startswith("- **World or setting**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["setting"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
                elif line.startswith("- **Genre**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["genre"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
                elif line.startswith("- **Tone**"):
                    parts = line.split("]:", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        if val and val != "—":
                            meta["tone"] = _fact(
                                value=val,
                                source="living_brief",
                                source_ref=ref,
                                provenance="ai-inferred",
                                confidence=0.65,
                            )
    except Exception:
        pass

    return StoryEvidenceModel(
        project_id=project_id,
        format=meta.get("format"),
        title=meta.get("title"),
        protagonist=meta.get("protagonist"),
        primary_characters=meta.get("primary_characters", []),
        setting=meta.get("setting"),
        premise=meta.get("premise"),
        objective=meta.get("objective"),
        conflict=meta.get("conflict"),
        tone=meta.get("tone"),
        genre=meta.get("genre"),
        relationships=meta.get("relationships", []),
        story_beats=meta.get("story_beats", []),
        themes=meta.get("themes", []),
        unresolved_questions=meta.get("unresolved_questions", []),
        source_refs=source_refs,
    )


__all__ = ["StoryFact", "StoryEvidenceModel", "build_story_evidence"]
