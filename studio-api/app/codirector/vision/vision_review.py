"""Shared Co-Director Vision layer — fal.ai any-llm/vision only.

Character Creator, ERS, and Scene Mini call this layer. Provider routing
stays here. No Kie fallback.
"""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

FAL_VISION_ENDPOINT = "fal-ai/any-llm/vision"
FAL_VISION_MODEL_DEFAULT = "google/gemini-2.5-flash-lite"
DEFAULT_VLM_MODEL = FAL_VISION_MODEL_DEFAULT
MAX_DATA_URL_BYTES = 4_000_000
_KIE_VISION_ALIASES = {
    "gemini-3-pro",
    "gemini-3.1-pro",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-3-flash",
}


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


def resolve_vision_model(requested: str | None = None) -> str:
    """Nested fal vision model. Kie Gemini ids resolve to the canonical fal model."""
    raw = str(requested or "").strip()
    if raw and raw not in _KIE_VISION_ALIASES and "/" in raw:
        return raw
    try:
        from ...hosted_providers.models import resolve_model_mapping

        mapping = resolve_model_mapping("Co-Director Vision", "fal") or {}
        nested = str(mapping.get("nestedModelId") or "").strip()
        if nested:
            return nested
    except Exception:
        pass
    return FAL_VISION_MODEL_DEFAULT


def _extract_part_url(part: dict[str, Any]) -> str:
    if not isinstance(part, dict):
        return ""
    if str(part.get("type") or "") == "text":
        return ""
    image = part.get("image_url")
    if isinstance(image, dict):
        return str(image.get("url") or "").strip()
    if isinstance(image, str):
        return image.strip()
    return str(part.get("url") or "").strip()


def _data_url_to_temp(url: str) -> Path | None:
    if not url.startswith("data:") or ";base64," not in url:
        return None
    header, _, b64 = url.partition(";base64,")
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return None
    if not raw:
        return None
    suffix = ".png" if "png" in header.lower() else ".jpg"
    tmp = tempfile.NamedTemporaryFile(prefix="adept-vision-", suffix=suffix, delete=False)
    tmp.write(raw)
    tmp.close()
    return Path(tmp.name)


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def _collect_fal_image_urls(
    *,
    api_key: str,
    parts: list[dict[str, Any]] | None,
    image_paths: list[Path] | None,
) -> list[str]:
    from ...fal_client import upload_file_to_fal

    urls: list[str] = []
    temps: list[Path] = []
    try:
        for path in image_paths or []:
            p = Path(path)
            if not p.is_file():
                raise FileNotFoundError(str(p))
            urls.append(await upload_file_to_fal(p, api_key))
        if urls:
            return urls
        for part in parts or []:
            ref = _extract_part_url(part)
            if not ref:
                continue
            if _is_http_url(ref):
                urls.append(ref)
                continue
            temp = _data_url_to_temp(ref)
            if temp is None:
                continue
            temps.append(temp)
            urls.append(await upload_file_to_fal(temp, api_key))
        return urls
    finally:
        for temp in temps:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass


def _fal_output(result: Any) -> str:
    if isinstance(result, dict):
        output = str(result.get("output") or "")
        if not output and isinstance(result.get("data"), dict):
            output = str(result["data"].get("output") or "")
        return output
    return str(result or "")


async def chat_vision(
    *,
    instructions: str,
    parts: list[dict[str, Any]] | None = None,
    image_paths: list[Path] | None = None,
    model_id: str = DEFAULT_VLM_MODEL,
    temperature: float = 0.0,
    timeout_sec: float = 90.0,
) -> dict[str, Any]:
    """One fal.ai vision review call. Returns {ok, output?, error?} — never raises.

    Honest degrade: missing fal key / provider error -> ok=False with a reason.
    Never calls Kie. No fake pass.
    """
    from ...secrets_store import get_secret

    api_key = get_secret("fal_api_key")
    if not api_key:
        return {"ok": False, "error": "no_vlm_configured", "reason": "no_vlm_configured"}

    model = resolve_vision_model(model_id)
    try:
        urls = await _collect_fal_image_urls(api_key=api_key, parts=parts, image_paths=image_paths)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision image upload failed: %s", exc)
        return {"ok": False, "error": str(exc), "reason": str(exc), "provider": "fal", "model": model}
    if not urls:
        return {
            "ok": False,
            "error": "image_unreadable",
            "reason": "image_unreadable",
            "provider": "fal",
            "model": model,
        }
    return await chat_vision_fal(
        prompt=instructions,
        image_urls=urls,
        model=model,
        timeout_sec=timeout_sec,
        temperature=temperature,
    )


async def chat_vision_fal(
    *,
    prompt: str,
    image_urls: list[str],
    model: str = FAL_VISION_MODEL_DEFAULT,
    timeout_sec: float = 120.0,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """fal-ai/any-llm/vision review call (HTTPS image URLs required)."""
    from ...secrets_store import get_secret

    api_key = get_secret("fal_api_key")
    if not api_key:
        return {"ok": False, "error": "no_fal_configured", "reason": "no_vlm_configured"}
    urls = [u for u in (image_urls or []) if str(u or "").strip()]
    if not urls:
        return {"ok": False, "error": "no_image_urls", "reason": "generated_unreadable"}
    resolved = resolve_vision_model(model)
    args: dict[str, Any] = {
        "model": resolved,
        "prompt": prompt,
        "temperature": temperature,
    }
    if len(urls) == 1:
        args["image_url"] = urls[0]
    else:
        args["image_urls"] = urls
    try:
        from ...fal_client import run_fal_model

        result = await run_fal_model(
            FAL_VISION_ENDPOINT,
            args,
            api_key,
            timeout_sec=min(timeout_sec, 240.0),
        )
    except Exception as exc:  # noqa: BLE001
        err = str(exc).strip() or "vlm_error"
        return {
            "ok": False,
            "error": err,
            "reason": err,
            "provider": "fal",
            "model": resolved,
        }
    output = _fal_output(result)
    if not output:
        return {
            "ok": False,
            "error": "fal returned no vision text.",
            "reason": "empty_output",
            "provider": "fal",
            "model": resolved,
        }
    return {
        "ok": True,
        "provider": "fal",
        "model": resolved,
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
