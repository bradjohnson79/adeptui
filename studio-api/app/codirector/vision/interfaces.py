"""Protocols for vision providers and validators."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from .schemas import ValidatorFinding


@runtime_checkable
class VisionProvider(Protocol):
    provider_id: str

    def prepare_asset_context(
        self,
        *,
        asset_path: Optional[str],
        reference_path: Optional[str],
        requirements: dict[str, Any],
        fixture_profile: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return provider-local analysis context (pixels/metrics/fixtures)."""
        ...


@runtime_checkable
class VisionValidator(Protocol):
    validator_id: str

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        ...
