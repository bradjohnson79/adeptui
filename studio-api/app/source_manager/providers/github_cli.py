from __future__ import annotations

from ...setup.download_sources.cli_detect import detect_github_cli
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


class GitHubCliProvider:
    id = "github_cli"
    display_name = "GitHub CLI"
    priority = 10

    def capabilities(self) -> list[str]:
        return ["parse_github", "verify_github", "list_artifacts", "private_repos", "auth"]

    def supports_resume(self) -> bool:
        return False  # Phase 1A — resume arrives with CLI download pipeline

    def detect(self) -> ProviderDetectionResult:
        gh = detect_github_cli()
        return ProviderDetectionResult(
            provider_id=self.id,
            display_name=self.display_name,
            status=gh.status,
            available=bool(gh.cli_detected),
            executable_path=gh.executable_path,
            version=gh.version,
            authenticated=bool(gh.authenticated),
            account_name=gh.account_name,
            token_available=bool(gh.token_available),
            capabilities=self.capabilities(),
            priority=self.priority,
            last_verified_at=gh.last_verified_at,
            message=gh.message or "",
            diagnostics=dict(gh.diagnostics or {}),
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        parsed = parse_input(source_input)
        if parsed.provider != "github":
            raise ValueError("GitHub CLI provider only accepts GitHub URLs.")
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
        return stub_download_plan(self.id, source, selected_artifacts, context, supports_resume=False)
