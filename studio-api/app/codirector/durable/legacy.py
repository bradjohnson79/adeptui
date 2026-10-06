"""Retired Co-Director chat entries.

Calling one records the invocation and raises. It does not run a model,
select a tool, or write Master.
"""

from __future__ import annotations

from .journal import record_legacy


class LegacyRuntimeRetired(RuntimeError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Co-Director legacy entry '{name}' is retired. "
            "Chat runs only through the durable turn workflow."
        )


def refuse_legacy_chat(name: str) -> None:
    record_legacy(name)
    raise LegacyRuntimeRetired(name)
