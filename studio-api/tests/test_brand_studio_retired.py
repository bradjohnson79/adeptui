"""Brand Studio is retired from Adept UI v1.1 — no live catalog, tool, or runner."""

from __future__ import annotations

from app.codirector.tools.definitions import TOOL_IDS
from app.codirector.tools.registry import _MUTATION_HANDLERS, find as find_codirector_tool
from app.generation_tools.catalog import TOOL_CATALOG, get_tool
from app.generation_tools import ops
from app.generation_tools.retired import (
    BRAND_STUDIO_RETIREMENT_MESSAGE,
    RETIRED_CODIRECTOR_TOOL_IDS,
    is_retired_generation_tool,
)


def test_brand_studio_absent_from_generation_catalog():
    ids = [tool["id"] for tool in TOOL_CATALOG]
    assert "brand.studio" not in ids
    assert get_tool("brand.studio") is None


def test_brand_studio_codirector_tool_unregistered():
    assert "propose_brand_generate" in RETIRED_CODIRECTOR_TOOL_IDS
    assert "propose_brand_generate" not in TOOL_IDS
    assert find_codirector_tool("propose_brand_generate") is None
    assert "propose_brand_generate" not in _MUTATION_HANDLERS


def test_brand_generate_op_removed_from_live_ops():
    assert not hasattr(ops, "run_brand_generate")


def test_retired_generation_tool_run_is_gone(client):
    project = client.post("/api/projects", json={"name": "Brand Studio Retirement"}).json()
    run = client.post(
        f"/api/projects/{project['id']}/generation-tools/run",
        json={"toolId": "brand.studio", "prompt": "should not generate"},
    )
    assert run.status_code == 410, run.text
    detail = run.json().get("detail") or {}
    assert detail.get("status") == "RETIRED"
    assert detail.get("toolId") == "brand.studio"
    assert "v1.2" in (detail.get("message") or BRAND_STUDIO_RETIREMENT_MESSAGE)


def test_retired_generation_tool_status_is_gone(client):
    status = client.get("/api/generation-tools/brand.studio/status")
    assert status.status_code == 410, status.text
    assert is_retired_generation_tool("brand.studio")
