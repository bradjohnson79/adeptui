"""Shared helpers for Phase 1A providers."""

from __future__ import annotations

import uuid
from typing import Any

from ...setup.download_sources.service import verify_source_url
from ...setup.download_sources.url_parse import parse_source_url
from ..contracts import (
    ArtifactQueryContext,
    DownloadPlan,
    InstallContext,
    ParsedSource,
    SourceArtifact,
    SourceInput,
    VerificationContext,
    VerifiedSource,
)


def parsed_from_url(url: str, *, revision: str | None = None, asset_name: str | None = None) -> ParsedSource:
    normalized = parse_source_url(url)
    if revision:
        if normalized.provider == "huggingface":
            normalized.revision = revision
        else:
            normalized.release_tag = revision
    if asset_name:
        normalized.asset_name = asset_name
    return ParsedSource(
        provider=normalized.provider,
        source_type=normalized.kind,
        source_url=normalized.source_url,
        owner=normalized.owner,
        repository=normalized.repository,
        revision=normalized.revision or normalized.release_tag or normalized.branch,
        branch=normalized.branch,
        commit=None,
        asset_path=normalized.asset_name or normalized.file_path,
        repository_type=None,
        authentication_required=False,
        metadata=normalized.to_dict(),
    )


def verify_via_download_sources(
    source: ParsedSource,
    context: VerificationContext,
) -> VerifiedSource:
    result = verify_source_url(
        url=source.source_url,
        component_id=context.component_id,
        revision=source.revision,
        asset_name=source.asset_path,
    )
    return VerifiedSource(
        parsed=source,
        ok=bool(result.get("ok")),
        verification_status="verified" if result.get("ok") else "failed",
        verification_fingerprint=result.get("verification_fingerprint"),
        files=list(result.get("files") or []),
        warnings=list(result.get("warnings") or []),
        blocking_errors=list(result.get("blocking_errors") or []),
        authentication_required=bool(result.get("authentication_required")),
        size=result.get("size"),
        installation_method=result.get("installation_method"),
        message=str(result.get("message") or ""),
        raw=result,
    )


def artifacts_from_verified(verified: VerifiedSource) -> list[SourceArtifact]:
    artifacts: list[SourceArtifact] = []
    for item in verified.files:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("path") or "file")
        path = str(item.get("path") or name)
        artifacts.append(
            SourceArtifact(
                name=name,
                path=path,
                size=item.get("size"),
                kind=item.get("kind"),
                download_url=item.get("download_url"),
                classification=str(item.get("kind") or "unknown"),
                confidence=0.5 if item.get("kind") else 0.1,
                recommended=True,
            )
        )
    return artifacts


def stub_download_plan(
    provider_id: str,
    verified: VerifiedSource,
    selected: list[SourceArtifact],
    context: InstallContext,
    *,
    supports_resume: bool = False,
) -> DownloadPlan:
    total = 0
    known = False
    for artifact in selected:
        if artifact.size is not None:
            total += int(artifact.size)
            known = True
    return DownloadPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        provider_id=provider_id,
        source_id=None,
        component_id=context.component_id,
        artifacts=list(selected),
        total_bytes=total if known else None,
        destination=context.destination,
        supports_resume=supports_resume,
        authentication_required=verified.authentication_required,
        metadata={"phase": "1A", "execution": "deferred_to_pack_install"},
    )


def parse_input(source_input: SourceInput) -> ParsedSource:
    if source_input.local_path:
        path = source_input.local_path
        return ParsedSource(
            provider="local_folder",
            source_type="local_folder",
            source_url=path,
            asset_path=None,
            metadata={"path": path},
        )
    if not source_input.url:
        raise ValueError("Source URL or local path is required.")
    return parsed_from_url(
        source_input.url,
        revision=source_input.revision,
        asset_name=source_input.asset_name,
    )


def default_list_artifacts(
    verified: VerifiedSource, _context: ArtifactQueryContext
) -> list[SourceArtifact]:
    return artifacts_from_verified(verified)


def provider_meta(detection: dict[str, Any] | None) -> dict[str, Any]:
    return dict(detection or {})
