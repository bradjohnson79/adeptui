"""Canonical locale registry (mirrors studio-web/src/i18n)."""

from __future__ import annotations

from typing import Any, Optional

LOCALE_REGISTRY: list[dict[str, Any]] = [
    {
        "locale": "en",
        "displayName": "English",
        "nativeName": "English",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "HUMAN_APPROVED",
        "dateLocale": "en",
        "numberLocale": "en",
    },
    {
        "locale": "fr",
        "displayName": "French",
        "nativeName": "Français",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "fr",
        "numberLocale": "fr",
    },
    {
        "locale": "es",
        "displayName": "Spanish",
        "nativeName": "Español",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "es",
        "numberLocale": "es",
    },
    {
        "locale": "ja",
        "displayName": "Japanese",
        "nativeName": "日本語",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "ja",
        "numberLocale": "ja",
    },
    {
        "locale": "zh-Hans",
        "displayName": "Chinese (Simplified)",
        "nativeName": "简体中文",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "zh-CN",
        "numberLocale": "zh-CN",
    },
    {
        "locale": "hi",
        "displayName": "Hindi",
        "nativeName": "हिन्दी",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "hi",
        "numberLocale": "hi",
    },
    {
        "locale": "ru",
        "displayName": "Russian",
        "nativeName": "Русский",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "ru",
        "numberLocale": "ru",
    },
    {
        "locale": "pt",
        "displayName": "Portuguese",
        "nativeName": "Português",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "pt-BR",
        "numberLocale": "pt-BR",
        "notes": "Brazilian Portuguese baseline for locale id pt",
    },
    {
        "locale": "ar",
        "displayName": "Arabic",
        "nativeName": "العربية",
        "direction": "rtl",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "ar",
        "numberLocale": "ar",
    },
    {
        "locale": "bn",
        "displayName": "Bengali",
        "nativeName": "বাংলা",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "bn",
        "numberLocale": "bn",
    },
    {
        "locale": "id",
        "displayName": "Indonesian",
        "nativeName": "Bahasa Indonesia",
        "direction": "ltr",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "id",
        "numberLocale": "id",
    },
    {
        "locale": "ur",
        "displayName": "Urdu",
        "nativeName": "اردو",
        "direction": "rtl",
        "fallback": "en",
        "enabled": True,
        "status": "ACTIVE",
        "reviewLevel": "MACHINE_DRAFT",
        "dateLocale": "ur",
        "numberLocale": "ur",
    },
]

SUPPORTED = {row["locale"] for row in LOCALE_REGISTRY}


def get_locale(locale: str) -> Optional[dict[str, Any]]:
    for row in LOCALE_REGISTRY:
        if row["locale"] == locale:
            return row
    return None


def is_supported_locale(locale: str) -> bool:
    return locale in SUPPORTED


def resolve_locale(candidate: Optional[str]) -> str:
    if not candidate:
        return "en"
    if candidate in SUPPORTED:
        return candidate
    lower = candidate.lower()
    if lower.startswith("zh") and "zh-Hans" in SUPPORTED:
        if "hant" in lower or "tw" in lower or "hk" in lower:
            return "en"
        return "zh-Hans"
    primary = lower.split("-")[0]
    if primary in SUPPORTED:
        return primary
    return "en"
