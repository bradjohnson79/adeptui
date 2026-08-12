"""Krea 2 (Turbo / RAW) text-to-image ComfyUI graph builders — Phase B (Draft).

Krea 2 is a 12B single-stream flow-matching DiT (Qwen Image VAE + Qwen3-VL-4B
text encoder). Native ComfyUI support landed in v0.26.0 (Comfy-Org/ComfyUI
PR #14589): ``comfy/ldm/krea2/model.py``, ``CLIPType.KREA2`` and ``"krea2"`` in
the ``CLIPLoader`` type list. The PR file list contains **no Krea2-specific
sampler or model-sampling node**, so the signature timestep-shift (``mu``) is
applied with the closest documented core node, ``ModelSamplingAuraFlow``
(constant exponential shift — the same node the Qwen-Image-2512 builder uses
for flow DiTs). TODO(cert): re-probe ``/object_info`` on the live runtime and
confirm the official template's sampling chain before promoting past Draft.

Settings keys consumed (defined in ``app/config.py``, Phase A):
  - ``settings.krea2_turbo_checkpoint`` — Turbo UNET/diffusion model filename
  - ``settings.krea2_raw_checkpoint``   — RAW UNET/diffusion model filename
  - ``settings.krea2_text_encoder``     — Qwen3-VL-4B CLIP filename (CLIPLoader type "krea2")
  - ``settings.krea2_vae``              — Qwen Image VAE filename
  - ``settings.krea2_model_root``       — discovery/verifier root (not used by builders)
  - ``settings.krea2_turbo_steps`` / ``settings.krea2_turbo_cfg`` / ``settings.krea2_turbo_mu``
  - ``settings.krea2_raw_steps`` / ``settings.krea2_raw_cfg``

Official inference settings (verified 2026-08-08, see
``docs/release-gate/krea2/KREA2_IMAGE_PIPELINE_AUDIT.md`` §14):
  - Turbo (distilled): 8 steps, CFG disabled (0.0), constant mu = 1.15, 1024–2048 px.
    NOTE: the official repo's ``--cfg 0.0`` means "guidance disabled". ComfyUI's
    ``KSampler`` computes ``uncond + cfg * (cond - uncond)``, where cfg=0.0 yields
    the *negative* branch only — the equivalent of "disabled" in ComfyUI is 1.0.
    The official value is carried verbatim from settings for Phase B; Phase C
    live certification must validate (and if needed remap) this semantics gap.
  - RAW (base): 52 steps, CFG 3.5 (official README example invocation), mu derived
    from resolution (repo CLI interpolates y1=0.5 at min res → y2=1.15 at max res).

Phase C — references & LoRA (Draft, additive-only):
  - ``references`` accepts a :class:`RoleGroupedReferences` (style / moodboard /
    character-identity / environment — see ``image_runtime/asset_refs.py``).
    Each reference image is loaded via ``LoadImage`` (Adept asset path or the
    ComfyUI input name once QueueWorker upload wiring lands) and routed into
    the model-conditioning chain: ``CLIPVisionLoader`` → per-ref
    ``CLIPVisionEncode`` → per-ref ``IPAdapterApply`` chained onto the (optionally
    LoRA-loaded) model upstream of ``ModelSamplingAuraFlow``.
    TODO(cert): the repo has no prior IPAdapter infrastructure; the
    ``IPAdapterLoader`` / ``IPAdapterApply`` class names and their exact input
    keys (``weight``, ``clip_vision_output``) follow the standard ComfyUI
    IPAdapter plugin convention but are UNVERIFIED — re-probe the live
    runtime's ``/object_info`` before promoting past Draft.
  - ERS Semantic Role Law: Krea 2's open ComfyUI path (PR #14589) ships no
    role-separated reference interface, so every reference role — above all
    ``environment`` (ERS) — is preserved in Adept metadata: each reference
    node carries ``_meta.adeptRole`` and the request-side provenance comes
    from ``RoleGroupedReferences.role_metadata()``. Environment references
    feed their own dedicated conditioning nodes and are never merged into
    style/identity nodes or reassigned to another role.
    TODO(cert): validate role preservation end-to-end on the live stack.
  - ``lora`` accepts a :class:`LoraSpec` (``image_runtime/asset_refs.py``);
    a ``LoraLoader`` node is inserted between ``UNETLoader``/``CLIPLoader``
    and their consumers with the configured strength (default 0.8). Official
    guidance: train LoRAs on RAW, run them on Turbo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..image_runtime.asset_refs import AssetRef, LoraSpec, RoleGroupedReferences


KREA2_DEFAULT_SIZE = 1024
KREA2_MIN_RESOLUTION = 1024  # official Turbo range floor (1024–2048)
KREA2_MAX_RESOLUTION = 2048

KREA2_TURBO_DEFAULT_STEPS = 8
KREA2_TURBO_DEFAULT_CFG = 0.0
KREA2_TURBO_DEFAULT_MU = 1.15  # distilled checkpoint: constant timestep shift

KREA2_RAW_DEFAULT_STEPS = 52
KREA2_RAW_DEFAULT_CFG = 3.5

KREA2_DEFAULT_SAMPLER = "euler"
KREA2_DEFAULT_SCHEDULER = "simple"
KREA2_DEFAULT_WEIGHT_DTYPE = "fp8_e4m3fn"

# FlowMatchEulerDiscreteScheduler dynamic-shifting bounds (diffusers Krea2 pipeline):
# mu interpolates linearly in image-token space between base_shift and max_shift.
KREA2_SHIFT_BASE = 0.5
KREA2_SHIFT_MAX = 1.15
KREA2_BASE_IMAGE_SEQ_LEN = 256
KREA2_MAX_IMAGE_SEQ_LEN = 6400

KREA2_STANDARD_NEGATIVE = (
    "blurry, low quality, low resolution, deformed anatomy, extra fingers, extra limbs, "
    "cropped, duplicate subject, watermark, logo, text"
)


@dataclass(frozen=True)
class Krea2SamplingPreset:
    width: int = KREA2_DEFAULT_SIZE
    height: int = KREA2_DEFAULT_SIZE
    steps: int = KREA2_TURBO_DEFAULT_STEPS
    cfg: float = KREA2_TURBO_DEFAULT_CFG
    sampler_name: str = KREA2_DEFAULT_SAMPLER
    scheduler: str = KREA2_DEFAULT_SCHEDULER
    weight_dtype: str = KREA2_DEFAULT_WEIGHT_DTYPE
    # Constant mu for Turbo; None for RAW → resolution-derived at build time.
    mu: float | None = KREA2_TURBO_DEFAULT_MU
    negative: str = KREA2_STANDARD_NEGATIVE


def krea2_recommended_settings(preset: Literal["turbo", "raw"] = "turbo") -> dict[str, Any]:
    """Default sampling settings for a Krea 2 checkpoint variant."""
    if preset == "raw":
        return asdict(
            Krea2SamplingPreset(
                steps=KREA2_RAW_DEFAULT_STEPS,
                cfg=KREA2_RAW_DEFAULT_CFG,
                mu=None,
            )
        )
    return asdict(Krea2SamplingPreset())


def krea2_normalize_dimension(value: int, *, fallback: int = KREA2_DEFAULT_SIZE) -> int:
    """Pad up to a multiple of 16 (official repo behavior); non-positive → fallback."""
    if value <= 0:
        value = fallback
    return max(16, ((int(value) + 15) // 16) * 16)


def _latent_token_count(width: int, height: int) -> int:
    # Qwen Image VAE downsamples 8x; the DiT patchifies 2x → tokens = (W/16) * (H/16).
    return max(1, (width // 16) * (height // 16))


def krea2_resolution_shift(
    width: int,
    height: int,
    *,
    base_shift: float = KREA2_SHIFT_BASE,
    max_shift: float = KREA2_SHIFT_MAX,
    base_seq_len: int = KREA2_BASE_IMAGE_SEQ_LEN,
    max_seq_len: int = KREA2_MAX_IMAGE_SEQ_LEN,
) -> float:
    """Resolution-derived mu for the RAW checkpoint (diffusers dynamic shifting).

    Linear interpolation of mu in latent-token space, clamped to
    [base_shift, max_shift] — mirrors the official repo's y1 (mu at min res) →
    y2 (mu at max res) interpolation. 1024x1024 → 0.90625; >= ~1280x1280 → 1.15.
    """
    seq = _latent_token_count(
        krea2_normalize_dimension(width), krea2_normalize_dimension(height)
    )
    span = max(1, max_seq_len - base_seq_len)
    ratio = min(1.0, max(0.0, (seq - base_seq_len) / span))
    return float(base_shift + (max_shift - base_shift) * ratio)


def _normalize_seed(seed: int) -> int:
    return seed if seed >= 0 else 42


def _reference_node_meta(ref: AssetRef, index: int) -> dict[str, Any]:
    """Per-node label carrying the semantic role (ERS Semantic Role Law)."""
    role = ref.role or "style"
    meta = {
        "title": f"{role.replace('_', ' ').title()} Reference {index} — {ref.displayName or ref.assetId}",
        "adeptRole": role,
        "adeptAssetId": ref.assetId,
        "adeptConditioning": "generic_reference_interface",
    }
    if role == "environment":
        # ERS assets stay ENVIRONMENT conditioning; the role rides Adept
        # metadata until Krea 2 exposes provider-native role separation.
        meta["adeptRoleLaw"] = "ERS_SEMANTIC_ROLE_PRESERVED"
    return meta


def _wire_reference_conditioning(
    graph: dict[str, Any],
    *,
    model_ref: list[Any],
    references: RoleGroupedReferences,
    clip_vision_name: str,
    ipadapter_name: str,
) -> list[Any]:
    """Add LoadImage → CLIPVisionEncode → IPAdapterApply chains for each ref.

    Returns the model ref downstream of the chain. Every reference gets its own
    dedicated apply node labelled with its semantic role — roles are never
    merged or reassigned (ERS law). Node class names follow the standard
    ComfyUI IPAdapter plugin convention (TODO(cert): probe /object_info).
    """
    refs = references.flattened()
    if not refs:
        return model_ref
    graph["30"] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {"clip_name": clip_vision_name},
        "_meta": {"title": "Adept Reference CLIP Vision"},
    }
    # TODO(cert): unified IPAdapter loader name unverified — some plugin
    # versions split model/insightface loaders (IPAdapterModelLoader, …).
    graph["31"] = {
        "class_type": "IPAdapterLoader",
        "inputs": {"ipadapter_name": ipadapter_name},
        "_meta": {"title": "Adept Reference Adapter"},
    }
    current = model_ref
    for index, ref in enumerate(refs):
        base = 100 + index * 10
        load_id, encode_id, apply_id = str(base), str(base + 1), str(base + 2)
        graph[load_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": ref.image or ref.assetId},
            "_meta": _reference_node_meta(ref, index + 1),
        }
        graph[encode_id] = {
            "class_type": "CLIPVisionEncode",
            "inputs": {
                "clip_vision": ["30", 0],
                "image": [load_id, 0],
                "crop": "center",
            },
            "_meta": _reference_node_meta(ref, index + 1),
        }
        # TODO(cert): input keys (weight / clip_vision_output) follow the
        # plugin convention; confirm against /object_info before Certified.
        graph[apply_id] = {
            "class_type": "IPAdapterApply",
            "inputs": {
                "model": current,
                "ipadapter": ["31", 0],
                "clip_vision_output": [encode_id, 0],
                "weight": float(ref.weight),
            },
            "_meta": _reference_node_meta(ref, index + 1),
        }
        current = [apply_id, 0]
    return current


def _build_krea2_graph(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    cfg: float,
    mu: float,
    sampler_name: str,
    scheduler: str,
    weight_dtype: str,
    filename_prefix: str,
    references: RoleGroupedReferences | None = None,
    lora: LoraSpec | None = None,
    clip_vision_name: str = "",
    ipadapter_name: str = "",
) -> dict[str, Any]:
    norm_w = krea2_normalize_dimension(width)
    norm_h = krea2_normalize_dimension(height)
    graph: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": unet_name,
                "weight_dtype": weight_dtype or KREA2_DEFAULT_WEIGHT_DTYPE,
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": clip_name,
                "type": "krea2",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae_name,
            },
        },
        # Timestep shift (mu). ModelSamplingAuraFlow applies a constant exponential
        # shift to the flow-matching model sampling; for RAW the caller passes the
        # resolution-derived value, so both variants share one topology.
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {
                "model": ["1", 0],
                "shift": float(mu),
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive,
                "clip": ["2", 0],
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative or KREA2_STANDARD_NEGATIVE,
                "clip": ["2", 0],
            },
        },
        "7": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": norm_w,
                "height": norm_h,
                "batch_size": 1,
            },
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "seed": _normalize_seed(seed),
                "steps": max(1, int(steps)),
                "cfg": float(cfg),
                "sampler_name": sampler_name or KREA2_DEFAULT_SAMPLER,
                "scheduler": scheduler or KREA2_DEFAULT_SCHEDULER,
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["3", 0],
            },
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["9", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }

    model_ref: list[Any] = ["1", 0]
    clip_ref: list[Any] = ["2", 0]
    if lora is not None:
        # Train on RAW, run on Turbo: LoRA applies to base model + CLIP before
        # any reference conditioning and before the mu shift node.
        graph["20"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["2", 0],
                "lora_name": lora.resolvedName or lora.loraId,
                "strength_model": float(lora.strength),
                "strength_clip": float(lora.strength),
            },
            "_meta": {
                "title": f"Krea 2 LoRA — {lora.loraId}",
                "adeptLoraId": lora.loraId,
                "adeptLoraResolved": bool(lora.resolved),
            },
        }
        model_ref = ["20", 0]
        clip_ref = ["20", 1]

    if references is not None and not references.is_empty():
        model_ref = _wire_reference_conditioning(
            graph,
            model_ref=model_ref,
            references=references,
            clip_vision_name=clip_vision_name,
            ipadapter_name=ipadapter_name,
        )

    if model_ref != ["1", 0]:
        graph["4"]["inputs"]["model"] = model_ref
    if clip_ref != ["2", 0]:
        graph["5"]["inputs"]["clip"] = clip_ref
        graph["6"]["inputs"]["clip"] = clip_ref
    return graph


def build_krea2_turbo_txt2img_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = KREA2_STANDARD_NEGATIVE,
    width: int = KREA2_DEFAULT_SIZE,
    height: int = KREA2_DEFAULT_SIZE,
    seed: int = 42,
    steps: int = KREA2_TURBO_DEFAULT_STEPS,
    cfg: float = KREA2_TURBO_DEFAULT_CFG,
    mu: float = KREA2_TURBO_DEFAULT_MU,
    sampler_name: str = KREA2_DEFAULT_SAMPLER,
    scheduler: str = KREA2_DEFAULT_SCHEDULER,
    weight_dtype: str = KREA2_DEFAULT_WEIGHT_DTYPE,
    filename_prefix: str = "studio/krea2_turbo_txt2img",
    references: RoleGroupedReferences | None = None,
    lora: LoraSpec | None = None,
    clip_vision_name: str = "",
    ipadapter_name: str = "",
) -> dict[str, Any]:
    """Krea 2 Turbo txt2img — 8-step distilled, constant mu (default 1.15).

    Phase C: optional role-grouped references (style / moodboard / character /
    environment-ERS) and LoRA conditioning — additive only; the default graph
    is unchanged when neither is supplied.
    """
    return _build_krea2_graph(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        positive=positive,
        negative=negative or KREA2_STANDARD_NEGATIVE,
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        mu=KREA2_TURBO_DEFAULT_MU if mu is None else float(mu),
        sampler_name=sampler_name,
        scheduler=scheduler,
        weight_dtype=weight_dtype,
        filename_prefix=filename_prefix,
        references=references,
        lora=lora,
        clip_vision_name=clip_vision_name,
        ipadapter_name=ipadapter_name,
    )


def build_krea2_raw_txt2img_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    positive: str,
    negative: str = KREA2_STANDARD_NEGATIVE,
    width: int = KREA2_DEFAULT_SIZE,
    height: int = KREA2_DEFAULT_SIZE,
    seed: int = 42,
    steps: int = KREA2_RAW_DEFAULT_STEPS,
    cfg: float = KREA2_RAW_DEFAULT_CFG,
    mu: float | None = None,
    sampler_name: str = KREA2_DEFAULT_SAMPLER,
    scheduler: str = KREA2_DEFAULT_SCHEDULER,
    weight_dtype: str = KREA2_DEFAULT_WEIGHT_DTYPE,
    filename_prefix: str = "studio/krea2_raw_txt2img",
    references: RoleGroupedReferences | None = None,
    lora: LoraSpec | None = None,
    clip_vision_name: str = "",
    ipadapter_name: str = "",
) -> dict[str, Any]:
    """Krea 2 RAW txt2img — 52-step base model; mu resolution-derived unless pinned.

    RAW is the LoRA training base; references/LoRA wire identically to Turbo.
    """
    effective_mu = float(mu) if mu is not None else krea2_resolution_shift(width, height)
    return _build_krea2_graph(
        unet_name=unet_name,
        clip_name=clip_name,
        vae_name=vae_name,
        positive=positive,
        negative=negative or KREA2_STANDARD_NEGATIVE,
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        mu=effective_mu,
        sampler_name=sampler_name,
        scheduler=scheduler,
        weight_dtype=weight_dtype,
        filename_prefix=filename_prefix,
        references=references,
        lora=lora,
        clip_vision_name=clip_vision_name,
        ipadapter_name=ipadapter_name,
    )
