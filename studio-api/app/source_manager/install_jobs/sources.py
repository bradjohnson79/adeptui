from __future__ import annotations

from typing import Any

from ...setup.download_sources.service import verify_source_url
from ...source_manager.service import save_verified_source_for_component


def _requires_confirmation(verification: dict[str, Any]) -> bool:
    source = verification.get("source") or {}
    provider = str(source.get("provider") or verification.get("provider") or "").strip().lower()
    return provider != "fixture"


def validate_source(
    component_id: str,
    url: str,
    revision: str | None = None,
) -> dict[str, Any]:
    result = verify_source_url(url=url, component_id=component_id, revision=revision)
    result["requiresConfirmation"] = _requires_confirmation(result)
    return result


def save_source(
    component_id: str,
    *,
    verification: dict[str, Any] | None = None,
    url: str | None = None,
    revision: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    checked = verification
    if checked is None:
        raw_url = str(url or "").strip()
        if not raw_url:
            raise ValueError("url or verification is required")
        checked = validate_source(component_id, raw_url, revision=revision)
    if not checked.get("ok"):
        raise ValueError(str(checked.get("message") or "Source verification failed."))
    if _requires_confirmation(checked) and not confirm:
        raise ValueError("Saving a user-supplied source requires confirm=true.")
    return save_verified_source_for_component(component_id, checked)
