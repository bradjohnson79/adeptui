"""Living project brief — grows gently from conversation."""

from __future__ import annotations

from datetime import datetime, timezone

from .schemas import DiscoveryWikiCandidate, LivingProjectBrief, WikiCandidateCategory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_living_brief(
    brief: LivingProjectBrief,
    *,
    project_id: str,
    user_message: str,
    candidates: list[DiscoveryWikiCandidate],
) -> LivingProjectBrief:
    brief.project_id = project_id
    brief.updated_at = _now()
    fields = dict(brief.fields or {})

    if len(user_message or "") >= 80 and "premise" not in fields:
        fields["premise"] = (user_message or "")[:280]

    for c in candidates:
        if c.category == WikiCandidateCategory.CHARACTER and "main_characters" not in fields:
            fields["main_characters"] = c.title
        if c.category == WikiCandidateCategory.LOCATION and "setting" not in fields:
            fields["setting"] = c.title
        if c.category == WikiCandidateCategory.TONE and "tone" not in fields:
            fields["tone"] = c.content[:160]
        if c.category == WikiCandidateCategory.THEME and "themes" not in fields:
            fields["themes"] = c.content[:160]
        if c.category == WikiCandidateCategory.EVENT and "central_conflict" not in fields:
            fields["central_conflict"] = c.content[:200]
        if c.category == WikiCandidateCategory.WORLD_RULE and "world_rules" not in fields:
            fields["world_rules"] = c.content[:200]

    domains = [
        "project_identity",
        "format",
        "genre",
        "tone",
        "premise",
        "audience_experience",
        "main_characters",
        "central_conflict",
        "timeline",
        "world_rules",
        "visual_direction",
        "themes",
        "open_questions",
        "confirmed_decisions",
        "setting",
    ]
    brief.fields = fields
    filled = sum(1 for d in domains if fields.get(d))
    brief.confirmed_field_count = sum(
        1 for c in candidates if c.status == "CONFIRMED"
    ) + sum(1 for k in ("premise", "main_characters", "setting") if fields.get(k))
    brief.emerging_field_count = sum(1 for c in candidates if c.status in {"EMERGING", "INFERRED"})
    brief.unresolved_field_count = max(0, len(domains) - filled)
    brief.completeness = round(min(1.0, filled / max(1, len(domains))), 3)
    return brief
