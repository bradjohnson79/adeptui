"""Language module interface."""

from __future__ import annotations

from typing import Protocol

from ..intent import PromptIntent
from ..models import GenerationDomain, LanguageBalance


class LanguageModule(Protocol):
    language_id: str
    status: str  # active | future | disabled

    def enhance(
        self,
        intent: PromptIntent,
        *,
        domain: GenerationDomain,
        balance: LanguageBalance,
    ) -> str: ...
