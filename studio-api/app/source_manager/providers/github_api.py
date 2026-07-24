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


class GitHubApiProvider:
    id = "github_api"
    display_name = "GitHub API"
    priority = 20

    def capabilities(self) -> list[str]:
        return ["parse_github", "verify_github", "list_artifacts", "public_releases"]

    def supports_resume(self) -> bool:
        return False

    def detect(self) -> ProviderDetectionResult:
        return ProviderDetectionResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            available=True,
            capabilities=self.capabilities(),
            priority=self.priority,
            message="Anonymous or token-backed GitHub Releases API (no token stored by Source Manager).",
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        parsed = parse_input(source_input)
        if parsed.provider != "github":
            raise ValueError("GitHub API provider only accepts GitHub URLs.")
        return parsed

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
