"""Project GET/POST must not run _project_out on the uvicorn event loop."""

from __future__ import annotations

import asyncio
import inspect
import threading
from unittest.mock import MagicMock, patch

from app.routers.api import create_project, get_project, list_projects
from app.schemas import ProjectCreate


def _record_serialize(seen: dict[str, object], db: object, project: object) -> MagicMock:
    seen["thread"] = threading.get_ident()
    try:
        asyncio.get_running_loop()
        seen["had_running_loop"] = True
    except RuntimeError:
        seen["had_running_loop"] = False
    seen["db"] = db
    seen["project"] = project
    dummy = MagicMock(name="project_out")
    dummy.model_dump.side_effect = RuntimeError("skip redact")
    return dummy


def _assert_off_loop(seen: dict[str, object], loop_thread: int, fake_session: MagicMock) -> None:
    assert seen["thread"] != loop_thread
    assert seen["had_running_loop"] is False
    assert seen["db"] is fake_session
    fake_session.close.assert_called_once()


def test_get_project_does_not_serialize_on_event_loop() -> None:
    assert inspect.iscoroutinefunction(get_project)

    loop_thread = threading.get_ident()
    seen: dict[str, object] = {}
    fake_session = MagicMock(name="thread_session")
    fake_project = MagicMock(name="project")
    fake_project.id = "proj-schnick-pin"
    fake_session.get.return_value = fake_project

    def fake_project_out(db: object, project: object) -> MagicMock:
        return _record_serialize(seen, db, project)

    async def _invoke() -> object:
        with (
            patch("app.routers.api.SessionLocal", return_value=fake_session),
            patch("app.routers.api._project_out", fake_project_out),
        ):
            return await get_project("proj-schnick-pin", request=MagicMock(name="request"))

    result = asyncio.run(_invoke())
    assert seen["project"] is fake_project
    _assert_off_loop(seen, loop_thread, fake_session)
    assert result is not None


def test_list_projects_does_not_serialize_on_event_loop() -> None:
    assert inspect.iscoroutinefunction(list_projects)

    loop_thread = threading.get_ident()
    seen: dict[str, object] = {}
    fake_session = MagicMock(name="thread_session")
    fake_project = MagicMock(name="project")
    fake_project.id = "proj-list-pin"
    fake_project.archived = 0
    fake_session.query.return_value.order_by.return_value.all.return_value = [fake_project]

    def fake_project_out(db: object, project: object) -> MagicMock:
        return _record_serialize(seen, db, project)

    async def _invoke() -> object:
        with (
            patch("app.routers.api.SessionLocal", return_value=fake_session),
            patch("app.routers.api._project_out", fake_project_out),
        ):
            return await list_projects(request=MagicMock(name="request"))

    result = asyncio.run(_invoke())
    assert seen["project"] is fake_project
    _assert_off_loop(seen, loop_thread, fake_session)
    assert isinstance(result, list) and len(result) == 1


def test_create_project_does_not_serialize_on_event_loop() -> None:
    assert inspect.iscoroutinefunction(create_project)

    loop_thread = threading.get_ident()
    seen: dict[str, object] = {}
    fake_session = MagicMock(name="thread_session")

    def fake_project_out(db: object, project: object) -> MagicMock:
        return _record_serialize(seen, db, project)

    async def _invoke() -> object:
        with (
            patch("app.routers.api.SessionLocal", return_value=fake_session),
            patch("app.routers.api._project_out", fake_project_out),
            patch("app.feature_flags.feature_flags") as ff,
            patch("app.vram_profiles.detect_vram_gb", return_value=32),
            patch("app.vram_profiles.apply_profile_to_project"),
            patch("app.vram_profiles.normalize_vram_tier", return_value=32),
            patch("app.project_library.service.init_project_library"),
        ):
            ff.templates_presets_v1 = False
            return await create_project(ProjectCreate(name="pin-create"))

    result = asyncio.run(_invoke())
    assert seen["db"] is fake_session
    _assert_off_loop(seen, loop_thread, fake_session)
    assert result is not None
    fake_session.add.assert_called()
    fake_session.commit.assert_called_once()
