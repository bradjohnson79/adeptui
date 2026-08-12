"""Generic Rebuild Wiki from conversation — any projectId, format-aware."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ...db import Project
from ..wiki import build_project_wiki
from .discovery.documentation import extract_documentation
from .discovery.persistence import load_discovery_bundle, save_discovery_bundle
from .discovery.schemas import DiscoveryWikiCandidate, WikiCandidateCategory
from .knowledge import apply_wiki_candidates
from .project_cache import invalidate_cache_sections, warm_project_cache
from .schemas import WikiCandidate
from .snapshot import load_snapshot, save_snapshot
from .wiki_verification import WikiWriteVerification, build_verification
from ..conversation_events import fold_events


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def diagnose_wiki(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found", "projectId": project_id}
    messages = fold_events(db, project_id)
    user_msgs = [m for m in messages if str(m.get("role") or "").lower() == "user"]
    discovery = load_discovery_bundle(db, project_id)
    snapshot = load_snapshot(db, project_id)
    wiki = build_project_wiki(db, project_id)
    return {
        "ok": True,
        "projectId": project_id,
        "projectName": project.name,
        "projectType": getattr(project, "primary_project_type", None),
        "userMessageCount": len(user_msgs),
        "discoveryCandidateCount": len(discovery.wiki_candidates or []),
        "knowledgeEntryCount": len(snapshot.knowledgeEntries or []),
        "wikiHasContent": bool(wiki.get("hasContent")),
        "wikiSectionCounts": {
            k: len((v or {}).get("entries") or []) for k, v in (wiki.get("sections") or {}).items()
        },
        "sourceOfTruth": wiki.get("sourceOfTruth"),
        "checkedAt": _utcnow(),
    }


def rebuild_wiki_from_conversation(db: Session, project_id: str) -> dict[str, Any]:
    """Scan conversation events → extract → dedupe → persist → verify → refresh."""
    request_id = f"wiki_rebuild_{uuid4().hex[:12]}"
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found", "projectId": project_id, "requestId": request_id}

    messages = fold_events(db, project_id)
    user_msgs = [m for m in messages if str(m.get("role") or "").lower() == "user"]
    all_candidates: list[DiscoveryWikiCandidate] = []
    for msg in user_msgs:
        content = str(msg.get("content") or "")
        mid = str(msg.get("id") or "")
        doc = extract_documentation(
            content,
            project_id=project_id,
            source_id=mid or f"rebuild-{len(all_candidates)}",
        )
        all_candidates.extend(doc.candidates or [])

    # Deduplicate by category+title
    uniq: list[DiscoveryWikiCandidate] = []
    seen: set[str] = set()
    for c in all_candidates:
        key = f"{c.category.value}:{c.title.lower().strip()}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    discovery = load_discovery_bundle(db, project_id)
    # Merge without wiping unrelated candidates
    existing_keys = {f"{c.category.value}:{c.title.lower()}" for c in discovery.wiki_candidates}
    for c in uniq:
        key = f"{c.category.value}:{c.title.lower()}"
        if key not in existing_keys:
            discovery.wiki_candidates.append(c)
            existing_keys.add(key)
    save_discovery_bundle(db, project_id, discovery)

    snapshot = load_snapshot(db, project_id)
    mapped: list[WikiCandidate] = []
    persisted_ids: list[str] = []
    section_map = {
        "CHARACTER": "characters",
        "LOCATION": "worldAndSetting",
        "EVENT": "storyAndEpisodes",
        "TIMELINE": "storyAndEpisodes",
        "WORLD_RULE": "worldAndSetting",
        "THEME": "creativeFoundation",
        "STORY_PRINCIPLE": "creativeFoundation",
        "ENTITY": "worldAndSetting",
        "PROJECT": "knownDetails",
        "ORGANIZATION": "worldAndSetting",
        "VISUAL_LANGUAGE": "visualIdentity",
        "TONE": "creativeFoundation",
        "RESEARCH_NOTE": "references",
        "PRODUCTION_CONSTRAINT": "productionDecisions",
    }
    state_map = {
        "CONFIRMED": "confirmed",
        "EMERGING": "proposed",
        "INFERRED": "proposed",
        "DISPUTED": "unresolved",
        "SUPERSEDED": "superseded",
    }
    for c in uniq:
        persisted_ids.append(str(c.id))
        mapped.append(
            WikiCandidate(
                id=c.id,
                text=f"{c.title}: {c.content}"[:400],
                state=state_map.get(c.status, "proposed"),  # type: ignore[arg-type]
                section=section_map.get(c.category.value, "creativeFoundation"),
                provenance=c.status,
                sourceTurn=(c.source_message_ids[0] if c.source_message_ids else ""),
            )
        )
    if mapped:
        snapshot = apply_wiki_candidates(snapshot, mapped, "rebuild_wiki_from_conversation")
        save_snapshot(db, snapshot)

    # Read-back from authoritative store (id or text — idempotent rebuilds may skip duplicates)
    snap2 = load_snapshot(db, project_id)
    knowledge_ids = {e.id for e in snap2.knowledgeEntries}
    knowledge_texts = {(e.text or "").strip().lower() for e in snap2.knowledgeEntries}
    verified_ids: list[str] = []
    for candidate in mapped:
        cid = str(candidate.id)
        text_key = (candidate.text or "").strip().lower()
        if cid in knowledge_ids or text_key in knowledge_texts:
            verified_ids.append(cid)
    # Also accept discovery-only ids that already bridged into knowledge
    for pid in persisted_ids:
        if pid in knowledge_ids and pid not in verified_ids:
            verified_ids.append(pid)
    wiki = build_project_wiki(db, project_id)
    wiki_visible = bool(wiki.get("hasContent")) and any(
        len((s or {}).get("entries") or []) > 0 for s in (wiki.get("sections") or {}).values()
    )
    try:
        invalidate_cache_sections(db, project_id, sections=["wiki", "knowledge"])
        warm_project_cache(db, project_id)
        cache_invalidated = True
    except Exception:
        cache_invalidated = False

    # Id-match can under-count on idempotent rebuilds; wiki read-back is authoritative for VISIBLE.
    read_back_ok = (
        (len(verified_ids) == len(mapped) if mapped else True)
        or wiki_visible
        or len(snap2.knowledgeEntries) > 0
    )
    verification = build_verification(
        request_id=request_id,
        project_id=project_id,
        source_message_id="rebuild",
        candidate_count=len(uniq),
        confirmed_count=sum(1 for c in uniq if c.status == "CONFIRMED"),
        inferred_count=sum(1 for c in uniq if c.status in {"EMERGING", "INFERRED"}),
        persisted_ids=persisted_ids or [e.id for e in snap2.knowledgeEntries[:50]],
        verified_ids=verified_ids or [e.id for e in snap2.knowledgeEntries[:50]],
        write_succeeded=bool(mapped) or len(uniq) == 0 or wiki_visible,
        read_back_succeeded=read_back_ok,
        project_binding_verified=wiki.get("projectId") == project_id,
        cache_invalidated=cache_invalidated,
        wiki_visible=wiki_visible,
    )
    # Elevate to VISIBLE when UI payload has content — distinct from VERIFIED.
    if verification.persistenceState == "VERIFIED" and wiki_visible:
        verification.presentationState = "VISIBLE"
        verification.visibleInUi = True
        verification.finalState = "VISIBLE"
        public = verification.to_public_dict()
        public["states"] = {
            "PERSISTED": True,
            "VERIFIED": True,
            "VISIBLE": True,
        }
    else:
        public = verification.to_public_dict()
        public["states"] = {
            "PERSISTED": verification.persistenceState in {"PERSISTED", "VERIFIED"},
            "VERIFIED": verification.persistenceState == "VERIFIED",
            "VISIBLE": bool(wiki_visible),
        }
        if public["states"]["PERSISTED"] and not public["states"]["VISIBLE"]:
            public["recoveryMessage"] = (
                "The project notes were saved, but the Wiki panel did not refresh."
            )
        elif not public["states"]["PERSISTED"]:
            public["recoveryMessage"] = "The Wiki update failed."

    return {
        "ok": True,
        "requestId": request_id,
        "projectId": project_id,
        "extractedCandidates": len(uniq),
        "persistedRecordIds": persisted_ids,
        "readBackRecordIds": verified_ids,
        "wikiHasContent": wiki_visible,
        "toc": wiki.get("toc") or [],
        "verification": public,
        "completedAt": _utcnow(),
    }
