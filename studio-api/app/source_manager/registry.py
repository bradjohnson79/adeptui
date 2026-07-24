"""Provider registry with capability + priority selection."""

from __future__ import annotations

from typing import Any

from ..setup.download_sources.url_parse import parse_source_url
from .contracts import ProviderDetectionResult, SourceInput, SourceProvider
from .providers import (
    DirectHttpProvider,
    ExistingInstallProvider,
    FixtureProvider,
    GitHubApiProvider,
    GitHubCliProvider,
    HuggingFaceCliProvider,
    LocalFolderProvider,
)

_PROVIDERS: list[SourceProvider] | None = None


def all_providers() -> list[SourceProvider]:
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = [
            FixtureProvider(),
            GitHubCliProvider(),
            HuggingFaceCliProvider(),
            GitHubApiProvider(),
            DirectHttpProvider(),
            LocalFolderProvider(),
            ExistingInstallProvider(),
        ]
    return list(_PROVIDERS)


def get_provider(provider_id: str) -> SourceProvider | None:
    for provider in all_providers():
        if provider.id == provider_id:
            return provider
    return None


def detect_all() -> list[ProviderDetectionResult]:
    results = [provider.detect() for provider in all_providers()]
    return sorted(results, key=lambda item: (item.priority, item.display_name))


def select_provider(source_input: SourceInput) -> SourceProvider:
    """Choose a provider by hint, parsed kind, capability, availability, and priority."""
    providers = all_providers()
    detections = {item.provider_id: item for item in detect_all()}

    hint = (source_input.provider_hint or "").strip().lower()
    if hint:
        for provider in providers:
            if provider.id == hint or provider.id.replace("_", "") == hint.replace("_", ""):
                return provider
        # legacy aliases
        aliases = {
            "github": "github_cli",
            "huggingface": "huggingface_cli",
            "hf": "huggingface_cli",
            "manual_url": "direct_http",
            "url": "direct_http",
        }
        alias = aliases.get(hint)
        if alias:
            provider = get_provider(alias)
            if provider:
                return provider

    if source_input.local_path:
        return get_provider("local_folder") or providers[-1]

    url = (source_input.url or "").strip()
    if not url:
        # Prefer first available non-fixture provider
        for provider in sorted(providers, key=lambda p: p.priority):
            if provider.id == "fixture":
                continue
            det = detections.get(provider.id)
            if det and det.available:
                return provider
        return get_provider("direct_http") or providers[0]

    try:
        normalized = parse_source_url(url)
        kind_provider = normalized.provider
    except Exception:
        kind_provider = None

    candidates: list[SourceProvider] = []
    if kind_provider == "github":
        candidates = [p for p in providers if p.id in {"github_cli", "github_api", "direct_http"}]
    elif kind_provider == "huggingface":
        candidates = [p for p in providers if p.id in {"huggingface_cli", "direct_http"}]
    else:
        candidates = [p for p in providers if p.id in {"direct_http", "fixture"}]

    scored: list[tuple[int, SourceProvider]] = []
    for provider in candidates:
        det = detections.get(provider.id)
        score = provider.priority
        if det and not det.available:
            score += 1000
        if det and provider.id == "github_cli" and det.authenticated:
            score -= 5
        if det and provider.id == "huggingface_cli" and det.authenticated:
            score -= 5
        scored.append((score, provider))
    scored.sort(key=lambda item: item[0])
    return scored[0][1] if scored else (get_provider("direct_http") or providers[0])


def overview_payload() -> dict[str, Any]:
    from .downloads.queue import get_queue_manager
    from .downloads.receipts import history_entries
    from .migration import ensure_migrated
    from .persistence import components_using_source, list_assignments, list_sources

    ensure_migrated()
    providers = [item.to_dict() for item in detect_all()]
    sources = list_sources()
    assignments = list_assignments()
    saved = []
    for source_id, record in sources.items():
        saved.append(
            {
                **record,
                "componentsUsing": components_using_source(source_id),
                "artifactCount": len((record.get("metadata") or {}).get("selectedFiles") or []),
            }
        )
    saved.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    active = get_queue_manager().list({"active": True})
    history = history_entries()[:50]
    return {
        "schemaVersion": 3,
        "providers": providers,
        "sources": saved,
        "assignments": assignments,
        "activeDownloads": active,
        "installHistory": history,
        "diagnostics": {
            "phase": "1B",
            "downloadQueue": "active",
            "assetIntelligence": "deferred",
            "dependencyGraph": "deferred",
            "healthDashboard": "deferred",
        },
        "messages": {
            "intro": (
                "Source Manager centralizes providers, saved sources, the download queue, "
                "and install history. Asset intelligence and dependency graphs arrive in later phases."
            ),
        },
    }
