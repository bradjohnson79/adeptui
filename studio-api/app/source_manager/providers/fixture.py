from __future__ import annotations

import os

from ..contracts import (
    ArtifactQueryContext,
    DownloadPlan,
    InstallContext,
    ParsedSource,
    ProviderDetectionResult,
    SourceArtifact,
    SourceInput,
    VerificationContext,
    VerifiedSource,
)
from .base import stub_download_plan


class FixtureProvider:
    """E2E / deterministic fixture pack provider surface."""

    id = "fixture"
    display_name = "Fixture Provider"
    priority = 5

    def capabilities(self) -> list[str]:
        return ["fixture_http", "deterministic", "e2e"]

    def supports_resume(self) -> bool:
        return False

    def _enabled(self) -> bool:
        e2e = os.environ.get("STUDIO_E2E", "").strip().lower() in {"1", "true", "yes"}
        provider = os.environ.get("ADEPT_PACK_PROVIDER", "").strip().lower()
        # Opt-in for Source Manager visibility without enabling full STUDIO_E2E mocks.
        surface = os.environ.get("ADEPT_ENABLE_FIXTURE_PROVIDER", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        return e2e or provider == "fixture_http" or surface

    def detect(self) -> ProviderDetectionResult:
        enabled = self._enabled()
        base = os.environ.get("ADEPT_PACK_FIXTURE_BASE_URL") or "http://127.0.0.1:8765"
        e2e = os.environ.get("STUDIO_E2E", "").strip().lower() in {"1", "true", "yes"}
        provider = os.environ.get("ADEPT_PACK_PROVIDER", "").strip().lower()
        return ProviderDetectionResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready" if enabled else "Unavailable",
            available=enabled,
            capabilities=self.capabilities(),
            priority=self.priority,
            message=(
                f"Fixture HTTP pack provider at {base}."
                if enabled
                else (
                    "Fixture Provider is for deterministic E2E pack installs. "
                    "Enable with ADEPT_PACK_PROVIDER=fixture_http (plus a fixture server), "
                    "or ADEPT_ENABLE_FIXTURE_PROVIDER=1 for Source Manager visibility. "
                    "Do not enable on production Beta when using real GitHub/HF downloads."
                )
            ),
            diagnostics={
                "baseUrl": base,
                "e2e": e2e,
                "packProvider": provider or None,
                "enabled": enabled,
            },
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        url = (source_input.url or "").strip() or os.environ.get("ADEPT_PACK_FIXTURE_BASE_URL") or ""
        return ParsedSource(
            provider=self.id,
            source_type="fixture",
            source_url=url,
            metadata={"fixture": True},
        )

    def verify_source(self, source: ParsedSource, context: VerificationContext) -> VerifiedSource:
        if not self._enabled():
            return VerifiedSource(
                parsed=source,
                ok=False,
                verification_status="failed",
                blocking_errors=[
                    {"code": "fixture_disabled", "message": "Fixture provider is not enabled."}
                ],
                message="Fixture provider unavailable.",
            )
        return VerifiedSource(
            parsed=source,
            ok=True,
            verification_status="verified",
            files=[
                {
                    "name": "pack.zip",
                    "path": "pack.zip",
                    "kind": "pack",
                    "size": None,
                }
            ],
            message="Fixture source accepted for deterministic installs.",
            raw={"component_id": context.component_id},
        )

    def list_artifacts(
        self, source: VerifiedSource, context: ArtifactQueryContext
    ) -> list[SourceArtifact]:
        return [
            SourceArtifact(
                name="pack.zip",
                path="pack.zip",
                kind="pack",
                classification="pack",
                confidence=0.95,
                recommended=True,
                required=True,
            )
        ]

    def create_download_plan(
        self,
        source: VerifiedSource,
        selected_artifacts: list[SourceArtifact],
        context: InstallContext,
    ) -> DownloadPlan:
        return stub_download_plan(self.id, source, selected_artifacts, context)
