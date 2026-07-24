from __future__ import annotations

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
from .base import default_list_artifacts, parse_input, stub_download_plan, verify_via_download_sources


class DirectHttpProvider:
    id = "direct_http"
    display_name = "Direct URL"
    priority = 40

    def capabilities(self) -> list[str]:
        return ["parse_url", "verify_url", "list_artifacts", "https"]

    def supports_resume(self) -> bool:
        return False  # Range support arrives in Phase 1B after probe

    def detect(self) -> ProviderDetectionResult:
        return ProviderDetectionResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            available=True,
            capabilities=self.capabilities(),
            priority=self.priority,
            message="HTTPS direct downloads with SSRF protection.",
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        return parse_input(source_input)

    def verify_source(self, source: ParsedSource, context: VerificationContext) -> VerifiedSource:
        return verify_via_download_sources(source, context)

    def list_artifacts(
        self, source: VerifiedSource, context: ArtifactQueryContext
    ) -> list[SourceArtifact]:
        return default_list_artifacts(source, context)

    def create_download_plan(
        self,
        source: VerifiedSource,
        selected_artifacts: list[SourceArtifact],
        context: InstallContext,
    ) -> DownloadPlan:
        return stub_download_plan(self.id, source, selected_artifacts, context)
