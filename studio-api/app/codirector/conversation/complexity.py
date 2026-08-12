"""Request complexity classification and context budgets for Co-Director."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CoDirectorRequestComplexity = Literal[
    "TINY",
    "SMALL",
    "MEDIUM",
    "LARGE",
    "DEEP_RESEARCH",
    "PRODUCTION_EXECUTION",
]


@dataclass(frozen=True)
class ContextBudget:
    complexity: CoDirectorRequestComplexity
    max_retrieval_sources: int
    max_context_tokens: int
    max_retrieval_latency_ms: int
    allow_full_wiki_scan: bool
    allow_bible_scan: bool
    allow_timeline_scan: bool
    allow_library_scan: bool
    allow_specialists: bool
    allow_web_research: bool
    background_documentation: bool


_BUDGETS: dict[CoDirectorRequestComplexity, ContextBudget] = {
    # Tight token ceilings: ordinary TTFT is dominated by model prefill, not Core.
    "TINY": ContextBudget("TINY", 2, 1400, 500, False, False, False, False, False, False, True),
    "SMALL": ContextBudget("SMALL", 4, 2800, 1000, False, False, False, False, False, False, True),
    "MEDIUM": ContextBudget("MEDIUM", 8, 8000, 2000, False, True, False, False, False, False, True),
    "LARGE": ContextBudget("LARGE", 12, 16000, 8000, True, True, True, False, True, False, True),
    "DEEP_RESEARCH": ContextBudget(
        "DEEP_RESEARCH", 16, 24000, 30000, True, True, True, True, True, True, True
    ),
    "PRODUCTION_EXECUTION": ContextBudget(
        "PRODUCTION_EXECUTION", 6, 6000, 3000, False, False, False, True, False, False, True
    ),
}


def classify_request_complexity(user_message: str, *, mode: str = "chat") -> CoDirectorRequestComplexity:
    text = (user_message or "").strip()
    lower = text.lower()
    words = len(text.split())
    if re.search(r"\b(research|compare|look up|similar works)\b", lower):
        return "DEEP_RESEARCH"
    if re.search(r"\b(generate|render|queue|comfy|lipsync|approve draft)\b", lower):
        return "PRODUCTION_EXECUTION"
    if re.search(r"\b(whole project|entire season|assess the season|review everything)\b", lower):
        return "LARGE"
    if re.search(
        r"\b(i(?:'|’)ve filled in how i(?:'|’)d like us to work|call me |skip the setup|"
        r"rename|what did i call|make this line)\b",
        lower,
    ):
        return "TINY"
    if words < 40 or re.search(r"\b(help me improve|does this character|listen first)\b", lower):
        return "SMALL"
    if words > 180:
        return "MEDIUM"
    return "SMALL"


def budget_for(complexity: CoDirectorRequestComplexity) -> ContextBudget:
    return _BUDGETS[complexity]
