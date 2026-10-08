"""SafeTensors inspection for LoRA weights. Never executes file contents."""

from __future__ import annotations

import json
from pathlib import Path

from . import compat

MAX_LORA_BYTES = 8 * 1024 * 1024 * 1024
_EXECUTABLE_MAGICS = (b"MZ", b"PK\x03\x04", b"PK\x05\x06", b"\x7fELF", b"#!")


def family_from_base_model(text: str | None) -> str:
    """Map a published base-model string onto a canonical LoRA family.

    Returns an empty string when the text does not name a known family.
    Callers must keep that as unknown rather than guessing.
    """
    raw = str(text or "").strip().lower().replace("_", " ").replace("-", " ")
    if not raw:
        return ""
    if "z image" in raw or "zimage" in raw:
        return compat.LORA_FAMILY_ZIMAGE
    if "qwen" in raw:
        return compat.LORA_FAMILY_QWEN_IMAGE
    if "flux" in raw:
        return compat.LORA_FAMILY_FLUX
    if "krea" in raw:
        return compat.LORA_FAMILY_KREA2
    if "ltx" in raw:
        return compat.LORA_FAMILY_LTX
    if "hunyuan" in raw:
        return compat.LORA_FAMILY_HUNYUAN
    if "wan2" in raw or "wan 2" in raw or raw == "wan" or raw.startswith("wan "):
        return compat.LORA_FAMILY_WAN
    if any(token in raw for token in ("sdxl", "sd xl", "illustrious", "pony", "sd1", "sd 1", "stable diffusion")):
        return compat.LORA_FAMILY_SDXL
    return ""


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def triggers_from_metadata(meta: dict) -> list[str]:
    found: list[str] = []
    for key in ("modelspec.trigger_phrase", "ss_trigger_words", "trigger_words", "trained_words"):
        raw = meta.get(key)
        if isinstance(raw, str) and raw.strip():
            parts = [part.strip() for part in raw.replace("\n", ",").split(",")]
            found.extend(part for part in parts if part)
        elif isinstance(raw, list):
            found.extend(str(part).strip() for part in raw if str(part).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for word in found:
        marker = word.lower()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(word)
    return deduped


def strength_from_metadata(meta: dict) -> float | None:
    for key in ("ss_recommended_weight", "recommended_weight", "modelspec.recommendation.weight"):
        if key in meta:
            return _as_float(meta.get(key))
    return None


def inspect_safetensors_header(path: Path) -> tuple[bool, str, dict]:
    """Read only the safetensors header. Returns ok, message, metadata dict."""
    if path.suffix.lower() != ".safetensors":
        return False, "Only .safetensors LoRA weights can be installed.", {}
    if not path.is_file():
        return False, "That file could not be found.", {}
    size = path.stat().st_size
    if size < 16:
        return False, "That file is too small to be a LoRA.", {}
    if size > MAX_LORA_BYTES:
        return False, "That file is larger than Adept UI will install as a LoRA.", {}
    try:
        with open(path, "rb") as handle:
            magic = handle.read(8)
            if magic.startswith(_EXECUTABLE_MAGICS) or magic[:2] == b"MZ" or magic[:2] == b"PK":
                return False, "That file is not a LoRA weights file.", {}
            header_len = int.from_bytes(magic, "little")
            if header_len <= 2 or header_len > 64 * 1024 * 1024:
                return False, "That file is not a LoRA weights file.", {}
            header = handle.read(header_len)
    except OSError:
        return False, "That file could not be read.", {}
    if len(header) != header_len:
        return False, "That file is not a LoRA weights file.", {}
    try:
        data = json.loads(header.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "That file is not a LoRA weights file.", {}
    if not isinstance(data, dict):
        return False, "That file is not a LoRA weights file.", {}
    meta = data.get("__metadata__")
    if not isinstance(meta, dict):
        meta = {}
    tensor_keys = [key for key in data.keys() if key != "__metadata__"]
    if not tensor_keys:
        return False, "That file does not contain model weights.", {}
    return True, "ok", meta


def classify_lora_file(path: Path) -> dict:
    """Inspect a weights file and return only facts that were actually present."""
    ok, message, meta = inspect_safetensors_header(path)
    base_raw = ""
    author = ""
    license_text = ""
    title = ""
    if ok:
        base_raw = str(
            meta.get("modelspec.base_model")
            or meta.get("ss_base_model_version")
            or meta.get("ss_sd_model_name")
            or meta.get("modelspec.architecture")
            or ""
        ).strip()
        author = str(meta.get("modelspec.author") or meta.get("ss_author") or "").strip()
        license_text = str(meta.get("modelspec.license") or meta.get("ss_license") or "").strip()
        title = str(meta.get("modelspec.title") or meta.get("ss_output_name") or "").strip()
    header_family = family_from_base_model(base_raw) if base_raw else ""
    filename_family = compat.infer_family_from_filename(path.name) if ok else compat.LORA_FAMILY_UNASSIGNED
    return {
        "ok": ok,
        "message": message,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "base_model": base_raw,
        "family": header_family,
        "filename_family": filename_family,
        "compatibility": "known" if header_family else "unknown",
        "trigger_words": triggers_from_metadata(meta) if ok else [],
        "recommended_strength": strength_from_metadata(meta) if ok else None,
        "author": author,
        "license": license_text,
        "display_name": title,
    }
