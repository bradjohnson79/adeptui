"""Flexible response plan — no fixed six-part template repetition."""

from __future__ import annotations

from app.codirector.conversation.response_composer import (
    build_response_plan,
    compose_reply,
    render_response_plan,
)
from app.codirector.conversation.schemas import (
    ConversationPlan,
    ProjectDirectorState,
    ProjectIntelligenceSnapshot,
)

_RICH_STORY = (
    "I'm developing a twelve-episode series about a lighthouse keeper who hears "
    "coordinates in the fog. The world rule is that every answered call costs a memory. "
    "Themes are identity and consequence. Characters include Mara Vale and Jonah Reed. "
    "The harbor itself behaves like a living archive of unfinished conversations."
)


def _snap() -> ProjectIntelligenceSnapshot:
    return ProjectIntelligenceSnapshot(projectId="proj-test", title="Harbor Fog")


def test_no_fixed_response_template_repetition():
    plan = ConversationPlan(primaryIntent="receive_information", responseMode="receive_information")
    shapes: list[str] = []
    texts: list[str] = []
    for i in range(6):
        rp = build_response_plan(plan, _snap(), ProjectDirectorState(), _RICH_STORY, turn_index=i)
        shapes.append(rp.shape)
        texts.append(render_response_plan(rp))
    # Structural variety across consecutive turns
    assert len(set(shapes)) >= 3
    # Not all replies share the same optional-block sequence
    with_obs = sum(1 for i in range(6) if build_response_plan(plan, _snap(), ProjectDirectorState(), _RICH_STORY, turn_index=i).observation)
    with_interp = sum(
        1 for i in range(6) if build_response_plan(plan, _snap(), ProjectDirectorState(), _RICH_STORY, turn_index=i).interpretation
    )
    assert with_obs >= 1
    assert with_interp >= 1
    # Verified wiki note only when wiki_verified=True
    unverified = build_response_plan(plan, _snap(), ProjectDirectorState(), _RICH_STORY, wiki_verified=False, turn_index=0)
    assert unverified.verified_wiki_note is None
    verified = build_response_plan(plan, _snap(), ProjectDirectorState(), _RICH_STORY, wiki_verified=True, turn_index=0)
    assert verified.verified_wiki_note


def test_composer_strips_jargon():
    plan = ConversationPlan(primaryIntent="receive_information")
    # Force a path that includes our stripper on rendered text
    text = compose_reply(plan, _snap(), ProjectDirectorState(), _RICH_STORY, turn_index=1)
    assert "grounding gate" not in text.lower()
    assert "token budget" not in text.lower()


def test_required_ack_and_relevant_always_present():
    plan = ConversationPlan(primaryIntent="invite_continuation", selectedQuestion="What happens next?")
    rp = build_response_plan(plan, _snap(), ProjectDirectorState(), "keep going", turn_index=0)
    assert rp.acknowledgement.strip()
    assert rp.relevant.strip()
