"""Phase 7 — runtime `allowed_context` allowlist enforcement in ContextCompiler.

Covers CODIRECTOR2_PHASE7 Section 4 (scoped-context contract):
- union-of-`allowed_context` allowlist across selected specialists
- forbidden-domain filter (FORBIDDEN_CONTEXT_CATEGORIES) always excluded
- `user.message` parity fact always present regardless of category
- backward-compatible empty-specialist fallback (all categories minus forbidden)
- per-specialist `filter_for_specialist` narrowing preserved
- diagnostics (`allowedCategories` / `forbiddenCategories`) prove allowlist applied
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.codirector.intelligence.context_compiler import (
    FORBIDDEN_CONTEXT_CATEGORIES,
    ContextCompiler,
)
from app.codirector.intelligence.schemas import ContextPackage
from app.codirector.intelligence.specialist_registry import SpecialistDefinition
from app.db import Project, SessionLocal, init_db


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    project = Project(id="proj-p7-ctx", name="Phase 7 Context Allowlist Project")
    session.merge(project)
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _specialist(
    specialist_id: str,
    *,
    allowed_context: tuple[str, ...],
) -> SpecialistDefinition:
    return SpecialistDefinition(
        id=specialist_id,
        prompt_id=specialist_id,
        display_name=specialist_id.replace("-", " ").title(),
        description=f"Test specialist {specialist_id}.",
        enabled=True,
        allowed_context=allowed_context,
        output_schema_id="specialist-finding-v1",
        may_propose_tools=False,
        may_execute_tools=False,
        default_priority=50,
        prompt_version="1.0.0",
    )


def _run_compile(
    db: Session,
    *,
    specialists: tuple[SpecialistDefinition, ...] = (),
    scene_id: str | None = None,
) -> ContextPackage:
    import asyncio

    return asyncio.run(
        ContextCompiler().compile(
            db,
            project_id="proj-p7-ctx",
            user_message="Shape the scene around Korri's emotional arc.",
            scene_id=scene_id,
            specialists=specialists,
        )
    )


def test_allowlist_excludes_unrelated_and_forbidden_categories(db: Session):
    crew = (
        _specialist("scene-master", allowed_context=("scene", "characters")),
        # Deliberate forbidden-category attempt: must never enter the package.
        _specialist("tool-leaker", allowed_context=("full_tool_registry",)),
    )
    package = _run_compile(db, specialists=crew)

    forbidden = set(FORBIDDEN_CONTEXT_CATEGORIES)
    fact_categories = {fact.category for fact in package.facts}
    fact_keys = {fact.key for fact in package.facts}

    # Not a single facts entry may carry a forbidden category.
    assert not (fact_categories & forbidden)
    # Unrelated allowed-domain categories are excluded (capabilities is never
    # in this crew's union, so no capabilities.snapshot is assembled).
    assert "capabilities" not in fact_categories
    assert "capabilities" not in package.capabilities.keys()
    # All facts belong to the crew's allowlist or are the parity user message.
    for fact in package.facts:
        assert fact.key == "user.message" or fact.category in {"scene", "characters"}
    # The always-on user.message parity fact survived an allowlist that does
    # not even include its own category.
    assert "user.message" in fact_keys


def test_forbidden_categories_are_filtered_from_allowed_labels(db: Session):
    crew = (
        _specialist(
            "scene-master",
            allowed_context=("scene", "full_tool_registry", "full_marketing_plan"),
        ),
    )
    package = _run_compile(db, specialists=crew)

    forbidden = set(FORBIDDEN_CONTEXT_CATEGORIES)
    diagnostics = package.diagnostics
    allowed_labels = set(diagnostics.get("allowedCategories", []))
    forbidden_labels = set(diagnostics.get("forbiddenCategories", []))

    # Forbidden categories are filtered from the allowlist labels ...
    assert not (allowed_labels & forbidden)
    # ... while they are reported as applied denials in diagnostics.
    assert forbidden.issubset(forbidden_labels)
    assert forbidden.issubset(set(package.omittedCategories))
    # And they never leak into the compiled facts.
    assert not ({fact.category for fact in package.facts} & forbidden)
    # Allowed labels reflect only what survived the filter.
    assert allowed_labels == {"scene"}


def test_user_message_parity_survives_tight_allowlist(db: Session):
    package = _run_compile(db, specialists=(_specialist("audio-only", allowed_context=("audio",)),))

    fact_keys = {fact.key for fact in package.facts}
    assert "user.message" in fact_keys
    assert package.userMessageDelimited.startswith("<<<USER_MESSAGE>>>")
    assert len(package.facts) >= 1
    # With an allowlist of {"audio"}, no project_overview facts are assembled
    # (the always-on user.message parity fact is the sole exception: it retains
    # category "project_overview" while remaining in the package).
    assert not any(
        fact.category == "project_overview" and fact.key != "user.message"
        for fact in package.facts
    )


def test_empty_specialists_falls_back_to_all_categories_minus_forbidden(db: Session):
    package = _run_compile(db, specialists=())

    forbidden = set(FORBIDDEN_CONTEXT_CATEGORIES)
    diagnostics = package.diagnostics
    allowed_labels = set(diagnostics.get("allowedCategories", []))

    # Backward compatibility: no specialists => all known categories (minus
    # forbidden) are allowed and facts are assembled from the full union.
    assert "capabilities" in allowed_labels
    assert "scene" in allowed_labels
    assert "characters" in allowed_labels
    assert not (allowed_labels & forbidden)
    assert diagnostics.get("forbiddenCategories") == []
    assert "capabilities" in {fact.category for fact in package.facts}
    assert "user.message" in {fact.key for fact in package.facts}


def test_filter_for_specialist_narrows_to_own_categories(db: Session):
    package = _run_compile(db, specialists=())
    audience = _specialist("story", allowed_context=("story",))
    scoped = ContextCompiler.filter_for_specialist(package, audience)

    assert isinstance(scoped, ContextPackage)
    assert len(scoped.facts) <= len(package.facts)
    for fact in scoped.facts:
        assert fact.key == "user.message" or fact.category == "story"
    assert not any(fact.category == "capabilities" for fact in scoped.facts)
    assert "user.message" in {fact.key for fact in scoped.facts}