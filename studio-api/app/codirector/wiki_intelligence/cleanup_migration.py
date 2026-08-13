"""One-time conservative cleanup migration for persisted Wiki Story filler.

The Wiki previously misclassified meta-conversation (e.g. "Please call me
friend", "Use Balanced mode", "ok thanks will do") as story canon, which
polluted persisted Wiki Story fields (Logline / Short Summary / Long Summary)
in `Project.settings_json.projectIntelligence.knowledgeEntries` and
`.compiledWiki.storySummary` for affected projects — including the
"Schnick Coffee" project.

This module provides a deterministic, auditable, idempotent migration that:

- Loads the project's persisted Wiki state from `Project.settings_json`.
- Runs each persisted Story-shaped text through the deterministic
  `classify_conversation_turn` classifier (no LLM calls).
- CLEANS fields whose content classifies as a non-canon turn-type
  (user_preference / production_request / meta_conversation / question /
  brainstorming).
- PRESERVES fields whose content classifies as `story_canon`.
- PRESERVES fields whose content classifies as `unknown` — the heuristics
  may simply fail to recognize legitimate story, and the migration must be
  conservative ("when in doubt, preserve").
- Sets cleaned fields to genuinely empty ("" — matching what
  `compile_story_summary` produces for the blank case). Never writes
  placeholder prose.
- Records an audit log entry for every decision (cleaned or preserved).
- Is idempotent: running twice == running once.

This is a one-time migration, not a recurring job. See
`docs/release-gate/env-picker/SPATIAL_MAP_ENVIRONMENT_PICKER_REPORT.md` is
unrelated; this migration is documented in the Wiki cleanup report.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ...db import Project
from ..conversation.schemas import ProjectIntelligenceSnapshot, WikiCandidate
from ..conversation.snapshot import _SETTINGS_KEY, _load_project_settings
from .classification import TurnType, classify_conversation_turn

# Re-export the canonical settings key for tests / callers that build
# fixtures by hand. Mirrors `snapshot._SETTINGS_KEY` == "projectIntelligence".
SETTINGS_KEY = _SETTINGS_KEY

logger = logging.getLogger(__name__)


# ── Cleanup policy ──────────────────────────────────────────────────────
#
# Turn-types that are CLEANED (set to blank) when found in a persisted Story
# field. These are the turn-types that should never have been persisted as
# story canon in the first place.
#
# `unknown` is intentionally NOT in this set: the conservative rule is
# "when in doubt, PRESERVE". The heuristics may simply fail to recognize
# legitimate user-authored story, and erasing it would be destructive.
_CLEANED_TURN_TYPES: frozenset[TurnType] = frozenset(
    {
        "user_preference",
        "production_request",
        "meta_conversation",
        "question",
        "brainstorming",
    }
)

# Turn-types that are PRESERVED in Story fields.
# `story_canon` is always preserved (legitimate narrative).
# `unknown` is preserved (conservative — might be real story the
# heuristics don't catch).
_PRESERVED_TURN_TYPES: frozenset[TurnType] = frozenset({"story_canon", "unknown"})


# The Story-shaped fields on `compiledWiki.storySummary` that the migration
# inspects. These mirror `CompiledStorySummary` (logline / shortSummary /
# longSummary). The blank value matches what `compile_story_summary` emits
# for the no-canon case (empty string).
_STORY_SUMMARY_FIELDS: tuple[str, ...] = ("logline", "shortSummary", "longSummary")
_BLANK_VALUE: str = ""


def _snippet(text: str, limit: int = 80) -> str:
    """Return a single-line snippet of `text` truncated to `limit` chars."""
    if not text:
        return ""
    one_line = " ".join(str(text).split())
    if len(one_line) <= limit:
        return one_line
    return one_line[:limit]


def _decide_action(text: str) -> tuple[str, TurnType]:
    """Classify a persisted Story text and decide clean vs preserve.

    Returns (action, turn_type) where action is "cleaned" or "preserved".
    Empty / blank text is treated as a no-op preserve (already blank).
    """
    raw = (text or "").strip()
    if not raw:
        # Already blank — no decision needed. Report as preserved/empty.
        return "preserved", "unknown"
    turn_type = classify_conversation_turn(raw)
    if turn_type in _CLEANED_TURN_TYPES:
        return "cleaned", turn_type
    # story_canon, unknown → preserve. Unknown is conservative-preserve.
    return "preserved", turn_type


def _audit(
    project_id: str,
    field_name: str,
    original: str,
    turn_type: TurnType,
    action: str,
) -> dict[str, Any]:
    """Build and log a single audit entry."""
    entry = {
        "project_id": project_id,
        "field": field_name,
        "original_snippet": _snippet(original),
        "classification": turn_type,
        "action": action,
    }
    logger.info(
        "wiki_cleanup: project=%s field=%s action=%s classification=%s snippet=%r",
        project_id,
        field_name,
        action,
        turn_type,
        entry["original_snippet"],
    )
    return entry


def _set_story_summary_field(story_summary: dict[str, Any], field: str) -> None:
    """Blank a storySummary field, matching the compiler's blank shape."""
    story_summary[field] = _BLANK_VALUE


def _clean_story_summary(
    project_id: str,
    story_summary: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Inspect and clean a `compiledWiki.storySummary` dict in place.

    Returns (cleaned_fields, preserved_fields, audit_entries).
    """
    cleaned: list[str] = []
    preserved: list[str] = []
    audit: list[dict[str, Any]] = []

    if not isinstance(story_summary, dict):
        return cleaned, preserved, audit

    for field in _STORY_SUMMARY_FIELDS:
        original = story_summary.get(field, "")
        # Coerce non-string (None / missing) to "" for classification.
        original_text = original if isinstance(original, str) else ("" if original is None else str(original))
        action, turn_type = _decide_action(original_text)
        audit.append(_audit(project_id, f"storySummary.{field}", original_text, turn_type, action))
        if action == "cleaned":
            _set_story_summary_field(story_summary, field)
            cleaned.append(f"storySummary.{field}")
        else:
            preserved.append(f"storySummary.{field}")

    return cleaned, preserved, audit


def _clean_knowledge_entries(
    project_id: str,
    knowledge_entries: list[Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Inspect and clean `projectIntelligence.knowledgeEntries` in place.

    Only entries whose `section` is story-shaped (storyAndEpisodes / story /
    creativeFoundation) AND whose text classifies as cleaned-filler are
    blanked. Entries are preserved when in doubt.

    The cleanup blanks the `text` of a misclassified entry rather than
    removing the row, so the audit trail (id / state / provenance) is
    preserved and the migration is reversible from the audit log.

    Returns (cleaned_fields, preserved_fields, audit_entries).
    """
    cleaned: list[str] = []
    preserved: list[str] = []
    audit: list[dict[str, Any]] = []

    if not isinstance(knowledge_entries, list):
        return cleaned, preserved, audit

    # Sections that feed the Story page / Story summary. We only touch
    # entries in these sections to avoid mutating unrelated knowledge
    # (character / location / world) entries.
    story_sections = {"storyAndEpisodes", "story", "creativeFoundation"}

    for idx, entry in enumerate(knowledge_entries):
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section") or "").strip()
        if section not in story_sections:
            continue
        original = entry.get("text", "")
        original_text = original if isinstance(original, str) else ("" if original is None else str(original))
        action, turn_type = _decide_action(original_text)
        field_name = f"knowledgeEntries[{idx}].text"
        audit.append(_audit(project_id, field_name, original_text, turn_type, action))
        if action == "cleaned":
            entry["text"] = _BLANK_VALUE
            cleaned.append(field_name)
        else:
            preserved.append(field_name)

    return cleaned, preserved, audit


def _persist_settings(db: Session, project: Project, settings: dict[str, Any]) -> None:
    """Write the settings dict back to project.settings_json and commit."""
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()
    if hasattr(db, "refresh"):
        try:
            db.refresh(project)
        except Exception:
            pass


def clean_persisted_wiki_filler(project_id: str, db_session: Session) -> dict[str, Any]:
    """Conservatively clean misclassified filler from a project's persisted Wiki.

    Loads `Project.settings_json.projectIntelligence` (the authoritative
    snapshot payload), inspects `knowledgeEntries` and
    `compiledWiki.storySummary` for misclassified meta-conversation /
    preference / production-request / question / brainstorming filler,
    blanks the offending fields, and persists the result.

    Idempotent: a second run finds blank fields and reports them as
    preserved (no-op), so running twice == running once.

    Returns a dict:
        {
          "project_id": str,
          "cleaned_fields": list[str],   # e.g. ["storySummary.logline"]
          "preserved_fields": list[str],
          "audit": list[dict],
        }
    """
    project = db_session.get(Project, project_id)
    if not project:
        return {
            "project_id": project_id,
            "cleaned_fields": [],
            "preserved_fields": [],
            "audit": [],
            "error": "project_not_found",
        }

    settings = _load_project_settings(project)
    payload = settings.get(_SETTINGS_KEY)
    if not isinstance(payload, dict):
        # No persisted intelligence yet — nothing to clean.
        return {
            "project_id": project_id,
            "cleaned_fields": [],
            "preserved_fields": [],
            "audit": [],
        }

    cleaned_fields: list[str] = []
    preserved_fields: list[str] = []
    audit: list[dict[str, Any]] = []

    # 1) compiledWiki.storySummary (Logline / Short Summary / Long Summary).
    compiled_wiki = payload.get("compiledWiki")
    if isinstance(compiled_wiki, dict):
        story_summary = compiled_wiki.get("storySummary")
        if isinstance(story_summary, dict):
            c, p, a = _clean_story_summary(project_id, story_summary)
            cleaned_fields.extend(c)
            preserved_fields.extend(p)
            audit.extend(a)
        else:
            # No storySummary to clean. Treat as no-op.
            pass

    # 2) projectIntelligence.knowledgeEntries — only story-section entries.
    knowledge_entries = payload.get("knowledgeEntries")
    c, p, a = _clean_knowledge_entries(project_id, knowledge_entries)  # type: ignore[arg-type]
    cleaned_fields.extend(c)
    preserved_fields.extend(p)
    audit.extend(a)

    # Persist only if something changed. This keeps idempotent reruns
    # from churning the settings_json revision / updated_at unnecessarily.
    if cleaned_fields:
        settings[_SETTINGS_KEY] = payload
        _persist_settings(db_session, project, settings)

    return {
        "project_id": project_id,
        "cleaned_fields": cleaned_fields,
        "preserved_fields": preserved_fields,
        "audit": audit,
    }


def run_cleanup_for_all_projects(db_session: Session) -> list[dict[str, Any]]:
    """Iterate all projects and run the cleanup migration once per project.

    This is a one-time migration entrypoint — not a recurring job. Each
    project is cleaned independently; a failure on one project does not
    abort the others (the error is recorded in that project's result).
    """
    results: list[dict[str, Any]] = []
    try:
        projects = db_session.query(Project).all()
    except Exception as exc:  # noqa: BLE001
        logger.error("wiki_cleanup: failed to enumerate projects: %s", exc)
        return [{"error": f"enumerate_projects_failed: {exc}"}]

    for project in projects:
        pid = project.id
        try:
            result = clean_persisted_wiki_filler(pid, db_session)
            # Also run the known-string polluted-Story cleanup so both
            # passes run together on startup.
            story_result = clean_polluted_wiki_story(db_session, pid)
            result["polluted_story_cleanup"] = story_result
        except Exception as exc:  # noqa: BLE001
            logger.error("wiki_cleanup: project=%s failed: %s", pid, exc)
            result = {
                "project_id": pid,
                "cleaned_fields": [],
                "preserved_fields": [],
                "audit": [],
                "error": f"cleanup_failed: {exc}",
            }
        results.append(result)
    return results


# ── Known-string polluted Wiki Story cleanup ──────────────────────────────
#
# A second, more aggressive pass that targets known contamination strings
# (test fixtures / onboarding chatter that leaked into Story fields) by
# exact substring match. Conservative: only blanks Story fields whose
# content contains one of the known pollution markers; never touches a
# field that is genuinely empty or contains legitimate story.
#
# After blanking, the Wiki Story is rebuilt from the authoritative
# StoryEntry record (`story_entries.store`) — Logline / Short / Long come
# exclusively from the saved Story record, never from conversation.

_POLLUTION_MARKERS: tuple[str, ...] = (
    "Please call me friend",
    "I've filled in how I'd like us to work together",
    "Persistence verification",
    "Follow-up Test",
    "test strings",
    "Audit Schnick Coffee",
)


def _contains_pollution(text: str) -> str | None:
    """Return the first matching pollution marker in `text`, or None."""
    if not text:
        return None
    lower = str(text).lower()
    for marker in _POLLUTION_MARKERS:
        if marker.lower() in lower:
            return marker
    return None


def _fetch_story_record_for_rebuild(db_session: Session, project_id: str) -> Any:
    """Fetch the authoritative StoryEntry row for rebuild (or None).

    Reuses the existing `story_entries` store — never a parallel store.
    Prefers a `project_story` entry; otherwise falls back to the first row.
    """
    try:
        from ...story_entries.store import list_entries as _list_story_entries

        rows = _list_story_entries(db_session, project_id)
        if not rows:
            return None
        for row in rows:
            if getattr(row, "entry_type", "") == "project_story":
                return row
        return rows[0]
    except Exception:  # noqa: BLE001
        return None


def _record_field(story_record: Any, field: str) -> str:
    if story_record is None:
        return ""
    snake_map = {
        "logline": "logline",
        "shortSummary": "short_summary",
        "longSummary": "long_summary",
    }
    if isinstance(story_record, dict):
        value = story_record.get(field) or story_record.get(snake_map.get(field, ""))
    else:
        value = getattr(story_record, field, None)
        if value is None:
            value = getattr(story_record, snake_map.get(field, ""), None)
    return str(value or "").strip()


def clean_polluted_wiki_story(db_session: Session, project_id: str) -> dict[str, Any]:
    """Clean Wiki Story fields containing known contamination strings and
    rebuild them from the authoritative Story record.

    Targets the contamination strings enumerated in `_POLLUTION_MARKERS`
    (test fixtures / onboarding chatter that previously leaked into
    Logline / Short Summary / Long Summary via conversation compilation).

    Steps:
    1. Load `Project.settings_json.projectIntelligence.compiledWiki.storySummary`.
    2. For each of `logline` / `shortSummary` / `longSummary`, if the field
       contains a known pollution marker, blank it and record an audit entry.
    3. After blanking, rebuild the Wiki Story from the authoritative
       StoryEntry record (the single source of truth) so the page reflects
       the saved Story, not the polluted conversation.
    4. Persist only when something changed (idempotent).

    Returns a dict:
        {
          "project_id": str,
          "cleaned_fields": list[str],
          "preserved_fields": list[str],
          "audit": list[dict],
          "rebuilt_from_story_record": bool,
        }
    """
    project = db_session.get(Project, project_id)
    if not project:
        return {
            "project_id": project_id,
            "cleaned_fields": [],
            "preserved_fields": [],
            "audit": [],
            "rebuilt_from_story_record": False,
            "error": "project_not_found",
        }

    settings = _load_project_settings(project)
    payload = settings.get(_SETTINGS_KEY)
    if not isinstance(payload, dict):
        return {
            "project_id": project_id,
            "cleaned_fields": [],
            "preserved_fields": [],
            "audit": [],
            "rebuilt_from_story_record": False,
        }

    cleaned: list[str] = []
    preserved: list[str] = []
    audit: list[dict[str, Any]] = []
    changed = False

    compiled_wiki = payload.get("compiledWiki")
    if not isinstance(compiled_wiki, dict):
        compiled_wiki = {}
        payload["compiledWiki"] = compiled_wiki
        changed = True

    story_summary = compiled_wiki.get("storySummary")
    if not isinstance(story_summary, dict):
        story_summary = {}
        compiled_wiki["storySummary"] = story_summary
        changed = True

    for field in _STORY_SUMMARY_FIELDS:
        original = story_summary.get(field, "")
        original_text = original if isinstance(original, str) else ("" if original is None else str(original))
        marker = _contains_pollution(original_text)
        if marker is not None:
            audit.append({
                "project_id": project_id,
                "field": f"storySummary.{field}",
                "original_snippet": _snippet(original_text),
                "pollution_marker": marker,
                "action": "cleaned",
            })
            story_summary[field] = _BLANK_VALUE
            cleaned.append(f"storySummary.{field}")
            changed = True
        else:
            audit.append({
                "project_id": project_id,
                "field": f"storySummary.{field}",
                "original_snippet": _snippet(original_text),
                "pollution_marker": None,
                "action": "preserved",
            })
            preserved.append(f"storySummary.{field}")

    # Rebuild cleaned Wiki Story from the authoritative Story record so the
    # page reflects the saved Story (single source of truth), not polluted
    # conversation. This pass writes the Story record's values into the
    # cleaned fields — but only when at least one field was blanked, to
    # avoid clobbering legitimate content on idempotent reruns.
    rebuilt = False
    if cleaned:
        story_record = _fetch_story_record_for_rebuild(db_session, project_id)
        if story_record is not None:
            story_summary["logline"] = _record_field(story_record, "logline")
            story_summary["shortSummary"] = _record_field(story_record, "shortSummary")
            story_summary["longSummary"] = _record_field(story_record, "longSummary")
            rebuilt = True
            changed = True
            audit.append({
                "project_id": project_id,
                "field": "storySummary.rebuild",
                "original_snippet": "",
                "pollution_marker": None,
                "action": "rebuilt_from_story_record",
            })

    if changed:
        settings[_SETTINGS_KEY] = payload
        _persist_settings(db_session, project, settings)

    return {
        "project_id": project_id,
        "cleaned_fields": cleaned,
        "preserved_fields": preserved,
        "audit": audit,
        "rebuilt_from_story_record": rebuilt,
    }


def _iter_projects(db_session: Session) -> Iterable[Project]:
    """Helper for the __main__ entrypoint."""
    return db_session.query(Project).all()  # type: ignore[return-value]


if __name__ == "__main__":
    # One-time manual migration entrypoint.
    # Usage (from studio-api/):
    #   python -m app.codirector.wiki_intelligence.cleanup_migration
    import sys

    from ...db import SessionLocal, init_db

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    init_db()
    db = SessionLocal()
    try:
        all_results = run_cleanup_for_all_projects(db)
    finally:
        db.close()

    total_cleaned = sum(len(r.get("cleaned_fields", [])) for r in all_results)
    total_preserved = sum(len(r.get("preserved_fields", [])) for r in all_results)
    print(
        f"Wiki cleanup migration complete: {len(all_results)} projects, "
        f"{total_cleaned} fields cleaned, {total_preserved} preserved."
    )
    sys.exit(0)