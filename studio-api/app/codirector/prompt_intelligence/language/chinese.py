"""Selective Chinese semantic enhancement from intent — not full translation."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain, LanguageBalance

# Category → Chinese clause. Selected by intent, not pasted wholesale.
_CATEGORY_CLAUSES: dict[str, str] = {
    "micro_expression": "细腻的微表情",
    "breath": "自然呼吸",
    "eye": "轻微眼神变化",
    "performance": "真实的人物表演",
    "lighting": "柔和电影光影",
    "camera_motion": "稳定流畅的镜头运动",
    "environment": "细腻的环境动态",
    "body": "自然的身体动作",
    "emotion": "克制而深沉的情绪",
    "depth": "清晰的空间层次",
    "material": "真实的材质细节",
    "ambience": "沉浸式环境音",
    "sound_layers": "细腻的声音层次",
    "voice_tone": "温暖而克制的语气",
}


def _select_categories(intent: PromptIntent, domain: GenerationDomain) -> list[str]:
    cats: list[str] = []
    if domain in ("image", "video"):
        if intent.performance or intent.emotion or intent.subject:
            cats.append("micro_expression")
            cats.append("performance")
        if intent.lighting or domain in ("image", "video"):
            cats.append("lighting")
        if domain == "video":
            cats.append("camera_motion")
            cats.append("environment")
            cats.append("body")
        if intent.emotion:
            cats.append("emotion")
        cats.append("depth")
        if domain == "image":
            cats.append("material")
    if domain in ("audio", "music", "sfx"):
        cats.extend(["ambience", "sound_layers"])
    if domain == "voice":
        cats.extend(["breath", "voice_tone", "emotion"])
    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in cats:
        if c not in seen and c in _CATEGORY_CLAUSES:
            seen.add(c)
            out.append(c)
    return out


class ChineseLanguageModule:
    language_id = "zh"
    status = "active"

    def enhance(
        self,
        intent: PromptIntent,
        *,
        domain: GenerationDomain,
        balance: LanguageBalance,
    ) -> str:
        cats = _select_categories(intent, domain)
        if balance == "subtle":
            cats = cats[:2]
        elif balance == "balanced":
            cats = cats[:4]
        else:  # strong — still not a full translation dump
            cats = cats[:7]
        clauses = [_CATEGORY_CLAUSES[c] for c in cats]
        return "，".join(clauses)


class _FutureLanguageModule:
    def __init__(self, language_id: str):
        self.language_id = language_id
        self.status = "future"

    def enhance(
        self,
        intent: PromptIntent,
        *,
        domain: GenerationDomain,
        balance: LanguageBalance,
    ) -> str:
        return ""
