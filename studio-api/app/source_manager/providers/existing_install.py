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
from .base import stub_download_plan
from .local_folder import LocalFolderProvider


class ExistingInstallProvider:
    """Treat an already-installed component location as a source (link / detect)."""

    id = "existing_install"
    display_name = "Existing Install"
    priority = 60

    def __init__(self) -> None:
        self._local = LocalFolderProvider()

    def capabilities(self) -> list[str]:
        return ["link_existing", "detect_installed", "list_artifacts"]

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
            message="Locate and link files already installed on disk.",
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        parsed = self._local.parse_source(source_input)
        parsed.provider = self.id
        parsed.source_type = "existing_install"
        return parsed

    def verify_source(self, source: ParsedSource, context: VerificationContext) -> VerifiedSource:
        verified = self._local.verify_source(source, context)
        verified.parsed.provider = self.id
        return verified

    def list_artifacts(
        self, source: VerifiedSource, context: ArtifactQueryContext
    ) -> list[SourceArtifact]:
        return self._local.list_artifacts(source, context)

    def create_download_plan(
        self,
        source: VerifiedSource,
        selected_artifacts: list[SourceArtifact],
        context: InstallContext,
    ) -> DownloadPlan:
        plan = stub_download_plan(self.id, source, selected_artifacts, context)
        plan.metadata["mode"] = "existing_install"
        return plan
