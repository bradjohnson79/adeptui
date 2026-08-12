"""Permissioned research / comparative intelligence (no silent fetch)."""

from __future__ import annotations

from .schemas import CreativeComparison, ResearchNote, ResearchPermission


def research_allowed(permission: str, *, user_authorized: bool = False) -> tuple[bool, str]:
    mode = (permission or "ASK_FIRST").upper()
    if mode == ResearchPermission.OFFLINE.value:
        return False, "Research is offline unless you change the preference."
    if mode == ResearchPermission.ASK_FIRST.value and not user_authorized:
        return False, "Research requires your go-ahead first."
    if mode in {ResearchPermission.WHEN_USEFUL.value, ResearchPermission.ACTIVE.value, ResearchPermission.ASK_FIRST.value}:
        if mode == ResearchPermission.ASK_FIRST.value and user_authorized:
            return True, "Authorized"
        if mode != ResearchPermission.ASK_FIRST.value:
            return True, "Permission allows research"
    return False, "Research not permitted"


def build_comparative_note(
    *,
    project_id: str,
    project_snippet: str,
    user_authorized: bool,
    permission: str,
) -> tuple[ResearchNote | None, CreativeComparison | None, str]:
    ok, reason = research_allowed(permission, user_authorized=user_authorized)
    if not ok:
        return None, None, reason

    # Controlled, sourced-style synthesis without live web in unit path.
    # Live cert may authorize; we still produce structured notes with explicit source placeholders.
    comparison = CreativeComparison(
        reference_title="Comparable intimate-mythic narratives (general class)",
        reference_type="FILM",
        comparison_dimensions=["tone", "scale of consequence", "visual tactility"],
        relevant_similarities=[
            "Intimate human stakes set against a larger consequence",
            "Sensory, place-bound atmosphere",
        ],
        critical_differences=[
            "Your project’s specific entity/event language remains distinct",
            "Local continuity rules (what the world must never do) are project-owned",
        ],
        useful_lessons=["Protect the sensory rules early so production does not sand them down"],
        risks_of_over_similarity=["Borrowing pacing tropes that flatten the intimate register"],
        project_distinctiveness=[(project_snippet or "")[:180] or "Creator-specific hooks from narration"],
        source_ids=["research:class-comparables:v1"],
        confidence=0.45,
    )
    note = ResearchNote(
        project_id=project_id,
        title="Creative comparison notes",
        category="CREATIVE_COMPARABLES",
        summary=(
            "Comparison framed as class-level references with explicit differences. "
            "Not proof of imitation."
        ),
        project_relevance="Helps clarify originality while keeping creator voice primary.",
        key_findings=comparison.critical_differences + comparison.project_distinctiveness[:1],
        source_ids=comparison.source_ids,
        status="DRAFT",
    )
    return note, comparison, "OK"
