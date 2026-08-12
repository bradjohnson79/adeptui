"""English structural language module — usually already represented by refined English."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain, LanguageBalance


class EnglishLanguageModule:
    language_id = "en"
    status = "active"

    def enhance(
        self,
        intent: PromptIntent,
        *,
        domain: GenerationDomain,
        balance: LanguageBalance,
    ) -> str:
        # English structure lives in refinedEnglishPrompt; module returns empty enhancement.
        return ""
