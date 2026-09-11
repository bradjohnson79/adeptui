"""Provider video catalog — parser fixtures, sync diff/review logic, predicates.

Pure-function fixtures only: no network, no paid calls, no provider keys.
"""

from __future__ import annotations

import json

import pytest

from app.hosted_providers.catalog_contract import (
    CatalogVideoRow,
    eligible_one_frame,
    eligible_text_to_video,
    eligible_three_frame,
    eligible_timeline_omni,
    surface_eligibility,
)
from app.hosted_providers.catalog_sources.wavespeed_catalog_source import (
    parse_wavespeed_models,
)
from app.hosted_providers.catalog_sources.kie_catalog_source import (
    parse_kie_market_index,
    parse_kie_market_page,
)
from app.hosted_providers.catalog_sources.fal_catalog_source import _row_from_model
from app.hosted_providers import catalog_sync


# ---------------------------------------------------------------------------
# WaveSpeed parser fixtures
# ---------------------------------------------------------------------------

WAVESPEED_FIXTURE = {
    "data": {
        "models": [
            {
                "model_id": "wavespeed-ai/seedance-2.5/text-to-video",
                "name": "Seedance 2.5 Text to Video",
                "type": "video",
                "base_price": 0.35,
                "api_path": "/api/v3/wavespeed-ai/seedance-2.5/text-to-video",
                "request_schema": {
                    "properties": {
                        "prompt": {"type": "string"},
                        "duration": {"enum": [4, 5, 6, 8, 10, 12, 15, 20, 30]},
                        "resolution": {"enum": ["480p", "720p", "1080p"]},
                        "generate_audio": {"type": "boolean"},
                    }
                },
            },
            {
                "model_id": "wavespeed-ai/kling-3.0/first-last-frame-to-video",
                "name": "Kling 3.0 FLF",
                "type": "video",
                "base_price": 0.2,
                "api_path": "/api/v3/wavespeed-ai/kling-3.0/first-last-frame-to-video",
                "request_schema": {
                    "properties": {
                        "prompt": {"type": "string"},
                        "first_frame": {"type": "string"},
                        "tail_image": {"type": "string"},
                        "duration": {"minimum": 3, "maximum": 15},
                    }
                },
            },
            {
                "model_id": "wavespeed-ai/video-upscaler-pro",
                "name": "Video Upscaler",
                "type": "video",
                "api_path": "/api/v3/wavespeed-ai/video-upscaler-pro",
            },
            {
                "model_id": "wavespeed-ai/flux-dev",
                "name": "Flux Dev",
                "type": "image",
                "api_path": "/api/v3/wavespeed-ai/flux-dev",
            },
        ]
    }
}


def test_wavespeed_parser_modes_and_schema():
    rows = parse_wavespeed_models(WAVESPEED_FIXTURE)
    by_endpoint = {r.endpoint: r for r in rows}
    # Upscaler excluded (video-adjacent non-generation); flux excluded (image).
    assert set(by_endpoint) == {
        "wavespeed-ai/seedance-2.5/text-to-video",
        "wavespeed-ai/kling-3.0/first-last-frame-to-video",
    }
    seedance = by_endpoint["wavespeed-ai/seedance-2.5/text-to-video"]
    assert seedance.t2v is True and seedance.i2v is False
    assert seedance.family == "seedance" and seedance.version == "2.5"
    assert seedance.durationsSec == [4, 5, 6, 8, 10, 12, 15, 20, 30]
    assert seedance.resolutions == ["480p", "720p", "1080p"]
    assert seedance.audio is True
    assert seedance.pricing == {"base_price": 0.35, "currency": "USD"}
    assert seedance.liveSubmit is False  # no Adept WaveSpeed video submit path

    flf = by_endpoint["wavespeed-ai/kling-3.0/first-last-frame-to-video"]
    assert flf.firstFrame is True and flf.lastFrame is True
    assert flf.durationMinSec == 3.0 and flf.durationMaxSec == 15.0
    assert flf.family == "kling" and flf.version == "3.0"


def test_wavespeed_parser_garbage_in_empty_out():
    assert parse_wavespeed_models(None) == []
    assert parse_wavespeed_models({"unexpected": True}) == []
    assert parse_wavespeed_models([{"no_id": True}]) == []


# ---------------------------------------------------------------------------
# Kie parser fixtures
# ---------------------------------------------------------------------------

KIE_INDEX_FIXTURE = """# Kie.ai Docs

--- Market [MiniMax H3 Text-to-Video](https://docs.kie.ai/market/minimax-h3/text-to-video.md)
--- Market [Kling v2.5 Turbo Pro Video](https://docs.kie.ai/market/kling/v2-5-turbo-pro-video.md)
--- Market [Video Upscale](https://docs.kie.ai/market/upscale/video-upscale.md)
--- Veo3 API [Veo 3.1 Video](https://docs.kie.ai/veo3-api/veo-3-1.md)
--- Market [中文镜像 Video](https://docs.kie.ai/cn/market/kling/v2-5-turbo-pro-video.md)
--- Image [Flux 2 Pro](https://docs.kie.ai/market/flux/2-pro.md)
"""

KIE_PAGE_FIXTURE = """# MiniMax H3 Text-to-Video

```yaml
openapi: 3.0.0
paths:
  /api/v1/jobs/createTask:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                model:
                  type: string
                  description: Must be `minimax-h3/t2v`.
                  enum: [minimax-h3/t2v]
                input:
                  type: object
                  properties:
                    prompt: {type: string}
                    duration:
                      type: integer
                      minimum: 4
                      maximum: 15
                    resolution: {enum: ["768P", "1080P"]}
              required: [model, input]
```
"""


def test_kie_index_filters_video_pages():
    entries = parse_kie_market_index(KIE_INDEX_FIXTURE)
    slugs = {e["slug"] for e in entries}
    assert "text-to-video" in slugs  # minimax-h3 t2v page
    assert "v2-5-turbo-pro-video" in slugs  # kling page
    assert "veo-3-1" in slugs  # veo3-api section
    # Excluded: upscale page, /cn/ mirror, image-only flux page.
    assert "video-upscale" not in slugs
    assert not any("/cn/" in e["url"] for e in entries)
    assert "2-pro" not in slugs


def test_kie_page_parse_market_shape():
    entry = {"slug": "text-to-video", "title": "MiniMax H3 Text-to-Video"}
    rows = parse_kie_market_page(entry, KIE_PAGE_FIXTURE)
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "kie"
    assert row.endpoint == "minimax-h3/t2v"
    assert row.family == "minimax"  # version None: "h3" has no separator before the digit
    assert row.t2v is True
    assert row.durationMinSec == 4.0 and row.durationMaxSec == 15.0
    assert row.resolutions == ["768P", "1080P"]
    assert row.liveSubmit is False


def test_kie_page_without_spec_returns_empty():
    assert parse_kie_market_page({"slug": "x", "title": "y"}, "prose only, no yaml") == []


# ---------------------------------------------------------------------------
# Fal row builder fixtures
# ---------------------------------------------------------------------------

def test_fal_row_from_model_modes_and_duration_enum():
    model = {
        "endpoint_id": "bytedance/seedance-2.5/image-to-video",
        "metadata": {
            "display_name": "Seedance 2.5 Image to Video",
            "category": "image-to-video",
            "description": "Seedance 2.5 I2V with native audio.",
        },
    }
    schema_props = {
        "prompt": {"type": "string"},
        "image_url": {"type": "string"},
        "end_image_url": {"type": "string"},
        "duration": {"enum": ["4", "5", "6", "8", "10", "12", "15", "20", "30"]},
        "resolution": {"enum": ["480p", "720p", "1080p"]},
        "generate_audio": {"type": "boolean"},
    }
    row = _row_from_model(model, schema_props=schema_props)
    assert row is not None
    assert row.provider == "fal"
    assert row.i2v is True and row.t2v is False
    assert row.firstFrame is True and row.lastFrame is True  # end_image_url prop
    assert row.family == "seedance" and row.version == "2.5"
    # Enum durations land in durationsSec (min/max stay None for enum props).
    assert 30.0 in row.durationsSec  # Seedance 2.5 ≤30s native
    assert row.durationMaxSec is None
    assert row.audio is True


def test_fal_row_from_model_rejects_non_video():
    model = {
        "endpoint_id": "fal-ai/flux/dev",
        "metadata": {"display_name": "Flux Dev", "category": "text-to-image", "description": ""},
    }
    assert _row_from_model(model, schema_props={}) is None


# ---------------------------------------------------------------------------
# catalog_sync diff / review logic (in-memory store via tmp_path)
# ---------------------------------------------------------------------------

def _row(provider: str, endpoint: str, **overrides) -> CatalogVideoRow:
    base = dict(
        provider=provider,
        family="seedance",
        model=endpoint,
        endpoint=endpoint,
        t2v=True,
        durationsSec=[4, 5, 6],
        status="verified",
        source="live_api",
    )
    base.update(overrides)
    return CatalogVideoRow(**base)


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    store = tmp_path / "provider_catalog.json"
    monkeypatch.setattr(catalog_sync, "_STORE_PATH", store)
    return store


def test_diff_new_rows_pending_review(isolated_store):
    merged, stats = catalog_sync._diff_rows([], [_row("fal", "a/t2v")], removable_providers={"fal"})
    assert stats["new"] == 1
    assert merged[0]["reviewStatus"] == "pending_review"
    assert merged[0]["rowId"] == "fal:a/t2v"


def test_diff_preserves_review_status_and_flags_capability_change(isolated_store):
    first, _ = catalog_sync._diff_rows([], [_row("fal", "a/t2v")], removable_providers={"fal"})
    # Approve the row, then change a capability field upstream.
    first[0]["reviewStatus"] = "approved"
    changed = _row("fal", "a/t2v", durationsSec=[4, 5, 6, 8, 10])
    merged, stats = catalog_sync._diff_rows(first, [changed], removable_providers={"fal"})
    assert stats["updated"] == 1
    assert merged[0]["reviewStatus"] == "approved"  # preserved
    assert merged[0]["providerChangedSinceReview"] is True  # flagged for re-review


def test_diff_removal_requires_complete_enumeration(isolated_store):
    first, _ = catalog_sync._diff_rows([], [_row("fal", "a/t2v")], removable_providers={"fal"})
    # Provider NOT in removable set (truncated/rate-limited fetch) → row kept as-is.
    merged, stats = catalog_sync._diff_rows(first, [], removable_providers=set())
    assert stats["removed"] == 0
    assert merged[0]["status"] != "removed_at_source"
    # Complete enumeration → marked removed_at_source (kept for audit, never deleted).
    merged2, stats2 = catalog_sync._diff_rows(first, [], removable_providers={"fal"})
    assert stats2["removed"] == 1
    assert merged2[0]["status"] == "removed_at_source"


def test_review_endpoint_roundtrip(isolated_store):
    catalog_sync.save_provider_catalog({"schemaVersion": 1, "rows": []})
    merged, _ = catalog_sync._diff_rows([], [_row("fal", "a/t2v")], removable_providers={"fal"})
    doc = catalog_sync.load_provider_catalog()
    doc["rows"] = merged
    catalog_sync.save_provider_catalog(doc)

    row = catalog_sync.review_endpoint("fal:a/t2v", "approved")
    assert row is not None and row["reviewStatus"] == "approved"
    row = catalog_sync.review_endpoint("fal:a/t2v", "hidden")
    assert row["reviewStatus"] == "hidden"
    row = catalog_sync.review_endpoint("fal:a/t2v", "pending_review")
    assert row["reviewStatus"] == "pending_review"
    assert catalog_sync.review_endpoint("fal:missing", "approved") is None
    with pytest.raises(ValueError):
        catalog_sync.review_endpoint("fal:a/t2v", "bogus")

    listed = catalog_sync.list_catalog(review_status="pending_review")
    assert [r["rowId"] for r in listed["rows"]] == ["fal:a/t2v"]


def test_live_submit_truth_limited_to_seedance_rows(isolated_store):
    rows = [
        _row("fal", "bytedance/seedance-2.0/text-to-video"),
        _row("fal", "bytedance/seedance-2.5/reference-to-video"),
        _row("fal", "fal-ai/kling-video/v3/pro/text-to-video"),
        _row("kie", "minimax-h3/t2v"),
    ]
    merged, _ = catalog_sync._diff_rows([], rows, removable_providers={"fal", "kie"})
    live = {r["rowId"]: r["liveSubmit"] for r in merged}
    assert live["fal:bytedance/seedance-2.0/text-to-video"] is True
    assert live["fal:bytedance/seedance-2.5/reference-to-video"] is True
    # Honest: no Adept live video submit for fal Kling or any Kie endpoint today.
    assert live["fal:fal-ai/kling-video/v3/pro/text-to-video"] is False
    assert live["kie:minimax-h3/t2v"] is False


# ---------------------------------------------------------------------------
# Surface predicates (catalog_contract)
# ---------------------------------------------------------------------------

def test_surface_predicates():
    t2v_only = _row("fal", "x/t2v", t2v=True, i2v=False, firstFrame=False)
    assert eligible_text_to_video(t2v_only) is True
    assert eligible_one_frame(t2v_only) is False

    i2v = _row("fal", "x/i2v", t2v=False, i2v=True, firstFrame=True)
    assert eligible_one_frame(i2v) is True
    assert eligible_text_to_video(i2v) is False

    flf = _row("fal", "x/flf", t2v=False, i2v=True, firstFrame=True, lastFrame=True)
    assert eligible_three_frame(flf) is True
    assert eligible_one_frame(flf) is True

    r2v = _row("fal", "x/r2v", t2v=False, i2v=False, firstFrame=False, r2v=True, references=3)
    assert eligible_timeline_omni(r2v) is True
    assert eligible_text_to_video(r2v) is False

    eligibility = surface_eligibility(r2v)
    assert eligibility["timeline_omni"] is True
    assert eligibility["text_to_video"] is False
