"""Deterministic tests for the Verified Operator channel (Co-Director 2.0 Mission A).

All tests use mocks — no real project, no real DB. Covers:
  - request registration
  - ack state transition
  - lazy timeout
  - late ack ignored
  - unknown request 404
  - premature success detection
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.codirector.operator.contracts import (
    OPERATOR_ACKNOWLEDGED,
    OPERATOR_REQUESTED,
    OPERATOR_TIMEOUT,
    OPERATOR_TIMEOUT_SEC,
    OperatorRecord,
)
from app.codirector.operator.service import (
    _elapsed_seconds,
    _fold_operator_state,
    _is_timed_out,
    _latest_operator_event,
    acknowledge_operator_request,
    get_operator_record,
    has_operator_ack,
    register_operator_request,
    resolve_operator_project,
)
from app.codirector.service import _operator_premature_success_claim


# ---------------------------------------------------------------------------
# 1. test_register_operator_request
# ---------------------------------------------------------------------------


def test_register_operator_request() -> None:
    db = MagicMock()

    result = register_operator_request(
        db,
        project_id="test",
        request_id="req1",
        tool_id="audio.open_studio",
        result={"ok": True, "uiAction": "open_audio_studio"},
        origin_session_id="tab_abc",
    )

    assert result["requestId"] == "req1"
    assert result["state"] == "pending"
    assert result["toolId"] == "audio.open_studio"
    assert result["originSessionId"] == "tab_abc"


# ---------------------------------------------------------------------------
# 2. test_has_operator_ack_true
# ---------------------------------------------------------------------------


def test_has_operator_ack_true() -> None:
    db = MagicMock()

    register_operator_request(
        db,
        project_id="test",
        request_id="req2",
        tool_id="audio.open_studio",
        result={"ok": True},
        origin_session_id="tab_abc",
    )

    with patch(
        "app.codirector.operator.service._latest_operator_event",
        return_value=MagicMock(event_type=OPERATOR_ACKNOWLEDGED),
    ):
        assert has_operator_ack(db, project_id="test", request_id="req2") is True


# ---------------------------------------------------------------------------
# 3. test_operator_timeout_lazy
# ---------------------------------------------------------------------------


def test_operator_timeout_lazy() -> None:
    db = MagicMock()

    register_operator_request(
        db,
        project_id="test",
        request_id="req3",
        tool_id="audio.open_studio",
        result={"ok": True},
        origin_session_id="tab_abc",
    )

    # Pending within timeout window — provide a recent created_at so it doesn't timeout
    import datetime

    recent = datetime.datetime.utcnow()
    mock_pending = MagicMock()
    mock_pending.event_type = OPERATOR_REQUESTED
    mock_pending.tool_id = "audio.open_studio"
    mock_pending.tool_result_json = '{"ok": true, "operator": {"originSessionId": "tab_abc"}}'
    mock_pending.created_at = recent

    with patch(
        "app.codirector.operator.service._latest_operator_event",
        return_value=mock_pending,
    ):
        rec = get_operator_record(db, project_id="test", request_id="req3")
        assert rec["state"] == "pending"

    # Timed out past OPERATOR_TIMEOUT_SEC
    fake_requested = MagicMock()
    fake_requested.event_type = OPERATOR_REQUESTED
    fake_requested.tool_id = "audio.open_studio"
    fake_requested.tool_result_json = '{"ok": true, "operator": {"originSessionId": "tab_abc"}}'
    fake_requested.created_at = datetime.datetime(2020, 1, 1)

    with patch(
        "app.codirector.operator.service._latest_operator_event",
        return_value=fake_requested,
    ):
        rec = get_operator_record(db, project_id="test", request_id="req3")
        assert rec["state"] == OPERATOR_TIMEOUT


# ---------------------------------------------------------------------------
# 4. test_operator_late_ack_ignored
# ---------------------------------------------------------------------------


def test_operator_late_ack_ignored() -> None:
    db = MagicMock()

    register_operator_request(
        db,
        project_id="test",
        request_id="req4",
        tool_id="audio.open_studio",
        result={"ok": True},
        origin_session_id="tab_abc",
    )

    # Force timed-out state for the ack check
    fake_requested = MagicMock()
    fake_requested.event_type = OPERATOR_REQUESTED
    fake_requested.tool_id = "audio.open_studio"
    fake_requested.tool_result_json = '{"ok": true, "operator": {"originSessionId": "tab_abc"}}'
    import datetime

    fake_requested.created_at = datetime.datetime(2020, 1, 1)

    with (
        patch(
            "app.codirector.operator.service._latest_operator_event",
            return_value=fake_requested,
        ),
        patch("app.codirector.operator.service.append_events"),
        patch(
            "app.codirector.operator.service._fold_operator_state",
            return_value="timeout",
        ),
    ):
        rec = acknowledge_operator_request(
            db,
            project_id="test",
            request_id="req4",
            origin_session_id="tab_abc",
            workspace="audio",
            target="studio",
            verified=True,
        )
        assert rec["state"] == "timeout"


# ---------------------------------------------------------------------------
# 5. test_operator_unknown_request_404
# ---------------------------------------------------------------------------


def test_operator_unknown_request_404() -> None:
    db = MagicMock()

    # Patch _latest_operator_event to return None (no matching event)
    with patch(
        "app.codirector.operator.service._latest_operator_event",
        return_value=None,
    ):
        rec = get_operator_record(db, project_id="nonexistent", request_id="no_such")
        assert rec["state"] == "unknown"
        assert rec["createdAt"] is None

    # resolve_operator_project with no matching events returns None
    # Patch the query result to simulate no matching row
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    project = resolve_operator_project(db, "no_such")
    assert project is None


# ---------------------------------------------------------------------------
# 6. test_operator_premature_success_detection
# ---------------------------------------------------------------------------


def test_operator_premature_success_detection() -> None:
    # No ack → premature claim detected for "opened the audio studio"
    premature, match = _operator_premature_success_claim(
        reply="opened the audio studio",
        executed_operator_tool_ids=["audio.open_studio"],
        has_ack=False,
    )
    assert premature is True
    assert match == "opened the audio studio"

    # With has_ack=True → no premature claim
    premature, match = _operator_premature_success_claim(
        reply="opened the audio studio",
        executed_operator_tool_ids=["audio.open_studio"],
        has_ack=True,
    )
    assert premature is False
    assert match is None

    # No matching tool → no premature claim
    premature, match = _operator_premature_success_claim(
        reply="opened the audio studio",
        executed_operator_tool_ids=["some.other_tool"],
        has_ack=False,
    )
    assert premature is False
    assert match is None

    # Voice pattern: "open the voice studio" matches voice_performance.open_workspace
    premature, match = _operator_premature_success_claim(
        reply="open the voice studio",
        executed_operator_tool_ids=["voice_performance.open_workspace"],
        has_ack=False,
    )
    assert premature is True
    assert match == "open the voice studio"

    # "focus the timeline" matches timeline.focus_ui
    premature, match = _operator_premature_success_claim(
        reply="focus the timeline",
        executed_operator_tool_ids=["timeline.focus_ui"],
        has_ack=False,
    )
    assert premature is True
    assert match == "focus the timeline"
