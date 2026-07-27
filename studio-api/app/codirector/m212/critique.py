"""M2.12 critique agent + mistake classification (structured, no weight updates)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m212_tables
from .lessons import LessonStore
from .safety import AdaptiveLearningSafetyError, assert_verified_outcome

MISTAKE_CLASSES = (
    "continuity",
    "bible",
    "timeline",
    "music",
    "sfx_timing",
    "camera",
    "structured_output",
    "provider",
    "confidence_miscalibration",
    "agent_conflict",
    "export",
    "test_failure",
    "success",
)

_CLASS_HINTS: dict[str, tuple[str, ...]] = {
    "continuity": ("continuity", "wardrobe", "prop state", "orientation", "match cut"),
    "bible": ("bible", "character bible", "locked fact", "entity"),
    "timeline": ("timeline", "clip order", "edit decision", "sequence"),
    "music": ("music", "score", "cue", "underscore"),
    "sfx_timing": ("sfx", "sound effect", "timing", "foley", "sync"),
    "camera": ("camera", "lens", "framing", "shot", "cinematograph"),
    "structured_output": ("schema", "json", "structured", "parse", "format"),
    "provider": ("provider", "model missing", "endpoint", "capability"),
    "confidence_miscalibration": ("overconfident", "miscalibrat", "confidence wrong"),
    "agent_conflict": ("conflict", "disagree", "specialist conflict"),
    "export": ("export", "render package", "delivery"),
    "test_failure": ("test fail", "pytest", "regression fail", "assert"),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def classify_mistake(action: dict[str, Any], outcome: dict[str, Any], traces: list[dict[str, Any]]) -> str:
    blob_parts = [
        str(action.get("summary") or ""),
        str(action.get("recommendation") or ""),
        str(outcome.get("message") or ""),
        str(outcome.get("note") or ""),
        str(outcome.get("mistakeClass") or ""),
    ]
    for t in traces[:5]:
        blob_parts.append(str(t.get("status") or ""))
        fails = t.get("failures") or []
        if isinstance(fails, list):
            blob_parts.extend(str(f) for f in fails[:5])
    blob = " ".join(blob_parts).lower()

    forced = str(outcome.get("mistakeClass") or "").strip().lower()
    if forced in MISTAKE_CLASSES:
        return forced

    if outcome.get("success") is True or str(outcome.get("status") or "").lower() == "success":
        return "success"

    scores: dict[str, int] = {c: 0 for c in MISTAKE_CLASSES if c != "success"}
    for cls, hints in _CLASS_HINTS.items():
        for h in hints:
            if h in blob:
                scores[cls] += 1
    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        return "structured_output"
    return best[0]


def score_evidence(
    action: dict[str, Any],
    outcome: dict[str, Any],
    traces: list[dict[str, Any]],
    mistake_class: str,
) -> tuple[float, float, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    score = 0.15
    if outcome.get("verified") is True:
        score += 0.35
        evidence.append({"type": "verified_outcome", "text": "Outcome marked verified"})
    if outcome.get("humanRejected") or outcome.get("rejected"):
        score += 0.25
        evidence.append({"type": "human_reject", "text": str(outcome.get("note") or "rejected")})
    if traces:
        score += min(0.2, 0.05 * len(traces))
        evidence.append({"type": "trace_refs", "count": len(traces)})
    if action.get("decisionId"):
        score += 0.1
        evidence.append({"type": "decision", "id": action.get("decisionId")})
    if mistake_class and mistake_class != "success":
        score += 0.1
        evidence.append({"type": "mistake_class", "class": mistake_class})
    score = max(0.0, min(1.0, score))
    confidence = float(outcome.get("confidence") or action.get("confidence") or score)
    confidence = max(0.0, min(1.0, confidence))
    return score, confidence, evidence


def critique_action(
    db: Session,
    *,
    project_id: str,
    action: dict[str, Any],
    outcome: dict[str, Any],
    traces: Optional[list[dict[str, Any]]] = None,
    layer: str = "project",
    session_id: Optional[str] = None,
    create_lesson: bool = True,
) -> dict[str, Any]:
    """Structured critique from action + outcome + traces. Never auto-activates system layer."""

    traces = traces or []
    # Allow classified failed/unverified outcomes; block unclassified ones.
    try:
        assert_verified_outcome(outcome)
    except AdaptiveLearningSafetyError:
        if not (outcome.get("mistakeClass") or outcome.get("classified")):
            raise
        outcome = {**outcome, "classified": True}

    mistake_class = classify_mistake(action, outcome, traces)
    evidence_score, confidence, evidence = score_evidence(action, outcome, traces, mistake_class)

    summary = (
        f"{'Success' if mistake_class == 'success' else 'Mistake'} classified as {mistake_class}. "
        f"{str(outcome.get('message') or outcome.get('note') or action.get('summary') or '')[:240]}"
    ).strip()

    lesson_text = str(
        outcome.get("lessonText")
        or action.get("correction")
        or (
            f"Avoid repeating {mistake_class} issue: "
            f"{outcome.get('message') or action.get('recommendation') or summary}"
        )
    ).strip()

    policy = {
        "avoid": mistake_class if mistake_class != "success" else None,
        "prefer": outcome.get("prefer"),
        "hints": outcome.get("hints") or [],
    }

    candidate: dict[str, Any] | None = None
    if create_lesson and mistake_class != "success":
        # System layer candidates require explicit layer request; never auto-activate.
        candidate_layer = layer if layer in ("session", "project", "user", "system") else "project"
        if candidate_layer == "system":
            # Still create as candidate only; promote gates handle approval.
            pass
        candidate = LessonStore.create_candidate(
            db,
            layer=candidate_layer,
            text_body=lesson_text,
            title=str(outcome.get("title") or f"{mistake_class} lesson")[:120],
            policy=policy,
            evidence=evidence,
            confidence=confidence,
            evidence_score=evidence_score,
            mistake_class=mistake_class,
            source_signals=[
                {"type": "action", "data": {k: action.get(k) for k in ("decisionId", "summary", "specialistId")}},
                {"type": "outcome", "data": {k: outcome.get(k) for k in ("status", "message", "verified")}},
                {"type": "traces", "ids": [t.get("id") for t in traces if t.get("id")]},
            ],
            project_id=project_id if candidate_layer in ("session", "project") else None,
            session_id=session_id,
            actor="critique",
        )

    return {
        "id": str(uuid.uuid4()),
        "projectId": project_id,
        "sessionId": session_id,
        "result": "success" if mistake_class == "success" else "mistake",
        "mistakeClass": mistake_class,
        "summary": summary,
        "evidenceScore": evidence_score,
        "confidence": confidence,
        "evidence": evidence,
        "candidateLesson": candidate,
        "systemAutoActivate": False,
        "notes": "System-layer lessons never auto-activate.",
    }


def create_retrospective(
    db: Session,
    *,
    project_id: str,
    summary: str,
    critique: dict[str, Any],
    candidate_lesson_ids: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    ensure_m212_tables()
    import json

    rid = str(uuid.uuid4())
    ids = candidate_lesson_ids or []
    if critique.get("candidateLesson") and critique["candidateLesson"].get("id"):
        if critique["candidateLesson"]["id"] not in ids:
            ids.append(critique["candidateLesson"]["id"])
    db.execute(
        text(
            """
            INSERT INTO m212_retrospectives
            (id, project_id, session_id, summary, critique_json, candidate_lesson_ids_json, trace_id, created_at)
            VALUES
            (:id, :project_id, :session_id, :summary, :critique_json, :ids_json, :trace_id, :created_at)
            """
        ),
        {
            "id": rid,
            "project_id": project_id,
            "session_id": session_id,
            "summary": summary or critique.get("summary") or "",
            "critique_json": json.dumps(critique, ensure_ascii=False),
            "ids_json": json.dumps(ids, ensure_ascii=False),
            "trace_id": trace_id,
            "created_at": _now(),
        },
    )
    db.commit()
    return {
        "id": rid,
        "projectId": project_id,
        "sessionId": session_id,
        "summary": summary or critique.get("summary") or "",
        "critique": critique,
        "candidateLessonIds": ids,
        "traceId": trace_id,
        "createdAt": _now(),
    }


def list_retrospectives(db: Session, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    ensure_m212_tables()
    import json

    rows = db.execute(
        text(
            """
            SELECT * FROM m212_retrospectives
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"project_id": project_id, "limit": max(1, min(limit, 200))},
    ).mappings().fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "projectId": r["project_id"],
                "sessionId": r["session_id"],
                "summary": r["summary"],
                "critique": json.loads(r["critique_json"] or "{}"),
                "candidateLessonIds": json.loads(r["candidate_lesson_ids_json"] or "[]"),
                "traceId": r["trace_id"],
                "createdAt": r["created_at"],
            }
        )
    return out


def sanitize_untrusted_text(raw: str, max_len: int = 2000) -> str:
    """Strip obvious instruction-injection patterns from untrusted content."""

    text_in = (raw or "")[:max_len]
    cleaned = re.sub(r"(?i)ignore\s+(all\s+)?previous\s+instructions?", "[redacted]", text_in)
    cleaned = re.sub(r"(?i)system\s*:\s*", "[redacted] ", cleaned)
    return cleaned
