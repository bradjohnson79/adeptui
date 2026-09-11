"""WaveSpeed catalog source — official model-list endpoint.

GET https://api.wavespeed.ai/api/v3/models (Bearer key) returns the full
model catalog; video-generation rows carry ``type`` plus ``api_path`` and an
inline ``request_schema`` — so Pass 3 (schema inspection) is free for this
provider. Read-only: this module never submits a prediction.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..catalog_contract import CatalogVideoRow

MODELS_URL = "https://api.wavespeed.ai/api/v3/models"

# WaveSpeed api_path mode suffixes → Adept mode flags.
_MODE_SUFFIXES = (
    ("text-to-video", "t2v"),
    ("image-to-video", "i2v"),
    ("reference-to-video", "r2v"),
    ("first-last-frame-to-video", "flf"),
    ("video-to-video", "v2v"),
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
)

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)?)")
_TIER_TOKENS = ("pro", "turbo", "fast", "mini", "standard", "lite", "max", "plus", "distilled")


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


def _schema_props(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    if isinstance(props, dict):
        return props
    # Some schemas nest under a request/input key.
    for key in ("request", "input", "schema"):
        nested = schema.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("properties"), dict):
            return nested["properties"]
    return {}


def _enum_values(prop: Any) -> list[Any]:
    if not isinstance(prop, dict):
        return []
    values = prop.get("enum")
    if isinstance(values, list):
        return values
    return []


def _numeric_bounds(prop: Any) -> tuple[float | None, float | None]:
    if not isinstance(prop, dict):
        return None, None
    lo = prop.get("minimum")
    hi = prop.get("maximum")
    try:
        lo_f = float(lo) if lo is not None else None
        hi_f = float(hi) if hi is not None else None
    except (TypeError, ValueError):
        return None, None
    return lo_f, hi_f


def _duration_seconds(value: Any) -> float | None:
    """Parse a duration enum/bound value: 5, "5", "5s" → 5.0."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*s?\s*$", value)
        if m:
            return float(m.group(1))
    return None


def _is_video_model(model_id: str, mtype: str, api_path: str) -> bool:
    hay = f"{model_id} {mtype} {api_path}".lower()
    if "video" not in hay:
        return False
    # Exclude video-adjacent non-generation types (upscalers, editors, lipsync utilities).
    for excluded in ("upscale", "enhance", "interpolat", "subtitle", "transcribe", "caption"):
        if excluded in hay:
            return False
    return True


def parse_wavespeed_models(payload: Any) -> list[CatalogVideoRow]:
    """Normalize the /api/v3/models payload into video catalog rows.

    Pure function — fixture-testable, no network.
    """
    if isinstance(payload, dict):
        items = payload.get("data")
        if isinstance(items, dict):
            items = items.get("models") or items.get("items")
        if items is None:
            items = payload.get("models")
    else:
        items = payload
    if not isinstance(items, list):
        return []

    rows: list[CatalogVideoRow] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or item.get("modelId") or item.get("id") or "").strip()
        name = str(item.get("name") or item.get("display_name") or item.get("displayName") or "").strip()
        mtype = str(item.get("type") or item.get("model_type") or item.get("modelType") or "").strip()
        api_path = str(item.get("api_path") or item.get("apiPath") or item.get("path") or model_id).strip()
        if not model_id:
            continue
        if not _is_video_model(model_id, mtype, api_path):
            continue

        schema = item.get("request_schema") or item.get("requestSchema")
        props = _schema_props(schema)

        hay = f"{model_id} {api_path}".lower()
        modes = {suffix for suffix, _ in _MODE_SUFFIXES if suffix in hay}
        t2v = "text-to-video" in modes
        i2v = "image-to-video" in modes
        r2v = "reference-to-video" in modes
        flf = "first-last-frame-to-video" in modes
        v2v = "video-to-video" in modes

        # Schema-driven refinement (Pass 3, inline for WaveSpeed).
        first_frame = i2v or flf or any(
            k in props for k in ("image", "image_url", "first_frame", "start_image", "first_frame_image")
        )
        last_frame = flf or any(k in props for k in ("end_image", "end_image_url", "last_frame", "tail_image"))
        max_ref_images = 0
        for key in ("image_urls", "images", "reference_images", "references"):
            prop = props.get(key)
            if isinstance(prop, dict):
                hi = prop.get("maxItems") or prop.get("max_items")
                if isinstance(hi, int) and hi > 0:
                    max_ref_images = max(max_ref_images, hi)
                else:
                    max_ref_images = max(max_ref_images, 1)
        if r2v and max_ref_images == 0:
            max_ref_images = 1  # R2V implies at least one reference; exact cap UNVERIFIED
        max_ref_videos = 0
        for key in ("video_urls", "videos", "reference_videos"):
            prop = props.get(key)
            if isinstance(prop, dict):
                hi = prop.get("maxItems") or prop.get("max_items")
                max_ref_videos = max(max_ref_videos, hi if isinstance(hi, int) and hi > 0 else 1)
        if v2v and max_ref_videos == 0:
            max_ref_videos = 1

        durations: list[float] = []
        dur_min: float | None = None
        dur_max: float | None = None
        for key in ("duration", "duration_sec", "duration_seconds", "num_seconds"):
            prop = props.get(key)
            if prop is None:
                continue
            enums = [_duration_seconds(v) for v in _enum_values(prop)]
            enums = [e for e in enums if e is not None]
            if enums:
                durations = sorted(set(enums))
                break
            lo, hi = _numeric_bounds(prop)
            if lo is not None or hi is not None:
                dur_min, dur_max = lo, hi
                break

        resolutions: list[str] = []
        for key in ("resolution", "size", "quality"):
            prop = props.get(key)
            enums = [str(v) for v in _enum_values(prop) if isinstance(v, (str, int))]
            if enums:
                resolutions = enums
                break

        audio = any(k in props for k in ("generate_audio", "audio", "enable_audio", "with_audio"))

        pricing = None
        if item.get("base_price") is not None:
            pricing = {"base_price": item.get("base_price"), "currency": item.get("currency") or "USD"}

        notes_bits: list[str] = []
        if v2v:
            notes_bits.append("video-to-video endpoint (V2V not an Adept surface today)")
        if r2v and max_ref_images <= 1:
            notes_bits.append("exact reference image cap UNVERIFIED from schema")

        rows.append(
            CatalogVideoRow(
                provider="wavespeed",
                family=_classify_family(f"{model_id} {name}"),
                model=name or model_id,
                version=_classify_version(f"{model_id} {name}"),
                tier=_classify_tier(f"{model_id} {name}"),
                endpoint=model_id,
                apiPath=api_path or None,
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
                pricing=pricing,
                requestSchema=schema if isinstance(schema, dict) else None,
                liveSubmit=False,  # no Adept video submit path for WaveSpeed today
                status="verified" if props else "discovered",
                source="live_api",
                notes="; ".join(notes_bits),
            )
        )
    rows.sort(key=lambda r: (r.family, r.version or "", r.tier or "", r.endpoint))
    return rows


async def fetch_wavespeed_catalog(api_key: str, *, timeout_sec: float = 30.0) -> dict[str, Any]:
    """GET the official model list and normalize video rows. Read-only."""
    key = (api_key or "").strip()
    if not key:
        return {
            "ok": False,
            "error": "NOT_CONFIGURED",
            "message": "No WaveSpeed.ai API key is configured.",
            "rows": [],
            "mock": False,
        }
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(
                MODELS_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "rows": [], "mock": False}
    if response.status_code in (401, 403):
        return {
            "ok": False,
            "error": "INVALID_KEY",
            "message": f"WaveSpeed.ai rejected the configured key (HTTP {response.status_code}).",
            "rows": [],
            "mock": False,
        }
    if response.status_code >= 400:
        return {
            "ok": False,
            "error": "HTTP_ERROR",
            "message": f"WaveSpeed.ai models list returned HTTP {response.status_code}.",
            "rows": [],
            "mock": False,
        }
    try:
        payload = response.json()
    except Exception:
        return {"ok": False, "error": "BAD_JSON", "message": "Models list was not JSON.", "rows": [], "mock": False}
    rows = parse_wavespeed_models(payload)
    return {
        "ok": True,
        "rows": rows,
        "rawCount": len(payload.get("data") or []) if isinstance(payload, dict) and isinstance(payload.get("data"), list) else None,
        "mock": False,
    }
