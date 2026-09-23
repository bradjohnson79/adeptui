"""Provider Catalog Sync — permanent read-only catalog refresh utility.

Replaces the 10-15 minute per-provider manual investigation. Orchestrates
the three catalog sources (WaveSpeed / fal / Kie), diffs against the stored
catalog, flags newly discovered endpoints ``pending_review`` (never
auto-exposed to creators), and persists to
``settings.data_dir/hosted_providers/provider_catalog.json`` following the
model_store.py pattern.

Hard rules (contract freeze 2026-09-10):
- Read-only against providers. Never submits a generation.
- Missing API key -> that provider's refresh is ``requires_setup``, never
  an error.
- New rows are ALWAYS ``pending_review``. ``approved`` only via the admin
  review endpoint; approval makes a row ELIGIBLE for registry merge — it is
  still never auto-exposed.
- Rows that vanish from a provider are marked ``removed_at_source`` and
  kept for audit, never silently deleted.
- ``liveSubmit`` is computed from Adept's actual live submit truth
  (LIVE_SUBMIT_ADAPTERS products + their resolved endpoints), never from
  what a provider catalog claims.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..secrets_store import get_secret
from .catalog_contract import CATALOG_SCHEMA_VERSION, CatalogVideoRow
from .catalog_sources.fal_catalog_source import fetch_fal_catalog
from .catalog_sources.kie_catalog_source import fetch_kie_catalog
from .catalog_sources.wavespeed_catalog_source import fetch_wavespeed_catalog
from .registry import PROVIDERS

_STORE_PATH = settings.data_dir / "hosted_providers" / "provider_catalog.json"

_SOURCES = {
    "fal": fetch_fal_catalog,
    "kie": fetch_kie_catalog,
    "wavespeed": fetch_wavespeed_catalog,
}

# Adept live video submit truth, derived from LIVE_SUBMIT_ADAPTERS products
# (seedance-2.0 / seedance-2.5 on fal) resolved to their fal_catalog.py
# per-mode endpoints. Kie has no video createTask path today (image-only
# adapter); WaveSpeed video submit is not wired. Everything else is
# liveSubmit=False no matter what the provider catalog says.
_LIVE_VIDEO_ROW_IDS = frozenset(
    {
        "fal:bytedance/seedance-2.0/text-to-video",
        "fal:bytedance/seedance-2.0/image-to-video",
        "fal:bytedance/seedance-2.0/reference-to-video",
        "fal:bytedance/seedance-2.0/mini/reference-to-video",
        "fal:bytedance/seedance-2.5/text-to-video",
        "fal:bytedance/seedance-2.5/image-to-video",
        "fal:bytedance/seedance-2.5/reference-to-video",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_path() -> Path:
    return _STORE_PATH


def load_provider_catalog() -> dict[str, Any]:
    path = _STORE_PATH
    if not path.is_file():
        return {
            "version": CATALOG_SCHEMA_VERSION,
            "updatedAt": None,
            "providers": {},
            "rows": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"version": CATALOG_SCHEMA_VERSION, "rows": []}
    except Exception:
        return {"version": CATALOG_SCHEMA_VERSION, "rows": [], "storeError": True}


def save_provider_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    path = _STORE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["version"] = CATALOG_SCHEMA_VERSION
    body["updatedAt"] = _now()
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return body


def _capability_hash(row: CatalogVideoRow) -> str:
    """Fingerprint of the capability fields a review decision is based on."""
    body = {
        "t2v": row.t2v,
        "i2v": row.i2v,
        "r2v": row.r2v,
        "firstFrame": row.firstFrame,
        "lastFrame": row.lastFrame,
        "references": row.references,
        "videoReferences": row.videoReferences,
        "durationMinSec": row.durationMinSec,
        "durationMaxSec": row.durationMaxSec,
        "durationsSec": row.durationsSec,
        "resolutions": row.resolutions,
        "audio": row.audio,
        "status": row.status,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _diff_rows(
    stored_rows: list[dict[str, Any]],
    fresh_rows: list[CatalogVideoRow],
    *,
    removable_providers: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge freshly fetched rows into stored rows.

    - New endpoint -> appended as pending_review.
    - Existing endpoint -> capability fields updated; reviewStatus preserved;
      a capability change on an approved/hidden row is flagged
      ``providerChangedSinceReview`` so a human can re-review.
    - Stored endpoint absent from the fresh fetch -> ``removed_at_source``
      (kept for audit, never deleted) — but ONLY when the row's provider
      produced a COMPLETE enumeration this refresh (``removable_providers``).
      A truncated/rate-limited fetch never removes anything.
    """
    now = _now()
    fresh_by_id = {row.row_id: row for row in fresh_rows}
    stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0}

    merged: list[dict[str, Any]] = []
    stored_by_id: dict[str, dict[str, Any]] = {}
    for stored in stored_rows:
        rid = str(stored.get("rowId") or "")
        if rid:
            stored_by_id[rid] = stored

    for rid, fresh in fresh_by_id.items():
        fresh.liveSubmit = rid in _LIVE_VIDEO_ROW_IDS
        body = json.loads(fresh.model_dump_json())
        body["rowId"] = rid
        body["lastSeenAt"] = now
        stored = stored_by_id.get(rid)
        if stored is None:
            body["reviewStatus"] = "pending_review"
            body["discoveredAt"] = now
            body["capabilityHash"] = _capability_hash(fresh)
            stats["new"] += 1
        else:
            body["reviewStatus"] = stored.get("reviewStatus") or "pending_review"
            body["discoveredAt"] = stored.get("discoveredAt") or now
            previous_hash = str(stored.get("capabilityHash") or "")
            new_hash = _capability_hash(fresh)
            body["capabilityHash"] = new_hash
            if previous_hash and previous_hash != new_hash:
                stats["updated"] += 1
                if body["reviewStatus"] != "pending_review":
                    body["providerChangedSinceReview"] = True
            else:
                stats["unchanged"] += 1
                if stored.get("providerChangedSinceReview"):
                    body["providerChangedSinceReview"] = True
        merged.append(body)

    for rid, stored in stored_by_id.items():
        if rid in fresh_by_id:
            continue
        if str(stored.get("provider") or "") in removable_providers:
            if stored.get("status") != "removed_at_source":
                stored = dict(stored)
                stored["status"] = "removed_at_source"
                stored["removedAt"] = now
                stats["removed"] += 1
        merged.append(stored)

    merged.sort(key=lambda r: (str(r.get("provider")), str(r.get("family") or ""), str(r.get("endpoint"))))
    return merged, stats


async def refresh_all(*, providers: list[str] | None = None, timeout_sec: float = 60.0) -> dict[str, Any]:
    """Refresh the stored catalog from all keyed providers. Read-only.

    Returns a summary dict; persists the merged catalog. A provider without
    a configured key contributes a ``requires_setup`` status and its stored
    rows (if any) are left untouched.
    """
    started = time.monotonic()
    selected = [p for p in (providers or list(_SOURCES)) if p in _SOURCES]

    async def _run(provider_id: str) -> tuple[str, dict[str, Any]]:
        definition = PROVIDERS.get(provider_id)
        api_key = get_secret(definition.secret_name) if definition else None
        if not api_key:
            return provider_id, {
                "ok": False,
                "error": "NOT_CONFIGURED",
                "message": f"No {definition.display_name if definition else provider_id} API key is configured.",
                "rows": [],
                "requiresSetup": True,
            }
        try:
            return provider_id, await _SOURCES[provider_id](api_key, timeout_sec=timeout_sec)
        except Exception as exc:  # noqa: BLE001
            return provider_id, {"ok": False, "error": "SOURCE_ERROR", "message": str(exc), "rows": []}

    results = dict(await asyncio.gather(*(_run(p) for p in selected)))

    stored = load_provider_catalog()
    stored_rows = [r for r in (stored.get("rows") or []) if isinstance(r, dict)]

    fresh_rows: list[CatalogVideoRow] = []
    provider_summaries: dict[str, Any] = {}
    for provider_id in selected:
        result = results.get(provider_id) or {"ok": False, "error": "NO_RESULT", "rows": []}
        rows = result.get("rows") or []
        fresh_rows.extend(rows)
        provider_summaries[provider_id] = {
            "status": (
                "requires_setup"
                if result.get("requiresSetup") or result.get("error") == "NOT_CONFIGURED"
                else ("ok" if result.get("ok") else "error")
            ),
            "error": None if result.get("ok") else result.get("error"),
            "message": None if result.get("ok") else result.get("message"),
            "rowCount": len(rows),
            "rawCount": result.get("rawCount"),
            "schemaCount": result.get("schemaCount"),
            "unparsed": result.get("unparsed"),
            "complete": bool(result.get("complete", True)) if result.get("ok") else False,
            "fetchFailures": result.get("fetchFailures") or result.get("schemaFailures") or [],
        }

    # Rows can be ADDED from any successful fetch (discovery is opportunistic);
    # REMOVAL requires a complete enumeration from that provider.
    participating = {pid for pid, s in provider_summaries.items() if s["status"] == "ok"}
    removable = {pid for pid in participating if provider_summaries[pid]["complete"]}
    merged, stats = _diff_rows(
        [r for r in stored_rows if r.get("provider") in participating],
        fresh_rows,
        removable_providers=removable,
    )
    merged.extend(r for r in stored_rows if r.get("provider") not in participating)
    merged.sort(key=lambda r: (str(r.get("provider")), str(r.get("family") or ""), str(r.get("endpoint"))))

    pending = sum(1 for r in merged if r.get("reviewStatus") == "pending_review")
    payload = save_provider_catalog(
        {
            "providers": provider_summaries,
            "rows": merged,
            "lastRefresh": {
                "at": _now(),
                "durationMs": int((time.monotonic() - started) * 1000),
                "providers": list(selected),
                **stats,
            },
        }
    )
    return {
        "ok": all(s["status"] in ("ok", "requires_setup") for s in provider_summaries.values()),
        "providers": provider_summaries,
        "totalRows": len(merged),
        "pendingReview": pending,
        "new": stats["new"],
        "updated": stats["updated"],
        "removed": stats["removed"],
        "durationMs": payload["lastRefresh"]["durationMs"],
        "updatedAt": payload["updatedAt"],
    }


def list_catalog(*, provider: str | None = None, review_status: str | None = None) -> dict[str, Any]:
    """Read the stored catalog (optionally filtered). Never hits the network."""
    cat = load_provider_catalog()
    rows = [r for r in (cat.get("rows") or []) if isinstance(r, dict)]
    if provider:
        rows = [r for r in rows if r.get("provider") == provider]
    if review_status:
        rows = [r for r in rows if r.get("reviewStatus") == review_status]
    return {
        "updatedAt": cat.get("updatedAt"),
        "providers": cat.get("providers") or {},
        "lastRefresh": cat.get("lastRefresh"),
        "totalRows": len(rows),
        "pendingReview": sum(1 for r in rows if r.get("reviewStatus") == "pending_review"),
        "rows": rows,
    }


def review_endpoint(row_id: str, action: str) -> dict[str, Any] | None:
    """Apply an admin review decision. ``approved`` makes the row eligible
    for registry merge; ``hidden`` removes it from consideration. Neither
    exposes anything to creators by itself."""
    if action not in ("approved", "hidden", "pending_review"):
        raise ValueError(f"invalid review action: {action}")
    cat = load_provider_catalog()
    rows = cat.get("rows") or []
    target: dict[str, Any] | None = None
    for row in rows:
        if isinstance(row, dict) and row.get("rowId") == row_id:
            row["reviewStatus"] = action
            row["reviewedAt"] = _now()
            row.pop("providerChangedSinceReview", None)
            target = row
            break
    if target is None:
        return None
    cat["rows"] = rows
    save_provider_catalog(cat)
    return target
