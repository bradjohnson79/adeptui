"""Marketing strategy — emerges from strengths; never forced on personal projects."""

from __future__ import annotations

from .destination import destination_strategy_notes
from .schemas import MarketingStrategyProfile, PartnershipProjectBundle, ProjectDestination


def update_marketing(
    bundle: PartnershipProjectBundle,
    *,
    user_message: str,
    intrigue_hooks: list[str] | None = None,
) -> MarketingStrategyProfile:
    vision = bundle.vision
    m = bundle.marketing
    m.project_id = bundle.journey.project_id

    if vision.primary_destination == ProjectDestination.PERSONAL:
        m.forced = False
        m.status = "EMERGING"
        m.positioning_statement = "Personal project — marketing optional, not pushed."
        m.campaign_phases = []
        m.platform_strategies = []
        return m

    hooks = list(intrigue_hooks or [])
    for h in hooks[:5]:
        if h not in m.key_hooks:
            m.key_hooks.append(h)
    if vision.intended_audience:
        m.audience_segments = list(dict.fromkeys(m.audience_segments + vision.intended_audience))[:8]

    notes = destination_strategy_notes(vision)
    m.platform_strategies = notes
    if vision.primary_destination == ProjectDestination.YOUTUBE:
        m.promotional_content_ideas = [
            "Trailer/teaser cut for retention",
            "Thumbnail concepts from the central image",
            "Community post series from production diary",
        ]
        m.calls_to_action = ["Watch", "Subscribe for next episode", "Join community discussion"]
    elif vision.primary_destination == ProjectDestination.FILM_FESTIVALS:
        m.brand_assets_needed = ["Poster", "Stills", "Synopsis variants", "Director statement"]
        m.promotional_content_ideas = ["Festival one-sheet", "Press kit draft"]
    elif vision.primary_destination in {
        ProjectDestination.PRODUCER_PITCH,
        ProjectDestination.NETWORK_PITCH,
    }:
        m.brand_assets_needed = ["Pitch deck outline", "Lookbook", "Pilot/treatment"]
        m.differentiation_points = m.key_hooks[:3]

    msg = (user_message or "").lower()
    if any(k in msg for k in ("marketing", "launch", "promote", "trailer", "poster")):
        m.status = "DRAFT"
        if not m.positioning_statement and m.key_hooks:
            m.positioning_statement = f"Position around: {m.key_hooks[0][:120]}"
    elif m.key_hooks:
        m.status = "EMERGING"

    m.forced = False
    bundle.marketing = m
    return m


def marketing_guidance(m: MarketingStrategyProfile, personal: bool) -> str:
    if personal:
        return "Personal destination: do not push marketing or commercial packaging."
    lines = ["Marketing guidance must come from project strengths, not clickbait."]
    if m.key_hooks:
        lines.append("Hooks: " + "; ".join(m.key_hooks[:3]))
    if m.platform_strategies:
        lines.append("Platform focus: " + "; ".join(m.platform_strategies[:3]))
    return "\n".join(lines)
