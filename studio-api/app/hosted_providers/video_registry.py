"""Canonical video-generator registry — ONE source of truth for video products.

Promotes the per-mode endpoint model (fal_catalog.SEEDANCE_MODEL_IDS /
FAL_MODELS) and the drifting backend literals (video_readiness.PRODUCT_ALIASES /
PRODUCT_ADAPTER / LIVE_SUBMIT_ADAPTERS / HOSTED_LIVE_ONLY / SETUP_COMPONENTS /
REQUIRED_NODES, generator_authority._ADAPTER_ONLY_IDS / CREATE_ENGINE_ROWS,
workflow_capabilities._LOCAL_WORKFLOW, model_registry video rows) into a single
frozen registry. Those modules now expose DERIVED VIEWS of these rows — the
view functions below reproduce today's literal values exactly (parity-tested in
tests/test_video_registry_parity.py).

Import-cycle law: this module must stay dependency-free at module level (no
``app`` imports). The provider catalog store (catalog_contract / catalog_sync)
is loaded lazily inside functions so tests can monkeypatch the store path and
production_control can import this module without a cycle.

Creator-surface views (product_aliases / product_adapter_map /
live_submit_adapters / hosted_live_only / setup_components / required_nodes /
adapter_only_ids / create_engine_rows / surface_workflow_map /
video_model_descriptors) iterate CORE_VIDEO_REGISTRY ONLY. Catalog-sourced
registrations (approved provider-catalog rows) are review inventory: they merge
into ``merged_registry()`` but NEVER into creator-surface views, and are never
auto-exposed (exposed=False, live_submit=False, create_live=False).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VideoGeneratorRegistration:
    """One video generator product (or review-inventory endpoint).

    ``endpoints`` maps Adept mode -> provider endpoint id ("t2v" / "i2v" /
    "r2v"). ``surface_workflows`` maps Adept CREATE surface ("t2v" / "i2v" /
    "multiFrame" / "r2v") -> certified workflow key. ``live_submit`` marks a
    Timeline adapter whose submit() reaches a runtime/provider today;
    ``create_live`` marks a live CREATE queue-worker hosted submit path
    (fal ``build_fal_arguments``). ``adapter_only`` lists execution-only ids
    attached to this product that must never appear as a second product row.
    ``exposed`` marks the 16 Production Dock catalog rows; core row "runway"
    and all catalog-sourced rows are not exposed.
    """

    product_id: str
    label: str
    family: str = ""
    version: str | None = None
    tier: str | None = None
    provider: str | None = None
    locality: str = "local"  # "local" | "hosted"
    endpoints: dict[str, str] = field(default_factory=dict)
    duration_min_sec: float | None = None
    duration_max_sec: float | None = None
    durations_sec: tuple[float, ...] = ()
    resolutions: tuple[str, ...] = ()
    audio: bool = False
    live_submit: bool = False
    create_live: bool = False
    adapter_id: str | None = None
    aliases: tuple[str, ...] = ()
    hosted_secret: str | None = None
    setup_components: tuple[str, ...] = ()
    required_nodes: tuple[str, ...] = ()
    surface_workflows: dict[str, str] = field(default_factory=dict)
    create_engine_token: str | None = None
    create_engine_label: str | None = None
    create_engine_group: str | None = None
    adapter_only: tuple[str, ...] = ()
    turbo_lora: bool = False
    capability: str = "Requires Setup"
    lifecycle: str | None = None
    supports: tuple[str, ...] = ()
    does_not_support: tuple[str, ...] = ()
    vram: float | None = None
    gpu: bool = False
    executable_default: bool = False
    exposed: bool = False
    source: str = "core"
    notes: str = ""


# ---------------------------------------------------------------------------
# Core registry — reproduces today's truth exactly (parity-tested).
# Order follows the Production Dock video catalog rows; "runway" is core
# inventory (CREATE engine token fal_runway) with no Dock row.
# ---------------------------------------------------------------------------

_LTX_25_COMPONENTS = ("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae", "ltx_2_5_audio_vae")
# Inventory lists LTXVBaseSampler (video-only). Audio-on graphs use SamplerCustomAdvanced;
# treat either as satisfying the sampler gate (see missing_required_nodes / certified nodeAliasGroups).
_LTX_25_NODES = ("UNETLoader", "LTXVBaseSampler", "LTXVScheduler", "LTXVImgToVideo", "LoadImage")
_LTX_25_SAMPLER_ALTERNATES = frozenset({"LTXVBaseSampler", "SamplerCustomAdvanced"})
_H3_NODES = ("MiniMaxH3ReferenceToVideo", "UNETLoader", "CLIPLoader", "VAELoader", "LoadImage")

# Canonical Adept UI local video architecture: MiniMax H3 + LTX 2.5 only.
# API / hosted video products are a separate catalog and must stay intact.
SUPPORTED_LOCAL_VIDEO_FAMILIES = frozenset({"minimax", "ltx"})
SUPPORTED_LOCAL_VIDEO_GENERATOR_IDS = frozenset(
    {
        "minimax-h3",
        "minimax-h3-i2v-local",
        "ltx-2.5-full",
        "ltx-2.5-distilled",
        "ltx-2.5-comfy",
    }
)
RETIRED_LOCAL_VIDEO_GENERATOR_IDS = frozenset(
    {
        "ltx-local",
        "wan-local",
        "hunyuan-video-1.5-local",
        "hunyuan-video-13b-local",
    }
)
RETIRED_LOCAL_VIDEO_ALIASES = frozenset(
    {
        "ltx",
        "ltx-2.3",
        "ltx_2_3",
        "wan",
        "wan_2_2",
        "wan-2.1",
        "wan-2.2",
        "wan-3",
        "wan-3.0",
        "wan_3",
        "wan_3_0",
        "wan-3.0-prime",
        "hunyuan",
        "hunyuan15",
        "hunyuan13b",
        "hunyuan-video-15",
        "hunyuan-video-13b",
    }
)


def is_retired_local_video(product_id: str | None) -> bool:
    token = str(product_id or "").strip()
    return token in RETIRED_LOCAL_VIDEO_GENERATOR_IDS or token in RETIRED_LOCAL_VIDEO_ALIASES


CORE_VIDEO_REGISTRY: tuple[VideoGeneratorRegistration, ...] = (
    # -- Video — local (Comfy :8188) --------------------------------------
    VideoGeneratorRegistration(
        product_id="ltx-2.5-full",
        label="LTX 2.5 Full",
        family="ltx",
        version="2.5",
        tier="full",
        provider="comfy",
        locality="local",
        audio=True,
        live_submit=True,
        adapter_id="ltx-2.5-distilled",
        setup_components=_LTX_25_COMPONENTS,
        required_nodes=_LTX_25_NODES,
        surface_workflows={"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
        turbo_lora=True,
        capability="Testing",
        lifecycle="Installed",
        supports=(
            "text_to_video",
            "image_to_video",
            "continuation",
            "native_multishot",
            "audio_generation",
            "auto_duration",
            "fast_generation",
        ),
        vram=24.0,
        gpu=True,
        executable_default=True,
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="ltx-2.5-distilled",
        label="LTX 2.5",
        family="ltx",
        version="2.5",
        tier="distilled",
        provider="comfy",
        locality="local",
        audio=True,
        live_submit=True,
        adapter_id="ltx-2.5-distilled",
        aliases=("ltx-2.5",),
        setup_components=_LTX_25_COMPONENTS,
        required_nodes=_LTX_25_NODES,
        surface_workflows={"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
        create_engine_token="ltx-2.5",
        create_engine_label="LTX 2.5",
        create_engine_group="local",
        capability="Available",
        lifecycle="Installed",
        supports=(
            "text_to_video",
            "image_to_video",
            "continuation",
            "native_multishot",
            "audio_generation",
            "auto_duration",
            "fast_generation",
        ),
        vram=16.0,
        gpu=True,
        executable_default=True,
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="ltx-2.5-comfy",
        label="LTX 2.5 Comfy INT8",
        family="ltx",
        version="2.5",
        tier="int8",
        provider="comfy",
        locality="local",
        audio=True,
        live_submit=True,
        adapter_id="ltx-2.5-distilled",
        setup_components=("ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"),
        required_nodes=_LTX_25_NODES,
        surface_workflows={"t2v": "ltx_25.t2v", "i2v": "ltx_25.i2v", "r2v": "ltx_25.i2v"},
        capability="Testing",
        lifecycle="Installed",
        supports=("text_to_video", "image_to_video", "continuation", "audio_generation"),
        vram=12.0,
        gpu=True,
        executable_default=True,
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="minimax-h3",
        label="MiniMax H3",
        family="minimax",
        locality="local",
        audio=True,
        live_submit=True,
        adapter_id="minimax-h3-t2v-local",
        aliases=("minimax-h3-local", "minimax-h3-t2v-local"),
        required_nodes=_H3_NODES,
        surface_workflows={
            "t2v": "route_a.t2va",
            "i2v": "route_a.i2va",
            "multiFrame": "route_a.flf2va",
            "r2v": "h3.ref2v",
        },
        create_engine_token="minimax-h3",
        create_engine_label="MiniMax H3",
        create_engine_group="local",
        adapter_only=("minimax-h3-t2v-local",),
        capability="Requires Setup",
        supports=("native_audio", "text_to_video", "image_to_video"),
        does_not_support=("native_three_keyframe", "three_frame_uses_adept_segmented_assembly"),
        gpu=True,
        executable_default=False,
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="minimax-h3-i2v-local",
        label="MiniMax H3 Image-to-Video",
        family="minimax",
        locality="local",
        audio=True,
        live_submit=True,
        adapter_id="minimax-h3-i2v-local",
        aliases=("minimax-h3-i2v",),
        required_nodes=_H3_NODES,
        surface_workflows={"i2v": "route_a.i2va"},
        capability="Requires Setup",
        supports=("image_to_video", "start_end_frame", "native_audio"),
        does_not_support=("text_to_video", "native_three_keyframe"),
        gpu=True,
        executable_default=False,
        exposed=True,
    ),
    # -- Video — hosted ----------------------------------------------------
    VideoGeneratorRegistration(
        product_id="kling-kie",
        label="Kling (Kie)",
        family="kling",
        version="2.5",
        tier="turbo-pro",
        provider="kie",
        locality="hosted",
        adapter_id="kling-api",
        hosted_secret="kie_api_key",
        capability="Testing",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
        notes="Kie adapter is image-only createTask — no certified video path.",
    ),
    VideoGeneratorRegistration(
        product_id="kling-fal",
        label="Kling (fal.ai)",
        family="kling",
        version="2.5",
        tier="turbo-pro",
        provider="fal",
        locality="hosted",
        endpoints={"i2v": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"},
        duration_min_sec=5.0,
        duration_max_sec=10.0,
        durations_sec=(5, 10),
        create_live=True,
        adapter_id="kling-api",
        hosted_secret="fal_api_key",
        surface_workflows={"i2v": "fal.kling-v25-turbo-pro.i2v"},
        create_engine_token="fal_kling",
        create_engine_label="Kling",
        create_engine_group="hosted",
        adapter_only=("kling-api",),
        capability="Unavailable",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="seedance-2.0",
        label="Seedance 2.0",
        family="seedance",
        version="2.0",
        provider="fal",
        locality="hosted",
        endpoints={
            "t2v": "bytedance/seedance-2.0/text-to-video",
            "i2v": "bytedance/seedance-2.0/image-to-video",
            "r2v": "bytedance/seedance-2.0/reference-to-video",
        },
        duration_min_sec=4.0,
        duration_max_sec=15.0,
        durations_sec=(4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        resolutions=("480p", "720p"),
        audio=True,
        live_submit=True,
        create_live=True,
        adapter_id="seedance-2.0",
        aliases=("seedance-api", "seedance-fal", "fal_seedance"),
        hosted_secret="fal_api_key",
        surface_workflows={
            "t2v": "fal.seedance-2.0.t2v",
            "i2v": "fal.seedance-2.0.i2v",
            "r2v": "fal.seedance-2.0.r2v",
        },
        create_engine_token="seedance-2.0",
        create_engine_label="Seedance 2.0",
        create_engine_group="hosted",
        adapter_only=("seedance-api", "seedance-fal"),
        capability="Unavailable",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="seedance-2.0-mini",
        label="Seedance 2.0 Mini",
        family="seedance",
        version="2.0-mini",
        provider="fal",
        locality="hosted",
        endpoints={
            "t2v": "bytedance/seedance-2.0/mini/reference-to-video",
            "i2v": "bytedance/seedance-2.0/mini/reference-to-video",
            "r2v": "bytedance/seedance-2.0/mini/reference-to-video",
        },
        duration_min_sec=4.0,
        duration_max_sec=15.0,
        durations_sec=(4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        resolutions=("480p", "720p"),
        audio=True,
        live_submit=True,
        create_live=True,
        adapter_id="seedance-2.0-mini",
        aliases=("fal_seedance_mini", "seedance-mini"),
        hosted_secret="fal_api_key",
        surface_workflows={
            "r2v": "fal.seedance-2.0-mini.r2v",
        },
        create_engine_token="seedance-2.0-mini",
        create_engine_label="Seedance 2.0 Mini",
        create_engine_group="hosted",
        adapter_only=("fal_seedance_mini", "seedance-mini"),
        capability="Available",
        supports=("image_to_video",),
        exposed=True,
        notes="Scene 12 Mini R2V only — bytedance/seedance-2.0/mini/reference-to-video; no T2V/full remap.",
    ),
    VideoGeneratorRegistration(
        product_id="seedance-2.0-fast",
        label="Seedance 2.0 Fast",
        family="seedance",
        version="2.0-fast",
        provider="fal",
        locality="hosted",
        endpoints={
            "t2v": "bytedance/seedance-2.0/fast/text-to-video",
            "i2v": "bytedance/seedance-2.0/fast/image-to-video",
            "r2v": "bytedance/seedance-2.0/fast/reference-to-video",
        },
        duration_min_sec=4.0,
        duration_max_sec=15.0,
        durations_sec=(4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        resolutions=("480p", "720p"),
        audio=True,
        live_submit=True,
        create_live=True,
        adapter_id="seedance-2.0-fast",
        aliases=("fal_seedance_fast", "seedance-fast"),
        hosted_secret="fal_api_key",
        surface_workflows={
            "t2v": "fal.seedance-2.0-fast.t2v",
            "i2v": "fal.seedance-2.0-fast.i2v",
            "r2v": "fal.seedance-2.0-fast.r2v",
        },
        create_engine_token="seedance-2.0-fast",
        create_engine_label="Seedance 2.0 Fast",
        create_engine_group="hosted",
        capability="Available",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="seedance-2.5",

        label="Seedance 2.5",
        family="seedance",
        version="2.5",
        provider="fal",
        locality="hosted",
        endpoints={
            "t2v": "bytedance/seedance-2.5/text-to-video",
            "i2v": "bytedance/seedance-2.5/image-to-video",
            "r2v": "bytedance/seedance-2.5/reference-to-video",
        },
        duration_min_sec=4.0,
        duration_max_sec=30.0,
        durations_sec=tuple(range(4, 31)),
        resolutions=("480p", "720p"),
        audio=True,
        live_submit=True,
        create_live=True,
        adapter_id="seedance-2.5",
        aliases=("fal_seedance_25",),
        hosted_secret="fal_api_key",
        surface_workflows={
            "t2v": "fal.seedance-2.5.t2v",
            "i2v": "fal.seedance-2.5.i2v",
            "r2v": "fal.seedance-2.5.r2v",
        },
        create_engine_token="seedance-2.5",
        create_engine_label="Seedance 2.5",
        create_engine_group="hosted",
        capability="Unavailable",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="seedance-kie",
        label="Seedance (Kie)",
        family="seedance",
        provider="kie",
        locality="hosted",
        hosted_secret="kie_api_key",
        capability="Testing",
        supports=("text_to_video", "image_to_video"),
        exposed=True,
        notes="Kie submit path is not implemented — will not silently use fal.",
    ),
    VideoGeneratorRegistration(
        product_id="veo-fal",
        label="Veo (fal.ai)",
        family="veo",
        version="3.1",
        provider="fal",
        locality="hosted",
        endpoints={"t2v": "fal-ai/veo3.1", "i2v": "fal-ai/veo3.1/image-to-video"},
        duration_min_sec=4.0,
        duration_max_sec=8.0,
        durations_sec=(4, 6, 8),
        resolutions=("480p", "720p", "1080p"),
        audio=True,
        create_live=True,
        adapter_id="veo-api",
        hosted_secret="fal_api_key",
        surface_workflows={"t2v": "fal.veo31.t2v", "i2v": "fal.veo31.i2v"},
        create_engine_token="fal_veo",
        create_engine_label="Veo",
        create_engine_group="hosted",
        adapter_only=("veo-api",),
        capability="Unavailable",
        supports=("text_to_video",),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="veo-kie",
        label="Veo (Kie)",
        family="veo",
        version="3.1",
        provider="kie",
        locality="hosted",
        adapter_id="veo-api",
        hosted_secret="kie_api_key",
        capability="Testing",
        supports=("text_to_video",),
        exposed=True,
    ),
    VideoGeneratorRegistration(
        product_id="runway",
        label="Runway (fal.ai)",
        family="runway",
        version="gen3",
        tier="turbo",
        provider="fal",
        locality="hosted",
        endpoints={"i2v": "fal-ai/runway-gen3/turbo/image-to-video"},
        duration_min_sec=5.0,
        duration_max_sec=10.0,
        durations_sec=(5, 10),
        hosted_secret="fal_api_key",
        surface_workflows={"i2v": "fal.runway-gen3-turbo.i2v"},
        create_engine_token="fal_runway",
        create_engine_label="Runway",
        create_engine_group="hosted",
        capability="Unavailable",
        supports=("image_to_video",),
        exposed=False,
        notes="endpoint NOT FOUND in live fal catalog 2026-09-10 — dead in provider catalog",
    ),
)

_CORE_BY_ID: dict[str, VideoGeneratorRegistration] = {r.product_id: r for r in CORE_VIDEO_REGISTRY}

# CREATE /api/engines ordering is a product decision — explicit, not derived
# from registry row order (which follows the Dock catalog).
_CREATE_ENGINE_ORDER: tuple[str, ...] = (
    "minimax-h3",
    "ltx-2.5",
    "seedance-2.0",
    "seedance-2.0-mini",
    "seedance-2.0-fast",
    "seedance-2.5",
    "fal_kling",
    "fal_veo",
    "fal_runway",
)


def core_registration(product_id: str | None) -> VideoGeneratorRegistration | None:
    """Core registry row for a canonical product id (aliases NOT resolved here)."""
    return _CORE_BY_ID.get(str(product_id or "").strip())


# ---------------------------------------------------------------------------
# Creator-surface derived views — CORE rows only, never catalog inventory.
# Each view reproduces today's drifting literal exactly (parity-tested).
# ---------------------------------------------------------------------------


def product_aliases() -> dict[str, str]:
    """= video_readiness.PRODUCT_ALIASES. Aliases never become a second product."""
    out: dict[str, str] = {}
    for row in CORE_VIDEO_REGISTRY:
        for alias in row.aliases:
            out[alias] = row.product_id
    return out


def product_adapter_map() -> dict[str, str]:
    """= video_readiness.PRODUCT_ADAPTER. Provider variants are not collapsed."""
    return {row.product_id: row.adapter_id for row in CORE_VIDEO_REGISTRY if row.adapter_id}


def live_submit_adapters() -> frozenset[str]:
    """= video_readiness.LIVE_SUBMIT_ADAPTERS — adapters whose submit() reaches a runtime."""
    return frozenset(row.adapter_id for row in CORE_VIDEO_REGISTRY if row.live_submit and row.adapter_id)


def hosted_live_only() -> dict[str, str]:
    """= video_readiness.HOSTED_LIVE_ONLY — exposed hosted products gated on a provider secret.

    "runway" carries hosted_secret for surface honesty but is not an exposed
    Dock product, so it stays out of this view (as today).
    """
    return {
        row.product_id: row.hosted_secret
        for row in CORE_VIDEO_REGISTRY
        if row.locality == "hosted" and row.hosted_secret and row.exposed
    }


def setup_components() -> dict[str, tuple[str, ...]]:
    """= video_readiness.SETUP_COMPONENTS."""
    return {row.product_id: row.setup_components for row in CORE_VIDEO_REGISTRY if row.setup_components}


def required_nodes() -> dict[str, tuple[str, ...]]:
    """= video_readiness.REQUIRED_NODES."""
    return {row.product_id: row.required_nodes for row in CORE_VIDEO_REGISTRY if row.required_nodes}




def missing_required_nodes(product_id: str, present: set[str]) -> list[str]:
    """Return required nodes absent from Comfy inventory, honoring LTX sampler alternates."""
    needed = required_nodes().get(product_id) or ()
    missing = {name for name in needed if name not in present}
    if missing & _LTX_25_SAMPLER_ALTERNATES and (present & _LTX_25_SAMPLER_ALTERNATES):
        missing -= _LTX_25_SAMPLER_ALTERNATES
    return sorted(missing)


def adapter_only_ids() -> frozenset[str]:
    """= generator_authority._ADAPTER_ONLY_IDS — execution ids, never product rows.

    seedance-api / seedance-fal are BOTH aliases of seedance-2.0 and
    adapter-only execution tokens; both views keep them.
    """
    out: set[str] = set()
    for row in CORE_VIDEO_REGISTRY:
        out.update(row.adapter_only)
    return frozenset(out)


def create_engine_rows() -> tuple[tuple[str, str, str], ...]:
    """= generator_authority.CREATE_ENGINE_ROWS (token, fallback label, group)."""
    by_token = {row.create_engine_token: row for row in CORE_VIDEO_REGISTRY if row.create_engine_token}
    rows = []
    for token in _CREATE_ENGINE_ORDER:
        row = by_token[token]
        rows.append((token, str(row.create_engine_label or row.label), str(row.create_engine_group or row.locality)))
    return (("auto", "Auto Select", "auto"), *rows)


def surface_workflow_map() -> dict[str, dict[str, str]]:
    """Product -> surface -> certified workflow key.

    Today's workflow_capabilities._LOCAL_WORKFLOW exactly, PLUS hosted entries
    for kling-fal / veo-fal / runway — the intended new honesty: hosted
    products with a real submit path render server truth on CREATE surfaces
    instead of falling through to generic hosted capability flags.
    """
    return {row.product_id: dict(row.surface_workflows) for row in CORE_VIDEO_REGISTRY if row.surface_workflows}


def video_model_descriptors() -> list[dict[str, Any]]:
    """The 16 Production Dock video ``_desc`` kwarg dicts, in catalog order."""
    out: list[dict[str, Any]] = []
    for row in CORE_VIDEO_REGISTRY:
        if not row.exposed:
            continue
        out.append(
            {
                "id": row.product_id,
                "modality": "video",
                "label": row.label,
                "locality": row.locality,
                "provider_id": row.provider,
                "capability": row.capability,
                "lifecycle": row.lifecycle,
                "supports": list(row.supports),
                "does_not_support": list(row.does_not_support),
                "vram": row.vram,
                "gpu": row.gpu,
                "executable": row.executable_default,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Provider-catalog merge — approved rows join as review inventory ONLY.
# ---------------------------------------------------------------------------


def _registration_from_catalog_row(row: dict[str, Any]) -> VideoGeneratorRegistration:
    """Convert one stored CatalogVideoRow dict into a registration.

    Catalog rows are never auto-exposed to creators: exposed=False,
    live_submit=False, create_live=False, no adapter, no workflow keys.
    """
    row_id = str(row.get("rowId") or f"{row.get('provider')}:{row.get('endpoint')}")
    endpoint = str(row.get("endpoint") or "")
    endpoints: dict[str, str] = {}
    for mode in ("t2v", "i2v", "r2v"):
        if row.get(mode) and endpoint:
            endpoints[mode] = endpoint
    supports: list[str] = []
    if row.get("t2v"):
        supports.append("text_to_video")
    if row.get("i2v"):
        supports.append("image_to_video")
    if row.get("r2v"):
        supports.append("reference_conditioning")
    return VideoGeneratorRegistration(
        product_id=row_id,
        label=str(row.get("model") or endpoint or row_id),
        family=str(row.get("family") or ""),
        version=row.get("version"),
        tier=row.get("tier"),
        provider=str(row.get("provider") or "") or None,
        locality="hosted",
        endpoints=endpoints,
        duration_min_sec=row.get("durationMinSec"),
        duration_max_sec=row.get("durationMaxSec"),
        durations_sec=tuple(row.get("durationsSec") or ()),
        resolutions=tuple(row.get("resolutions") or ()),
        audio=bool(row.get("audio")),
        live_submit=False,
        create_live=False,
        adapter_id=None,
        capability="Draft",
        supports=tuple(supports),
        exposed=False,
        source=f"catalog:{row_id}",
        notes=str(row.get("notes") or ""),
    )


def catalog_registrations() -> list[VideoGeneratorRegistration]:
    """Approved provider-catalog rows as registrations. Pending/hidden never merge.

    Lazy catalog_sync import: keeps this module cycle-free and lets tests
    monkeypatch catalog_sync._STORE_PATH.
    """
    try:
        from .catalog_sync import load_provider_catalog

        doc = load_provider_catalog()
    except Exception:
        return []
    out: list[VideoGeneratorRegistration] = []
    for row in doc.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if row.get("reviewStatus") != "approved":
            continue
        out.append(_registration_from_catalog_row(row))
    return out


def merged_registry() -> list[VideoGeneratorRegistration]:
    """Core rows + approved catalog rows (review inventory, never creator views)."""
    return list(CORE_VIDEO_REGISTRY) + catalog_registrations()


def supported_local_video_ids() -> frozenset[str]:
    """Canonical local video product ids currently exposed for Adept UI."""
    return frozenset(
        row.product_id
        for row in CORE_VIDEO_REGISTRY
        if row.locality == "local" and row.family in SUPPORTED_LOCAL_VIDEO_FAMILIES
    )


def supported_hosted_video_ids() -> frozenset[str]:
    """API / hosted video product ids (not subject to the two-family local rule)."""
    return frozenset(row.product_id for row in CORE_VIDEO_REGISTRY if row.locality == "hosted")
