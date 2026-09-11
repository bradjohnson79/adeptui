"""Shared Co-Director context enrichment helpers (wiki snapshot + attachment honesty).

Kept outside `service.py` so intelligence compilers can import without cycles.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db import Asset


# Lightweight pillar labels for the active Project Content tab. This is a HINT
# only — Co-Director still uses its own judgment. Kept intentionally minimal so
# it never becomes a hard filter on context retrieval.
_CONTENT_TAB_LABELS: dict[str, str] = {
    "wiki": "the Project Wiki",
    "notes": "the Notes document",
    "casting": "Casting / Characters",
    "library": "the Project Library",
    "bible": "the Production Bible",
    "approvals": "Approvals",
    "plans": "Production Plans",
    "jobs": "Jobs",
    "vision": "the Vision document",
    "pitch": "the Pitch & Launch document",
    "scriptwriter": "the Script document",
    "story": "the Story document",
    "script": "the Storyboard",
    "characters": "the Character Creator",
    "development": "Development",
    "production": "Production",
}


def content_tab_hint_block(active_content_tab: str | None) -> str:
    """Return a short prompt hint naming the pillar the user is currently viewing.

    This is a contextual hint, NOT a hard filter — Co-Director may still pull
    context from any pillar. Empty string when no tab is active or recognized.
    """
    if not active_content_tab:
        return ""
    tab = str(active_content_tab).strip().lower()
    if not tab:
        return ""
    label = _CONTENT_TAB_LABELS.get(tab)
    if not label:
        return ""
    return (
        "Active context hint:\n"
        f"- The user is currently viewing {label}. Prioritize this pillar when "
        "relevant, but continue to use your own judgment and other project context."
    )


def story_script_context_block(
    db: Session,
    project_id: str | None,
    *,
    active_document_id: str | None = None,
    scriptwriter_scene_id: str | None = None,
) -> str:
    """Live Story + Script state for this conversation turn.

    Reads the canonical stores (``story_entries`` and the Script Writer
    document's canonical content projection) on EVERY call — never a cached
    or startup snapshot — so an edit the creator made seconds ago is what
    Co-Director sees (no stale story/script context).

    Bounded by design: story summaries are truncated, the scene list is
    capped, and only the current scene (when known) is read out in full.
    Deeper detail remains available through the read tools
    (``project.read_context`` / ``script.scene_context``). Never raises.
    """
    if not project_id:
        return ""
    lines: list[str] = []

    # ── Story (canonical story_entries; legacy freeform doc as fallback) ──
    try:
        from ..story_entries.store import list_entries

        entries = list_entries(db, project_id)
        if entries:
            lines.append("Story (live from the Story workspace):")
            for e in entries[:6]:
                head = f"- [{e.entry_type}] {e.title or 'Untitled'}"
                if e.logline:
                    head += f" — {e.logline[:300]}"
                lines.append(head)
                if e.short_summary:
                    lines.append(f"  Summary: {e.short_summary[:500]}")
                if e.long_summary:
                    lines.append(f"  Treatment: {e.long_summary[:800]}")
    except Exception:
        pass
    if not any(l.startswith("Story (live") for l in lines):
        try:
            from ..story.store import load_document

            row = load_document(db, project_id)
            if row and row.content:
                lines.append("Story (live from the Story workspace):")
                lines.append(f"- {row.title or 'Story'}: {row.content[:900]}")
        except Exception:
            pass

    # ── Script (canonical content projection — typed HTML aware) ─────────
    try:
        from ..scriptwriter.service import (
            canonical_elements,
            navigator_scenes,
            scene_segment_readout,
        )
        from ..scriptwriter.store import list_documents, load_document

        docs = list_documents(db, project_id)
        doc = None
        if active_document_id:
            candidate = load_document(db, active_document_id)
            if candidate and candidate.projectId == project_id:
                doc = candidate
        if doc is None and docs:
            doc = load_document(db, docs[0].id)
        if doc is not None:
            elements = canonical_elements(doc)
            scenes = navigator_scenes(doc)
            lines.append(
                f"Script (live): \"{doc.title or 'Untitled Script'}\" — "
                f"{len(scenes)} scene(s), {sum(len((e.text or '').split()) for e in elements)} words, revision {doc.revision}."
            )
            if scenes:
                lines.append("Scene list:")
                for s in scenes[:40]:
                    marker = " ← current" if scriptwriter_scene_id and s.get("sceneHeadingId") == scriptwriter_scene_id else ""
                    lines.append(f"- {s.get('sceneNumber') or '—'}. {s.get('heading')}{marker}")
            if scriptwriter_scene_id:
                readout = scene_segment_readout(doc, scriptwriter_scene_id)
                if readout:
                    lines.append(f"Current scene the creator is editing: {readout.get('heading')}")
                    action = (readout.get("action") or "")[:1200]
                    dialogue = (readout.get("dialogue") or "")[:1200]
                    if action:
                        lines.append(f"  Action: {action}")
                    if dialogue:
                        speaker = readout.get("speaker") or ""
                        lines.append(f"  Dialogue{f' ({speaker})' if speaker else ''}: {dialogue}")
            # Bounded scene-content readout so dialogue/action questions are
            # answerable even when no current scene is tagged. The current
            # scene (already read out above) is skipped here; remaining scenes
            # share a total character budget, in script order.
            budget = 2600
            content_lines: list[str] = []
            for s in scenes[:40]:
                sid = s.get("sceneHeadingId")
                if not sid or sid == scriptwriter_scene_id:
                    continue
                if budget <= 0:
                    break
                try:
                    readout = scene_segment_readout(doc, sid)
                except Exception:
                    continue
                if not readout:
                    continue
                action = (readout.get("action") or "")[:400]
                dialogue = (readout.get("dialogue") or "")[:400]
                if not action and not dialogue:
                    continue
                chunk_lines = [f"Scene \"{readout.get('heading')}\":"]
                if action:
                    chunk_lines.append(f"  Action: {action}")
                if dialogue:
                    speaker = readout.get("speaker") or ""
                    chunk_lines.append(f"  Dialogue{f' ({speaker})' if speaker else ''}: {dialogue}")
                chunk = "\n".join(chunk_lines)
                if len(chunk) > budget:
                    chunk = chunk[:budget]
                content_lines.append(chunk)
                budget -= len(chunk)
            if content_lines:
                lines.append("Scene contents (live, bounded):")
                lines.extend(content_lines)
    except Exception:
        pass

    if not lines:
        return ""
    return "\n".join(
        [
            "Current project Story + Script state (read live for this turn — always up to date;",
            "use script.scene_context / project.read_context tools for deeper detail):",
            *lines,
        ]
    )


def compact_wiki_context(db: Session, project_id: str, *, limit: int = 12) -> str:
    """Inject a short Project Wiki snapshot into chat/intelligence context.

    Prefers the revisioned Project Intelligence Cache (warm, compact) over a full
    Wiki rebuild on every turn. Falls back to a bounded wiki build only when cold.
    """
    try:
        from .conversation.project_cache import load_project_cache, warm_project_cache

        cache = load_project_cache(db, project_id) or warm_project_cache(db, project_id)
        lines = ["Project knowledge snapshot (compact cache — not a full Wiki dump):"]
        if cache.projectSummary:
            lines.append(f"- Overview: {cache.projectSummary[:320]}")
        if cache.developmentStage:
            lines.append(f"- Stage: {cache.developmentStage}")
        if cache.activeGoal:
            lines.append(f"- Active goal: {cache.activeGoal[:180]}")
        count = 0
        for bucket_name, bucket in (
            ("characters", cache.characterIndex),
            ("locations", cache.locationIndex),
            ("principles", cache.storyPrinciples),
            ("open questions", cache.openQuestions),
            ("recent decisions", cache.recentDecisions),
        ):
            for entity in bucket[: max(1, limit // 3)]:
                note = f" — {entity.note}" if entity.note else ""
                lines.append(f"- [{bucket_name}] {entity.name}{note}"[:240])
                count += 1
                if count >= limit:
                    break
            if count >= limit:
                break
        if count or cache.projectSummary:
            return "\n".join(lines)
    except Exception:
        pass

    try:
        from .wiki_intelligence.maintenance import tool_wiki_context

        tool_ctx = tool_wiki_context(db, project_id)
        if tool_ctx.get("ok") and tool_ctx.get("context"):
            lines = ["Project Wiki tool context (professional projection — project-scoped):"]
            title = str(tool_ctx.get("title") or "").strip()
            if title:
                lines.append(f"- Title: {title[:180]}")
            count = 0
            for section_key, bucket in (tool_ctx.get("context") or {}).items():
                for item in bucket:
                    lines.append(f"- [{section_key}] {item}"[:240])
                    count += 1
                    if count >= limit:
                        break
                if count >= limit:
                    break
            if count:
                return "\n".join(lines)
    except Exception:
        pass

    try:
        from .conversation.circuit_breakers import is_open, record_failure, record_success

        if is_open("full_wiki_rebuild"):
            return ""
        from .wiki import build_project_wiki

        wiki = build_project_wiki(db, project_id)
        record_success("full_wiki_rebuild")
    except Exception:
        try:
            from .conversation.circuit_breakers import record_failure

            record_failure("full_wiki_rebuild")
        except Exception:
            pass
        return ""
    if not wiki or not wiki.get("hasContent"):
        return ""
    lines = ["Project Wiki snapshot (confirmed/proposed project knowledge — not chat residue):"]
    overview = str(wiki.get("overview") or "").strip()
    if overview:
        lines.append(f"- Overview: {overview[:320]}")
    sections = wiki.get("sections") or {}
    count = 0
    for section_key in (
        "knownDetails",
        "creativeFoundation",
        "characters",
        "worldAndSetting",
        "storyAndEpisodes",
        "visualIdentity",
        "productionDecisions",
        "openQuestions",
    ):
        section = sections.get(section_key) or {}
        for entry in section.get("entries") or []:
            text = str(entry.get("text") or "").strip()
            state = str(entry.get("state") or "proposed").strip()
            if not text:
                continue
            lines.append(f"- [{state}] {text[:220]}")
            count += 1
            if count >= limit:
                break
        if count >= limit:
            break
    return "\n".join(lines) if count or overview else ""


def execution_result_context_block(db: Session, project_id: str | None) -> str:
    """Inject a short result-aware context block for the next conversation turn.

    Workstream H, spec §42: after an execution completes, Co-Director must
    know that "number 3" refers to Frame 3 of the current result set. This
    reads the most recent completed execution pack and returns a compact,
    indexed summary. Empty string when no completed execution exists or the
    pack store (Workstream C) is unavailable. Never raises.
    """
    if not project_id:
        return ""
    try:
        from .execution.result_context import result_context_block

        return result_context_block(db, project_id)
    except Exception:  # noqa: BLE001
        return ""


def attachment_context_block(
    db: Session,
    *,
    project_id: str | None,
    attachment_ids: list[str] | None,
) -> str:
    """Describe attached assets honestly. Do not claim vision/audio analysis occurred."""
    ids = [str(value).strip() for value in (attachment_ids or []) if str(value).strip()]
    if not ids or not project_id:
        return ""
    lines = [
        "Attached media for this turn (metadata only):",
        "Vision, audio, and video cognition are not automatically run in chat.",
        "Do not invent visual, audio, or motion details. Acknowledge the attachment and its creator-stated purpose only.",
    ]
    for asset_id in ids[:8]:
        asset = db.get(Asset, asset_id)
        if not asset or asset.project_id != project_id:
            lines.append(f"- Missing or out-of-project asset reference ({asset_id[:8]}…)")
            continue
        kind = (asset.kind or "asset").strip()
        name = (asset.tag or asset.filename or asset.id).strip()
        approval = (asset.production_approval or "none").strip()
        lifecycle = (asset.validation_lifecycle or "not_requested").strip()
        lines.append(
            f"- {name} | type={kind} | approval={approval} | vision_validation={lifecycle}"
        )
        if kind == "image" and lifecycle in ("not_requested", "", "none"):
            lines.append(
                "  Note: image perception was not performed for this chat turn. Treat as reference unless the creator approved it."
            )
    return "\n".join(lines)

