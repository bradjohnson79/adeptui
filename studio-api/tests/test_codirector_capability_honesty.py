"""Advertised Co-Director capabilities must reach a live handler or tool."""

from __future__ import annotations

import importlib
from pathlib import Path

from app.codirector.capabilities.registry import (
    HandlerKind,
    all_capabilities,
    capability_live_destination,
)
from app.codirector.tools import registry as tool_registry

_SERVICE = Path(__file__).resolve().parents[1] / "app" / "codirector" / "service.py"


def test_every_advertised_capability_has_a_live_destination() -> None:
    missing: list[str] = []
    for cap in all_capabilities():
        destination = capability_live_destination(cap)
        if not destination:
            missing.append(f"{cap.id}: no destination")
            continue
        if cap.handler_kind == HandlerKind.CAPABILITY_HANDLER:
            try:
                module = importlib.import_module(destination)
            except Exception as exc:
                missing.append(f"{cap.id}: handler import failed ({exc})")
                continue
            if not callable(getattr(module, "handle", None)):
                missing.append(f"{cap.id}: handler module has no handle()")
        elif cap.handler_kind == HandlerKind.TOOL:
            if tool_registry.find(destination) is None:
                missing.append(f"{cap.id}: tool '{destination}' is not registered")
    assert missing == [], "dead advertised capabilities:\n" + "\n".join(missing)


def test_script_time_binds_live_estimate_timing_tool() -> None:
    cap = next(c for c in all_capabilities() if c.id == "script.time")
    assert cap.handler_kind == HandlerKind.TOOL
    assert cap.tool_ids == ("script.estimate_timing",)
    assert capability_live_destination(cap) == "script.estimate_timing"
    assert tool_registry.find("script.estimate_timing") is not None
    assert tool_registry.find("script.timing") is None


def test_library_collection_aliases_are_not_advertised() -> None:
    ids = {cap.id for cap in all_capabilities()}
    assert "library.group" not in ids
    assert "library.assign" not in ids
    assert "library.save" in ids


def test_chat_and_stream_share_one_durable_turn() -> None:
    src = _SERVICE.read_text(encoding="utf-8")
    for name in ("async def chat_for_project", "async def stream_for_project", "async def _stream_for_project_inner"):
        assert name not in src
    router = (_SERVICE.parents[1] / "routers" / "codirector.py").read_text(encoding="utf-8")
    api = (_SERVICE.parents[1] / "routers" / "api.py").read_text(encoding="utf-8")
    assert router.count("begin_turn(") >= 2
    assert "begin_turn(" in api
    assert "from ..codirector.execution.dispatcher import" not in router
    assert "dispatch_execution(" not in router
