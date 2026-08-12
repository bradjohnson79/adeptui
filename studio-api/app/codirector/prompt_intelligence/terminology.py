"""Terminology protection — placeholder swap during enhancement."""

from __future__ import annotations

import re
from typing import Iterable

from .errors import LOCKED_TERM_CORRUPTED, PromptIntelligenceError

_PLACEHOLDER = "⟦LOCK_{i}⟧"


def collect_locked_terms(
    prompt: str,
    *,
    explicit: Iterable[str] | None = None,
    character_names: Iterable[str] | None = None,
) -> list[str]:
    terms: list[str] = []
    for group in (explicit or [], character_names or []):
        for t in group:
            s = (t or "").strip()
            if s and s not in terms:
                terms.append(s)

    # Quoted dialogue / locked phrases
    for m in re.finditer(r'"([^"\n]{1,120})"|\'([^\'\n]{1,120})\'', prompt or ""):
        q = (m.group(1) or m.group(2) or "").strip()
        if q and q not in terms:
            terms.append(q)

    # Asset-like tokens and LoRA triggers (word_word, <lora:...>, @ref)
    for m in re.finditer(r"(?:<lora:[^>]+>|@[A-Za-z0-9_\-]+|[A-Za-z]+_[A-Za-z0-9_\-]+)", prompt or ""):
        tok = m.group(0)
        if tok not in terms:
            terms.append(tok)

    # Sort longest-first so nested replacements stay stable
    terms.sort(key=len, reverse=True)
    return terms


def protect(text: str, terms: list[str]) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    out = text or ""
    for i, term in enumerate(terms):
        if not term or term not in out:
            continue
        token = _PLACEHOLDER.format(i=i)
        mapping[token] = term
        out = out.replace(term, token)
    return out, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    out = text or ""
    for token, term in mapping.items():
        if token not in out:
            raise PromptIntelligenceError(
                LOCKED_TERM_CORRUPTED,
                f"Locked term placeholder was lost during enhancement: {term}",
                details={"term": term, "placeholder": token},
                recoverable=True,
                recommended_action="fallback_english_only",
            )
        out = out.replace(token, term)
    # Ensure no leftover placeholders
    leftovers = re.findall(r"⟦LOCK_\d+⟧", out)
    if leftovers:
        raise PromptIntelligenceError(
            LOCKED_TERM_CORRUPTED,
            "Unresolved locked-term placeholders remain in the prompt.",
            details={"placeholders": leftovers},
            recoverable=True,
            recommended_action="fallback_english_only",
        )
    return out
