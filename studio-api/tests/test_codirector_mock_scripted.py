"""Scripted mode for the mock Co-Director provider (test-only infrastructure).

Covers: script install/match/emit, follow-up turn behavior, no-match fallthrough,
invalid script rejection, and e2e-router endpoint gating when e2e is disabled.
The scripted mode is unreachable when e2e is disabled and the mock provider
remains non-selectable in production config (the c2 allowMockProvider guard).
"""

from __future__ import annotations

import asyncio
import json

import pytest


def _clear():
    from app.codirector.providers.mock import clear_scripted_steps

    clear_scripted_steps()


@pytest.fixture(autouse=True)
def _clean_script():
    _clear()
    yield
    _clear()


def _req(content: str, *, request_id: str = "r1", follow_up: str | None = None):
    from app.codirector.providers.base import ChatRequest

    messages = [{"role": "user", "content": content}]
    if follow_up is not None:
        messages.append({"role": "assistant", "content": "(requesting a lookup)"})
        messages.append({"role": "user", "content": follow_up})
    return ChatRequest(request_id=request_id, messages=messages, model_id=None)


def _generate(request) -> str:
    from app.codirector.providers.mock import MockCoDirectorProvider

    provider = MockCoDirectorProvider()
    result = asyncio.run(provider.generate(request))
    return result.reply


# ---------------------------------------------------------------------------
# Install / match / emit
# ---------------------------------------------------------------------------


def test_scripted_step_emits_reply_and_tool_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps(
        [
            {
                "match": r"how many scenes",
                "reply": "[scripted] Let me check the scene list.",
                "tool": {"toolId": "list_scenes", "arguments": {"limit": 10}},
            }
        ]
    )
    reply = _generate(_req("how many scenes are there?"))
    assert "[scripted] Let me check the scene list." in reply
    assert "```tool" in reply
    fence = reply.split("```tool\n", 1)[1].split("\n```", 1)[0]
    parsed = json.loads(fence)
    assert parsed["toolId"] == "list_scenes"
    assert parsed["arguments"] == {"limit": 10}
    # read_tool_call is the default response type when omitted.
    assert parsed["responseType"] == "read_tool_call"


def test_scripted_step_respects_explicit_response_type(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps(
        [
            {
                "match": r"add a scene",
                "tool": {
                    "toolId": "create_scene",
                    "arguments": {"name": "Rooftop"},
                    "responseType": "mutation_proposal",
                },
            }
        ]
    )
    reply = _generate(_req("add a scene please"))
    fence = reply.split("```tool\n", 1)[1].split("\n```", 1)[0]
    parsed = json.loads(fence)
    assert parsed["responseType"] == "mutation_proposal"
    assert parsed["toolId"] == "create_scene"


def test_scripted_first_match_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps(
        [
            {"match": r"scene", "reply": "[scripted-first]"},
            {"match": r"how many", "reply": "[scripted-second]"},
        ]
    )
    reply = _generate(_req("how many scenes?"))
    assert "[scripted-first]" in reply
    assert "[scripted-second]" not in reply


# ---------------------------------------------------------------------------
# Follow-up turn behavior
# ---------------------------------------------------------------------------


def test_scripted_follow_up_emits_follow_up_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps(
        [
            {
                "match": r"how many scenes",
                "reply": "[scripted] checking.",
                "tool": {"toolId": "list_scenes", "arguments": {}},
                "followUpReply": "[scripted] There are three scenes ready to shoot.",
            }
        ]
    )
    reply = _generate(
        _req("how many scenes?", follow_up="Tool result for list_scenes: ...")
    )
    assert "[scripted] There are three scenes ready to shoot." in reply
    assert "```tool" not in reply


def test_scripted_follow_up_without_follow_up_reply_is_neutral(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps(
        [
            {
                "match": r"how many scenes",
                "reply": "[scripted] checking.",
                "tool": {"toolId": "list_scenes", "arguments": {}},
            }
        ]
    )
    reply = _generate(
        _req("how many scenes?", follow_up="Tool result for list_scenes: ...")
    )
    assert "```tool" not in reply
    assert "Noted" in reply


# ---------------------------------------------------------------------------
# No-match fallthrough + missing script
# ---------------------------------------------------------------------------


def test_scripted_no_match_falls_through_to_default_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps([{"match": r"never-matches-this", "reply": "[scripted]"}])
    reply = _generate(_req("hello there"))
    assert "[scripted]" not in reply
    assert "[mock]" in reply


def test_scripted_scenario_without_script_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    reply = _generate(_req("hello there"))
    assert "```tool" not in reply
    assert "[mock]" in reply


def test_clear_scripted_steps_removes_script(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.providers.mock import clear_scripted_steps, set_scripted_steps

    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    set_scripted_steps([{"match": r"hi", "reply": "[scripted]"}])
    clear_scripted_steps()
    reply = _generate(_req("hi"))
    assert "[scripted]" not in reply
    assert "[mock]" in reply


# ---------------------------------------------------------------------------
# Invalid script rejection
# ---------------------------------------------------------------------------


def test_set_scripted_steps_rejects_non_list() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError):
        set_scripted_steps({"match": "x"})  # type: ignore[arg-type]


def test_set_scripted_steps_rejects_missing_match() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError, match="match"):
        set_scripted_steps([{"reply": "no match field"}])


def test_set_scripted_steps_rejects_bad_regex() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError, match="regex"):
        set_scripted_steps([{"match": "(unclosed"}])


def test_set_scripted_steps_rejects_tool_without_tool_id() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError, match="toolId"):
        set_scripted_steps([{"match": "x", "tool": {"arguments": {}}}])


def test_set_scripted_steps_rejects_tool_arguments_not_dict() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError, match="arguments"):
        set_scripted_steps([{"match": "x", "tool": {"toolId": "t", "arguments": "nope"}}])


def test_set_scripted_steps_rejects_non_string_reply() -> None:
    from app.codirector.providers.mock import ScriptValidationError, set_scripted_steps

    with pytest.raises(ScriptValidationError, match="reply"):
        set_scripted_steps([{"match": "x", "reply": 123}])


def test_set_scripted_steps_empty_list_clears_and_returns_zero() -> None:
    from app.codirector.providers.mock import get_scripted_steps, set_scripted_steps

    assert set_scripted_steps([]) == 0
    assert get_scripted_steps() == []


def test_set_scripted_steps_returns_count() -> None:
    from app.codirector.providers.mock import set_scripted_steps

    count = set_scripted_steps(
        [
            {"match": "a", "reply": "1"},
            {"match": "b", "reply": "2"},
        ]
    )
    assert count == 2


# ---------------------------------------------------------------------------
# e2e router endpoint gating (tested by calling the route functions directly)
# ---------------------------------------------------------------------------
# The e2e router is included by app.main only when STUDIO_E2E is set at import
# time, which the test session does not do (it would flip the default provider
# to mock). The route functions are plain callables, so we exercise the gating
# logic directly — the same `e2e_enabled()` guard the scenario endpoint uses.

@pytest.fixture()
def _e2e_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    yield
    from app.codirector.providers.mock import clear_scripted_steps

    clear_scripted_steps()


@pytest.fixture()
def _e2e_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    yield
    from app.codirector.providers.mock import clear_scripted_steps

    clear_scripted_steps()


def _install(body, monkeypatch):
    from app.routers.e2e import e2e_codirector_script

    return e2e_codirector_script(body)


def _delete(monkeypatch):
    from app.routers.e2e import e2e_codirector_script_delete

    return e2e_codirector_script_delete()


def test_script_endpoint_unavailable_when_e2e_disabled(_e2e_off) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _install({"steps": [{"match": "x", "reply": "y"}]}, _e2e_off)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        _delete(_e2e_off)
    assert exc.value.status_code == 404


def test_script_endpoint_install_and_clear_when_e2e_enabled(_e2e_on) -> None:
    res = _install(
        {"steps": [{"match": r"how many", "reply": "[scripted]", "tool": {"toolId": "list_scenes", "arguments": {}}}]},
        _e2e_on,
    )
    assert res["installed"] == 1
    assert len(res["steps"]) == 1

    cleared = _install({"steps": []}, _e2e_on)
    assert cleared["installed"] == 0
    assert cleared["steps"] == []


def test_script_endpoint_delete_clears_when_e2e_enabled(_e2e_on) -> None:
    _install({"steps": [{"match": "x", "reply": "y"}]}, _e2e_on)
    res = _delete(_e2e_on)
    assert res["installed"] == 0


def test_script_endpoint_empty_body_clears_when_e2e_enabled(_e2e_on) -> None:
    _install({"steps": [{"match": "x", "reply": "y"}]}, _e2e_on)
    res = _install({}, _e2e_on)
    assert res["installed"] == 0


def test_script_endpoint_rejects_invalid_script_with_400(_e2e_on) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _install({"steps": [{"match": "(unclosed"}]}, _e2e_on)
    assert exc.value.status_code == 400
    assert "regex" in exc.value.detail


def test_script_endpoint_rejects_non_list_steps_with_400(_e2e_on) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _install({"steps": {"not": "a list"}}, _e2e_on)
    assert exc.value.status_code == 400


def test_script_endpoint_install_drives_provider_generate(_e2e_on, monkeypatch) -> None:
    """An installed script drives the mock provider's generate() output."""
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")
    _install(
        {
            "steps": [
                {
                    "match": r"how many scenes",
                    "reply": "[scripted] checking.",
                    "tool": {"toolId": "list_scenes", "arguments": {"limit": 5}},
                }
            ]
        },
        _e2e_on,
    )
    reply = _generate(_req("how many scenes?"))
    assert "[scripted] checking." in reply
    assert "```tool" in reply
    fence = reply.split("```tool\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(fence)["toolId"] == "list_scenes"
