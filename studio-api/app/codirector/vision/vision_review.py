"""Shared vision review layer — one Kie Gemini vision call with images + text.

Reused by the ERS semantic gate and Scene Creator Mini candidate validation.
No new VLM infrastructure: this wraps the existing hosted_providers Kie chat
adapter with data-URL encoding for local images (bounded), exactly like the
original ers_gate implementation.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_VLM_MODEL = "gemini-3-pro"
MAX_DATA_URL_BYTES = 4_000_000


def data_url_from_path(path: str | Path, *, max_bytes: int = MAX_DATA_URL_BYTES) -> str:
    """Inline a local image as a data URL (bounded). Empty string when too big."""
    try:
        p = Path(path)
        size = p.stat().st_size
        if size <= 0 or size > max_bytes:
            return ""
        raw = p.read_bytes()
    except OSError:
        return ""
    suffix = p.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


async def chat_vision(
    *,
    instructions: str,
    parts: list[dict[str, Any]],
    model_id: str = DEFAULT_VLM_MODEL,
    temperature: float = 0.0,
    timeout_sec: float = 90.0,
) -> dict[str, Any]:
    """One vision review call. Returns {ok, output?, error?} — never raises.

    Honest degrade: missing provider key / provider error -> ok=False with a
    reason. No fake pass is ever returned by this layer.
    """
    from ...secrets_store import get_secret

    api_key = get_secret("kie_api_key")
    if not api_key:
        return {"ok": False, "error": "no_vlm_configured", "reason": "no_vlm_configured"}

    content: list[dict[str, Any]] = [{"type": "text", "text": instructions}, *parts]
    try:
        from ...hosted_providers.adapters.kie_adapter import chat_kie

        response = await chat_kie(
            api_key,
            model_id=model_id,
            messages=[{"role": "user", "content": content}],
            temperature=temperature,
            timeout_sec=timeout_sec,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision review call failed: %s", exc)
        return {"ok": False, "error": str(exc), "reason": "vlm_error"}
    if not response.get("ok"):
        return {
            "ok": False,
            "error": str(response.get("error") or "vlm_error"),
            "reason": str(response.get("error") or "vlm_error"),
        }
    return {"ok": True, "output": str(response.get("output") or "")}


FAL_VISION_MODEL_DEFAULT = "google/gemini-2.5-flash-lite"


async def chat_vision_fal(
    *,
    prompt: str,
    image_urls: list[str],
    model: str = FAL_VISION_MODEL_DEFAULT,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """fal-ai/any-llm/vision review call (public image URLs required).

    Honest degrade: missing fal key / provider error -> ok=False with reason.
    """
    from ...secrets_store import get_secret

    api_key = get_secret("fal_api_key")
    if not api_key:
        return {"ok": False, "error": "no_fal_configured", "reason": "no_vlm_configured"}
    urls = [u for u in (image_urls or []) if str(u or "").strip()]
    if not urls:
        return {"ok": False, "error": "no_image_urls", "reason": "generated_unreadable"}
    args: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "image_url": urls[0],
    }
    if len(urls) > 1:
        args["image_urls"] = urls
    try:
        from ...fal_client import run_fal_model

        result = await run_fal_model("fal-ai/any-llm/vision", args, api_key, timeout_sec=min(timeout_sec, 240.0))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "reason": "vlm_error"}
    output = ""
    if isinstance(result, dict):
        output = str(result.get("output") or "")
        if not output and isinstance(result.get("data"), dict):
            output = str(result["data"].get("output") or "")
    if not output:
        return {"ok": False, "error": "empty_output", "reason": "vlm_error"}
    return {
        "ok": True,
        "provider": "fal",
        "model": model,
        "output": output,
    }


def parse_field_verdicts(text: str) -> dict[str, str]:
    """Parse structured per-field verdicts from a Mini validation response.

    Expected format (one line per field):
        FIELD: <field name>
        PASS/FAIL: <verdict>
    Returns {field: PASS|FAIL} plus "VERDICT" for the overall decision.
    """
    raw = str(text or "")
    out: dict[str, str] = {}
    lines = raw.splitlines()
    current_field = ""
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("verdict:"):
            value = stripped.split(":", 1)[1].strip().upper()
            if value in {"PASS", "FAIL"}:
                out["VERDICT"] = value
            continue
        if lower.startswith("field:"):
            current_field = stripped.split(":", 1)[1].strip().lower().replace(" ", "_")
            continue
        if lower.startswith("pass") or lower.startswith("fail"):
            value = "PASS" if lower.startswith("pass") else "FAIL"
            if current_field:
                out[current_field] = value
            else:
                out.setdefault("VERDICT", value)
            current_field = ""
    if "VERDICT" not in out:
        field_values = {v for k, v in out.items()}
        if field_values and "FAIL" not in field_values:
            out["VERDICT"] = "PASS"
        else:
            out["VERDICT"] = "FAIL"
    return out
