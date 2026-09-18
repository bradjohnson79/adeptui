"""Canonical generation request memory — durable production history, not chat."""

from .contracts import CanonicalGenerationRequest, InheritAudit, ResolvedRetry
from .referential import is_referential_generation
from .resolve import apply_canonical_retry_to_context, resolve_canonical_retry
from .store import attach_canonical_request, request_from_pack

__all__ = [
    "CanonicalGenerationRequest",
    "InheritAudit",
    "ResolvedRetry",
    "apply_canonical_retry_to_context",
    "attach_canonical_request",
    "is_referential_generation",
    "request_from_pack",
    "resolve_canonical_retry",
]
