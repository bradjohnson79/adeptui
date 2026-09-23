"""Creator-facing response isolation — never stream/persist internal reasoning."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("adept.codirector.creator_response_gate")

# Confirmed contamination patterns (thinking / prompt / policy leakage).
_CONTAMINATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"here'?s a thinking process",
        r"analyze user input",
        r"check constraints?\s*(&|and)?\s*directives?",
        r"draft construction",
        r"self[- ]correction",
        r"constraint check",
        r"output generation",
        r"\bsystem prompt\b",
        r"\bquestion budget\b",
        r"\bintent classification\b",
        r"\bgrounding gate\b",
        r"\bcontext budget\b",
        r"\btoken budget\b",
        r"\bspecialist routing\b",
        r"\bbackground enrichment\b",
        r"\bcandidate extraction\b",
        r"\bstate machine\b",
        r"\bpipeline\b",
        r"\bschema\b",
        r"<think>",
        r"</think>",
    )
)

# Internal / stale product guidance that must never leak into scene-turn prose
# unless the creator explicitly asked about that product.
_INTERNAL_PRODUCT_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bSpatial Map\b",
        r"\bPoseCraft\b",
        r"\bFire3D\b",
        r"\bSceneCraft\b",
        r"\bStandalone\b",
        r"\bImage Runtime\b",
        r"\bLocal Video Runtime\b",
        r"Adept is the filmmaking app",
        r"\bEnvironment Creator Express\b",
        r"hidden engines",
    )
)


def find_internal_product_leak(text: str, *, user_message: str = "") -> list[str]:
    """Phrases that are internal guidance, not a scene-production answer."""
    asked = (user_message or "").lower()
    hits: list[str] = []
    for pat in _INTERNAL_PRODUCT_LEAK_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        token = m.group(0)
        if token.lower() in asked:
            continue
        hits.append(token)
    return hits


def strip_internal_product_leak(text: str, *, user_message: str = "") -> str:
    """Drop sentences that recite internal/stale product guidance."""
    hits = find_internal_product_leak(text, user_message=user_message)
    if not hits:
        return (text or "").strip()
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        if find_internal_product_leak(sentence, user_message=user_message):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


# Developer jargon that must not appear in ordinary creator replies.
_JARGON_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bpipeline\b",
        r"\bgrounding gate\b",
        r"\bcontext budget\b",
        r"\bintent classification\b",
        r"\bpersistence event\b",
        r"\bSSE\b",
        r"\bcache revision\b",
        r"\bartifact readiness\b",
        r"\bspecialist routing\b",
        r"\bbackground enrichment\b",
        r"\bcandidate extraction\b",
        r"\bschema\b",
        r"\bstate machine\b",
        r"\blatency\b",
        r"\btoken budget\b",
    )
)

# Heuristic: thinking blocks often precede a clear creator answer after blank lines.
_SPLIT_MARKERS = (
    re.compile(r"\n{2,}(?=(?:I(?:'ve| have)|The |What |Keep |Here'?s what|Looking at))", re.I),
    re.compile(r"(?<=\n)(?=(?:I(?:'ve| have) (?:noted|added|logged|tracked)))", re.I),
)


@dataclass
class ProviderTurnResult:
    creatorFacingContent: str
    internalReasoning: str | None = None
    toolCalls: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    contaminated: bool = False
    contaminationMatches: list[str] = field(default_factory=list)


def extract_creator_content(msg: dict[str, Any] | None) -> ProviderTurnResult:
    """Split Ollama message fields — never promote thinking into creator content."""
    if not isinstance(msg, dict):
        return ProviderTurnResult(creatorFacingContent="")
    content = str(msg.get("content") or "").strip()
    thinking = str(msg.get("thinking") or msg.get("reasoning") or "").strip()
    return ProviderTurnResult(
        creatorFacingContent=content,
        internalReasoning=thinking or None,
        metadata={"hadThinkingField": bool(thinking)},
    )


def find_contamination(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _CONTAMINATION_PATTERNS:
        m = pat.search(text or "")
        if m:
            hits.append(m.group(0))
    return hits


def find_jargon(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _JARGON_PATTERNS:
        m = pat.search(text or "")
        if m:
            hits.append(m.group(0))
    return hits


def is_contaminated(text: str) -> bool:
    return bool(find_contamination(text or ""))


def separate_leaked_reasoning(text: str) -> tuple[str, str | None]:
    """Best-effort: keep creator-facing portion; quarantine reasoning prefix/suffix."""
    raw = str(text or "")
    if not raw.strip():
        return "", None
    if not is_contaminated(raw):
        return raw.strip(), None

    # Prefer content after the last contamination-heavy block.
    for marker in _SPLIT_MARKERS:
        parts = marker.split(raw)
        if len(parts) >= 2:
            creator = parts[-1].strip()
            internal = "\n".join(parts[:-1]).strip()
            if creator and not is_contaminated(creator):
                return creator, internal or None

    # Strip lines that match contamination; keep the rest.
    kept: list[str] = []
    quarantined: list[str] = []
    for line in raw.splitlines():
        if find_contamination(line):
            quarantined.append(line)
        else:
            kept.append(line)
    creator = "\n".join(kept).strip()
    internal = "\n".join(quarantined).strip() or raw
    if creator and not is_contaminated(creator):
        return creator, internal
    # Cannot safely separate — quarantine entire message for remediation path.
    return "", raw


def gate_creator_facing(
    text: str,
    *,
    internal_reasoning: str | None = None,
    request_id: str = "",
    user_message: str = "",
) -> ProviderTurnResult:
    """Final protection gate before stream/persist."""
    content = strip_internal_product_leak(str(text or "").strip(), user_message=user_message)
    hits = find_contamination(content)
    if hits:
        separated, leftover = separate_leaked_reasoning(content)
        if separated and not is_contaminated(separated):
            logger.warning(
                "creator_response_gate: stripped contamination requestId=%s matches=%s",
                request_id,
                hits[:5],
            )
            return ProviderTurnResult(
                creatorFacingContent=separated,
                internalReasoning=leftover or internal_reasoning,
                contaminated=True,
                contaminationMatches=hits,
                metadata={"stripped": True},
            )
        logger.error(
            "creator_response_gate: blocked contaminated reply requestId=%s matches=%s",
            request_id,
            hits[:5],
        )
        return ProviderTurnResult(
            creatorFacingContent="",
            internalReasoning=content,
            contaminated=True,
            contaminationMatches=hits,
            metadata={"blocked": True},
        )
    return ProviderTurnResult(
        creatorFacingContent=content,
        internalReasoning=internal_reasoning,
        contaminated=False,
    )


def record_contamination_incident(
    *,
    project_id: str,
    request_id: str,
    matches: list[str],
    action: str,
) -> None:
    logger.warning(
        "contamination_incident projectId=%s requestId=%s action=%s matches=%s",
        project_id,
        request_id,
        action,
        matches[:8],
    )
