"""Story Summary Editor — LLM-backed primary, conservative fallback.

Builds curated evidence, invokes the specialist prompt via the provider when
available, applies the ten hard laws, and persists the result into the
compiled Wiki cache. Falls back to a conservative deterministic synopsis when
no provider is available (no silent degradation — provenance records
`editorMode`).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ....conversation.snapshot import load_snapshot, save_snapshot
from .contracts import CompiledStorySummary, PreviousApprovedSummary, StorySummarySource
from .evidence import build_story_summary_source, evidence_hash
from .fallback import conservative_fallback
from .laws import validate
from .readiness import (
    logline_readiness,
    long_summary_readiness,
    short_summary_readiness,
    should_render,
)

_SPECIALIST_ID = "story-summary-editor"
_JSON_RE = re.compile(r"```json\s*([\s\S]*?)```", re.IGNORECASE)


def _load_specialist_prompt() -> str:
    try:
        from ....prompts.loader import get_prompt_library

        library = get_prompt_library()
        record = library.get(_SPECIALIST_ID)
        if record:
            return record.body
    except Exception:  # noqa: BLE001
        pass
    # Minimal inline fallback doctrine.
    return (
        "You are the Story Summary Editor. Write simple, natural, professional "
        "editorial prose for the Logline, Short Summary, and Long Summary. "
        "Write less when project knowledge is sparse. Never use technical "
        "language, placeholder filler, or promotional voice. Revise rather "
        "than rewrite when evidence changes are minor. Return strict JSON."
    )


def _build_messages(source: StorySummarySource, specialist_body: str) -> list[dict[str, str]]:
    evidence_payload = {
        "confirmedFacts": source.confirmedFacts,
        "approvedScriptSummaries": source.approvedScriptSummaries,
        "creatorStatedInterpretations": source.creatorStatedInterpretations,
        "specialistInterpretations": source.specialistInterpretations,
        "confirmedCharacterRoles": source.confirmedCharacterRoles,
        "confirmedTimelineEvents": source.confirmedTimelineEvents,
        "confirmedWorldRules": source.confirmedWorldRules,
        "inferredThemes": source.inferredThemes,
        "unresolvedQuestions": source.unresolvedQuestions,
        "formatProfile": source.formatProfile,
        "previousApprovedSummary": (source.previousApprovedSummary.model_dump() if source.previousApprovedSummary else None),
    }
    user_content = (
        "Project format: " + source.formatProfile + "\n\n"
        "Curated evidence (JSON):\n"
        + json.dumps(evidence_payload, indent=2, ensure_ascii=False)
        + "\n\n"
        "Return strict JSON with keys: logline, shortSummary, longSummary, "
        "themes, centralConflicts, narrativeFrame, revisionDelta. Leave any "
        "field empty when its readiness is insufficient. Do not invent."
    )
    return [
        {"role": "system", "content": specialist_body},
        {"role": "user", "content": user_content},
    ]


def _parse_provider_payload(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    match = _JSON_RE.search(raw)
    if match:
        raw = match.group(1)
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    return data


def _from_provider(
    data: dict[str, Any], source: StorySummarySource
) -> CompiledStorySummary:
    logline_cov = logline_readiness(source)
    short_cov = short_summary_readiness(source)
    long_cov = long_summary_readiness(source)

    logline = str(data.get("logline") or "").strip()
    short = str(data.get("shortSummary") or data.get("short_summary") or "").strip()
    long_summary = str(data.get("longSummary") or data.get("long_summary") or "").strip()

    # Respect per-section readiness: blank sections that cannot render.
    if not should_render(logline_cov):
        logline = ""
    if not should_render(short_cov):
        short = ""
    if not should_render(long_cov):
        long_summary = ""

    return CompiledStorySummary(
        logline=logline,
        shortSummary=short,
        longSummary=long_summary,
        themes=list(data.get("themes") or source.inferredThemes or []),
        centralConflicts=list(data.get("centralConflicts") or []),
        narrativeFrame=str(data.get("narrativeFrame") or ""),
        unresolvedQuestions=list(source.unresolvedQuestions),
        sourceRecordIds=list(source.sourceIds),
        lastCompiledAt=datetime.now(timezone.utc).isoformat(),
        loglineCoverage=logline_cov,
        shortSummaryCoverage=short_cov,
        longSummaryCoverage=long_cov,
        requiresCreatorReview=False,
        editorMode="llm",
        revisionDelta=str(data.get("revisionDelta") or "initial draft"),
    )


async def edit_story_summary(
    db: Session,
    project_id: str,
    *,
    provider: Any = None,
    force: bool = False,
    pitch_mode: bool = False,
) -> CompiledStorySummary:
    source = build_story_summary_source(db, project_id, include_previous=True)

    # Load previous approved summary for stability check.
    previous_summary: CompiledStorySummary | None = None
    if source.previousApprovedSummary and (
        source.previousApprovedSummary.logline
        or source.previousApprovedSummary.shortSummary
        or source.previousApprovedSummary.longSummary
    ):
        previous_summary = CompiledStorySummary(
            logline=source.previousApprovedSummary.logline,
            shortSummary=source.previousApprovedSummary.shortSummary,
            longSummary=source.previousApprovedSummary.longSummary,
        )

    # Decide whether evidence changed minimally (for stability law).
    evidence_changed_minimally = _evidence_changed_minimally(db, project_id, source)

    # Resolve provider (with a bounded timeout so an unreachable provider
    # never blocks the compile route indefinitely).
    provider_to_use, use_provider, _ = await _resolve_provider(provider)

    summary: CompiledStorySummary
    if use_provider and provider_to_use is not None:
        summary = await _run_provider(provider_to_use, source)
    else:
        summary = conservative_fallback(source)

    # Apply laws as post-conditions.
    violations = validate(
        summary,
        source,
        previous=previous_summary,
        evidence_changed_minimally=evidence_changed_minimally,
        pitch_mode=pitch_mode,
    )
    if violations:
        summary = _apply_violations(summary, violations, source)

    # Story-record pass-through: the LLM editor must NEVER overwrite
    # Logline / Short / Long. Those fields come exclusively from the saved
    # StoryEntry record. The editor may only refine themes, centralConflicts,
    # narrativeFrame, unresolvedQuestions — never Story text. Read the
    # authoritative record and pass its values through unchanged.
    story_record = _fetch_story_record(db, project_id)
    if story_record is not None:
        logline = _record_field(story_record, "logline")
        short = _record_field(story_record, "shortSummary")
        long_summary = _record_field(story_record, "longSummary")
        summary.logline = logline
        summary.shortSummary = short
        summary.longSummary = long_summary

    # Persist into compiled Wiki cache + bump revision.
    _persist(db, project_id, summary, source)
    return summary


def _fetch_story_record(db: Session, project_id: str) -> Any:
    """Return the authoritative StoryEntry row for the project, or None.

    Reads from the existing `story_entries` store — never a parallel store.
    """
    try:
        from ....story_entries.store import list_entries as _list_story_entries

        rows = _list_story_entries(db, project_id)
        if not rows:
            return None
        # Prefer a `project_story` entry; otherwise fall back to the first row.
        for row in rows:
            if getattr(row, "entry_type", "") == "project_story":
                return row
        return rows[0]
    except Exception:  # noqa: BLE001
        return None


def _record_field(story_record: Any, field: str) -> str:
    """Read a Story field from a StoryEntry row/dict, normalized to "".

    Accepts both SQLAlchemy row attributes (logline / short_summary /
    long_summary) and dict shapes (logline / shortSummary / longSummary).
    """
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


async def _run_provider(provider: Any, source: StorySummarySource) -> CompiledStorySummary:
    from ....providers.base import ChatRequest

    specialist_body = _load_specialist_prompt()
    messages = _build_messages(source, specialist_body)
    request = ChatRequest(
        request_id=f"story-summary-{source.projectId}",
        messages=messages,
        model_id=None,
        temperature=0.4,
        mode="chat",
    )
    try:
        result = await asyncio.wait_for(provider.generate(request), timeout=45.0)
        data = _parse_provider_payload(result.reply)
        if data is None:
            return conservative_fallback(source)
        return _from_provider(data, source)
    except asyncio.TimeoutError:
        return conservative_fallback(source)
    except Exception:  # noqa: BLE001
        return conservative_fallback(source)


def _apply_violations(
    summary: CompiledStorySummary, violations: list[str], source: StorySummarySource
) -> CompiledStorySummary:
    """Blank offending fields on violation; fall back if too many violations."""
    fields_to_blank: set[str] = set()
    for v in violations:
        # Violation format: "LAW:field" or "LAW:field:detail"
        parts = v.split(":")
        if len(parts) >= 2:
            field = parts[1]
            if field in {"logline", "shortSummary", "longSummary"}:
                fields_to_blank.add(field)
    for field in fields_to_blank:
        setattr(summary, field, "")
    # If long summary was blanked but short is fine, keep short.
    if len(fields_to_blank) >= 2:
        # Too many violations — fall back to conservative.
        fallback = conservative_fallback(source)
        fallback.editorMode = "deterministic"
        fallback.revisionDelta = "fell back to conservative after law violations"
        return fallback
    return summary


def _evidence_changed_minimally(
    db: Session, project_id: str, source: StorySummarySource
) -> bool:
    """Heuristic: compare current evidence hash to the last persisted hash."""
    snapshot = load_snapshot(db, project_id)
    compiled = getattr(snapshot, "compiledWiki", None) or {}
    prev_hash = compiled.get("storySummaryEvidenceHash") or ""
    current_hash = evidence_hash(source)
    if not prev_hash:
        return False
    if prev_hash == current_hash:
        return True
    # Minimal change: hashes differ but evidence lists overlap heavily.
    return False


def _persist(
    db: Session,
    project_id: str,
    summary: CompiledStorySummary,
    source: StorySummarySource,
) -> None:
    snapshot = load_snapshot(db, project_id)
    compiled = getattr(snapshot, "compiledWiki", None) or {}
    revision = int(compiled.get("compiledRevision") or 0) + 1
    compiled["storySummary"] = summary.model_dump(mode="json")
    compiled["storySummaryEvidenceHash"] = evidence_hash(source)
    compiled["compiledRevision"] = revision
    compiled["lastCompiledAt"] = datetime.now(timezone.utc).isoformat()
    compiled["projection"] = "compiled_bible_v1"
    snapshot.compiledWiki = compiled
    save_snapshot(db, snapshot)


async def _resolve_provider(provider: Any = None) -> tuple[Any, bool, str]:
    try:
        from ....intelligence.specialist_runner import resolve_provider_for_specialists

        return await asyncio.wait_for(
            resolve_provider_for_specialists(provider), timeout=15.0
        )
    except asyncio.TimeoutError:
        return None, False, "limited-analysis"
    except Exception:  # noqa: BLE001
        return None, False, "limited-analysis"


__all__ = ["edit_story_summary"]
