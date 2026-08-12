"""M42 Multi-Provider Hosted AI Strategy — Kie.ai / WaveSpeed.ai / fal.ai."""

from .resolver import resolve_hosted_provider
from .service import catalog, resolve

__all__ = ["catalog", "resolve", "resolve_hosted_provider"]
