"""fal catalog source — centralized Platform API, never serial page browsing.

Pass 1 enumerate: ``GET https://api.fal.ai/v1/models`` paginated by video
categories (``text-to-video``, ``image-to-video``) plus targeted searches for
reference/video-to-video families. Endpoint IDs first.

Pass 3 schema-inspect: only filtered candidates, batched
``endpoint_id`` (max 10 per call — the API rejects larger) with
``expand=openapi-3.0``, paginating each batch via ``next_cursor``.

Read-only: this module never submits to the queue. Auth header follows the
existing fal client convention (``Authorization: Key <key>``); the endpoint
also works unauthenticated at a lower rate limit.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from ..catalog_contract import CatalogVideoRow

MODELS_URL = "https://api.fal.ai/v1/models"

# Pass 1: video categories to enumerate. fal categories are kebab-case.
_LIST_CATEGORIES: tuple[str, ...] = (
    "text-to-video",
    "image-to-video",
    "reference-to-video",
    "video-to-video",
)
# Families Adept cares about that may live under other categories
# (reference-to-video, video-to-video, ...). Searched by free text.
_FAMILY_SEARCHES: tuple[str, ...] = (
    "reference to video",
    "video to video",
    "kling",
    "seedance",
    "veo",
    "minimax",
    "runway",
    "wan",
    "hunyuan",
    "ltx",
    "happy horse",
)

_FAMILY_TOKENS: tuple[tuple[str, str], ...] = (
    ("seedance", "seedance"),
    ("kling", "kling"),
    ("veo", "veo"),
    ("minimax", "minimax"),
    ("hailuo", "minimax"),
    ("runway", "runway"),
    ("wan", "wan"),
    ("hunyuan", "hunyuan"),
    ("ltx", "ltx"),
    ("vidu", "vidu"),
    ("pixverse", "pixverse"),
    ("pika", "pika"),
    ("luma", "luma"),
    ("sora", "sora"),
    ("happy-horse", "happy-horse"),
    ("happyhorse", "happy-horse"),
    ("bytedance", "seedance"),
)

_VERSION_RE = re.compile(r"v?(\d+(?:\.\d+)?)")
_TIER_TOKENS = ("pro", "turbo", "fast", "mini", "standard", "lite", "max", "plus", "distilled", "master")

# Endpoints that are video-adjacent but not generation surfaces for Adept.
_EXCLUDE_TOKENS = (
    "upscale",
    "enhance",
    "interpolat",
    "subtitle",
    "transcribe",
    "caption",
    "lipsync",
    "lip-sync",
    "sound-effects",
    "audio",
    "music",
    "speech",
    "training",
    "trainer",
    "lora",
    "controlnet",
    "face-swap",
    "watermark",
    # video utilities / editors, not generation surfaces
    "eraser",
    "erase",
    "background",
    "removal",
    "colorize",
    "deblur",
    "denoise",
    "sdr-to-hdr",
    "workflow-utilities",
    "ffmpeg",
    "depth-anything",
    "inpainting",
    "avatar",
    "router",
    "infinitalk",
    "foley",
    "effects",
    "elements",
    "motion-control",
    "tts",
    "create-voice",
    "video-edit",
    "edit-video",
    "/edit",
    "extend",
    "retake",
    "multiconditioning",
    "increase-resolution",
    "tryon",
    "try-on",
    "vton",
)


def _classify_family(text: str) -> str:
    low = text.lower()
    for token, family in _FAMILY_TOKENS:
        if token in low:
            return family
    return ""


def _classify_version(text: str) -> str | None:
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def _classify_tier(text: str) -> str | None:
    low = text.lower()
    for token in _TIER_TOKENS:
        if re.search(rf"(?:^|[/\-_\s]){re.escape(token)}(?:$|[/\-_\s])", low):
            return token
    return None


def _is_video_generation(endpoint_id: str, category: str, title: str) -> bool:
    hay = f"{endpoint_id} {category} {title}".lower()
    if "video" not in hay:
        return False
    for token in _EXCLUDE_TOKENS:
        if token in hay:
            return False
    return True


def _openapi_input_props(openapi: Any) -> dict[str, Any]:
    """Extract the request input schema properties from an expanded OpenAPI doc."""
    if not isinstance(openapi, dict):
        return {}
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        post = path_item.get("post")
        if not isinstance(post, dict):
            continue
        body = post.get("requestBody")
        if not isinstance(body, dict):
            continue
        content = body.get("content")
        if not isinstance(content, dict):
            continue
        for media in content.values():
            if not isinstance(media, dict):
                continue
            schema = media.get("schema")
            ref = isinstance(schema, dict) and schema.get("$ref")
            if ref:
                # Resolve local component refs: #/components/schemas/Input
                name = str(ref).rsplit("/", 1)[-1]
                components = openapi.get("components")
                schemas = components.get("schemas") if isinstance(components, dict) else None
                resolved = schemas.get(name) if isinstance(schemas, dict) else None
                if isinstance(resolved, dict) and isinstance(resolved.get("properties"), dict):
                    return resolved["properties"]
            if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
                return schema["properties"]
    return {}


def _enum_strs(prop: Any) -> list[str]:
    if not isinstance(prop, dict):
        return []
    values = prop.get("enum")
    if not isinstance(values, list):
        return []
    return [str(v) for v in values]


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*s?\s*$", value)
        if m:
            return float(m.group(1))
    return None


def _row_from_model(model: dict[str, Any], *, schema_props: dict[str, Any] | None) -> CatalogVideoRow | None:
    endpoint = str(model.get("endpoint_id") or model.get("endpointId") or "").strip()
    if not endpoint:
        return None
    category = str(model.get("category") or model.get("_queried_category") or "").strip()
    meta = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
    title = str(meta.get("display_name") or meta.get("title") or model.get("title") or "").strip()
    description = str(model.get("description") or "")
    if not _is_video_generation(endpoint, category, title):
        return None

    hay = f"{endpoint} {category}".lower()
    t2v = "text-to-video" in hay
    i2v = "image-to-video" in hay
    r2v = "reference-to-video" in hay
    flf = "first-last-frame" in hay or "first-last" in hay
    v2v = "video-to-video" in hay

    props = schema_props or {}
    if props:
        first_frame = i2v or flf or any(
            k in props for k in ("image_url", "start_image", "first_frame", "first_frame_image", "image")
        )
        last_frame = flf or any(k in props for k in ("end_image_url", "end_image", "last_frame", "tail_image"))
    else:
        first_frame = i2v or flf
        last_frame = flf

    max_ref_images = 0
    for key in ("image_urls", "images", "reference_images", "references"):
        prop = props.get(key)
        if isinstance(prop, dict):
            hi = prop.get("maxItems") or prop.get("max_items")
            max_ref_images = max(max_ref_images, hi if isinstance(hi, int) and hi > 0 else 1)
    if r2v and max_ref_images == 0:
        max_ref_images = 1  # R2V implies >=1 reference; exact cap UNVERIFIED
    max_ref_videos = 0
    for key in ("video_urls", "videos", "reference_videos", "video_url"):
        prop = props.get(key)
        if isinstance(prop, dict):
            hi = prop.get("maxItems") or prop.get("max_items")
            max_ref_videos = max(max_ref_videos, hi if isinstance(hi, int) and hi > 0 else 1)
    if v2v and max_ref_videos == 0:
        max_ref_videos = 1

    durations: list[float] = []
    dur_min: float | None = None
    dur_max: float | None = None
    dur_prop = props.get("duration")
    if isinstance(dur_prop, dict):
        enums = [d for d in (_duration_seconds(v) for v in _enum_strs(dur_prop)) if d is not None]
        if enums:
            durations = sorted(set(enums))
        else:
            lo, hi = dur_prop.get("minimum"), dur_prop.get("maximum")
            try:
                dur_min = float(lo) if lo is not None else None
                dur_max = float(hi) if hi is not None else None
            except (TypeError, ValueError):
                dur_min = dur_max = None

    resolutions: list[str] = []
    for key in ("resolution", "size", "aspect_ratio"):
        prop = props.get(key)
        enums = _enum_strs(prop)
        if enums and key != "aspect_ratio":
            resolutions = enums
            break

    audio = any(k in props for k in ("generate_audio", "audio", "enable_audio", "with_audio"))

    notes_bits: list[str] = []
    if v2v:
        notes_bits.append("video-to-video endpoint (V2V not an Adept surface today)")
    if str(model.get("status") or "") == "deprecated":
        notes_bits.append("provider marks this endpoint deprecated")
    if r2v and max_ref_images <= 1:
        notes_bits.append("exact reference image cap UNVERIFIED from schema")

    return CatalogVideoRow(
        provider="fal",
        family=_classify_family(f"{endpoint} {title}"),
        model=title or endpoint,
        version=_classify_version(f"{endpoint} {title}"),
        tier=_classify_tier(f"{endpoint} {title}"),
        endpoint=endpoint,
        t2v=t2v,
        i2v=i2v,
        r2v=r2v,
        firstFrame=first_frame,
        lastFrame=last_frame,
        references=max_ref_images,
        videoReferences=max_ref_videos,
        durationMinSec=dur_min,
        durationMaxSec=dur_max,
        durationsSec=durations,
        resolutions=resolutions,
        audio=audio,
        liveSubmit=False,  # set by catalog_sync against LIVE_SUBMIT_ADAPTERS
        status="verified" if props else "discovered",
        source="live_api",
        notes="; ".join(notes_bits),
    )


def parse_fal_catalog(
    listed_models: list[dict[str, Any]],
    *,
    schemas_by_endpoint: dict[str, dict[str, Any]] | None = None,
) -> list[CatalogVideoRow]:
    """Normalize enumerated fal models (+ optional OpenAPI expansions).

    Pure function — fixture-testable, no network.
    """
    schemas_by_endpoint = schemas_by_endpoint or {}
    rows: list[CatalogVideoRow] = []
    seen: set[str] = set()
    for model in listed_models:
        if not isinstance(model, dict):
            continue
        endpoint = str(model.get("endpoint_id") or "").strip()
        if not endpoint or endpoint in seen:
            continue
        openapi = schemas_by_endpoint.get(endpoint)
        if openapi is None and isinstance(model.get("openapi"), dict):
            openapi = model["openapi"]
        props = _openapi_input_props(openapi) if openapi else {}
        row = _row_from_model(model, schema_props=props)
        if row is None:
            continue
        seen.add(endpoint)
        rows.append(row)
    rows.sort(key=lambda r: (r.family, r.version or "", r.tier or "", r.endpoint))
    return rows


async def _list_category(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    category: str | None = None,
    query: str | None = None,
    status: str | None = "active",
    limit: int = 100,
    max_pages: int = 10,
) -> tuple[list[dict[str, Any]], bool]:
    """Paginate /v1/models for one category or search. Read-only listing.

    Returns (models, complete). A transient HTTP error retries with backoff;
    a persistent failure returns the partial listing with complete=False so
    the sync layer never treats a truncated listing as grounds for removal.
    """
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(max_pages):
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if category:
            params["category"] = category
        if query:
            params["q"] = query
        if cursor:
            params["cursor"] = cursor
        body: dict[str, Any] | None = None
        for attempt in range(3):
            try:
                resp = await client.get(MODELS_URL, headers=headers, params=params)
            except Exception:
                resp = None
            if resp is not None and resp.status_code < 400:
                try:
                    parsed = resp.json()
                    body = parsed if isinstance(parsed, dict) else None
                except Exception:
                    body = None
                if body is not None:
                    break
            await asyncio.sleep(1.0 * (attempt + 1))
        if body is None:
            return out, False
        models = body.get("models")
        if not isinstance(models, list):
            return out, False
        out.extend(m for m in models if isinstance(m, dict))
        cursor = body.get("next_cursor")
        if not cursor:
            return out, True
    return out, True


async def _expand_batch(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    batch: list[str],
    out: dict[str, dict[str, Any]],
    failed: list[str],
) -> None:
    """Fetch one endpoint_id batch with expand=openapi-3.0.

    The API rejects the whole call with HTTP 400 when any single endpoint in
    the batch is unknown — bisect on 400 so one stale endpoint cannot sink
    the other 49.
    """
    # endpoint_id queries cap at limit=10 ("Requested limit 50 exceeds
    # maximum of 10 for this query") and paginate via next_cursor.
    params: list[tuple[str, str]] = [("endpoint_id", e) for e in batch]
    params.append(("expand", "openapi-3.0"))
    params.append(("limit", "10"))
    cursor: str | None = None
    for _ in range(6):  # paginate within the batch if the API pages
        page_params = list(params)
        if cursor:
            page_params.append(("cursor", cursor))
        resp: httpx.Response | None = None
        for attempt in range(3):
            try:
                resp = await client.get(MODELS_URL, headers=headers, params=page_params)
            except Exception:
                resp = None
            # Retry transient failures (429/5xx/network); a persistent 400 is
            # an unknown-endpoint rejection — handled by bisection below.
            if resp is not None and (resp.status_code < 400):
                break
            if resp is not None and resp.status_code == 400:
                break
            await asyncio.sleep(1.0 * (attempt + 1))
        if resp is None:
            failed.extend(batch)
            return
        if resp.status_code >= 400:
            if resp.status_code != 400:
                failed.extend(batch)
                return
            if len(batch) == 1:
                failed.append(batch[0])
                return
            mid = len(batch) // 2
            await _expand_batch(client, headers, batch[:mid], out, failed)
            await _expand_batch(client, headers, batch[mid:], out, failed)
            return
        body = resp.json()
        models = body.get("models") if isinstance(body, dict) else None
        if not isinstance(models, list):
            return
        for model in models:
            if not isinstance(model, dict):
                continue
            endpoint = str(model.get("endpoint_id") or "")
            openapi = model.get("openapi")
            if endpoint and isinstance(openapi, dict):
                out[endpoint] = openapi
        cursor = body.get("next_cursor") if isinstance(body, dict) else None
        if not cursor:
            return


async def _expand_schemas(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    endpoint_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Batch endpoint_id fetches with expand=openapi-3.0 (max 10 per call).

    A gentle single-endpoint recovery pass follows the batched pass: transient
    429s under batch load must not permanently sink a row's schema when the
    same endpoint answers fine on its own.
    """
    out: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    for i in range(0, len(endpoint_ids), 10):
        await _expand_batch(client, headers, endpoint_ids[i : i + 10], out, failed)
    if failed:
        recovered: list[str] = []
        for endpoint in list(failed):
            await asyncio.sleep(0.4)
            single_out: dict[str, dict[str, Any]] = {}
            single_failed: list[str] = []
            await _expand_batch(client, headers, [endpoint], single_out, single_failed)
            if single_out.get(endpoint):
                out[endpoint] = single_out[endpoint]
                recovered.append(endpoint)
        failed = [e for e in failed if e not in set(recovered)]
    return out, failed


async def fetch_fal_catalog(api_key: str | None, *, timeout_sec: float = 30.0) -> dict[str, Any]:
    """Enumerate + schema-inspect the fal video catalog. Read-only."""
    headers = {"Accept": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Key {key}"
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            listed: list[dict[str, Any]] = []
            # The list response does not echo a per-model category — stamp the
            # query context so mode flags can use it downstream.
            complete = True
            for category in _LIST_CATEGORIES:
                models, cat_complete = await _list_category(client, headers, category=category)
                complete = complete and cat_complete
                for model in models:
                    model["_queried_category"] = category
                    listed.append(model)
            # Family searches run unfiltered by status so removed/deprecated
            # endpoints (e.g. runway-*) surface as honest NOT FOUND / deprecated
            # findings instead of silently vanishing. Search membership never
            # affects `complete` — searches are sampled discovery, not census.
            for query in _FAMILY_SEARCHES:
                models, _ = await _list_category(client, headers, query=query, status=None, limit=50, max_pages=3)
                listed.extend(models)

            # Pass 2: filter to Adept-relevant video generation endpoints.
            candidates: dict[str, dict[str, Any]] = {}
            for model in listed:
                endpoint = str(model.get("endpoint_id") or "").strip()
                category = str(model.get("category") or model.get("_queried_category") or "")
                meta = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
                title = str(meta.get("display_name") or meta.get("title") or model.get("title") or "")
                if endpoint and _is_video_generation(endpoint, category, title):
                    # First occurrence wins (category listings carry the
                    # authoritative category stamp); searches only fill gaps.
                    candidates.setdefault(endpoint, model)

            # Pass 3: schema-inspect only the filtered candidates.
            schemas, schema_failures = await _expand_schemas(client, headers, sorted(candidates))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "rows": [], "mock": False}

    rows = parse_fal_catalog(list(candidates.values()), schemas_by_endpoint=schemas)
    return {
        "ok": True,
        "rows": rows,
        "rawCount": len(listed),
        "candidateCount": len(candidates),
        "schemaCount": len(schemas),
        "schemaFailures": schema_failures,
        # False when any category listing truncated — removal diff must not
        # trust a partial census.
        "complete": complete,
        "mock": False,
    }
