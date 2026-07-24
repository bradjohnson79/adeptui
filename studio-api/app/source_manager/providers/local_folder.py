from __future__ import annotations

from pathlib import Path

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


class LocalFolderProvider:
    id = "local_folder"
    display_name = "Local Folder"
    priority = 50

    def capabilities(self) -> list[str]:
        return ["local_path", "link_existing", "list_artifacts"]

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
            message="Link or inspect local folders without downloading.",
        )

    def parse_source(self, source_input: SourceInput) -> ParsedSource:
        path = (source_input.local_path or source_input.url or "").strip()
        if not path:
            raise ValueError("Local folder path is required.")
        return ParsedSource(
            provider=self.id,
            source_type="local_folder",
            source_url=path,
            metadata={"path": path},
        )

    def verify_source(self, source: ParsedSource, context: VerificationContext) -> VerifiedSource:
        path = Path(source.source_url)
        try:
            resolved = path.resolve()
        except OSError as exc:
            return VerifiedSource(
                parsed=source,
                ok=False,
                verification_status="failed",
                blocking_errors=[{"code": "path_error", "message": str(exc)}],
                message="Could not resolve local path.",
            )
        exists = resolved.exists()
        is_dir = resolved.is_dir() if exists else False
        files: list[dict] = []
        if is_dir:
            for child in list(resolved.iterdir())[:100]:
                if child.is_file():
                    files.append(
                        {
                            "name": child.name,
                            "path": child.name,
                            "size": child.stat().st_size,
                            "kind": "file",
                        }
                    )
        ok = exists and is_dir
        return VerifiedSource(
            parsed=source,
            ok=ok,
            verification_status="verified" if ok else "failed",
            files=files,
            blocking_errors=[]
            if ok
            else [{"code": "not_a_folder", "message": "Path must be an existing folder."}],
            message="Local folder verified." if ok else "Local folder is not usable.",
            raw={"resolved": str(resolved), "component_id": context.component_id},
        )

    def list_artifacts(
        self, source: VerifiedSource, context: ArtifactQueryContext
    ) -> list[SourceArtifact]:
        return [
            SourceArtifact(
                name=str(item.get("name")),
                path=str(item.get("path")),
                size=item.get("size"),
                kind=item.get("kind"),
                classification="unknown",
                confidence=0.2,
            )
            for item in source.files
            if isinstance(item, dict)
        ]

    def create_download_plan(
        self,
        source: VerifiedSource,
        selected_artifacts: list[SourceArtifact],
        context: InstallContext,
    ) -> DownloadPlan:
        plan = stub_download_plan(self.id, source, selected_artifacts, context)
        plan.metadata["mode"] = "link_existing"
        return plan
