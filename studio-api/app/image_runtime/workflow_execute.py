"""Sole production builder import site for image workflows (M42 W2).

QueueWorker and product surfaces must call build_leaf_graph — never import
builders directly. Allowed builder imports: this module, cert scripts, tests.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .certified_registry import get_workflow
from .contract import CanonicalImageWorkflowContract
from .fingerprints import assert_no_graph_drift


def build_leaf_graph(
    contract: CanonicalImageWorkflowContract | Mapping[str, Any],
    *,
    settings: Any,
    prompt: str,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    seed: int = 0,
    steps: int = 8,
    cfg: float = 1.0,
    filename_prefix: str = "studio/image",
    reference_image: Optional[str] = None,
    source_image: Optional[str] = None,
    mask_image: Optional[str] = None,
    checkpoint: Optional[str] = None,
    denoise: float = 0.45,
    mu: Optional[float] = None,
    use_clip_vision: bool = True,
    upscale_model: Optional[str] = None,
    outpaint_left: int = 0,
    outpaint_top: int = 0,
    outpaint_right: int = 256,
    outpaint_bottom: int = 256,
    style_references: Optional[list[Any]] = None,
    character_references: Optional[list[Any]] = None,
    environment_references: Optional[list[Any]] = None,
    moodboard_references: Optional[list[Any]] = None,
    lora_id: Optional[str] = None,
    lora_strength: Optional[float] = None,
) -> dict[str, Any]:
    """Build a Comfy (or adapter) graph from a resolved contract. Builder imports only here."""
    if isinstance(contract, CanonicalImageWorkflowContract):
        key = contract.workflow_key
        builder_path = contract.builder_path
    else:
        key = str(contract.get("workflowKey") or contract.get("workflow_key") or "")
        builder_path = contract.get("builderPath") or contract.get("builder_path")

    if key in {"zimage.txt2img"}:
        from ..workflows.image_tools import build_zimage_txt2img_workflow

        return build_zimage_txt2img_workflow(
            unet_name=settings.zimage_unet,
            clip_name=settings.zimage_clip,
            vae_name=settings.zimage_vae,
            positive=prompt,
            negative=negative or "blurry, low quality, watermark",
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=filename_prefix,
        )

    if key in {"zimage.ref_edit"}:
        from ..workflows.image_tools import build_zimage_ref_workflow

        ref = reference_image or source_image
        if not ref:
            raise RuntimeError("zimage.ref_edit requires reference_image")
        return build_zimage_ref_workflow(
            unet_name=settings.zimage_unet,
            clip_name=settings.zimage_clip,
            vae_name=settings.zimage_vae,
            clip_vision_name=settings.zimage_clip_vision,
            reference_image=ref,
            prompt=prompt,
            negative=negative or "blurry, low quality",
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=filename_prefix,
            use_clip_vision=use_clip_vision,
        )

    if key in {"zimage.inpaint"}:
        from ..workflows.image_edit_tools import build_zimage_inpaint_workflow

        src = source_image or reference_image
        if not src:
            raise RuntimeError("zimage.inpaint requires source_image")
        if not mask_image:
            raise RuntimeError(
                "zimage.inpaint requires mask_image; cannot build inpaint graph without mask"
            )
        try:
            return build_zimage_inpaint_workflow(
                unet_name=settings.zimage_unet,
                clip_name=settings.zimage_clip,
                vae_name=settings.zimage_vae,
                clip_vision_name=settings.zimage_clip_vision,
                source_image=src,
                mask_image=mask_image,
                prompt=prompt,
                negative=negative or "blurry, low quality",
                width=width,
                height=height,
                seed=seed,
                steps=steps,
                cfg=cfg,
                denoise=denoise if denoise != 0.45 else 0.85,
                filename_prefix=filename_prefix,
                use_clip_vision=use_clip_vision,
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"zimage.inpaint graph build failed ({exc}); "
                "VAEEncodeForInpaint/SetLatentNoiseMask required"
            ) from exc

    if key in {"zimage.outpaint"}:
        from ..workflows.image_edit_tools import build_zimage_outpaint_workflow

        src = source_image or reference_image
        if not src:
            raise RuntimeError("zimage.outpaint requires source_image")
        return build_zimage_outpaint_workflow(
            unet_name=settings.zimage_unet,
            clip_name=settings.zimage_clip,
            vae_name=settings.zimage_vae,
            clip_vision_name=settings.zimage_clip_vision,
            source_image=src,
            prompt=prompt,
            negative=negative or "blurry, low quality",
            left=outpaint_left,
            top=outpaint_top,
            right=outpaint_right,
            bottom=outpaint_bottom,
            seed=seed,
            steps=steps,
            cfg=cfg,
            denoise=denoise if denoise != 0.45 else 0.85,
            filename_prefix=filename_prefix,
            use_clip_vision=use_clip_vision,
        )

    if key in {"image.upscale"}:
        from ..workflows.image_edit_tools import build_image_upscale_workflow

        src = source_image or reference_image
        if not src:
            raise RuntimeError("image.upscale requires source_image")
        # Empty model → ImageScaleBy path (no ESRGAN weights required for cert)
        model = upscale_model or getattr(settings, "upscale_model", None) or ""
        return build_image_upscale_workflow(
            source_image=src,
            upscale_model=model if model not in {"RealESRGAN_x4plus.pth"} else "",
            filename_prefix=filename_prefix,
            scale=2.0,
        )

    if key in {
        "qwen2512.txt2img",
        "qwen2512.character_concept",
        "qwen2512.character_profile",
    }:
        from ..workflows.qwen_image_2512 import (
            build_qwen_2512_character_concept_workflow,
            build_qwen_2512_txt2img_workflow,
        )

        if key == "qwen2512.txt2img":
            return build_qwen_2512_txt2img_workflow(
                unet_name=settings.qwen_image_2512_unet,
                clip_name=settings.qwen_image_2512_clip,
                vae_name=settings.qwen_image_2512_vae,
                positive=prompt,
                negative=negative,
                width=width or settings.qwen_image_2512_size,
                height=height or settings.qwen_image_2512_size,
                seed=seed,
                steps=steps if steps != 8 else settings.qwen_image_2512_steps,
                cfg=cfg if cfg != 1.0 else settings.qwen_image_2512_cfg,
                sampler_name=settings.qwen_image_2512_sampler,
                scheduler=settings.qwen_image_2512_scheduler,
                model_shift=settings.qwen_image_2512_shift,
                filename_prefix=filename_prefix,
            )

        variant = "profile" if key == "qwen2512.character_profile" else "concept"
        default_prefix = (
            "studio/qwen2512_character_profile"
            if variant == "profile"
            else "studio/qwen2512_character_concept"
        )
        return build_qwen_2512_character_concept_workflow(
            unet_name=settings.qwen_image_2512_unet,
            clip_name=settings.qwen_image_2512_clip,
            vae_name=settings.qwen_image_2512_vae,
            prompt=prompt,
            negative=negative,
            width=width or settings.qwen_image_2512_size,
            height=height or settings.qwen_image_2512_size,
            seed=seed,
            steps=steps if steps != 8 else settings.qwen_image_2512_steps,
            cfg=cfg if cfg != 1.0 else settings.qwen_image_2512_cfg,
            sampler_name=settings.qwen_image_2512_sampler,
            scheduler=settings.qwen_image_2512_scheduler,
            model_shift=settings.qwen_image_2512_shift,
            filename_prefix=filename_prefix or default_prefix,
            workflow_variant=variant,
        )

    if key in {"krea2.turbo_txt2img", "krea2.raw_txt2img"}:
        from ..workflows.krea2_image import (
            build_krea2_raw_txt2img_workflow,
            build_krea2_turbo_txt2img_workflow,
        )
        from .asset_refs import RoleGroupedReferences, resolve_krea2_lora

        # mu precedence: explicit call-site value → pinned contract runtime
        # requirements (registry runtimeParams) → builder default (Turbo constant
        # 1.15 / RAW resolution-derived).
        contract_mu: Optional[float] = None
        if isinstance(contract, CanonicalImageWorkflowContract):
            raw_mu = (contract.runtime_requirements or {}).get("mu")
        else:
            rr = contract.get("runtimeRequirements") or contract.get("runtime_requirements") or {}
            raw_mu = rr.get("mu") if isinstance(rr, Mapping) else None
        if raw_mu is not None:
            contract_mu = float(raw_mu)
        effective_mu = mu if mu is not None else contract_mu

        # Phase C reference / LoRA precedence: explicit call-site → contract
        # carriers (resolve_image_workflow present_inputs) → empty/none.
        def _contract_list(*names: str) -> Optional[list[Any]]:
            if isinstance(contract, CanonicalImageWorkflowContract):
                for name in names:
                    value = getattr(contract, name, None)
                    if value:
                        return list(value)
            else:
                for name in names:
                    value = contract.get(name)
                    if value:
                        return list(value)
            return None

        references = RoleGroupedReferences.from_inputs(
            styleReferences=style_references
            if style_references is not None
            else _contract_list("style_references", "styleReferences"),
            characterReferences=character_references
            if character_references is not None
            else _contract_list("character_references", "characterReferences"),
            environmentReferences=environment_references
            if environment_references is not None
            else _contract_list("environment_references", "environmentReferences"),
            moodboardReferences=moodboard_references
            if moodboard_references is not None
            else _contract_list("moodboard_references", "moodboardReferences"),
        )
        effective_lora_id = lora_id
        contract_lora_strength: Optional[float] = None
        if effective_lora_id is None:
            if isinstance(contract, CanonicalImageWorkflowContract):
                effective_lora_id = contract.lora_id
            else:
                effective_lora_id = contract.get("loraId") or contract.get("lora_id")
        if isinstance(contract, CanonicalImageWorkflowContract):
            contract_lora_strength = contract.lora_strength
        else:
            raw_strength = contract.get("loraStrength")
            contract_lora_strength = float(raw_strength) if raw_strength is not None else None
        effective_strength = (
            float(lora_strength)
            if lora_strength is not None
            else (contract_lora_strength if contract_lora_strength is not None else 0.8)
        )
        lora = resolve_krea2_lora(effective_lora_id, strength=effective_strength, settings=settings)
        ref_support = {
            "clip_vision_name": getattr(settings, "krea2_clip_vision", "") or "",
            "ipadapter_name": getattr(settings, "krea2_ipadapter", "") or "",
        }

        if key == "krea2.turbo_txt2img":
            return build_krea2_turbo_txt2img_workflow(
                unet_name=settings.krea2_turbo_checkpoint,
                clip_name=settings.krea2_text_encoder,
                vae_name=settings.krea2_vae,
                positive=prompt,
                negative=negative,
                width=width,
                height=height,
                seed=seed,
                steps=steps if steps != 8 else settings.krea2_turbo_steps,
                cfg=cfg if cfg != 1.0 else settings.krea2_turbo_cfg,
                mu=effective_mu if effective_mu is not None else settings.krea2_turbo_mu,
                filename_prefix=filename_prefix,
                references=references,
                lora=lora,
                **ref_support,
            )
        return build_krea2_raw_txt2img_workflow(
            unet_name=settings.krea2_raw_checkpoint,
            clip_name=settings.krea2_text_encoder,
            vae_name=settings.krea2_vae,
            positive=prompt,
            negative=negative,
            width=width,
            height=height,
            seed=seed,
            steps=steps if steps != 8 else settings.krea2_raw_steps,
            cfg=cfg if cfg != 1.0 else settings.krea2_raw_cfg,
            mu=effective_mu,
            filename_prefix=filename_prefix,
            references=references,
            lora=lora,
            **ref_support,
        )

    if key in {"flux.txt2img", "qwen.txt2img", "checkpoint.txt2img"}:
        from ..imagegen_workflows import build_txt2img_workflow

        ckpt = checkpoint or getattr(settings, "default_checkpoint", None) or ""
        if not ckpt:
            raise RuntimeError(f"{key} requires checkpoint")
        return build_txt2img_workflow(
            checkpoint=ckpt,
            positive=prompt,
            negative=negative,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=filename_prefix,
        )

    if key in {
        "flux.img2img",
        "flux.edit",
        "flux.reference",
        "flux.inpaint",
        "flux.outpaint",
        "qwen.edit",
        "qwen.reference",
        "checkpoint.img2img",
    }:
        from ..imagegen_workflows import build_img2img_edit_stub

        img = reference_image or source_image
        if not img:
            raise RuntimeError(f"{key} requires source/reference image")
        ckpt = checkpoint or getattr(settings, "default_checkpoint", None) or ""
        if not ckpt:
            raise RuntimeError(f"{key} requires checkpoint")
        return build_img2img_edit_stub(
            checkpoint=ckpt,
            positive=prompt,
            negative=negative,
            image_name=img,
            denoise=denoise,
            seed=seed,
            steps=steps,
            filename_prefix=filename_prefix,
        )

    if key.startswith("imagen."):
        raise RuntimeError(
            f"Cloud workflow {key} uses provider adapter — not a local Comfy graph builder"
        )

    raise RuntimeError(
        f"No local Comfy builder for image workflow: {key}"
        + (f" (builderPath={builder_path})" if builder_path else "")
    )


def legacy_comfy_workflow_key(workflow_key: str) -> str | None:
    """Map image certified keys onto legacy DEFAULT_WORKFLOW_REGISTRY keys for ensure_queueable."""
    mapping = {
        "zimage.txt2img": "image.txt2img",
        "zimage.ref_edit": "image.zimage_reference",
        # Map onto existing registry keys for ensure_queueable (dedicated keys not in DEFAULT_WORKFLOW_REGISTRY)
        "zimage.inpaint": "image.zimage_reference",
        "zimage.outpaint": "image.zimage_reference",
        "image.upscale": "image.img2img_edit",
        "qwen2512.txt2img": "image.txt2img",
        "qwen2512.character_concept": "image.txt2img",
        "qwen2512.character_profile": "image.txt2img",
        "flux.txt2img": "image.txt2img",
        "flux.img2img": "image.img2img_edit",
        "flux.edit": "image.img2img_edit",
        "flux.reference": "image.img2img_edit",
        "flux.inpaint": "image.img2img_edit",
        "flux.outpaint": "image.img2img_edit",
        "qwen.txt2img": "image.txt2img",
        "qwen.edit": "image.img2img_edit",
        "qwen.reference": "image.img2img_edit",
        "checkpoint.txt2img": "image.txt2img",
        "checkpoint.img2img": "image.img2img_edit",
    }
    return mapping.get(workflow_key)


def prepare_executable_graph(
    contract: CanonicalImageWorkflowContract | Mapping[str, Any],
    graph: Mapping[str, Any],
    *,
    expected_graph_hash: str | None = None,
    enforce_certified_fingerprint: bool = True,
) -> dict[str, Any]:
    """Fingerprint-check before queue_prompt."""
    if isinstance(contract, CanonicalImageWorkflowContract):
        key = contract.workflow_key
        version = contract.workflow_version
        status = contract.status
        fps = (contract.fingerprints if hasattr(contract, "fingerprints") else {}) or {}
        expected = expected_graph_hash or (fps.get("graphHash") if isinstance(fps, dict) else None)
    else:
        key = str(contract.get("workflowKey") or "")
        version = str(contract.get("workflowVersion") or "1.0.0")
        status = str(contract.get("status") or "")
        expected = expected_graph_hash or (contract.get("fingerprints") or {}).get("graphHash")

    leaf = get_workflow(key)
    if leaf and leaf.fingerprints.get("graphHash"):
        expected = expected or leaf.fingerprints.get("graphHash")
    if expected and leaf and leaf.status == "Certified" and enforce_certified_fingerprint:
        assert_no_graph_drift(
            built_graph=graph,
            expected_graph_hash=expected,
            workflow_key=key,
            workflow_version=version,
        )
    elif expected and status == "Certified" and enforce_certified_fingerprint:
        assert_no_graph_drift(
            built_graph=graph,
            expected_graph_hash=expected,
            workflow_key=key,
            workflow_version=version,
        )
    return dict(graph)
