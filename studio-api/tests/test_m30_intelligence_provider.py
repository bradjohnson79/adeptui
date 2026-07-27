"""M3.0 Completion Phase 8 - provider vs limited-analysis specialist digests.

No pytest-asyncio plugin: async calls use asyncio.run(...) from sync tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.codirector.intelligence.specialist_runner import (
    LIMITED_ANALYSIS_ASSUMPTION,
    LIMITED_ANALYSIS_MODE,
    SpecialistRunner,
    resolve_provider_for_specialists,
)
from app.codirector.providers.base import ChatRequest, ChatResult, ProviderHealthResult, ProviderModel
from app.db import Project, SessionLocal, init_db


class BriefAwareProvider:
    """Mock provider that echoes brief-specific content into specialist JSON."""

    id = "brief-aware"
    display_name = "Brief-Aware Mock"

    def __init__(self) -> None:
        self.endpoint = "mock://brief-aware"

    async def list_models(self) -> list[ProviderModel]:
        return [ProviderModel(id="brief-model", name="brief-model")]

    async def health(self) -> ProviderHealthResult:
        models = await self.list_models()
        return ProviderHealthResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            reachable=True,
            endpoint=self.endpoint,
            selected_model="brief-model",
            model_available=True,
            models=models,
            message="ready",
        )

    async def generate(self, request: ChatRequest) -> ChatResult:
        user = ""
        for message in reversed(request.messages):
            if message.get("role") == "user":
                user = message.get("content") or ""
                break
        token = "generic"
        lowered = user.lower()
        if "noir detective" in lowered or "rain-soaked alley" in lowered:
            token = "noir-alley-reconciliation"
        elif "orbital chase" in lowered or "neon drone" in lowered:
            token = "orbital-drone-chase"
        elif "User request:" in user:
            token = hashlib.sha1(user.encode("utf-8")).hexdigest()[:12]

        payload = {
            "specialistId": "director",
            "summary": f"Provider digest for {token}",
            "recommendation": f"Direct the scene around {token} with brief-specific blocking.",
            "requirements": [f"Lock references for {token}"],
            "risks": [],
            "blockingIssues": [],
            "optionalImprovements": [],
            "proposedToolActions": [],
            "productionBibleReferences": [],
            "assumptions": ["Live provider path exercised (mock)."],
            "confidence": 0.91,
        }
        reply = "```json\n" + json.dumps(payload) + "\n```"
        return ChatResult(
            request_id=request.request_id,
            reply=reply,
            model_id=request.model_id or "brief-model",
            provider_id=self.id,
        )

    def supports_stream(self) -> bool:
        return False

    def stream(self, request: ChatRequest):
        raise NotImplementedError


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    session.merge(Project(id="proj-m30-intel", name="M30 Intelligence"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _digest(findings: list[Any]) -> str:
    material = []
    for finding in findings:
        material.append(
            {
                "id": finding.specialistId,
                "summary": finding.summary,
                "recommendation": finding.recommendation,
                "requirements": list(finding.requirements or []),
                "assumptions": list(finding.assumptions or []),
            }
        )
    blob = json.dumps(material, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def test_two_briefs_non_identical_digests_with_provider(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    provider = BriefAwareProvider()
    runner = SpecialistRunner()
    brief_a = "Noir detective farewell in a rain-soaked alley after a quiet reconciliation."
    brief_b = "Neon drone orbital chase above a flooded megacity at midnight."

    async def _run():
        findings_a, errors_a = await runner.run_all(
            db,
            project_id="proj-m30-intel",
            user_message=brief_a,
            specialist_ids=["director"],
            provider=provider,
            model_id="brief-model",
            use_provider=True,
        )
        findings_b, errors_b = await runner.run_all(
            db,
            project_id="proj-m30-intel",
            user_message=brief_b,
            specialist_ids=["director"],
            provider=provider,
            model_id="brief-model",
            use_provider=True,
        )
        return findings_a, errors_a, findings_b, errors_b

    findings_a, errors_a, findings_b, errors_b = asyncio.run(_run())
    assert not errors_a and not errors_b
    assert findings_a and findings_b
    digest_a = _digest(findings_a)
    digest_b = _digest(findings_b)
    assert digest_a != digest_b
    assert "noir-alley-reconciliation" in findings_a[0].summary
    assert "orbital-drone-chase" in findings_b[0].summary
    assert "limited-analysis" not in (findings_a[0].assumptions or [""])[0].lower()


def test_use_provider_false_honesty_labels_limited(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    runner = SpecialistRunner()

    async def _run():
        return await runner.run_all(
            db,
            project_id="proj-m30-intel",
            user_message="Create a suspenseful laboratory scene with two scientists.",
            specialist_ids=["director", "cinematographer"],
            provider=BriefAwareProvider(),
            use_provider=False,
        )

    findings, errors = asyncio.run(_run())
    assert not errors
    assert findings
    for finding in findings:
        assert any(
            "limited-analysis" in (a or "").lower() or "heuristic" in (a or "").lower()
            for a in (finding.assumptions or [LIMITED_ANALYSIS_ASSUMPTION])
        )
        assert "limited-analysis" in (finding.summary or "").lower() or any(
            "limited" in (a or "").lower() for a in (finding.assumptions or [])
        )


def test_resolve_provider_e2e_forces_limited(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    provider, use_provider, mode = asyncio.run(
        resolve_provider_for_specialists(BriefAwareProvider())
    )
    assert provider is None
    assert use_provider is False
    assert mode == LIMITED_ANALYSIS_MODE


def test_resolve_provider_ready_enables_use(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    ready = BriefAwareProvider()
    provider, use_provider, mode = asyncio.run(resolve_provider_for_specialists(ready))
    assert provider is ready
    assert use_provider is True
    assert mode == "provider"
