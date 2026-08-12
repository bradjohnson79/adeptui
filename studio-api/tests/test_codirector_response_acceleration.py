"""Unit/API coverage for Co-Director response acceleration (Waves 1–5)."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.conversation.circuit_breakers import is_open, record_failure, record_success, snapshot
from app.codirector.conversation.complexity import budget_for, classify_request_complexity
from app.codirector.conversation.next_steps import (
    build_next_step_options,
    option_to_prompt,
    persist_deferred_option,
    should_offer_options,
)


class _FakeDb:
    def __init__(self, project: SimpleNamespace):
        self.project = project

    def get(self, model, key):  # noqa: ANN001
        if key == self.project.id:
            return self.project
        return None

    def add(self, obj):  # noqa: ANN001
        self.project = obj

    def commit(self) -> None:
        return None


def test_complexity_tiny_onboarding_and_small_story():
    assert classify_request_complexity("I've filled in how I'd like us to work. Call me Brad.") == "TINY"
    assert budget_for("TINY").allow_specialists is False
    assert classify_request_complexity("Help me improve this character briefly.") == "SMALL"


def test_next_steps_continue_first_and_listen_suppress():
    assert (
        should_offer_options(
            user_message="just listen for now",
            primary_intent="invite_continuation",
            workflow_hold=True,
            listen_only=True,
        )
        is False
    )
    assert (
        should_offer_options(
            user_message=(
                "My series follows a young woman named Korri who discovers her testimony "
                "can rewrite flashbacks in a world where memory is evidence."
            ),
            primary_intent="invite_continuation",
            workflow_hold=False,
            listen_only=False,
        )
        is True
    )


def test_next_steps_treatment_requires_material_and_defers():
    # Production stores settings_json as a JSON string — engine must tolerate both.
    project = SimpleNamespace(id="proj-accel-1", settings_json="{}")
    db = _FakeDb(project)
    rich = (
        "The story is about Korri, a witness whose memories are used as evidence. "
        "Present-day testimony frames flashbacks. The conflict is the court rewriting "
        "her past against her will."
    )
    opts = build_next_step_options(
        db,
        project_id=project.id,
        user_message=rich,
        relationship_role="STORY_PARTNER",
        primary_intent="invite_continuation",
        wiki_candidate_count=2,
    )
    assert opts
    assert opts[0].type == "CONTINUE_STORY"
    assert len(opts) <= 4
    assert "telling the story" in option_to_prompt(opts[0]).lower()

    persist_deferred_option(db, project_id=project.id, option_type="BUILD_TREATMENT")
    opts2 = build_next_step_options(
        db,
        project_id=project.id,
        user_message=rich,
        relationship_role="STORY_PARTNER",
        primary_intent="invite_continuation",
        wiki_candidate_count=2,
    )
    assert all(o.type != "BUILD_TREATMENT" for o in opts2)


def test_circuit_breaker_opens_after_repeated_failures():
    source = "optional_wiki_scan_test"
    record_success(source)
    assert is_open(source) is False
    for _ in range(3):
        record_failure(source)
    assert is_open(source) is True
    snap = snapshot()
    assert source in snap["open"]
    record_success(source)
    assert is_open(source) is False


def test_ollama_provider_uses_true_stream_flag():
    import inspect

    from app.codirector.providers import ollama as ollama_mod

    src = inspect.getsource(ollama_mod.OllamaProvider.stream)
    assert '"stream": True' in src or "'stream': True" in src
    assert "keep_alive" in src


def test_compact_wiki_prefers_project_cache(monkeypatch):
    from app.codirector import context_enrichment as ce
    from app.codirector.conversation.project_cache import CompactEntitySummary, ProjectIntelligenceCache

    cache = ProjectIntelligenceCache(
        projectId="p1",
        projectSummary="A memory-as-evidence thriller.",
        developmentStage="discovery",
        characterIndex=[CompactEntitySummary(id="c1", name="Korri", kind="character")],
    )

    monkeypatch.setattr(ce, "load_project_cache", lambda db, pid: cache, raising=False)
    # Patch at import site used inside function
    import app.codirector.conversation.project_cache as pc

    monkeypatch.setattr(pc, "load_project_cache", lambda db, pid: cache)
    monkeypatch.setattr(pc, "warm_project_cache", lambda db, pid: cache)

    called = {"wiki": 0}

    def _boom(*_a, **_k):
        called["wiki"] += 1
        raise AssertionError("full wiki rebuild should not run when cache is warm")

    import app.codirector.wiki as wiki_mod

    monkeypatch.setattr(wiki_mod, "build_project_wiki", _boom)

    block = ce.compact_wiki_context(_FakeDb(SimpleNamespace(id="p1", settings_json={})), "p1")
    assert "Korri" in block
    assert "compact cache" in block.lower()
    assert called["wiki"] == 0
