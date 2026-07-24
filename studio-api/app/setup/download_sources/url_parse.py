"""Parse GitHub and Hugging Face URLs into normalized source descriptors."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import unquote, urlparse

from .security import SourceSecurityError, validate_remote_url

_GH_RELEASE_ASSET = re.compile(
    r"^/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)$"
)
_GH_RELEASE_TAG = re.compile(r"^/([^/]+)/([^/]+)/releases/tag/([^/]+)/?$")
_GH_RELEASES = re.compile(r"^/([^/]+)/([^/]+)/releases/?$")
_GH_ARCHIVE_HEAD = re.compile(r"^/([^/]+)/([^/]+)/archive/refs/heads/(.+?)(?:\.zip|\.tar\.gz)?$")
_GH_ARCHIVE_TAG = re.compile(r"^/([^/]+)/([^/]+)/archive/refs/tags/(.+?)(?:\.zip|\.tar\.gz)?$")
_GH_REPO = re.compile(r"^/([^/]+)/([^/]+)/?$")

_HF_RESOLVE = re.compile(r"^/([^/]+)/([^/]+)/resolve/([^/]+)/(.+)$")
_HF_BLOB = re.compile(r"^/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")
_HF_TREE = re.compile(r"^/([^/]+)/([^/]+)/tree/([^/]+)/?$")
_HF_REPO = re.compile(r"^/([^/]+)/([^/]+)/?$")
_HF_SCHEME = re.compile(r"^hf://([^/@]+)(?:/([^@]+))?(?:@([^/]+))?(?:/(.+))?$")


@dataclass
class NormalizedSource:
    provider: str
    source_url: str
    owner: str | None = None
    repository: str | None = None
    repository_id: str | None = None
    repository_type: str | None = None
    release_tag: str | None = None
    branch: str | None = None
    revision: str | None = None
    asset_name: str | None = None
    file_path: str | None = None
    archive_type: str | None = None
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    authentication_required: bool = False
    expected_component_type: str | None = None
    resolved_download_url: str | None = None
    kind: str = "unknown"  # release_asset | release | repo | branch_archive | tag_archive | hf_repo | hf_file

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_source_url(url: str) -> NormalizedSource:
    raw = (url or "").strip()
    if raw.lower().startswith("hf://"):
        return _parse_hf_scheme(raw)

    raw = validate_remote_url(raw)
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    path = unquote(parsed.path or "")

    if host in {"github.com", "www.github.com"}:
        return _parse_github(raw, path)
    if host in {"huggingface.co", "www.huggingface.co", "hf.co"}:
        return _parse_huggingface(raw, path)

    raise SourceSecurityError("provider_unrecognized", "URL is not a supported GitHub or Hugging Face source.")


def _parse_github(raw: str, path: str) -> NormalizedSource:
    m = _GH_RELEASE_ASSET.match(path)
    if m:
        owner, repo, tag, asset = m.groups()
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            release_tag=tag,
            asset_name=asset,
            archive_type=_guess_archive(asset),
            resolved_download_url=raw,
            kind="release_asset",
            expected_component_type="asset_pack",
        )
    m = _GH_RELEASE_TAG.match(path)
    if m:
        owner, repo, tag = m.groups()
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            release_tag=tag,
            kind="release",
            expected_component_type="asset_pack",
        )
    m = _GH_RELEASES.match(path)
    if m:
        owner, repo = m.groups()
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            kind="release",
            expected_component_type="asset_pack",
        )
    m = _GH_ARCHIVE_HEAD.match(path)
    if m:
        owner, repo, branch = m.groups()
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            branch=branch.removesuffix(".zip").removesuffix(".tar.gz"),
            archive_type="zip",
            resolved_download_url=raw,
            kind="branch_archive",
            expected_component_type="source_archive",
        )
    m = _GH_ARCHIVE_TAG.match(path)
    if m:
        owner, repo, tag = m.groups()
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            release_tag=tag.removesuffix(".zip").removesuffix(".tar.gz"),
            archive_type="zip",
            resolved_download_url=raw,
            kind="tag_archive",
            expected_component_type="source_archive",
        )
    m = _GH_REPO.match(path)
    if m:
        owner, repo = m.groups()
        if repo.endswith(".git"):
            repo = repo[:-4]
        return NormalizedSource(
            provider="github",
            source_url=raw,
            owner=owner,
            repository=repo,
            kind="repo",
            expected_component_type="asset_pack",
        )
    raise SourceSecurityError("github_url_unrecognized", "Unsupported GitHub URL form.")


def _parse_huggingface(raw: str, path: str) -> NormalizedSource:
    # Strip optional /datasets/ or /spaces/ prefix for type
    repo_type = "model"
    work = path
    for prefix, rtype in (("/datasets/", "dataset"), ("/spaces/", "space"), ("/models/", "model")):
        if work.startswith(prefix):
            work = "/" + work[len(prefix) :]
            repo_type = rtype
            break

    m = _HF_RESOLVE.match(work)
    if m:
        owner, repo, rev, file_path = m.groups()
        return NormalizedSource(
            provider="huggingface",
            source_url=raw,
            owner=owner,
            repository=repo,
            repository_id=f"{owner}/{repo}",
            repository_type=repo_type,
            revision=rev,
            file_path=file_path,
            resolved_download_url=raw,
            kind="hf_file",
            expected_component_type="model_file",
        )
    m = _HF_BLOB.match(work)
    if m:
        owner, repo, rev, file_path = m.groups()
        return NormalizedSource(
            provider="huggingface",
            source_url=raw,
            owner=owner,
            repository=repo,
            repository_id=f"{owner}/{repo}",
            repository_type=repo_type,
            revision=rev,
            file_path=file_path,
            kind="hf_file",
            expected_component_type="model_file",
        )
    m = _HF_TREE.match(work)
    if m:
        owner, repo, rev = m.groups()
        return NormalizedSource(
            provider="huggingface",
            source_url=raw,
            owner=owner,
            repository=repo,
            repository_id=f"{owner}/{repo}",
            repository_type=repo_type,
            revision=rev,
            kind="hf_repo",
            expected_component_type="model_repo",
        )
    m = _HF_REPO.match(work)
    if m:
        owner, repo = m.groups()
        return NormalizedSource(
            provider="huggingface",
            source_url=raw,
            owner=owner,
            repository=repo,
            repository_id=f"{owner}/{repo}",
            repository_type=repo_type,
            revision="main",
            kind="hf_repo",
            expected_component_type="model_repo",
        )
    raise SourceSecurityError("huggingface_url_unrecognized", "Unsupported Hugging Face URL form.")


def _parse_hf_scheme(raw: str) -> NormalizedSource:
    m = _HF_SCHEME.match(raw)
    if not m:
        raise SourceSecurityError("huggingface_url_unrecognized", "Unsupported hf:// URL form.")
    owner, repo, rev, file_path = m.groups()
    if not repo:
        raise SourceSecurityError("huggingface_url_unrecognized", "hf:// URL must include OWNER/REPOSITORY.")
    return NormalizedSource(
        provider="huggingface",
        source_url=raw,
        owner=owner,
        repository=repo,
        repository_id=f"{owner}/{repo}",
        repository_type="model",
        revision=rev or "main",
        file_path=file_path,
        kind="hf_file" if file_path else "hf_repo",
        expected_component_type="model_file" if file_path else "model_repo",
    )


def _guess_archive(name: str) -> str | None:
    lower = name.lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar.gz"
    if lower.endswith(".7z"):
        return "7z"
    return None
