from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

ProgressCb = Optional[Callable[[float, str], Awaitable[None]]]
RequestIdCb = Optional[Callable[[str], Awaitable[None]]]

# Any real endpoint id works for an authorized probe; the request id below never exists,
# so fal answers 404 for an accepted key and 401/403 for a rejected one. No job is created
# and nothing is billed.
_PROBE_MODEL_ID = "fal-ai/veo3.1"


class FalApiError(RuntimeError):
    pass


class FalAuthError(FalApiError):
    """fal rejected the credential itself (as opposed to the request)."""


async def upload_file_to_fal(path: Path, api_key: str) -> str:
    """Upload a local file to fal CDN and return a public URL."""
    if not path.exists():
        raise FalApiError(f"File not found: {path}")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Preferred: fal CDN v3 initiate + PUT
        init = await client.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            params={
                "file_name": path.name,
                "content_type": content_type,
            },
            headers={"Authorization": f"Key {api_key}"},
        )
        if init.status_code < 400:
            payload = init.json()
            upload_url = payload.get("upload_url") or payload.get("put_url")
            file_url = payload.get("file_url") or payload.get("url")
            if upload_url and file_url:
                put = await client.put(
                    upload_url,
                    content=data,
                    headers={"Content-Type": content_type, "Authorization": f"Key {api_key}"},
                )
                if put.status_code >= 400:
                    raise FalApiError(f"fal upload PUT failed ({put.status_code}): {put.text[:400]}")
                return file_url

        # Fallback: multipart to fal media
        multi = await client.post(
            "https://fal.media/files/upload",
            headers={"Authorization": f"Key {api_key}"},
            files={"file": (path.name, data, content_type)},
        )
        if multi.status_code < 400:
            body = multi.json()
            url = body.get("access_url") or body.get("url") or body.get("file_url")
            if url:
                return url

        raise FalApiError(
            "Could not upload file to fal.ai storage. "
            f"initiate={init.status_code} media={multi.status_code}: {(multi.text or init.text)[:400]}"
        )


async def validate_fal_key(api_key: str, *, timeout_sec: float = 15.0) -> dict[str, Any]:
    """Probe fal with the supplied key on a real authorized endpoint.

    Returns `{"valid": bool|None, ...}` where `None` means the probe itself could not be
    completed (network/service problem) — that is reported as unverified rather than
    silently treated as either success or a bad key.
    """
    key = (api_key or "").strip()
    out: dict[str, Any] = {
        "valid": None,
        "status": "unverified",
        "httpStatus": None,
        "message": "",
        "probeEndpoint": _PROBE_MODEL_ID,
    }
    if not key:
        out.update(valid=False, status="invalid", message="No API key supplied.")
        return out

    url = f"https://queue.fal.run/{_PROBE_MODEL_ID}/requests/{uuid.uuid4().hex}/status"
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(url, headers=_headers(key))
    except Exception as exc:  # noqa: BLE001 - network failure is "unverified", not "invalid"
        out["message"] = f"Could not reach fal.ai to verify the key: {exc}"
        return out

    out["httpStatus"] = response.status_code
    if response.status_code in (401, 403):
        out.update(
            valid=False,
            status="invalid",
            message="fal.ai rejected this API key. Check the key at fal.ai/dashboard/keys.",
        )
        return out
    if response.status_code < 500:
        # 404 (unknown request id) proves the key authenticated successfully.
        out.update(valid=True, status="verified", message="Key accepted by fal.ai.")
        return out
    out["message"] = f"fal.ai returned HTTP {response.status_code}; key could not be verified."
    return out


async def run_fal_model(
    model_id: str,
    arguments: dict[str, Any],
    api_key: str,
    *,
    on_progress: ProgressCb = None,
    on_request_id: RequestIdCb = None,
    poll_interval: float = 2.0,
    timeout_sec: float = 900.0,
) -> dict[str, Any]:
    """
    Submit to fal queue and wait for completion.
    Docs: https://docs.fal.ai/model-apis/model-endpoints/queue
    """
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        submit = await client.post(
            f"https://queue.fal.run/{model_id}",
            headers=headers,
            json=arguments,
        )
        if submit.status_code in (401, 403):
            raise FalAuthError(
                f"fal.ai rejected the API key ({submit.status_code}). "
                "Re-save a valid key in Project Settings → Integrations."
            )
        if submit.status_code >= 400:
            raise FalApiError(f"fal submit failed ({submit.status_code}): {submit.text[:800]}")
        meta = submit.json()
        status_url = meta.get("status_url")
        response_url = meta.get("response_url")
        request_id = meta.get("request_id") or meta.get("requestId")
        if request_id and on_request_id:
            await on_request_id(str(request_id))
        if not status_url:
            # Some responses are already completed inline
            if "video" in meta or "images" in meta:
                return meta
            raise FalApiError(f"fal submit missing status_url: {meta}")

        if on_progress:
            await on_progress(0.1, f"fal queued ({request_id or model_id})")

        elapsed = 0.0
        while elapsed < timeout_sec:
            st = await client.get(status_url, headers=headers)
            if st.status_code >= 400:
                raise FalApiError(f"fal status failed ({st.status_code}): {st.text[:500]}")
            body = st.json()
            status = (body.get("status") or "").upper()
            logs = body.get("logs") or []
            log_msg = ""
            if logs:
                last = logs[-1]
                log_msg = last.get("message") if isinstance(last, dict) else str(last)

            if status in ("IN_QUEUE", "IN_PROGRESS"):
                p = 0.25 if status == "IN_QUEUE" else 0.55
                if on_progress:
                    await on_progress(p, log_msg or f"fal {status.lower().replace('_', ' ')}")
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            if status == "COMPLETED":
                if on_progress:
                    await on_progress(0.9, "fal completed — downloading")
                if response_url:
                    resp = await client.get(response_url, headers=headers)
                    if resp.status_code >= 400:
                        raise FalApiError(f"fal result failed ({resp.status_code}): {resp.text[:500]}")
                    return resp.json()
                return body.get("response") or body

            if status in ("FAILED", "CANCELLED", "ERROR"):
                err = body.get("error") or body.get("message") or body
                raise FalApiError(f"fal job {status}: {err}")

            # Unknown — keep polling briefly
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise FalApiError(f"fal job timed out after {timeout_sec:.0f}s ({model_id})")


async def download_url(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        r = await client.get(url)
        if r.status_code >= 400:
            raise FalApiError(f"Download failed ({r.status_code}): {url}")
        dest.write_bytes(r.content)
    return dest


def extract_video_url(result: dict[str, Any]) -> str:
    video = result.get("video")
    if isinstance(video, dict) and video.get("url"):
        return video["url"]
    if isinstance(video, str) and video.startswith("http"):
        return video
    # nested data
    data = result.get("data")
    if isinstance(data, dict):
        return extract_video_url(data)
    raise FalApiError(f"No video URL in fal result keys={list(result.keys())}")


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Key {api_key}", "Accept": "application/json"}


async def fetch_fal_account_usage(api_key: str, *, days: int = 30) -> dict[str, Any]:
    """
    Pull credit balance + recent usage/spend from fal Platform APIs.
    Billing/usage typically need an ADMIN-scoped key; we degrade gracefully.
    """
    from datetime import datetime, timedelta, timezone

    days = max(1, min(90, int(days)))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_s = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    out: dict[str, Any] = {
        "ok": False,
        "configured": True,
        "username": None,
        "balance": None,
        "currency": "USD",
        "period_days": days,
        "period_start": start_s,
        "period_end": end_s,
        "usage_units": 0.0,
        "usage_unit_label": "units",
        "spend": 0.0,
        "request_count": 0,
        "top_endpoints": [],
        "manage_url": "https://fal.ai/dashboard/usage",
        "billing_url": "https://fal.ai/dashboard/billing",
        "keys_url": "https://fal.ai/dashboard/keys",
        "login_url": "https://fal.ai/login",
        "message": "",
        "needs_admin_key": False,
        "errors": [],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Credit balance
        try:
            bill = await client.get(
                "https://api.fal.ai/v1/account/billing",
                params={"expand": "credits"},
                headers=_headers(api_key),
            )
            if bill.status_code == 200:
                body = bill.json()
                out["username"] = body.get("username")
                credits = body.get("credits") or {}
                if "current_balance" in credits:
                    out["balance"] = float(credits["current_balance"])
                    out["currency"] = credits.get("currency") or "USD"
                    out["ok"] = True
            elif bill.status_code in (401, 403):
                out["needs_admin_key"] = True
                out["errors"].append("billing requires an ADMIN-scoped fal key")
            else:
                out["errors"].append(f"billing HTTP {bill.status_code}")
        except Exception as exc:
            out["errors"].append(f"billing: {exc}")

        # Usage / spend for the period
        try:
            usage = await client.get(
                "https://api.fal.ai/v1/models/usage",
                params={
                    "start": start_s,
                    "end": end_s,
                    "expand": "summary",
                    "limit": 100,
                    "timeframe": "day",
                },
                headers=_headers(api_key),
            )
            if usage.status_code == 200:
                body = usage.json()
                summary = body.get("summary") or []
                spend = 0.0
                units = 0.0
                unit_counts: dict[str, float] = {}
                endpoints: list[dict[str, Any]] = []
                for row in summary:
                    cost = float(row.get("cost") or 0)
                    qty = float(row.get("quantity") or 0)
                    unit = str(row.get("unit") or "unit")
                    spend += cost
                    units += qty
                    unit_counts[unit] = unit_counts.get(unit, 0.0) + qty
                    endpoints.append(
                        {
                            "endpoint_id": row.get("endpoint_id") or "",
                            "quantity": qty,
                            "unit": unit,
                            "cost": cost,
                            "currency": row.get("currency") or out["currency"],
                        }
                    )
                endpoints.sort(key=lambda r: r["cost"], reverse=True)
                out["spend"] = round(spend, 4)
                out["usage_units"] = round(units, 4)
                out["request_count"] = len(summary)
                out["top_endpoints"] = endpoints[:5]
                if unit_counts:
                    # Prefer "video" label if present, else most-used unit
                    if "video" in unit_counts:
                        out["usage_unit_label"] = "video units"
                        out["usage_units"] = round(unit_counts["video"], 4)
                    else:
                        top_unit = max(unit_counts.items(), key=lambda kv: kv[1])[0]
                        out["usage_unit_label"] = f"{top_unit}s" if not top_unit.endswith("s") else top_unit
                        out["usage_units"] = round(unit_counts[top_unit], 4)
                out["ok"] = True
            elif usage.status_code in (401, 403):
                out["needs_admin_key"] = True
                out["errors"].append("usage requires an ADMIN-scoped fal key")
            else:
                out["errors"].append(f"usage HTTP {usage.status_code}: {usage.text[:200]}")
        except Exception as exc:
            out["errors"].append(f"usage: {exc}")

    if out["ok"]:
        out["message"] = "Live from fal.ai"
    elif out["needs_admin_key"]:
        out["message"] = (
            "Usage/billing needs an ADMIN-scoped fal key. Create one at fal.ai/dashboard/keys "
            "(scope: ADMIN), save it here, then refresh."
        )
    else:
        out["message"] = "Could not load fal usage. " + ("; ".join(out["errors"][:2]) if out["errors"] else "Try again.")

    return out
