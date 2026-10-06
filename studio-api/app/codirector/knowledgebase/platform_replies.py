"""Deterministic Co-Director answers from retrieved Adept knowledge."""

from __future__ import annotations

import re
from typing import Optional

from .lexicon import DOMAIN_NETWORKING, LexiconHit, resolve_terms
from .loader import KnowledgeDocument, get_document
from .retrieve import KnowledgeRetrieval, retrieve_knowledge

_QUESTION_RE = re.compile(
    r"(?is)"
    r"^\s*(what|what's|whats|which|who|how|is|can|does|do)\b"
    r"|[?]"
    r"|\bvs\.?\b|\bversus\b"
    r"|\bcompared to\b"
    r"|\bis it broken\b"
    r"|—"
)

_CONTRAST_RE = re.compile(r"(?i)\bvs\.?\b|\bversus\b|\bcompared to\b")
_MIN_RETRIEVE_SCORE = 2.0
_EXCERPT_LIMIT = 360

# Adept UI v1.1: never let a retrieved excerpt recommend opening Spatial Map.
_SM_OPEN_RECOMMEND_RE = re.compile(
    r"(?i)\b(?:open|opening|go to|switch to|take me to|launch|use the)\s+(?:the\s+)?spatial\s+map\b"
)


def _without_sm_open_recommendation(reply: Optional[str]) -> Optional[str]:
    if not reply or not _SM_OPEN_RECOMMEND_RE.search(reply):
        return reply
    doc = get_document("spatial-map")
    if doc and doc.spoken:
        return _plain(doc.spoken)
    return "Use Environment Creator for environments and place identity."


def _is_platform_question(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_QUESTION_RE.search(text))


def _plain(text: str) -> str:
    cleaned = re.sub(r"[*`_]+", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _table_rows(body: str, terms: list[LexiconHit], message: str) -> list[str]:
    needles = [hit.term for hit in terms]
    needles.extend(alias for hit in terms for alias in hit.aliases[:4])
    if re.search(r"spatial map|placement grid|atlas", message or "", re.I):
        # Spatial Map is shelved in v1.1 — keep lexicon hits for honesty, prefer Env Creator / IG copy.
        needles.extend(["Spatial Map", "shelved", "Environment Creator", "Image Generator", "Atlas", "Circles", "placement grid"])
    rows: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        hay = stripped.lower()
        if not any(needle and needle.lower() in hay for needle in needles):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        cells = [cell for cell in cells if cell and cell.lower() not in {"creator says", "adept meaning", "not this"}]
        if len(cells) >= 2:
            rows.append(_plain(" — ".join(cells[:3])))
    return rows


def _question_needles(message: str, terms: list[LexiconHit]) -> list[str]:
    keys = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", message or "")
        if token.lower()
        not in {
            "what",
            "whats",
            "which",
            "does",
            "mean",
            "this",
            "that",
            "with",
            "from",
            "into",
            "make",
            "tool",
            "the",
        }
    ]
    for hit in terms:
        keys.append(hit.term.lower())
        keys.extend(alias.lower() for alias in hit.aliases if alias)
    out: list[str] = []
    for key in keys:
        token = key.strip()
        if token and token not in out:
            out.append(token)
    return out


def _relevant_excerpt(
    body: str,
    message: str,
    terms: list[LexiconHit],
    *,
    limit: int = _EXCERPT_LIMIT,
) -> str:
    keys = _question_needles(message, terms)
    if not keys:
        return ""
    need = 2 if len(keys) >= 2 else 1
    matches: list[str] = []
    used = 0
    for raw in re.split(r"(?<=[.!?])\s+|\n+", body or ""):
        sentence = _plain(raw)
        if len(sentence) < 8:
            continue
        hay = sentence.lower()
        if sum(1 for key in keys if key in hay) < need:
            continue
        if used + len(sentence) > limit:
            break
        matches.append(sentence)
        used += len(sentence) + 1
        if used >= limit:
            break
    return " ".join(matches).strip()


def _short_excerpt(body: str, *, limit: int = _EXCERPT_LIMIT) -> str:
    chunks: list[str] = []
    used = 0
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        if stripped.startswith("Sources:") or stripped.startswith("```"):
            continue
        take = _plain(stripped)
        if not take:
            continue
        if used + len(take) > limit:
            take = take[: max(0, limit - used)].rstrip()
            if take:
                chunks.append(take)
            break
        chunks.append(take)
        used += len(take) + 1
        if used >= limit:
            break
    return " ".join(chunks).strip()


def _adds_value(excerpt: str, spoken: str) -> bool:
    extra = _plain(excerpt).lower()
    base = _plain(spoken).lower()
    if not extra or extra in base:
        return False
    spoken_tokens = set(re.findall(r"[a-z0-9]{4,}", base))
    excerpt_tokens = set(re.findall(r"[a-z0-9]{4,}", extra))
    return bool(excerpt_tokens - spoken_tokens)


def _compose(doc: KnowledgeDocument, message: str, terms: list[LexiconHit]) -> str:
    spoken = _plain(doc.spoken)
    rows = _table_rows(doc.body, terms, message)
    if _CONTRAST_RE.search(message or "") and rows:
        return " ".join(rows)[:900]
    definition = bool(re.search(r"(?i)^\s*what(?:'s| is| does)\b", message or ""))
    if spoken and definition and not _CONTRAST_RE.search(message or ""):
        return spoken
    relevant = _relevant_excerpt(doc.body, message, terms)
    excerpt = rows[0] if rows else (relevant or _short_excerpt(doc.body))
    if spoken:
        if excerpt and _adds_value(excerpt, spoken):
            combined = f"{spoken} {excerpt}".strip()
            return combined[:900]
        return spoken
    return (excerpt or _plain(doc.title))[:900]


def _networking_spoken(terms: list[LexiconHit]) -> str | None:
    for hit in terms:
        if hit.domain == DOMAIN_NETWORKING and hit.spoken:
            return _plain(hit.spoken)
    return None


def _is_timeline_production_request(text: str, workspace: str | None) -> bool:
    """A Timeline scene-production request is never a platform Q&A.

    Dialogue inside a scene request ('CADE: "Where is the Adept?"') contains a
    question mark; the bare ``[?]`` in ``_QUESTION_RE`` would otherwise let the
    knowledge interceptor swallow the entire production request and answer it
    with a generator card instead of preparing the scene.
    """
    try:
        from ..routing.turn_intent import classify_turn_intent, is_production_turn

        kind = classify_turn_intent(text, workspace=workspace or None)
        return is_production_turn(kind)
    except Exception:
        pass
    try:
        from ..routing.generation_authority import classify_generation_authority
    except Exception:
        return False
    try:
        authority = classify_generation_authority(text, workspace=workspace or None)
    except Exception:
        return False
    return authority is not None and str(getattr(authority, "owner", "") or "") == "timeline"


def knowledge_reply(message: str, *, workspace: str | None = None) -> Optional[str]:
    text = (message or "").strip()
    if not text or not _is_platform_question(text):
        return None
    if _is_timeline_production_request(text, workspace):
        return None
    terms = resolve_terms(text, workspace=workspace)
    # Adept UI v1.1: never echo shelved Spatial/3D product names to creators.
    entity_ids = {hit.entity_id for hit in terms}
    if "spatial-map" in entity_ids:
        return "Use Environment Creator for environments and place identity."
    if "posecraft" in entity_ids:
        return "Use Image Generator for production stills."
    networking = _networking_spoken(terms)
    if networking:
        return networking
    status_ids = {hit.entity_id for hit in terms}
    if "adept-readiness" in status_ids and re.search(r"\b(broken|offline|on demand)\b", text, re.I):
        ready = get_document("adept-readiness")
        if ready and ready.spoken:
            return _plain(ready.spoken)
    retrieval: KnowledgeRetrieval = retrieve_knowledge(text, workspace=workspace, limit=4)
    best = None
    for hit in retrieval.hits:
        if hit.score < _MIN_RETRIEVE_SCORE:
            continue
        doc = get_document(hit.doc_id)
        if doc is None:
            continue
        best = doc
        break
    if best is not None:
        return _without_sm_open_recommendation(_compose(best, text, terms) or None)
    for hit in terms:
        if hit.spoken:
            return _without_sm_open_recommendation(_plain(hit.spoken))
        doc = get_document(hit.entity_id)
        if doc and doc.spoken:
            return _without_sm_open_recommendation(_plain(doc.spoken))
    return None
