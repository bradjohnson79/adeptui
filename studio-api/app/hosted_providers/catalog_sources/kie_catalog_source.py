"""Kie catalog source — Market documentation catalog (docs.kie.ai).

Kie has no public models/list API (see kie_adapter.py). The centralized
catalog is the docs index at ``https://docs.kie.ai/llms.txt``: it enumerates
every Market model page, and each Market page embeds a full OpenAPI 3.0 YAML
spec for ``POST /api/v1/jobs/createTask`` — including the official ``model``
enum string, input properties, duration enums, and reference limits. The
Veo3.1 API section uses the same embedded-YAML convention with a bespoke
body shape (top-level ``model`` enum + ``generationType``).

Pass 1 enumerate: parse llms.txt for video-model doc pages.
Pass 2 filter: Adept-relevant video generation (drop upscale/extend/edit/
callback/avatar utility pages; V2V rows kept but flagged).
Pass 3 schema-inspect: fetch only candidate pages, parse the embedded
OpenAPI YAML. Pages without a machine-readable spec (e.g. prose-only
runway-api quickstart) are skipped and counted in ``unparsed`` — never
prose-scraped into fake capability claims. Public docs: no API key
required, no generation calls.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import yaml

from ..catalog_contract import CatalogVideoRow

LLMS_INDEX_URL = "https://docs.kie.ai/llms.txt"

_INDEX_LINK_RE = re.compile(r"^-+\s*(?P<section>.*?)\[(?P<title>[^\]]+)\]\((?P<url>https://docs\.kie\.ai/[^)]+)\)")

# Doc sections whose pages carry machine-readable generation specs.
_INCLUDE_PREFIXES = ("/market/", "/veo3-api/", "/runway-api/")

# Pages that are not generation endpoints Adept can surface.
_EXCLUDE_SLUG_TOKENS = (
    "upscale",
    "extend",
    "callback",
    "get-task",
    "quickstart",
    "videoedit",
    "video-edit",
    "ai-avatar",
    "motion-control",
    "speech-to-video",
    "from-audio",
    "effect",
    "template",
    "record-detail",
    "details",
    "lip-sync",
    "lipsync",
    "human-identification",
    "subject-detection",
)

_FAMILY_TOKENS: tuple[tuple[str, str], ...] = (
    ("seedance", "seedance"),
    ("bytedance", "seedance"),
    ("kling", "kling"),
    ("veo", "veo"),
    ("hailuo", "minimax"),
    ("minimax", "minimax"),
    ("runway", "runway"),
    ("aleph", "runway"),
    ("wan", "wan"),
    ("hunyuan", "hunyuan"),
    ("ltx", "ltx"),
    ("vidu", "vidu"),
    ("pixverse", "pixverse"),
    ("pika", "pika"),
    ("luma", "luma"),
    ("sora", "sora"),
    ("grok-imagine", "grok-imagine"),
    ("happy-horse", "happy-horse"),
    ("happyhorse", "happy-horse"),
    ("omnihuman", "omnihuman"),
    ("gemini", "gemini-omni"),
)

_VERSION_RE = re.compile(r"(?:^|[/\-_\s])v?(\d+(?:\.\d+)?)(?:$|[/\-_\s])")
_TIER_TOKENS = ("pro", "turbo", "fast", "mini", "standard", "lite", "max", "plus", "master", "omni", "flash")

_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(?P<yaml>.*?)```", re.DOTALL)

# Body properties that are transport/control, not generation inputs.
_CONTROL_PROPS = {"callBackUrl", "callback_url", "enableFallback", "webhookUrl"}


def _looks_bogus(body: str | None) -> bool:
    """Detect a bogus doc-page body (CDN challenge / interstitial / error page).

    Kie doc pages are served as markdown (llms.txt convention) and start with
    ``# Title``. An HTML body means the real markdown was not served — the
    fetch must be retried, and if it stays bogus the page counts as FAILED
    (never silently as "nospec", which would make a partial census look
    complete). Checked tight — leading markup or a challenge title in the
    first KB — so legit prose pages with HTML snippets in examples are never
    misclassified.
    """
    stripped = (body or "").lstrip()
    if not stripped:
        return True
    head = stripped[:4096].lower()
    return stripped.startswith("<") or "just a moment" in head or "challenge-platform" in head


def _classify_family(text: str) -> str:
    low = text.lower()
    for token, family in _FAMILY_TOKENS:
        if token in low:
            return family
    return ""


def _classify_version(text: str) -> str | None:
    m = _VERSION_RE.search(text.lower())
    return m.group(1) if m else None


def _classify_tier(text: str) -> str | None:
    low = text.lower()
    for token in _TIER_TOKENS:
        if re.search(rf"(?:^|[/\-_\s]){re.escape(token)}(?:$|[/\-_\s])", low):
            return token
    return None


def parse_kie_market_index(llms_txt: str) -> list[dict[str, str]]:
    """Pass 1+2: enumerate video-model doc pages from the docs index.

    Pure function — fixture-testable. Returns candidate entries:
    {title, url, section, slug}.
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in (llms_txt or "").splitlines():
        m = _INDEX_LINK_RE.match(line.strip())
        if not m:
            continue
        url = m.group("url")
        title = m.group("title").strip()
        section = m.group("section").strip()
        if "/cn/" in url:
            continue  # Chinese mirror duplicates
        path = "/" + url.split("docs.kie.ai/", 1)[-1]
        if not any(path.startswith(f"/{p.strip('/')}/") for p in _INCLUDE_PREFIXES):
            continue
        slug = url.rsplit("/", 1)[-1].removesuffix(".md")
        low = f"{url} {title}".lower()
        if any(token in low for token in _EXCLUDE_SLUG_TOKENS):
            continue
        is_video_section = "video" in section.lower()
        is_video_slug = "video" in low
        if not (is_video_section or is_video_slug):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "section": section, "slug": slug})
    return out


def _post_body_schema(spec: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (api_path, request body schema) for the spec's POST operation."""
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return "", {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        post = path_item.get("post")
        if not isinstance(post, dict):
            continue
        schema = (
            post.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
            return str(path), schema
    return "", {}


_MODEL_EXAMPLE_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')
_MODEL_MUST_BE_RE = re.compile(r"[Mm]ust be `([^`]+)`")


def _resolve_model_ids(model_prop: dict[str, Any], schema: dict[str, Any]) -> tuple[list[str], str | None]:
    """Resolve official model string(s); detect docs enum/example disagreements.

    Kie docs occasionally ship a copy-pasted enum (e.g. the Kling v2.5-turbo
    I2V Pro page whose enum says ``kling/v2-1-master-image-to-video`` while
    the description and example require ``kling/v2-5-turbo-image-to-video-pro``).
    The description's "Must be `X`" and the schema-level example JSON are the
    stronger signal. Returns (model_ids, disagreement_note).
    """
    enum_ids = [str(v) for v in _enum_list(model_prop)]
    desc = str(model_prop.get("description") or "") if isinstance(model_prop, dict) else ""
    must = _MODEL_MUST_BE_RE.search(desc)
    example_id: str | None = None
    example = schema.get("example") if isinstance(schema, dict) else None
    if isinstance(example, str):
        m = _MODEL_EXAMPLE_RE.search(example)
        if m:
            example_id = m.group(1)
    chosen = (must.group(1) if must else None) or example_id
    if chosen and enum_ids and chosen not in enum_ids:
        return [chosen], (
            f"docs model enum {enum_ids} disagrees with example/description "
            f"'{chosen}'; used the example value"
        )
    if chosen and not enum_ids:
        return [chosen], None
    if not enum_ids and isinstance(model_prop, dict) and model_prop.get("default"):
        return [str(model_prop["default"])], None
    return enum_ids, None


def _merge_input_variants(input_prop: dict[str, Any]) -> tuple[dict[str, Any], list[set[str]]]:
    """Union the properties across oneOf/anyOf input variants.

    Also returns each variant's required set so mode inference can tell an
    optional image input (T2V-capable) from a required one (I2V-only).
    """
    props: dict[str, Any] = {}
    variants: list[dict[str, Any]] = []
    if isinstance(input_prop.get("properties"), dict):
        variants.append(input_prop)
    for key in ("oneOf", "anyOf"):
        for variant in input_prop.get(key) or []:
            if isinstance(variant, dict) and isinstance(variant.get("properties"), dict):
                variants.append(variant)
    requireds: list[set[str]] = []
    for variant in variants:
        req = variant.get("required")
        requireds.append({str(v) for v in req} if isinstance(req, list) else set())
        for name, prop in variant["properties"].items():
            if name not in props or (isinstance(prop, dict) and len(prop) > len(props[name])):
                props[name] = prop
    return props, requireds


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*s?\s*$", value)
        if m:
            return float(m.group(1))
    return None


def _enum_list(prop: Any) -> list[Any]:
    if isinstance(prop, dict) and isinstance(prop.get("enum"), list):
        return prop["enum"]
    return []


def _max_items(prop: Any) -> int:
    if isinstance(prop, dict):
        hi = prop.get("maxItems") or prop.get("max_items")
        if isinstance(hi, int) and hi > 0:
            return hi
        return 1
    return 0


# Input-property vocabularies (Kie docs use several naming generations).
_IMAGE_INPUT_PROPS = {
    "image_url", "image_urls", "imageUrls", "images", "image",
    "start_image", "start_image_url", "first_frame", "first_frame_url",
    "first_frame_image", "start_frame", "start_frame_url",
    "input_image", "input_images",
}
_FIRST_FRAME_PROPS = {
    "image_url", "start_image", "start_image_url", "first_frame",
    "first_frame_url", "first_frame_image", "start_frame", "start_frame_url",
    "image_urls", "imageUrls",
}
_LAST_FRAME_PROPS = {
    "end_image", "end_image_url", "last_frame", "last_frame_url",
    "tail_image", "tail_image_url", "end_frame", "end_frame_url",
}
_REF_IMAGE_PROPS = {
    "image_urls", "imageUrls", "images", "reference_images",
    "reference_image_urls", "references", "reference_urls",
}
_REF_VIDEO_PROPS = {
    "video_urls", "videoUrls", "videos", "reference_videos", "reference_video_urls",
}
_V2V_INPUT_PROPS = {"video_url", "videoUrl", "input_video", "source_video"}
_AUDIO_OUT_PROPS = {"generate_audio", "generateAudio", "audio", "enable_audio", "with_audio"}

_DUR_RANGE_RES = (
    re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*s(?:econds?)?\b"),
    re.compile(r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]\s*s\b"),
)


def _mode_flags(slug_title_model: str, props: dict[str, Any]) -> dict[str, bool]:
    """Mode flags from naming plus an explicit generationType enum when present."""
    hay = slug_title_model.lower()
    t2v = "text-to-video" in hay
    i2v = "image-to-video" in hay
    r2v = "reference-to-video" in hay or "r2v" in hay
    flf = "first-last" in hay or "flf" in hay or "transition" in hay
    v2v = "video-to-video" in hay

    gen_type = _enum_list(props.get("generationType"))
    if gen_type:
        tokens = {str(v).upper() for v in gen_type}
        t2v = t2v or "TEXT_2_VIDEO" in tokens
        flf = flf or "FIRST_AND_LAST_FRAMES_2_VIDEO" in tokens
        i2v = i2v or flf or "IMAGE_2_VIDEO" in tokens
        r2v = r2v or "REFERENCE_2_VIDEO" in tokens
    return {"t2v": t2v, "i2v": i2v, "r2v": r2v, "flf": flf, "v2v": v2v}


def _infer_unified_modes(modes: dict[str, bool], props: dict[str, Any], requireds: list[set[str]]) -> None:
    """Unified omni endpoints (Seedance 2.x, Kling 2.1 Pro, Wan 3.0, Gemini
    Omni) carry no mode suffix — the mode is implied by which optional inputs
    the caller provides. When naming found no mode, infer from the schema:
    optional image input -> T2V+I2V; reference props -> R2V; first+last props
    -> FLF; a singular input video -> V2V. Mutates ``modes`` in place."""
    if any(modes.values()):
        return
    keys = set(props.keys())
    img_present = bool(_IMAGE_INPUT_PROPS & keys)
    img_required_all = bool(requireds) and all(bool(_IMAGE_INPUT_PROPS & req) for req in requireds)
    modes["t2v"] = "prompt" in props and not img_required_all
    modes["i2v"] = img_present
    modes["r2v"] = bool((_REF_IMAGE_PROPS | _REF_VIDEO_PROPS) & keys)
    modes["flf"] = bool(_FIRST_FRAME_PROPS & keys) and bool(_LAST_FRAME_PROPS & keys)
    modes["v2v"] = bool(_V2V_INPUT_PROPS & keys)


def parse_kie_market_page(entry: dict[str, str], markdown: str) -> list[CatalogVideoRow]:
    """Pass 3: parse one doc page's embedded OpenAPI YAML into catalog rows.

    Returns one row per model enum value (multi-model endpoints like Veo
    expand into veo3 / veo3_fast / veo3_lite). Empty list when the page has
    no machine-readable spec. Pure function — fixture-testable, no network.
    """
    match = _YAML_BLOCK_RE.search(markdown or "")
    if not match:
        return []
    try:
        spec = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError:
        return []
    if not isinstance(spec, dict):
        return []

    api_path, body_schema = _post_body_schema(spec)
    if not body_schema:
        return []
    body_props = body_schema.get("properties") or {}

    # Market shape: model enum + input object. Bespoke shape (veo3-api):
    # top-level generation properties with a multi-value model enum.
    model_prop = body_props.get("model") or {}
    model_ids, model_note = _resolve_model_ids(model_prop, body_schema)
    requireds: list[set[str]] = []
    if "input" in body_props:
        props, requireds = _merge_input_variants(body_props.get("input") or {})
    else:
        props = {k: v for k, v in body_props.items() if k not in _CONTROL_PROPS and k != "model"}
        req = body_schema.get("required")
        requireds = [{str(v) for v in req} if isinstance(req, list) else set()]
    if not model_ids:
        return []

    slug = entry.get("slug", "")
    title = entry.get("title", "")

    rows: list[CatalogVideoRow] = []
    for model_id in model_ids:
        hay = f"{model_id} {slug} {title}"
        modes = _mode_flags(hay, props)
        _infer_unified_modes(modes, props, requireds)

        keys = set(props.keys())
        first_frame = modes["i2v"] or modes["flf"] or bool(_FIRST_FRAME_PROPS & keys)
        last_frame = modes["flf"] or bool(_LAST_FRAME_PROPS & keys)

        max_ref_images = 0
        for key in _REF_IMAGE_PROPS:
            max_ref_images = max(max_ref_images, _max_items(props.get(key)))
        if modes["r2v"] and max_ref_images == 0:
            max_ref_images = 1  # R2V implies >=1 reference; exact cap UNVERIFIED
        max_ref_videos = 0
        for key in _REF_VIDEO_PROPS | {"video_url"}:
            max_ref_videos = max(max_ref_videos, _max_items(props.get(key)))
        if modes["v2v"] and max_ref_videos == 0:
            max_ref_videos = 1

        durations: list[float] = []
        dur_min: float | None = None
        dur_max: float | None = None
        dur_prop = props.get("duration")
        if isinstance(dur_prop, dict):
            enums = [d for d in (_duration_seconds(v) for v in _enum_list(dur_prop)) if d is not None]
            if enums:
                durations = sorted(set(enums))
            lo, hi = dur_prop.get("minimum"), dur_prop.get("maximum")
            try:
                dur_min = float(lo) if lo is not None else None
                dur_max = float(hi) if hi is not None else None
            except (TypeError, ValueError):
                dur_min = dur_max = None
            if not durations and dur_min is None and dur_max is None:
                desc = str(dur_prop.get("description") or "")
                for rx in _DUR_RANGE_RES:
                    m = rx.search(desc)
                    if m:
                        dur_min, dur_max = float(m.group(1)), float(m.group(2))
                        break

        resolutions: list[str] = []
        for key in ("resolution", "size", "quality"):
            enums = [str(v) for v in _enum_list(props.get(key))]
            if enums:
                resolutions = enums
                break

        audio = bool(_AUDIO_OUT_PROPS & keys)
        # Veo3.1 docs: all videos ship with background audio by default.
        if not audio and "veo" in model_id.lower():
            audio = True

        notes_bits: list[str] = []
        if model_note:
            notes_bits.append(model_note)
        if modes["v2v"]:
            notes_bits.append("video-to-video endpoint (V2V not an Adept surface today)")
        if modes["r2v"] and max_ref_images <= 1:
            notes_bits.append("exact reference image cap UNVERIFIED from schema")

        rows.append(
            CatalogVideoRow(
                provider="kie",
                family=_classify_family(hay),
                model=title if len(model_ids) == 1 else f"{title} ({model_id})",
                version=_classify_version(f"{model_id} {slug}"),
                tier=_classify_tier(f"{model_id} {slug}"),
                endpoint=model_id,
                apiPath=api_path or None,
                t2v=modes["t2v"],
                i2v=modes["i2v"],
                r2v=modes["r2v"],
                firstFrame=first_frame,
                lastFrame=last_frame,
                references=max_ref_images,
                videoReferences=max_ref_videos,
                durationMinSec=dur_min,
                durationMaxSec=dur_max,
                durationsSec=durations,
                resolutions=resolutions,
                audio=audio,
                liveSubmit=False,  # no Adept Kie video submit path today
                status="verified",
                source="docs",
                notes="; ".join(notes_bits),
            )
        )
    return rows


async def fetch_kie_catalog(
    api_key: str | None = None,
    *,
    timeout_sec: float = 30.0,
    max_concurrency: int = 8,
) -> dict[str, Any]:
    """Enumerate + schema-inspect the Kie video catalog. Read-only.

    Kie docs are public; ``api_key`` is accepted for interface symmetry and
    future authenticated docs, never required.
    """
    del api_key
    try:
        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
            index_resp = await client.get(LLMS_INDEX_URL)
            if index_resp.status_code >= 400:
                return {
                    "ok": False,
                    "error": "HTTP_ERROR",
                    "message": f"docs.kie.ai index returned HTTP {index_resp.status_code}.",
                    "rows": [],
                    "mock": False,
                }
            entries = parse_kie_market_index(index_resp.text)
            if not entries:
                # A healthy index always yields entries — zero means the body
                # was not the index (CDN challenge page, truncated body, ...).
                # Fail honestly rather than reporting an empty catalog as ok.
                return {
                    "ok": False,
                    "error": "INDEX_EMPTY",
                    "message": "docs.kie.ai index parsed to zero candidate pages — unexpected body.",
                    "rows": [],
                    "mock": False,
                }

            semaphore = asyncio.Semaphore(max_concurrency)

            async def _fetch_page(entry: dict[str, str]) -> tuple[list[CatalogVideoRow], str]:
                """Return (rows, outcome): ok | nospec | failed (after retries).

                A fetched body that looks like an HTML challenge/interstitial
                is retried like a network error; a page that stays bogus is
                ``failed`` so the census is honestly marked incomplete.
                """
                async with semaphore:
                    text: str | None = None
                    for _attempt in range(3):
                        try:
                            resp = await client.get(entry["url"])
                        except Exception:
                            continue
                        if resp.status_code >= 400:
                            continue
                        if _looks_bogus(resp.text):
                            continue
                        text = resp.text
                        break
                    if text is None:
                        return [], "failed"
                    rows = parse_kie_market_page(entry, text)
                    return rows, ("ok" if rows else "nospec")

            parsed = await asyncio.gather(*(_fetch_page(e) for e in entries))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "rows": [], "mock": False}

    rows: list[CatalogVideoRow] = []
    unparsed = 0
    fetch_failures: list[str] = []
    for (page_rows, outcome), entry in zip(parsed, entries):
        rows.extend(page_rows)
        if outcome == "nospec":
            unparsed += 1
        elif outcome == "failed":
            fetch_failures.append(entry["url"])
    rows.sort(key=lambda r: (r.family, r.version or "", r.tier or "", r.endpoint))
    return {
        "ok": True,
        "rows": rows,
        "rawCount": len(entries),
        "schemaCount": len(rows),
        "unparsed": unparsed,
        "fetchFailures": fetch_failures,
        # Incomplete when any candidate page failed to fetch — removal diff
        # must not trust a partial census.
        "complete": not fetch_failures,
        "mock": False,
    }
