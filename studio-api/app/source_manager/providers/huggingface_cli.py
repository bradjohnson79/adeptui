from __future__ import annotations

from ...setup.download_sources.cli_detect import detect_huggingface_cli
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


class HuggingFaceCliProvider:
    id = "huggingface_cli"
    display_name = "Hugging Face CLI"
    priority = 15

    def capabilities(self) -> list[str]:
        return ["parse_huggingface", "verify_huggingface", "list_artifacts", "auth"]

    def supports_resume(self) -> bool:
        return False

    def detect(self) -> ProviderDetectionResult:
        hf = detect_huggingface_cli()
        return ProviderDetectionResult(
            provider_id=self.id,
            display_name=self.display_name,
            status=hf.status,
            available=bool(hf.cli_detected),
            executable_path=hf.executable_path,
            version=hf.version,
            authenticated=bool(hf.authenticated),
            account_name=hf.account_name,
            token_available=bool(hf.token_available),
            capabilities=self.capabilities(),
            priority=self.priority,
            last_verified_at=hf.last_verified_at,
            message=hf.message or "",
            diagnostics=dict(hf.diagnostics or {}),
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        parsed = parse_input(source_input)
        if parsed.provider != "huggingface":
            raise ValueError("Hugging Face CLI provider only accepts Hugging Face URLs.")
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
