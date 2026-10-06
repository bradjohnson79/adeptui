"""Brand Studio generate is retired — the live pin/lock runner must not exist."""

from __future__ import annotations

from app.generation_tools import ops
from app.generation_tools.retired import is_retired_generation_tool


def test_brand_generate_runner_retired() -> None:
    assert not hasattr(ops, "run_brand_generate")
    assert is_retired_generation_tool("brand.studio")
