"""Provider catalog sources — one bounded module per provider.

Each source enumerates that provider's video-generation catalog and
normalizes rows into the frozen contract (catalog_contract.CatalogVideoRow).

Pass discipline (Provider Catalog Fast Path, 2026-09-10):
- Pass 1 enumerate: endpoint IDs only.
- Pass 2 filter: Adept-relevant video generation (T2V/I2V/R2V/first+last frame).
- Pass 3 schema-inspect: only filtered candidates; machine-useful metadata.
- Pass 4 registry: handled by catalog_sync / registry merge, never by sources.

All sources are READ-ONLY against providers: no generation submit, no
inference wait, no paid endpoint calls.
"""

from __future__ import annotations

from .fal_catalog_source import fetch_fal_catalog, parse_fal_catalog
from .kie_catalog_source import fetch_kie_catalog, parse_kie_market_index, parse_kie_market_page
from .wavespeed_catalog_source import fetch_wavespeed_catalog, parse_wavespeed_models

__all__ = [
    "fetch_fal_catalog",
    "parse_fal_catalog",
    "fetch_kie_catalog",
    "parse_kie_market_index",
    "parse_kie_market_page",
    "fetch_wavespeed_catalog",
    "parse_wavespeed_models",
]
