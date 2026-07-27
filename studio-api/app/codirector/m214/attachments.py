"""Attachment classify / interpret / confirm (content-based, proposals until approved)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import AttachmentInterpretation
from .db import ensure_m214_tables
from .honesty import default_honesty
from .store import M214Store, _jid, _now

# Content signals (not filename alone)
_KIND_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("screenplay", (r"\bINT\.", r"\bEXT\.", r"FADE IN", r"CUT TO:", r"\bV\.O\.")),
    ("treatment", (r"\btreatment\b", r"\blogline\b", r"\bact\s+[i1]\b", r"\btheme\b")),
    ("storyboard", (r"\bstoryboard\b", r"\bpanel\s+\d+", r"\bframe\s+\d+")),
    ("sketch", (r"\bsketch\b", r"\bdoodle\b", r"\brough\b")),
    ("notes", (r"\bnotes?\b", r"\btodo\b", r"\bbeat\b")),
]


def _signals_from_text(text_body: str) -> list[str]:
    found: list[str] = []
    for kind, patterns in _KIND_PATTERNS:
        for pat in patterns:
            if re.search(pat, text_body, re.IGNORECASE):
                found.append(f"{kind}:{pat}")
    return found


def classify_content(
    *,
    text_body: str = "",
    mime_type: str = "",
    filename: str = "",
) -> tuple[str, float, list[str]]:
    """Classify by content signals; filename is a weak hint only."""
    signals = _signals_from_text(text_body or "")
    scores: dict[str, int] = {}
    for sig in signals:
        kind = sig.split(":", 1)[0]
        scores[kind] = scores.get(kind, 0) + 2
    # Weak filename hint (never sole authority)
    lower = (filename or "").lower()
    for kind, _ in _KIND_PATTERNS:
        if kind in lower:
            scores[kind] = scores.get(kind, 0) + 1
            signals.append(f"filename_hint:{kind}")
    if mime_type.startswith("image/") and "storyboard" not in scores:
        scores["reference_image"] = scores.get("reference_image", 0) + 1
        signals.append("mime:image")
    if mime_type.startswith("audio/"):
        scores["audio_reference"] = scores.get("audio_reference", 0) + 2
        signals.append("mime:audio")
    if mime_type.startswith("video/"):
        scores["video_reference"] = scores.get("video_reference", 0) + 2
        signals.append("mime:video")
    if not scores:
        return "unknown", 0.2, signals or ["no_content_signals"]
    best = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values())
    confidence = min(0.95, best[1] / max(total, 1))
    return best[0], confidence, signals


def interpret_attachment(
    db: Session,
    *,
    project_id: str,
    attachment_id: str,
    text_body: str = "",
    mime_type: str = "",
    filename: str = "",
) -> dict[str, Any]:
    ensure_m214_tables()
    kind, confidence, signals = classify_content(
        text_body=text_body, mime_type=mime_type, filename=filename
    )
    interp = AttachmentInterpretation(
        project_id=project_id,
        attachment_id=attachment_id,
        classified_kind=kind,
        confidence=confidence,
        summary=f"Proposed classification: {kind} (content-based; pending confirmation).",
        proposals=[
            {
                "action": "import_as",
                "kind": kind,
                "sections": ["summary", "beats"] if kind in {"treatment", "screenplay"} else ["media"],
            }
        ],
        status="proposed",
        content_signals=signals,
        honesty=default_honesty(),
        payload={"filename": filename, "mimeType": mime_type, "secureExtractionOnly": True},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_attachment_interpretations "
            "(id, project_id, attachment_id, classified_kind, confidence, summary, status, payload_json, created_at, updated_at) "
            "VALUES (:id, :pid, :aid, :kind, :conf, :summary, :status, :payload, :ts, :ts)"
        ),
        {
            "id": interp.id,
            "pid": project_id,
            "aid": attachment_id,
            "kind": kind,
            "conf": confidence,
            "summary": interp.summary,
            "status": "proposed",
            "payload": _jid(interp.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="codirector.attachment.interpret",
        action="interpret",
        project_id=project_id,
        payload={"interpretationId": interp.id, "kind": kind},
    )
    return interp.to_dict()


def confirm_interpretation(
    db: Session,
    interpretation_id: str,
    *,
    decision: str,
    corrected_kind: Optional[str] = None,
    note: str = "",
) -> dict[str, Any]:
    """Approve / Correct / Provisional / Import sections / Merge / Cancel — proposals until approved."""
    ensure_m214_tables()
    allowed = {
        "approve": "approved",
        "correct": "corrected",
        "provisional": "provisional",
        "import_sections": "approved",
        "merge": "approved",
        "cancel": "cancelled",
    }
    if decision not in allowed:
        raise ValueError(f"Unknown decision {decision}")
    row = db.execute(
        text("SELECT payload_json FROM m214_attachment_interpretations WHERE id = :id"),
        {"id": interpretation_id},
    ).fetchone()
    if not row:
        raise KeyError(interpretation_id)
    data = json.loads(row[0] or "{}")
    status = allowed[decision]
    data["status"] = status
    if corrected_kind:
        data["classified_kind"] = corrected_kind
    data.setdefault("payload", {})["confirmationNote"] = note
    data.setdefault("payload", {})["decision"] = decision
    # Silent bible/timeline mutation forbidden — only store interpretation status.
    db.execute(
        text(
            "UPDATE m214_attachment_interpretations SET status = :status, classified_kind = :kind, "
            "payload_json = :payload, updated_at = :ts WHERE id = :id"
        ),
        {
            "status": status,
            "kind": data.get("classified_kind", "unknown"),
            "payload": _jid(data),
            "ts": _now(),
            "id": interpretation_id,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="codirector.attachment.confirm",
        action=decision,
        project_id=data.get("project_id"),
        payload={"interpretationId": interpretation_id, "status": status},
    )
    return data
