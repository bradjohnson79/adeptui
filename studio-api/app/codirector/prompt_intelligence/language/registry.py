"""Language module registry — EN/ZH active; JA/KO/FR future stubs."""

from __future__ import annotations

from typing import Any

from .chinese import ChineseLanguageModule, _FutureLanguageModule
from .english import EnglishLanguageModule

_MODULES: dict[str, Any] = {
    "en": EnglishLanguageModule(),
    "zh": ChineseLanguageModule(),
    "ja": _FutureLanguageModule("ja"),
    "ko": _FutureLanguageModule("ko"),
    "fr": _FutureLanguageModule("fr"),
}


def get_language_module(language_id: str):
    return _MODULES.get((language_id or "").strip().lower())


def list_language_modules() -> list[dict[str, str]]:
    return [
        {"languageId": mid, "status": getattr(mod, "status", "unknown")}
        for mid, mod in _MODULES.items()
    ]
