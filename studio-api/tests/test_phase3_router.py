from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.codirector.routing.contracts import RouteActionClass
from app.codirector.routing.deterministic import classify_deterministic, NAVIGATION_TARGETS

_DEFAULT_WS = frozenset(NAVIGATION_TARGETS.values())


def test_navigate_script_writer():
    result = classify_deterministic("Open Script Writer.", available_workspaces=_DEFAULT_WS)
    assert result is not None
    assert result.actionClass == RouteActionClass.NAVIGATE
    assert result.target == "script_writer"
    assert result.writeAllowed is False


def test_navigate_indirect():
    result = classify_deterministic("Can you open up Script Writer for me?", available_workspaces=_DEFAULT_WS)
    assert result is not None
    assert result.actionClass == RouteActionClass.NAVIGATE
    assert result.writeAllowed is False


def test_discuss_korri_line():
    result = classify_deterministic("What do you think of Korri's final line?")
    assert result is not None
    assert result.actionClass == RouteActionClass.DISCUSS
    assert result.writeAllowed is False


def test_modify_knowledge_short_summary():
    result = classify_deterministic("Put this into the short summary.")
    assert result is not None
    assert result.actionClass == RouteActionClass.MODIFY_KNOWLEDGE
    assert result.writeAllowed is True


def test_stage_sensitive_script_create_shots():
    result = classify_deterministic("Create shots.", derived_stage="SCRIPT", available_workspaces=_DEFAULT_WS)
    assert result is None


def test_destructive_delete_batch():
    result = classify_deterministic("Delete Batch 3.")
    assert result is not None
    assert result.actionClass == RouteActionClass.EXECUTE_PRODUCTION
    assert result.destructive is True
    assert result.writeAllowed is True


def test_read_inspect():
    result = classify_deterministic("What batches do we have?")
    assert result is not None
    assert result.actionClass == RouteActionClass.READ_INSPECT
    assert result.writeAllowed is False


def test_approve_with_pending():
    result = classify_deterministic("Accept that.", pending_proposal_ids=["proposal-1"])
    assert result is not None
    assert result.actionClass == RouteActionClass.APPROVE
    assert result.target == "proposal-1"
    assert result.writeAllowed is True


def test_reject_with_pending():
    result = classify_deterministic("Keep what I wrote.", pending_proposal_ids=["proposal-2"])
    assert result is not None
    assert result.actionClass == RouteActionClass.REJECT
    assert result.target == "proposal-2"
    assert result.writeAllowed is True


def test_approve_no_pending_clarify():
    result = classify_deterministic("Accept that.")
    assert result is not None
    assert result.actionClass == RouteActionClass.CLARIFY
    assert result.writeAllowed is False


def test_negation_timeline():
    result = classify_deterministic("I don't want to open Timeline yet.")
    assert result is not None
    assert result.actionClass == RouteActionClass.DISCUSS
    assert result.writeAllowed is False


def test_false_positive_discuss_not_navigate():
    result = classify_deterministic("What do you think about using Script Writer for this?")
    assert result is not None
    assert result.actionClass == RouteActionClass.DISCUSS
    assert result.writeAllowed is False


def test_read_inspect_scenes():
    result = classify_deterministic("What scenes do we have?")
    assert result is not None
    assert result.actionClass == RouteActionClass.READ_INSPECT
    assert result.writeAllowed is False


def test_navigate_timeline():
    result = classify_deterministic("Show the timeline.", available_workspaces=_DEFAULT_WS)
    assert result is not None
    assert result.actionClass == RouteActionClass.NAVIGATE
    assert result.target == "timeline" or result.targetWorkspace == "timeline"


_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "codirector2_route_cases.json"


def _load_corpus() -> list[dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case", _load_corpus(), ids=lambda c: c["id"])
def test_route_corpus_comprehensive(case):
    kwargs = {}
    if case.get("pendingProposals"):
        kwargs["pending_proposal_ids"] = case["pendingProposals"]
    kwargs["available_workspaces"] = _DEFAULT_WS
    if case.get("stage"):
        kwargs["derived_stage"] = case["stage"]

    result = classify_deterministic(case["message"], **kwargs)

    if case.get("expectedReturnNone"):
        assert result is None, f"Expected None for {case['id']}, got {result}"
        return

    assert result is not None, f"Expected RouteDecision for {case['id']}, got None"
    assert result.actionClass == RouteActionClass(case["expectedActionClass"]), \
        f"{case['id']}: expected {case['expectedActionClass']}, got {result.actionClass}"
    assert result.writeAllowed is case["expectedWriteAllowed"], \
        f"{case['id']}: expected writeAllowed={case['expectedWriteAllowed']}, got {result.writeAllowed}"
    assert result.destructive is case.get("expectedDestructive", False), \
        f"{case['id']}: expected destructive={case.get('expectedDestructive', False)}, got {result.destructive}"

    if case.get("expectedTarget"):
        assert result.target == case["expectedTarget"], \
            f"{case['id']}: expected target={case['expectedTarget']}, got {result.target}"


@pytest.mark.parametrize("msg", [
    "What do you think of this?",
    "What do you think of the project?",
    "Show me the batches.",
    "List all scenes.",
    "What's in the wiki?",
])
def test_zero_write_for_non_mutating(msg):
    result = classify_deterministic(msg)
    assert result is not None
    assert result.writeAllowed is False
