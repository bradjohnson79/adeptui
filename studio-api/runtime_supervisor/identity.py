"""Port identity: healthy | starting | free | phantom | unrelated."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .constants import API_PORT
from .health import studio_api_healthy
from .ports import port_owner_pid
from .process import is_studio_api_command, process_alive, process_command_line

PortKind = Literal["healthy", "starting", "free", "phantom", "unrelated"]


@dataclass(frozen=True)
class PortState:
    state: PortKind
    pid: int | None = None
    cmd: str = ""


def classify_listener(
    *,
    owner_pid: int | None,
    alive: bool,
    healthy: bool,
    cmd: str,
    is_ours: bool,
) -> PortState:
    if not owner_pid:
        return PortState("free")
    if not alive:
        return PortState("phantom", pid=owner_pid, cmd=cmd)
    if healthy:
        return PortState("healthy", pid=owner_pid, cmd=cmd)
    if is_ours:
        return PortState("starting", pid=owner_pid, cmd=cmd)
    return PortState("unrelated", pid=owner_pid, cmd=cmd)


def classify_api_port(
    port: int = API_PORT,
    *,
    owner_fn: Callable[[int], int | None] = port_owner_pid,
    alive_fn: Callable[[int | None], bool] = process_alive,
    healthy_fn: Callable[[], bool] = studio_api_healthy,
    cmd_fn: Callable[[int], str] = process_command_line,
) -> PortState:
    owner = owner_fn(port)
    if not owner:
        return PortState("free")
    cmd = cmd_fn(owner) if alive_fn(owner) else ""
    return classify_listener(
        owner_pid=owner,
        alive=alive_fn(owner),
        healthy=healthy_fn(),
        cmd=cmd,
        is_ours=is_studio_api_command(cmd),
    )
