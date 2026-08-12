"""Load and query Creative Knowledge doctrine packs."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ..contracts import KnowledgeFrame, KnowledgePack
from .models import KnowledgeHit

_PACKS_RELATIVE_PATH = ("config", "codirector", "creative-knowledge")
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _tokenize(value: str) -> set[str]:
    return {_normalize_token(token) for token in _TOKEN_RE.findall(value.lower()) if token.strip()}


def _discover_packs_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent.joinpath(*_PACKS_RELATIVE_PATH)
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate config/codirector/creative-knowledge")


def _iter_pack_files() -> list[Path]:
    return sorted(_discover_packs_dir().glob("*.json"))


@lru_cache(maxsize=1)
def _load_pack_map() -> dict[str, KnowledgePack]:
    packs: dict[str, KnowledgePack] = {}
    for pack_file in _iter_pack_files():
        payload = json.loads(pack_file.read_text(encoding="utf-8"))
        pack_payloads = payload if isinstance(payload, list) else [payload]
        for pack_payload in pack_payloads:
            pack = KnowledgePack.model_validate(pack_payload)
            packs[pack.packId] = pack
    return packs


def list_pack_ids() -> list[str]:
    """Return all available creative knowledge pack ids."""

    return sorted(_load_pack_map().keys())


def get_knowledge_pack(pack_id: str) -> KnowledgePack | None:
    """Return a single knowledge pack by id."""

    return _load_pack_map().get(pack_id)


def _frame_search_blob(pack: KnowledgePack, frame: KnowledgeFrame) -> str:
    return " ".join(
        [
            pack.packId,
            pack.title,
            " ".join(pack.domainTags),
            frame.frameId,
            frame.title,
            frame.summary,
            " ".join(frame.tags),
            " ".join(frame.principles),
            " ".join(frame.patterns),
            " ".join(frame.antiPatterns),
            " ".join(frame.evidenceRefs),
        ]
    ).lower()


def query_knowledge(
    *,
    tags: list[str] | None = None,
    domain: str | None = None,
    intent: str | None = None,
    limit: int = 8,
) -> list[KnowledgeHit]:
    """Query knowledge frames by tags, domain, and optional intent text."""

    if limit <= 0:
        return []

    normalized_tags = {_normalize_token(tag) for tag in (tags or []) if tag.strip()}
    normalized_domain = _normalize_token(domain) if domain else None
    intent_terms = _tokenize(intent or "")

    ranked_hits: list[tuple[int, str, str, KnowledgeHit]] = []

    for pack in _load_pack_map().values():
        pack_domain_tags = {_normalize_token(tag) for tag in pack.domainTags}
        if normalized_domain and normalized_domain not in pack_domain_tags:
            continue

        for frame in pack.frames:
            frame_tags = {_normalize_token(tag) for tag in frame.tags}
            searchable_tags = frame_tags | pack_domain_tags | {_normalize_token(pack.packId)}

            score = 0

            if normalized_tags:
                tag_hits = normalized_tags & searchable_tags
                if not tag_hits:
                    continue
                score += len(tag_hits) * 10

            blob = _frame_search_blob(pack, frame)
            if intent_terms:
                matched_terms = {term for term in intent_terms if term in blob}
                if not matched_terms and not normalized_tags and not normalized_domain:
                    continue
                score += len(matched_terms) * 2

            if normalized_domain:
                score += 3

            ranked_hits.append((score, pack.packId, frame.frameId, KnowledgeHit(packId=pack.packId, frame=frame)))

    ranked_hits.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [hit for _, _, _, hit in ranked_hits[:limit]]


__all__ = ["get_knowledge_pack", "list_pack_ids", "query_knowledge"]
