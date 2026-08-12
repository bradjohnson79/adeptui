"""Phase 10 Tier B — Real-model narrative + music-video scenarios.

Uses the configured Ollama provider (qwen3.6:35b-a3b). Contrasts with
commercial workflow to prove format-awareness.
"""

from __future__ import annotations

import asyncio

import pytest

from app.codirector.providers.base import ChatRequest, ProviderHealthResult
from app.codirector.providers.ollama import OllamaProvider


@pytest.fixture(scope="module")
def provider():
    p = OllamaProvider(base_url="http://127.0.0.1:11434", default_model="qwen3.6:35b-a3b")
    try:

        async def _check():
            health = await p.health()
            return health.status == "Ready"

        ok = asyncio.run(_check())
        assert ok
    except Exception as e:
        pytest.skip(f"Provider not available: {e}")
    return p


def _generate(provider: OllamaProvider, system: str, user: str) -> str:
    """Synchronous wrapper around the async generate method."""
    import uuid

    req = ChatRequest(
        request_id=str(uuid.uuid4())[:8],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model_id="qwen3.6:35b-a3b",
    )

    async def _run():
        result = await provider.generate(req)
        return result.reply

    return asyncio.run(_run())


class TestRealNarrative:
    """Narrative scene — format-aware, not commercial assumptions."""

    def test_turn1_establish_narrative(self, provider):
        """Creator establishes a dramatic sci-fi scene."""
        user = "I want to write a dramatic scene where Captain Chen discovers a distress signal from a ship that vanished 20 years ago. She's alone on the bridge of the Aurora."
        response = _generate(
            provider,
            "You are Co-Director. The creator is starting a narrative/dramatic project. "
            "Respond professionally. Do not assume it's a commercial. "
            "Do not ask about runtime or format. Focus on the story being set up.",
            user,
        )
        assert response and len(response) > 30
        assert "commercial" not in response.lower()[:200], "Should not assume commercial format"

    def test_turn2_character_motivation(self, provider):
        """Ask about character motivation — discussion, zero action."""
        user = "What do you think drives Captain Chen to investigate the signal alone?"
        response = _generate(
            provider,
            "You are Co-Director. The creator is discussing a character's motivation. "
            "Give a thoughtful, specific answer. Do not suggest any production actions. "
            "Do not offer to open tools. Stay in discussion mode.",
            user,
        )
        assert response and len(response) > 30
        assert len(response.split()) > 15, "Response should be substantive"

    def test_turn3_script_readiness(self, provider):
        """Ask about shot readiness — workflow engine should assess contextually."""
        user = "Are we ready to start planning shots for this scene?"
        response = _generate(
            provider,
            "You are Co-Director. The creator has a narrative scene with a script draft established. "
            "They're asking about shot planning readiness. Give a grounded assessment based on what they've shared. "
            "Do not overpromise. If more story work is needed, say so professionally.",
            user,
        )
        assert response and len(response) > 30


class TestRealMusicVideo:
    """Music video — non-script-heavy workflow, no screenplay gate."""

    def test_turn1_establish_music_video(self, provider):
        """Creator establishes a music-video project."""
        user = "I'm working on a music video called 'Neon Drift'. It's a synthwave track and I want a cyberpunk visual style."
        response = _generate(
            provider,
            "You are Co-Director. The creator is starting a music-video project. "
            "Do NOT ask about a screenplay or script — music videos don't need one. "
            "Suggest appropriate next steps for music-video production.",
            user,
        )
        assert response and len(response) > 30
        lower = response.lower()[:300]
        assert "script" not in lower and "screenplay" not in lower, \
            "Should not ask about a script for a music video"

    def test_turn2_visual_focus(self, provider):
        """Creator chooses visual development first."""
        user = "Let's work on the look first — neon color palette and lighting."
        response = _generate(
            provider,
            "You are Co-Director. The creator wants to focus on visual development for their music video. "
            "Engage with their choice. Give specific visual/lighting suggestions appropriate for cyberpunk synthwave. "
            "Do not redirect to script or story development.",
            user,
        )
        assert response and len(response) > 30

    def test_turn3_performer_discussion(self, provider):
        """Discuss performer without a screenplay."""
        user = "The dancer should feel disconnected from the neon world. How do we convey that visually?"
        response = _generate(
            provider,
            "You are Co-Director. The creator is discussing a performer's visual treatment. "
            "Give specific performance/direction advice. Music videos work differently from narrative — "
            "don't apply screenplay logic.",
            user,
        )
        assert response and len(response) > 30
