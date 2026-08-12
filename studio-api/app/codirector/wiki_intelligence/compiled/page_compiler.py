"""Authoritative Wiki Page Compiler."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ...conversation.snapshot import load_snapshot, save_snapshot
from .character_compiler import resolve_characters
from .episode_compiler import compile_episode_pages
from .overview_compiler import compile_project_overview
from .readability import assert_wiki_readability
from .story_compiler import compile_story_page, compile_story_summary
from .story_summary_editor import (
    CompiledStorySummary as EditorStorySummary,
)
from .story_summary_editor import conservative_fallback, edit_story_summary


def _entry_texts(snapshot: Any, sections: set[str] | None = None) -> list[tuple[str, str, str]]:
    """Return (id, text, section) for confirmed-ish knowledge only."""
    out: list[tuple[str, str, str]] = []
    for entry in getattr(snapshot, "knowledgeEntries", None) or []:
        state = str(getattr(entry, "state", "proposed") or "proposed")
        if state in {"rejected", "superseded"}:
            continue
        # Prefer confirmed/approved for article body; proposed allowed for characters recognition
        text = str(getattr(entry, "text", "") or "").strip()
        if len(text) < 3:
            continue
        section = str(getattr(entry, "section", "") or "")
        if sections and section not in sections and state not in {"confirmed", "approved"}:
            continue
        out.append((str(entry.id), text, section))
    return out


def get_compiled_wiki(db: Session, project_id: str) -> dict[str, Any]:
    snapshot = load_snapshot(db, project_id)
    cached = getattr(snapshot, "compiledWiki", None) or {}
    if cached.get("pages") and cached.get("projection") == "compiled_bible_v1":
        return cached
    return compile_wiki_bundle(db, project_id, force_full=True)


def compile_wiki_bundle(
    db: Session,
    project_id: str,
    *,
    force_full: bool = False,
    dirty_page_ids: list[str] | None = None,
) -> dict[str, Any]:
    snapshot = load_snapshot(db, project_id)
    prior = getattr(snapshot, "compiledWiki", None) or {}
    revision = int(prior.get("compiledRevision") or 0) + 1

    entries = _entry_texts(snapshot)
    facts = [t for _, t, _ in entries]
    story_texts = [
        t
        for _, t, s in entries
        if s in {"storyAndEpisodes", "creativeFoundation", "knownDetails"} or True
    ]
    # Prefer story/creative sections but keep enough material
    story_pref = [t for _, t, s in entries if s in {"storyAndEpisodes", "creativeFoundation"}]
    if story_pref:
        story_texts = story_pref + [t for t in facts if t not in story_pref][:8]

    alias_map: dict[str, str] = {}
    installments: list[dict[str, Any]] = []
    try:
        from ...creative_operating.persistence import load_bundle

        bundle = load_bundle(db, project_id)
        alias_map = dict(bundle.identityAliases or {})
        installments = list(getattr(bundle, "installments", None) or [])
    except Exception:  # noqa: BLE001
        pass

    # Creator-learned correction memory: aliases + entity-type overrides take
    # highest precedence so corrected mistakes do not return on recompile.
    entity_overrides: dict[str, str] = {}
    try:
        from ..correction import memory as correction_memory

        learned_aliases = correction_memory.active_aliases(db, project_id)
        for alias, canonical in learned_aliases.items():
            alias_map.setdefault(alias, canonical)
        entity_overrides = correction_memory.entity_type_overrides(db, project_id)
    except Exception:  # noqa: BLE001
        pass

    life = getattr(snapshot, "productionLifecycle", None) or {}
    if not installments:
        installments = list(life.get("installments") or [])

    episode_pages = compile_episode_pages(installments if isinstance(installments, list) else [])
    episode_children = [
        {"pageId": p["pageId"], "label": p["title"], "id": p["pageId"]} for p in episode_pages
    ]

    overview = compile_project_overview(db, project_id, facts=facts)
    story_summary = compile_story_summary(
        story_texts=story_texts,
        open_questions=list(getattr(snapshot, "openQuestions", None) or [])[:8],
        episode_summaries=[p.get("summary") or "" for p in episode_pages],
        source_ids=[i for i, _, _ in entries[:20]],
    )
    story_page = compile_story_page(
        story_summary, episode_children=[{"pageId": c["pageId"], "label": c["label"]} for c in episode_children]
    )

    # Authoritative story entries — enrich story page sections.
    try:
        from ....story_entries.store import list_entries as _list_story_entries

        _story_rows = _list_story_entries(db, project_id)
        if _story_rows:
            story_entry_sections = []
            for _se in _story_rows:
                _body_parts = []
                if _se.logline:
                    _body_parts.append(f"Logline: {_se.logline}")
                if _se.short_summary:
                    _body_parts.append(f"Short Summary: {_se.short_summary}")
                if _se.long_summary:
                    _body_parts.append(_se.long_summary[:800])
                story_entry_sections.append({
                    "id": f"sec-story-entry-{_se.id}",
                    "title": _se.title or _se.entry_type.replace("_", " ").title(),
                    "body": "\n\n".join(_body_parts),
                    "bullets": [],
                })
            # Append authoritative sections after default story sections
            existing_ids = {s["id"] for s in story_page.get("sections") or []}
            for _sec in story_entry_sections:
                if _sec["id"] not in existing_ids:
                    story_page.setdefault("sections", []).append(_sec)
                    existing_ids.add(_sec["id"])
    except Exception:
        pass

    # Authoritative character profiles — replace conversation-derived characters.
    characters: list[dict[str, Any]] = []
    try:
        from ....character_identity.models import CharacterReferenceAssetRow as _RefRow
        from ....character_identity.service import list_profiles as _list_char_profiles

        _profiles = _list_char_profiles(db, project_id)
        if _profiles:
            for _prof in _profiles:
                _cid = re.sub(r"[^a-z0-9]+", "-", _prof.name.lower()).strip("-")[:40]
                _page_id = f"page-character-{_cid}"
                _refs = (
                    db.query(_RefRow)
                    .filter(_RefRow.character_profile_id == _prof.id)
                    .all()
                )
                _hero_portrait = None
                for _ref in _refs:
                    from app.character_identity.roles import canonical_role
                    if canonical_role(_ref.reference_role) == "hero_identity" and (_ref.canonical or _ref.approval_status == "approved"):
                        _hero_portrait = _ref.asset_id
                        break
                _personality = _prof.personality if hasattr(_prof, 'personality') else {}
                _summary_parts = [_prof.description] if _prof.description else []
                if _prof.role:
                    _summary_parts.append(f"Role: {_prof.role}")
                _summary = "; ".join(_summary_parts)[:200] if _summary_parts else f"{_prof.name} has been created."
                _sections = [
                    {
                        "id": f"sec-{_page_id}-overview",
                        "title": "Overview",
                        "body": _prof.description or "",
                        "bullets": [],
                    },
                    {
                        "id": f"sec-{_page_id}-details",
                        "title": "Details",
                        "body": "",
                        "bullets": [
                            b for b in [
                                f"Role: {_prof.role}" if _prof.role else "",
                                f"Age: {_prof.apparent_age}" if _prof.apparent_age else "",
                                f"Species: {_prof.species_or_type}" if _prof.species_or_type else "",
                            ] if b
                        ],
                    },
                ]
                if _personality:
                    _personality_bullets = [
                        v for k, v in _personality.items()
                        if isinstance(v, str) and v.strip() and k != "model_config"
                    ][:6]
                    if _personality_bullets:
                        _sections.append({
                            "id": f"sec-{_page_id}-personality",
                            "title": "Personality",
                            "body": "",
                            "bullets": _personality_bullets,
                        })
                characters.append({
                    "pageId": _page_id,
                    "pageType": "CHARACTER",
                    "title": _prof.name,
                    "summary": _summary,
                    "sections": _sections,
                    "relatedPageIds": ["page-story"],
                    "sourceRecordIds": [_prof.id],
                    "canonState": "CONFIRMED",
                    "questionsToExplore": [
                        f"What does {_prof.name.split()[-1]} want most deeply right now?",
                        f"How does {_prof.name.split()[-1]} relate to the central conflict?",
                    ][:2],
                    "profileId": _prof.id,
                    "approvedCastingImageAssetId": _hero_portrait,
                })
    except Exception:
        pass

    if not characters:
        char_texts = [t for _, t, s in entries if s == "characters"]
        characters = resolve_characters(
            char_texts,
            alias_map=alias_map,
            key_characters=list(getattr(snapshot, "keyCharacters", None) or []),
            entity_type_overrides=entity_overrides,
        )

    # World / locations light pages when material exists
    world_bits = [t for _, t, s in entries if s == "worldAndSetting"]
    pages: list[dict[str, Any]] = [overview, story_page, *characters, *episode_pages]
    if world_bits:
        pages.append(
            {
                "pageId": "page-world",
                "pageType": "WORLD",
                "title": "World & Lore",
                "summary": world_bits[0][:200],
                "sections": [
                    {
                        "id": "sec-world",
                        "title": "World Notes",
                        "body": "",
                        "bullets": world_bits[:8],
                    }
                ],
                "relatedPageIds": ["page-story"],
                "sourceRecordIds": [],
                "canonState": "CONFIRMED",
                "questionsToExplore": [],
            }
        )

    toc: list[dict[str, Any]] = []
    toc.append({"key": "projectOverview", "label": "Project Overview", "count": 1, "children": []})
    toc.append(
        {
            "key": "story",
            "label": "Story",
            "count": 1,
            "children": episode_children,
        }
    )
    toc.append(
        {
            "key": "characters",
            "label": "Characters",
            "count": len(characters),
            "children": [
                {
                    "id": c["pageId"],
                    "label": c["title"],
                    "canonState": "CONFIRMED",
                    "entityType": "character",
                }
                for c in characters
            ],
        }
    )
    if episode_pages:
        toc.append(
            {
                "key": "episodesAndScenes",
                "label": "Episodes & Scenes",
                "count": len(episode_pages),
                "children": episode_children,
            }
        )
    if world_bits:
        toc.append({"key": "worldAndLore", "label": "World & Lore", "count": 1, "children": []})
    toc.append({"key": "references", "label": "References", "count": 0, "children": []})

    # Hide empty references root if count 0 — keep structure minimal
    toc = [n for n in toc if n["key"] != "references" or n["count"] > 0]

    # Foundation page — optional, never breaks Wiki compilation if unavailable.
    try:
        from app.project_foundation.service import get_foundation_status

        foundation = get_foundation_status(db, project_id)
        pillar_labels = {
            "story": "Story",
            "script": "Script",
            "storyboard": "Storyboard",
            "characters": "Characters",
        }
        foundation_sections: list[dict[str, Any]] = []
        for key, label in pillar_labels.items():
            info = getattr(foundation, key)
            status_display = str(info.status).replace("_", " ").title()
            body_parts = [f"Status: {status_display}."]
            if info.item_count:
                body_parts.append(f"Items: {info.item_count}.")
            if info.last_updated:
                body_parts.append(f"Last updated: {info.last_updated}.")
            foundation_sections.append(
                {
                    "heading": label,
                    "body": " ".join(body_parts),
                    "status": info.status,
                    "exists": info.exists,
                }
            )
        foundation_page = {
            "pageId": "foundation",
            "pageType": "FOUNDATION",
            "title": "Project Foundation",
            "summary": (
                f"Story: {foundation.story.status}, "
                f"Script: {foundation.script.status}, "
                f"Storyboard: {foundation.storyboard.status}, "
                f"Characters: {foundation.characters.status}"
            ),
            "sections": foundation_sections,
            "questionsToExplore": [],
        }
        pages.insert(1, foundation_page)  # After overview
        toc.insert(
            1,
            {
                "key": "foundation",
                "label": "Project Foundation",
                "count": len(foundation_sections),
                "children": [],
            },
        )
    except Exception:  # noqa: BLE001
        pass

    issues = assert_wiki_readability(pages, toc)
    payload = {
        "projectId": project_id,
        "compiledRevision": revision,
        "lastCompiledAt": datetime.now(timezone.utc).isoformat(),
        "projection": "compiled_bible_v1",
        "toc": toc,
        "pages": pages,
        "storySummary": story_summary.model_dump(mode="json"),
        "readabilityOk": not issues,
        "readabilityIssues": issues,
        "forceFull": force_full,
        "dirtyPageIds": dirty_page_ids or [],
    }
    snapshot.compiledWiki = payload
    save_snapshot(db, snapshot)
    return payload


async def compile_wiki_bundle_async(
    db: Session,
    project_id: str,
    *,
    force_full: bool = False,
    dirty_page_ids: list[str] | None = None,
    provider: Any = None,
) -> dict[str, Any]:
    """Async compile path that uses the LLM-backed Story Summary Editor.

    Falls back to the conservative deterministic editor when no provider is
    available. The sync `compile_wiki_bundle` remains the conservative-only
    path used by tests with STUDIO_E2E=1.
    """
    # Run the Story Summary Editor (LLM-backed with conservative fallback).
    try:
        story_summary_editor = await edit_story_summary(
            db, project_id, provider=provider, force=force_full
        )
    except Exception:  # noqa: BLE001
        from .story_summary_editor.evidence import build_story_summary_source

        source = build_story_summary_source(db, project_id)
        story_summary_editor = conservative_fallback(source)

    # Reuse the sync bundle for pages/TOC, then overwrite storySummary with
    # the editor's result so per-section readiness + editorial prose win.
    payload = compile_wiki_bundle(
        db, project_id, force_full=force_full, dirty_page_ids=dirty_page_ids
    )
    payload["storySummary"] = story_summary_editor.model_dump(mode="json")
    # Persist the merged payload.
    snapshot = load_snapshot(db, project_id)
    snapshot.compiledWiki = payload
    save_snapshot(db, snapshot)
    return payload
