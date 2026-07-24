"""Provider-neutral Source Manager contracts (Phase 1A)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ProviderDetectionResult:
    provider_id: str
    display_name: str
    status: str
    available: bool
    executable_path: str | None = None
    version: str | None = None
    authenticated: bool = False
    account_name: str | None = None
    token_available: bool = False
    capabilities: list[str] = field(default_factory=list)
    priority: int = 100
    last_verified_at: str | None = None
    message: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.provider_id,
            "displayName": self.display_name,
            "status": self.status,
            "available": self.available,
            "executablePath": self.executable_path,
            "version": self.version,
            "authenticated": self.authenticated,
            "accountName": self.account_name,
            "tokenAvailable": self.token_available,
            "capabilities": list(self.capabilities),
            "priority": self.priority,
            "lastVerifiedAt": self.last_verified_at,
            "message": self.message,
            "diagnostics": dict(self.diagnostics),
        }


@dataclass
class SourceInput:
    url: str | None = None
    local_path: str | None = None
    provider_hint: str | None = None
    revision: str | None = None
    asset_name: str | None = None
    selected_files: list[str] | None = None
    component_id: str | None = None


@dataclass
class ParsedSource:
    provider: str
    source_type: str
    source_url: str
    owner: str | None = None
    repository: str | None = None
    revision: str | None = None
    branch: str | None = None
    commit: str | None = None
    asset_path: str | None = None
    repository_type: str | None = None
    authentication_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "sourceType": self.source_type,
            "sourceUrl": self.source_url,
            "owner": self.owner,
            "repository": self.repository,
            "revision": self.revision,
            "branch": self.branch,
            "commit": self.commit,
            "assetPath": self.asset_path,
            "repositoryType": self.repository_type,
            "authenticationRequired": self.authentication_required,
            "metadata": dict(self.metadata),
        }


@dataclass
class VerificationContext:
    component_id: str | None = None
    require_pack_asset: bool = False


@dataclass
class VerifiedSource:
    parsed: ParsedSource
    ok: bool
    verification_status: str
    verification_fingerprint: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_errors: list[dict[str, Any]] = field(default_factory=list)
    authentication_required: bool = False
    size: int | None = None
    installation_method: str | None = None
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceArtifact:
    name: str
    path: str
    size: int | None = None
    kind: str | None = None
    download_url: str | None = None
    classification: str = "unknown"
    confidence: float = 0.0
    required: bool = False
    recommended: bool = False
    destination: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "kind": self.kind,
            "downloadUrl": self.download_url,
            "classification": self.classification,
            "confidence": self.confidence,
            "required": self.required,
            "recommended": self.recommended,
            "destination": self.destination,
        }


@dataclass
class ArtifactQueryContext:
    component_id: str | None = None
    include_optional: bool = True


@dataclass
class InstallContext:
    component_id: str
    destination: str | None = None


@dataclass
class DownloadPlan:
    plan_id: str
    provider_id: str
    source_id: str | None
    component_id: str
    artifacts: list[SourceArtifact]
    total_bytes: int | None = None
    staging_dir: str | None = None
    destination: str | None = None
    supports_resume: bool = False
    authentication_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "providerId": self.provider_id,
            "sourceId": self.source_id,
            "componentId": self.component_id,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "totalBytes": self.total_bytes,
            "stagingDir": self.staging_dir,
            "destination": self.destination,
            "supportsResume": self.supports_resume,
            "authenticationRequired": self.authentication_required,
            "metadata": dict(self.metadata),
        }


@dataclass
class OperationContext:
    operation_id: str
    component_id: str


@dataclass
class DownloadResult:
    ok: bool
    phase: str
    message: str = ""
    files: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None


@dataclass
class AuthenticationRequest:
    provider_id: str
    method: str | None = None


@dataclass
class AuthenticationResult:
    ok: bool
    message: str
    command: list[str] | None = None
    command_summary: str | None = None
    requires_confirmation: bool = True


@runtime_checkable
class SourceProvider(Protocol):
    id: str
    display_name: str
    priority: int

    def detect(self) -> ProviderDetectionResult: ...

    def parse_source(self, source_input: SourceInput) -> ParsedSource: ...

    def verify_source(
        self, source: ParsedSource, context: VerificationContext
    ) -> VerifiedSource: ...

    def list_artifacts(
        self, source: VerifiedSource, context: ArtifactQueryContext
    ) -> list[SourceArtifact]: ...

    def create_download_plan(
        self,
        source: VerifiedSource,
        selected_artifacts: list[SourceArtifact],
        context: InstallContext,
    ) -> DownloadPlan: ...

    def supports_resume(self) -> bool: ...

    def capabilities(self) -> list[str]: ...
