"""Execution write handlers must not run sync DB/pack work on the uvicorn loop."""

from __future__ import annotations

import asyncio
import inspect
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.codirector.execution.api import (
    advance_execution,
    approve_execution,
    cancel_execution_endpoint,
)
from app.codirector.execution.contracts import ExecutionStatus


def _assert_off_loop(seen: dict[str, object], loop_thread: int, fake_session: MagicMock) -> None:
    assert seen["thread"] != loop_thread
    assert seen["had_running_loop"] is False
    assert seen["db"] is fake_session
    fake_session.close.assert_called_once()


def test_approve_and_cancel_handlers_run_sync_work_off_event_loop() -> None:
    assert inspect.iscoroutinefunction(approve_execution)
    assert inspect.iscoroutinefunction(cancel_execution_endpoint)
    assert inspect.iscoroutinefunction(advance_execution)

    loop_thread = threading.get_ident()

    def _record(seen: dict[str, object], db: object) -> SimpleNamespace:
        seen["thread"] = threading.get_ident()
        try:
            asyncio.get_running_loop()
            seen["had_running_loop"] = True
        except RuntimeError:
            seen["had_running_loop"] = False
        seen["db"] = db
        return SimpleNamespace(
            status=ExecutionStatus.QUEUED,
            error=None,
            model_dump=lambda mode="json": {"status": "queued", "execution_id": "ex-1"},
        )

    # --- cancel: sync cancel_execution must run in a worker thread ---
    cancel_seen: dict[str, object] = {}
    cancel_session = MagicMock(name="cancel_session")

    def fake_cancel(db: object, project_id: str, execution_id: str) -> SimpleNamespace:
        assert project_id == "proj-write-pin"
        assert execution_id == "ex-cancel"
        return _record(cancel_seen, db)

    async def _invoke_cancel() -> dict:
        with (
            patch("app.codirector.execution.api.SessionLocal", return_value=cancel_session),
            patch("app.codirector.execution.api.cancel_execution", fake_cancel),
        ):
            return await cancel_execution_endpoint("proj-write-pin", "ex-cancel")

    cancel_result = asyncio.run(_invoke_cancel())
    assert cancel_result["execution_id"] == "ex-cancel" or cancel_result["status"] == "queued"
    _assert_off_loop(cancel_seen, loop_thread, cancel_session)

    # --- advance: sync advance_execution_pack must run in a worker thread ---
    advance_seen: dict[str, object] = {}
    advance_session = MagicMock(name="advance_session")

    def fake_advance(db: object, project_id: str, execution_id: str) -> SimpleNamespace:
        assert project_id == "proj-write-pin"
        assert execution_id == "ex-advance"
        return _record(advance_seen, db)

    async def _invoke_advance() -> dict:
        with (
            patch("app.codirector.execution.api.SessionLocal", return_value=advance_session),
            patch("app.codirector.execution.api.advance_execution_pack", fake_advance),
        ):
            return await advance_execution("proj-write-pin", "ex-advance")

    advance_result = asyncio.run(_invoke_advance())
    assert advance_result["status"] == "queued"
    _assert_off_loop(advance_seen, loop_thread, advance_session)

    # --- approve: approve_and_execute + SessionLocal must run off the request loop ---
    approve_seen: dict[str, object] = {}
    approve_session = MagicMock(name="approve_session")

    async def fake_approve(db: object, project_id: str, execution_id: str) -> SimpleNamespace:
        assert project_id == "proj-write-pin"
        assert execution_id == "ex-approve"
        return _record(approve_seen, db)

    async def _invoke_approve() -> dict:
        with (
            patch("app.codirector.execution.api.SessionLocal", return_value=approve_session),
            patch(
                "app.codirector.execution.dispatcher.approve_and_execute",
                fake_approve,
            ),
        ):
            return await approve_execution("proj-write-pin", "ex-approve")

    approve_result = asyncio.run(_invoke_approve())
    assert approve_result["status"] == "queued"
    # asyncio.run inside the worker thread installs a loop there; still not the request loop.
    assert approve_seen["thread"] != loop_thread
    assert approve_seen["db"] is approve_session
    approve_session.close.assert_called_once()
