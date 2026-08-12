"""WAN 2.2 text-encoder / UNET embedding contract (no dimensional adapters).

Authoritative pairing (Comfy blueprint ``Image to Video (Wan 2.2).json``):
  CLIPLoader: umt5_xxl_fp8_e4m3fn_scaled.safetensors, type=wan
  UNETs: wan2.2_i2v_{high,low}_noise_14B_fp8_scaled.safetensors
  Expected text embedding last-dim: 4096 (comfy.ldm.wan.model text_dim)

The legacy ``umt5-xxl-enc-bf16.safetensors`` uses a non-Comfy key layout
(``blocks.N.attn.*``) and has been observed to emit 768-d conditioning that
breaks WAN ``text_embedding`` (4096x5120). Never "fix" with a projection.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Iterable, Optional

# WAN diffusion text_embedding Linear in_features (official).
WAN_TEXT_EMBEDDING_DIM = 4096

# Comfy-Org / blueprint filename (preferred).
WAN_AUTHORITATIVE_TEXT_ENCODER = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"

# Filenames known to load under type=wan but violate the 4096 contract.
WAN_REJECTED_TEXT_ENCODERS = frozenset(
    {
        "umt5-xxl-enc-bf16.safetensors",
        "umt5_xxl_enc_bf16.safetensors",
    }
)

# HuggingFace / Comfy-Org UMT5 XXL keys (must be present).
_REQUIRED_KEY_PREFIXES = ("encoder.block.0.",)


class WanEncoderContractError(ValueError):
    """Incompatible WAN text encoder — abort before UNET load."""


def _basename(name: str) -> str:
    return Path(str(name).replace("\\", "/")).name


def safetensors_key_names(path: Path, *, limit: int = 64) -> list[str]:
    """Read safetensors header keys without loading weights into VRAM."""
    with path.open("rb") as fh:
        header_len = struct.unpack("<Q", fh.read(8))[0]
        meta = json.loads(fh.read(header_len))
    keys = [k for k in meta.keys() if k != "__metadata__"]
    return keys[:limit] if limit else keys


def encoder_key_layout_ok(path: Path) -> tuple[bool, dict[str, Any]]:
    """Return whether the file looks like Comfy-compatible UMT5 XXL."""
    keys = safetensors_key_names(path, limit=80)
    joined = "\n".join(keys)
    has_hf = any(k.startswith(_REQUIRED_KEY_PREFIXES[0]) for k in keys)
    has_legacy_blocks = any(k.startswith("blocks.0.") for k in keys)
    detail = {
        "path": str(path),
        "sampleKeys": keys[:16],
        "hasEncoderBlockPrefix": has_hf,
        "hasLegacyBlocksPrefix": has_legacy_blocks,
    }
    return has_hf and not has_legacy_blocks, detail


def resolve_text_encoder_path(
    clip_name: str,
    search_roots: Iterable[Path],
) -> Optional[Path]:
    base = _basename(clip_name)
    for root in search_roots:
        if not root:
            continue
        candidate = Path(root) / "text_encoders" / base
        if candidate.is_file():
            return candidate
        # Also allow direct path / nested
        direct = Path(root) / base
        if direct.is_file():
            return direct
    return None


def assert_wan_text_encoder_contract(
    clip_name: str,
    *,
    search_roots: Optional[Iterable[Path]] = None,
    require_file_probe: bool = False,
) -> dict[str, Any]:
    """
    Reject incompatible encoders before dual-UNET load.

    Always applies filename deny/allow heuristics. When ``search_roots`` is
    provided (or ``require_file_probe``), also validates safetensors key layout.
    """
    base = _basename(clip_name)
    report: dict[str, Any] = {
        "clip_name": clip_name,
        "basename": base,
        "expectedEmbeddingDim": WAN_TEXT_EMBEDDING_DIM,
        "authoritativeEncoder": WAN_AUTHORITATIVE_TEXT_ENCODER,
        "loaderType": "wan",
        "ok": False,
    }

    if base in WAN_REJECTED_TEXT_ENCODERS or "enc-bf16" in base.lower():
        report["reason"] = (
            f"Rejected encoder {base!r}: known to emit 768-d conditioning "
            f"incompatible with WAN text_dim={WAN_TEXT_EMBEDDING_DIM}."
        )
        raise WanEncoderContractError(report["reason"])

    # Prefer Comfy-Org fp8 / umt5_xxl naming; still allow other HF-layout files
    # if key probe passes.
    looks_comfy_org = "umt5" in base.lower() and (
        "fp8" in base.lower() or "xxl" in base.lower()
    )
    if not looks_comfy_org and not search_roots:
        report["reason"] = (
            f"Encoder {base!r} is not a recognized WAN UMT5 XXL name; "
            f"expected {WAN_AUTHORITATIVE_TEXT_ENCODER!r} (or HF-layout umt5)."
        )
        raise WanEncoderContractError(report["reason"])

    if search_roots is not None:
        path = resolve_text_encoder_path(clip_name, search_roots)
        report["resolvedPath"] = str(path) if path else None
        if path is None:
            if require_file_probe:
                report["reason"] = f"Text encoder file not found for {base!r}"
                raise WanEncoderContractError(report["reason"])
        else:
            ok_layout, detail = encoder_key_layout_ok(path)
            report["keyLayout"] = detail
            if not ok_layout:
                report["reason"] = (
                    f"Encoder {base!r} key layout is not Comfy UMT5 XXL "
                    f"(need encoder.block.*; reject blocks.* legacy). "
                    f"Refusing before UNET load."
                )
                raise WanEncoderContractError(report["reason"])

    report["ok"] = True
    report["reason"] = "encoder filename/key layout matches WAN 2.2 4096-d contract"
    return report


def assert_conditioning_last_dim(last_dim: int, *, source: str = "CLIPTextEncode") -> None:
    if int(last_dim) != WAN_TEXT_EMBEDDING_DIM:
        raise WanEncoderContractError(
            f"{source} embedding last-dim={last_dim} != WAN contract "
            f"{WAN_TEXT_EMBEDDING_DIM}. Wrong encoder/model pairing — "
            f"do not insert a projection adapter."
        )
