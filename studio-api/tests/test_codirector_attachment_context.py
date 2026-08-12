"""Honest attachment + wiki context blocks for Co-Director chat."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.context_enrichment import attachment_context_block as _attachment_context_block


class _FakeDb:
    def __init__(self, assets: dict[str, object] | None = None):
        self._assets = assets or {}

    def get(self, model, key):  # noqa: ANN001
        return self._assets.get(key)


def test_attachment_context_does_not_claim_vision():
    asset = SimpleNamespace(
        id="asset-1",
        project_id="proj-1",
        kind="image",
        tag="Facility Ref",
        filename="facility.png",
        production_approval="none",
        validation_lifecycle="not_requested",
    )
    block = _attachment_context_block(
        _FakeDb({"asset-1": asset}),
        project_id="proj-1",
        attachment_ids=["asset-1"],
    )
    assert "Facility Ref" in block
    assert "not automatically run" in block.lower() or "were not performed" in block.lower() or "was not performed" in block.lower()
    assert "do not invent" in block.lower()


def test_attachment_context_rejects_cross_project():
    asset = SimpleNamespace(
        id="asset-1",
        project_id="other",
        kind="image",
        tag="Leak",
        filename="leak.png",
        production_approval="none",
        validation_lifecycle="not_requested",
    )
    block = _attachment_context_block(
        _FakeDb({"asset-1": asset}),
        project_id="proj-1",
        attachment_ids=["asset-1"],
    )
    assert "Leak" not in block
    assert "out-of-project" in block
