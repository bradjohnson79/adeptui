"""Versioned provider rate cards — historical usage retains the card version used."""

from __future__ import annotations

from typing import Any

RATE_CARD_VERSION = "adept.rate.1"

# Static estimates only — never present as exact charges.
RATE_CARDS: dict[str, dict[str, Any]] = {
    "fal": {
        "version": RATE_CARD_VERSION,
        "currency": "USD",
        "perUnit": {"image": 0.03, "video_sec": 0.08, "audio_sec": 0.01, "llm_1k_tokens": None},
        "source": "static_estimate",
    },
    "kie": {
        "version": RATE_CARD_VERSION,
        "currency": "USD",
        "perUnit": {"image": 0.02, "video_sec": 0.06, "audio_sec": 0.01, "llm_1k_tokens": 0.002},
        "source": "static_estimate",
    },
    "wavespeed": {
        "version": RATE_CARD_VERSION,
        "currency": "USD",
        "perUnit": {"image": 0.025, "video_sec": 0.07, "llm_1k_tokens": None},
        "source": "static_estimate",
    },
    "openai_compatible": {
        "version": RATE_CARD_VERSION,
        "currency": "USD",
        "perUnit": {"llm_1k_tokens": 0.01},
        "source": "static_estimate",
    },
}


def get_rate_card(provider_id: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    card = RATE_CARDS.get(pid) or {
        "version": RATE_CARD_VERSION,
        "currency": "USD",
        "perUnit": {},
        "source": "unknown",
    }
    return dict(card)


def estimate_cost(
    provider_id: str,
    *,
    capability: str,
    units: float,
) -> dict[str, Any]:
    card = get_rate_card(provider_id)
    per = card.get("perUnit") or {}
    key_map = {
        "image": "image",
        "video": "video_sec",
        "audio": "audio_sec",
        "llm": "llm_1k_tokens",
        "text": "llm_1k_tokens",
    }
    unit_key = key_map.get((capability or "").lower())
    rate = per.get(unit_key) if unit_key else None
    if rate is None:
        return {
            "estimatedCost": None,
            "currency": card.get("currency") or "USD",
            "pricingSource": "unknown",
            "rateCardVersion": card.get("version"),
            "disclaimer": "Pricing unknown — check provider billing. Estimate is not an exact charge.",
        }
    return {
        "estimatedCost": round(float(rate) * float(units), 6),
        "currency": card.get("currency") or "USD",
        "pricingSource": card.get("source") or "static_estimate",
        "rateCardVersion": card.get("version"),
        "unitRate": rate,
        "disclaimer": "Estimated cost — not an exact charge until confirmed by the provider.",
    }
