"""Ranked platform-knowledge retrieval. Never dumps the whole corpus."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable

from .lexicon import LexiconHit, losing_entity_ids, resolve_terms
from .sheet_intent_gate import allow_sheet_curriculum_doc
from .loader import (
    CREATOR_CHAT_EXCLUDED_IDS,
    KnowledgeDocument,
    get_document,
    load_all_documents,
)

DEFAULT_LIMIT = 4
BODY_SNIPPET_CHARS = 1200
CONTEXT_CHAR_BUDGET = 2000
MAX_SNIPPET_CHARS = 1600


@dataclass(frozen=True)
class RetrievedSnippet:
    doc_id: str
    title: str
    spoken: str
    excerpt: str
    snippet: str
    score: float


@dataclass(frozen=True)
class KnowledgeRetrieval:
    hits: tuple[RetrievedSnippet, ...]
    elapsed_ms: float
    doc_ids: tuple[str, ...]
    context_chars: int
    docs_retrieved: int


def _mentioned(text: str, alias: str) -> bool:
    token = (alias or "").strip()
    if not token:
        return False
    hay = text or ""
    if len(token) <= 3:
        return bool(re.search(rf"\b{re.escape(token)}\b", hay, re.I))
    if re.search(rf"\b{re.escape(token)}\b", hay, re.I):
        return True
    folded_alias = re.sub(r"[^a-z0-9]+", "", token.lower())
    folded_hay = re.sub(r"[^a-z0-9]+", "", hay.lower())
    return len(folded_alias) >= 4 and folded_alias in folded_hay


def _resolved_ids(hits: Iterable[LexiconHit]) -> set[str]:
    ids: set[str] = set()
    for hit in hits:
        if hit.entity_id:
            ids.add(hit.entity_id)
        ids.update(item for item in hit.also if item)
    return ids


def _losing_ids(hits: Iterable[LexiconHit]) -> set[str]:
    lost: set[str] = set()
    for hit in hits:
        lost.update(losing_entity_ids(hit.term, hit.entity_id))
    return lost - _resolved_ids(hits)


def _workspace_token(workspace: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(workspace or "").lower())


def _score_document(
    doc: KnowledgeDocument,
    message: str,
    *,
    workspace: str | None,
    terms: list[LexiconHit],
    resolved: set[str],
    losing: set[str],
) -> float:
    score = 0.0
    if any(item in resolved for item in doc.match_ids) or doc.id in resolved:
        score += 8.0
    if doc.id in losing or any(item in losing for item in doc.match_ids):
        score -= 12.0
    aliases = (doc.id, doc.title, *doc.aliases, *doc.product_ids, *doc.registry_ids)
    for alias in aliases:
        if doc.id in losing:
            break
        if _mentioned(message, str(alias)):
            score += 3.0
            break
    ws = _workspace_token(workspace)
    if ws and ws in {_workspace_token(tag) for tag in doc.workspaces}:
        score += 2.0
    for pid in (*doc.product_ids, *doc.registry_ids):
        label = str(pid).replace("_", " ").replace("-", " ")
        if _mentioned(message, label) or _mentioned(message, str(pid)):
            score += 2.0
            break
    if re.search(r"\b(broken|offline|on demand)\b", message or "", re.I):
        if doc.id == "adept-readiness" or any(alias.lower() == "on demand" for alias in doc.aliases):
            score += 12.0
    contrast = bool(re.search(r"\bvs\.?\b|\bversus\b|\bcompared to\b", message or "", re.I))
    if contrast and len(terms) >= 2:
        present = sum(
            1
            for hit in terms
            if _mentioned(doc.body, hit.term)
            or any(_mentioned(doc.body, alias) for alias in hit.aliases[:4])
        )
        if present >= 2:
            score += 10.0
    body_l = (doc.body or "").lower()
    spoken_l = (doc.spoken or "").lower()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", message or ""):
        low = token.lower()
        if low in {"the", "and", "for", "this", "that", "what", "does", "mean", "with"}:
            continue
        if low in body_l or low in spoken_l:
            score += 0.25
    return score


def _clip_snippet(doc: KnowledgeDocument) -> tuple[str, str]:
    excerpt = ""
    for line in (doc.body or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        if stripped.startswith("Sources:") or stripped.startswith("```"):
            continue
        excerpt = stripped
        break
    excerpt = excerpt[:BODY_SNIPPET_CHARS]
    parts = [part for part in (doc.title.strip(), doc.spoken.strip(), excerpt) if part]
    snippet = "\n".join(parts)
    if len(snippet) > MAX_SNIPPET_CHARS:
        snippet = snippet[:MAX_SNIPPET_CHARS].rstrip()
    return excerpt, snippet


def retrieve_knowledge(
    message: str,
    *,
    workspace: str | None = None,
    limit: int = DEFAULT_LIMIT,
    root=None,
    purpose: str | None = None,
) -> KnowledgeRetrieval:
    started = time.perf_counter()
    cap = max(1, int(limit or DEFAULT_LIMIT))
    docs = [
        doc
        for doc in load_all_documents(root=root)
        if getattr(doc, "creator_chat", True) and doc.id not in CREATOR_CHAT_EXCLUDED_IDS
    ]
    terms = resolve_terms(message, workspace=workspace)
    resolved = _resolved_ids(terms)
    losing = _losing_ids(terms)
    ranked: list[tuple[float, KnowledgeDocument]] = []
    for doc in docs:
        if not allow_sheet_curriculum_doc(doc.id, message, purpose=purpose):
            continue
        score = _score_document(
            doc,
            message,
            workspace=workspace,
            terms=terms,
            resolved=resolved,
            losing=losing,
        )
        if score > 0:
            ranked.append((score, doc))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    hits: list[RetrievedSnippet] = []
    context_chars = 0
    for score, doc in ranked[:cap]:
        excerpt, snippet = _clip_snippet(doc)
        hits.append(
            RetrievedSnippet(
                doc_id=doc.id,
                title=doc.title,
                spoken=doc.spoken,
                excerpt=excerpt,
                snippet=snippet,
                score=score,
            )
        )
        context_chars += len(snippet)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return KnowledgeRetrieval(
        hits=tuple(hits),
        elapsed_ms=elapsed_ms,
        doc_ids=tuple(item.doc_id for item in hits),
        context_chars=context_chars,
        docs_retrieved=len(hits),
    )


def render_knowledge_context_block(
    message: str,
    *,
    workspace: str | None = None,
    limit: int = DEFAULT_LIMIT,
    max_chars: int = CONTEXT_CHAR_BUDGET,
    purpose: str | None = None,
) -> str:
    retrieval = retrieve_knowledge(message, workspace=workspace, limit=limit, purpose=purpose)
    if not retrieval.hits:
        return ""
    lines = ["ADEPT KNOWLEDGE"]
    used = len(lines[0])
    budget = max(200, int(max_chars or CONTEXT_CHAR_BUDGET))
    for hit in retrieval.hits:
        spoken = (hit.spoken or "").strip()
        piece = f"- {hit.title}: {spoken or hit.snippet[:320]}"
        if used + len(piece) + 1 > budget:
            remain = budget - used - 1
            if remain > 40:
                lines.append(piece[:remain].rstrip() + "...")
            break
        lines.append(piece)
        used += len(piece) + 1
    if len(lines) == 1:
        return ""
    text = "\n".join(lines)
    return text[:budget]


def best_document(message: str, *, workspace: str | None = None):
    retrieval = retrieve_knowledge(message, workspace=workspace, limit=1)
    if not retrieval.hits:
        return None, retrieval
    return get_document(retrieval.hits[0].doc_id), retrieval
