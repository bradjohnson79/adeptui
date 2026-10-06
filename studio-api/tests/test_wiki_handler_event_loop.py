"""Wiki GET must not call build_project_wiki on the uvicorn event loop."""

from __future__ import annotations

import asyncio
import inspect
import threading
from unittest.mock import MagicMock, patch

from app.routers.codirector import get_project_wiki


def test_get_project_wiki_does_not_call_build_on_event_loop() -> None:
    assert inspect.iscoroutinefunction(get_project_wiki)

    loop_thread = threading.get_ident()
    seen: dict[str, object] = {}

    def fake_build(db: object, project_id: str) -> dict[str, object]:
        seen["thread"] = threading.get_ident()
        try:
            asyncio.get_running_loop()
            seen["had_running_loop"] = True
        except RuntimeError:
            seen["had_running_loop"] = False
        seen["project_id"] = project_id
        seen["db"] = db
        return {"projectId": project_id, "ok": True}

    fake_session = MagicMock(name="thread_session")

    async def _invoke() -> dict[str, object]:
        with (
            patch("app.routers.codirector.SessionLocal", return_value=fake_session),
            patch("app.codirector.wiki.build_project_wiki", fake_build),
        ):
            return await get_project_wiki("proj-hang-pin")

    result = asyncio.run(_invoke())
    assert result == {"projectId": "proj-hang-pin", "ok": True}
    assert seen["project_id"] == "proj-hang-pin"
    assert seen["thread"] != loop_thread
    assert seen["had_running_loop"] is False
    assert seen["db"] is fake_session
    fake_session.close.assert_called_once()
