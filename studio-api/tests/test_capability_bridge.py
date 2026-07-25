"""CoDirectorCapabilityBridge readiness against the PSR registry."""

from __future__ import annotations

import asyncio
import uuid

from app.codirector.tools.capability_bridge import CoDirectorCapabilityBridge, psr_ids_for_tool_key
from app.codirector.tools.capabilities import CapabilityAdapter
from app.db import Project, SessionLocal


def test_tool_key_maps_to_psr_ids() -> None:
    assert "comfyui.health" in psr_ids_for_tool_key("comfyui")
    assert "codirector.bible.read" in psr_ids_for_tool_key("bible")
    assert psr_ids_for_tool_key("not-a-key") == ()


def test_storyboard_tool_is_proposal_ready_when_comfy_blocked(client, monkeypatch) -> None:
    project_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Project(id=project_id, name="Bridge", engine_default="ltx"))
        db.commit()

    async def fake_get_capabilities(*, project_id=None, force=False):
        from app.capabilities.models import (
            CapabilityOut,
            CapabilitySnapshotOut,
            CapabilityStatus,
        )

        def cap(cid: str, status: CapabilityStatus, available: bool) -> CapabilityOut:
            return CapabilityOut(
                id=cid,
                displayName=cid,
                subsystem=cid.split(".")[0],
                status=status,
                available=available,
                configured=True,
                healthy=available,
                readOnly=True,
                requiresApproval=False,
                lastCheckedAt="2026-01-01T00:00:00Z",
            )

        caps = [
            cap("project.read", CapabilityStatus.LOCALLY_VERIFIED, True),
            cap("project.scenes.update", CapabilityStatus.LOCALLY_VERIFIED, True),
            cap("codirector.bible.propose", CapabilityStatus.LOCALLY_VERIFIED, True),
            cap("comfyui.health", CapabilityStatus.BLOCKED, False),
            cap("storyboard.generate", CapabilityStatus.BLOCKED, False),
        ]
        return CapabilitySnapshotOut(
            projectId=project_id,
            generatedAt="2026-01-01T00:00:00Z",
            correlationId="test",
            capabilities=caps,
            blockers=[],
            callable=[c.id for c in caps if c.available],
        )

    monkeypatch.setattr("app.capabilities.service.get_capabilities", fake_get_capabilities)

    with SessionLocal() as db:
        bridge = CoDirectorCapabilityBridge(db, project_id)
        readiness = asyncio.run(bridge.tool_readiness("propose_storyboard_generation"))
        assert readiness.status == "proposal_ready"
        assert readiness.proposalReady is True
        assert readiness.executionBlocked is True
        assert readiness.callable is False
        assert "comfyui.health" in readiness.missingCapabilities


def test_adapter_e2e_overrides_still_force_unavailable(client, monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "capability_blocked")
    project_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Project(id=project_id, name="E2E", engine_default="ltx"))
        db.commit()
        adapter = CapabilityAdapter(db, project_id)
        state = asyncio.run(adapter.state_for("comfyui"))
        assert state.available is False
        assert state.status == "unavailable"


def test_project_key_not_configured_without_project_id(client) -> None:
    with SessionLocal() as db:
        bridge = CoDirectorCapabilityBridge(db, None)
        state = asyncio.run(bridge.readiness_for_tool_key("project"))
        assert state["available"] is False
        assert state["configured"] is False
