"""Canonical provider video-catalog contract — the frozen row schema.

Every provider catalog source (WaveSpeed / fal / Kie) normalizes into
``CatalogVideoRow``. Adept surface eligibility is COMPUTED from capability
flags via the predicates below — never maintained as a hand-written list.

Contract freeze (Provider Catalog Fast Path, 2026-09-10):
- Sources may add rows; they may not change field meanings.
- ``status`` records discovery confidence; ``reviewStatus`` records the
  Adept review decision. Newly discovered rows are ALWAYS
  ``pending_review`` and are never auto-exposed to creators.
- ``liveSubmit`` is honest: True only when Adept has a certified live
  submit path for this endpoint today (adapter registered AND in
  LIVE_SUBMIT_ADAPTERS). Building request arguments is not live submit.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CATALOG_SCHEMA_VERSION = 1

ProviderId = Literal["fal", "kie", "wavespeed"]

# Discovery confidence — how the row's capability claims were established.
DiscoveryStatus = Literal[
    "verified",    # schema-inspected against the provider's own schema/docs
    "discovered",  # enumerated from a catalog list; capabilities not yet inspected
    "unverified",  # ambiguous or partially conflicting source data
    "not_found",   # expected model looked for and NOT found (e.g. Happy Horse)
]

# Adept review decision — gates registry merge. Never creator-facing by default.
ReviewStatus = Literal["pending_review", "approved", "hidden"]

# Where the row's data came from.
CatalogSource = Literal["live_api", "docs", "static_catalog"]

# Adept creator surfaces a hosted video endpoint can serve.
Surface = Literal["text_to_video", "one_frame", "three_frame", "timeline_omni"]


class CatalogVideoRow(BaseModel):
    """One normalized provider video-generation endpoint."""

    # Identity
    provider: ProviderId
    family: str = ""            # "seedance" | "kling" | "veo" | "minimax" | "runway" | "wan" | ...
    model: str = ""             # display name, e.g. "Seedance 2.0 Fast"
    version: str | None = None  # "2.0" | "2.5" | "3.0" | ...
    tier: str | None = None     # "pro" | "turbo" | "fast" | "mini" | "standard" | ...
    endpoint: str               # provider endpoint id, e.g. "fal-ai/kling-video/v3/pro/text-to-video"
    apiPath: str | None = None  # request path when distinct from endpoint (WaveSpeed api_path)

    # Mode capabilities
    t2v: bool = False           # text-to-video
    i2v: bool = False           # image-to-video (start frame)
    r2v: bool = False           # reference-to-video (multi-reference conditioning)
    firstFrame: bool = False    # accepts a first/start frame
    lastFrame: bool = False     # accepts a last/end frame
    references: int = 0         # max reference images (0 = none)
    videoReferences: int = 0    # max reference videos (0 = none)

    # Envelope
    durationMinSec: float | None = None
    durationMaxSec: float | None = None
    durationsSec: list[float] = Field(default_factory=list)  # discrete allowed values when enumerated
    resolutions: list[str] = Field(default_factory=list)     # provider labels ("480p") or pixel ("864x480")
    audio: bool = False         # native audio generation

    # Provenance / pricing
    pricing: dict[str, Any] | None = None        # provider-exposed pricing (e.g. WaveSpeed base_price)
    requestSchema: dict[str, Any] | None = None  # raw provider request schema when supplied inline

    # Adept status
    liveSubmit: bool = False    # certified live submit path exists TODAY
    status: DiscoveryStatus = "discovered"
    reviewStatus: ReviewStatus = "pending_review"
    source: CatalogSource = "live_api"
    notes: str = ""             # machine-useful caveats (never docs prose dumps)
    discoveredAt: str = ""

    @property
    def row_id(self) -> str:
        """Stable identity for diffing: provider + endpoint."""
        return f"{self.provider}:{self.endpoint}"


# ---------------------------------------------------------------------------
# Per-surface eligibility predicates — computed, never hand-maintained.
# ---------------------------------------------------------------------------

def eligible_text_to_video(row: CatalogVideoRow) -> bool:
    """Text to Video surface: prompt-only generation."""
    return row.t2v


def eligible_one_frame(row: CatalogVideoRow) -> bool:
    """1 Frame surface: one start picture drives the clip (I2V)."""
    return row.i2v and row.firstFrame


def eligible_three_frame(row: CatalogVideoRow) -> bool:
    """3 Frame surface: first + last frame required, middle guidance optional."""
    return row.i2v and row.firstFrame and row.lastFrame


def eligible_timeline_omni(row: CatalogVideoRow) -> bool:
    """Timeline (Omni): reference-driven batches — R2V, or I2V with a start frame."""
    return row.r2v or (row.i2v and row.firstFrame)


_SURFACE_PREDICATES = {
    "text_to_video": eligible_text_to_video,
    "one_frame": eligible_one_frame,
    "three_frame": eligible_three_frame,
    "timeline_omni": eligible_timeline_omni,
}


def surface_eligibility(row: CatalogVideoRow) -> dict[str, bool]:
    """All four Adept surface eligibility flags for one catalog row."""
    return {surface: pred(row) for surface, pred in _SURFACE_PREDICATES.items()}


def eligible_surfaces(row: CatalogVideoRow) -> list[Surface]:
    """Ordered list of surfaces this endpoint can serve."""
    return [s for s, pred in _SURFACE_PREDICATES.items() if pred(row)]  # type: ignore[misc]


def normalized_table_row(row: CatalogVideoRow) -> dict[str, Any]:
    """The mission's normalized table shape:
    provider | family | model | endpoint | T2V | I2V | R2V | first-frame |
    last-frame | references | duration | resolution | audio | status
    """
    if row.durationsSec:
        duration: str | None = "/".join(f"{d:g}s" for d in row.durationsSec)
    elif row.durationMinSec is not None and row.durationMaxSec is not None:
        duration = f"{row.durationMinSec:g}-{row.durationMaxSec:g}s"
    elif row.durationMaxSec is not None:
        duration = f"<={row.durationMaxSec:g}s"
    else:
        duration = None
    refs: list[str] = []
    if row.references:
        refs.append(f"{row.references} img")
    if row.videoReferences:
        refs.append(f"{row.videoReferences} vid")
    return {
        "provider": row.provider,
        "family": row.family,
        "model": row.model,
        "endpoint": row.endpoint,
        "T2V": row.t2v,
        "I2V": row.i2v,
        "R2V": row.r2v,
        "first-frame": row.firstFrame,
        "last-frame": row.lastFrame,
        "references": "+".join(refs) if refs else None,
        "duration": duration,
        "resolution": "/".join(row.resolutions) if row.resolutions else None,
        "audio": row.audio,
        "status": row.status,
    }
