"""ProviderUsageRecord persistence — estimated vs confirmed, never secrets."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .rate_cards import estimate_cost, get_rate_card

_LOCK = threading.RLock()


def ledger_path() -> Path:
    return settings.data_dir / "provider_usage_ledger.json"


def _load() -> dict[str, Any]:
    path = ledger_path()
    if not path.exists():
        return {"schemaVersion": 1, "records": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"schemaVersion": 1, "records": []}
        if not isinstance(raw.get("records"), list):
            raw["records"] = []
        return raw
    except (OSError, ValueError, TypeError):
        return {"schemaVersion": 1, "records": []}


def _save(data: dict[str, Any]) -> dict[str, Any]:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return data


def record_usage(
    *,
    provider_id: str,
    model_id: str | None = None,
    capability: str = "image",
    project_id: str | None = None,
    job_id: str | None = None,
    tool: str | None = None,
    user_action: str | None = None,
    workspace_origin: str | None = None,
    units: float = 1.0,
    estimated_cost: float | None = None,
    confirmed_cost: float | None = None,
    currency: str = "USD",
    pricing_source: str | None = None,
    status: str = "estimated",
    billing_status: str = "pending",
    failure_stage: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a ProviderUsageRecord. Never store API keys."""
    card = get_rate_card(provider_id)
    est = estimate_cost(provider_id, capability=capability, units=units)
    if estimated_cost is None:
        estimated_cost = est.get("estimatedCost")
    record = {
        "usageId": str(uuid.uuid4()),
        "providerId": (provider_id or "").strip().lower(),
        "modelId": model_id,
        "capability": capability,
        "projectId": project_id,
        "jobId": job_id,
        "tool": tool,
        "userAction": user_action,
        "workspaceOrigin": workspace_origin or "unknown",
        "units": float(units),
        "estimatedCost": estimated_cost,
        "confirmedCost": confirmed_cost,
        "currency": currency or card.get("currency") or "USD",
        "pricingSource": pricing_source or est.get("pricingSource") or "static_estimate",
        "rateCardVersion": card.get("version"),
        "status": status,  # estimated | confirmed | failed | cancelled | unknown
        "billingStatus": billing_status,  # pending | confirmed | unknown | refunded
        "failureStage": failure_stage,  # before_submit | after_accept | cancel | timeout | None
        "disclaimer": est.get("disclaimer"),
        "metadata": {k: v for k, v in (metadata or {}).items() if "key" not in k.lower() and "secret" not in k.lower()},
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        data = _load()
        data["records"].append(record)
        # Cap ledger growth
        if len(data["records"]) > 5000:
            data["records"] = data["records"][-4000:]
        _save(data)
    return record


def list_usage(
    *,
    project_id: str | None = None,
    provider_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with _LOCK:
        records = list(_load().get("records") or [])
    if project_id:
        records = [r for r in records if r.get("projectId") == project_id]
    if provider_id:
        pid = provider_id.lower()
        records = [r for r in records if r.get("providerId") == pid]
    records.sort(key=lambda r: str(r.get("createdAt") or ""), reverse=True)
    return records[: max(1, min(limit, 1000))]


def summarize_spend(
    *,
    project_id: str | None = None,
    provider_id: str | None = None,
) -> dict[str, Any]:
    records = list_usage(project_id=project_id, provider_id=provider_id, limit=5000)
    confirmed = 0.0
    estimated = 0.0
    unknown = 0
    by_provider: dict[str, dict[str, float]] = {}
    by_capability: dict[str, dict[str, float]] = {}
    for r in records:
        pid = str(r.get("providerId") or "unknown")
        cap = str(r.get("capability") or "unknown")
        by_provider.setdefault(pid, {"confirmed": 0.0, "estimated": 0.0})
        by_capability.setdefault(cap, {"confirmed": 0.0, "estimated": 0.0})
        cc = r.get("confirmedCost")
        ec = r.get("estimatedCost")
        if isinstance(cc, (int, float)):
            confirmed += float(cc)
            by_provider[pid]["confirmed"] += float(cc)
            by_capability[cap]["confirmed"] += float(cc)
        elif isinstance(ec, (int, float)):
            estimated += float(ec)
            by_provider[pid]["estimated"] += float(ec)
            by_capability[cap]["estimated"] += float(ec)
        else:
            unknown += 1
        if r.get("billingStatus") == "unknown" or r.get("status") == "unknown":
            unknown += 1
    return {
        "confirmedSpend": round(confirmed, 6),
        "estimatedPending": round(estimated, 6),
        "totalProjected": round(confirmed + estimated, 6),
        "unknownBillingCount": unknown,
        "currency": "USD",
        "byProvider": by_provider,
        "byCapability": by_capability,
        "recordCount": len(records),
        "disclaimer": "Confirmed vs estimated — estimates are not exact charges.",
        "mock": False,
    }
