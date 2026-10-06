# V-JEPA 2 License Clearance

Reviewed on `2026-08-20`.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

```
PASS — V-JEPA 2 LICENSE CLEARED
```

**CLEARED for Advanced / Recommended Setup install** under MIT License, subject to the pinned sources below.

The official Facebook V-JEPA 2 models on Hugging Face are published under the MIT license, which grants commercial use, reproduction, distribution, and creation of derivative works. No non-commercial clause was found on any pinned official model card.

> **⚠️ Critical:** Some unofficial forks and derivations (e.g., `abdelstark/vjepa2-vitl-fpc2-256-onnx`) carry CC-BY-NC-4.0 licenses. Adept UI must **only** use official `facebook/` namespace models and must never follow unofficial forks or ONNX-converted variants.

## Pinned authoritative sources

### Primary model — V-JEPA 2 ViT-L/16 (256px)

- Hugging Face model repository: `facebook/vjepa2-vitl-fpc64-256`
- Pinned repository revision: `b3c1679b7c34d3255ef3547f27c7b226aefab26f`
- Hugging Face license tag: `mit` (`cardData.license`, `license:mit` tag)
- Model card URL: `https://huggingface.co/facebook/vjepa2-vitl-fpc64-256/tree/b3c1679b7c34d3255ef3547f27c7b226aefab26f`

### Alternative model — V-JEPA 2 ViT-L (256px, SSv2)

- Hugging Face model repository: `facebook/vjepa2-vitl-fpc16-256-ssv2`
- Pinned revision: `7889973ee45421712562a49f6ad2da2eac21dad9`
- License: `mit`

### Larger variant — V-JEPA 2 ViT-H (256px)

- Hugging Face model repository: `facebook/vjepa2-vith-fpc64-256`
- License: `mit`

### Larger variant — V-JEPA 2 ViT-G (256px)

- Hugging Face model repository: `facebook/vjepa2-vitg-fpc64-256`
- License: `mit`

### V-JEPA 2 ViT-G (384px)

- Hugging Face model repository: `facebook/vjepa2-vitg-fpc64-384`
- License: `mit` (also observed as `apache-2.0` on ModelScope mirror)

### Code repository

- GitHub: `facebookresearch/vjepa2`
- License: MIT (primary), Apache-2.0 (some files)
- README: `https://github.com/facebookresearch/vjepa2/blob/main/README.md`

## V-JEPA 2.1 — PENDING TRANSFORMERS SUPPORT

V-JEPA 2.1 was released by Meta on 2026-03-16. The `facebookresearch/vjepa2` repository includes V-JEPA 2.1 backbone entries.

**HuggingFace Transformers support is pending** (PR #45497 — "Add V-JEPA 2.1 inference support"). Until that PR is merged and released:

- Adept UI will use V-JEPA 2 (`facebook/vjepa2-vitl-fpc64-256`) as the primary model.
- V-JEPA 2.1 remains a `TODO` for v1.1 or v1.2 depending on community support timeline.
- A community port exists at `apiantonio/vjepa2.1-vit-large-384` — this must be independently license-audited before use.

## Transformers integration

V-JEPA 2 is natively supported in HuggingFace Transformers (`VJEPA2Model`, `VJEPA2ImageProcessor`, `VJEPA2VideoProcessor`). The current environment has:

- Transformers 5.14.1 — confirms `VJEPA2Model` availability
- Models use HuggingFace's `transformers` library — no custom code dependencies

## Weight licensing

All official `facebook/vjepa2-*` models on Hugging Face declare `license: mit` on their model cards. The MIT license permits:

| Question | Finding |
|---|---|
| Commercial use | Permitted |
| Redistribution | Permitted with license notice |
| Derivative works | Permitted |
| Cloud/service restriction | None found |
| Territory restriction | None found |

## Base-model inheritance

V-JEPA 2 uses Vision Transformer (ViT) architectures trained via self-supervised learning. No separate LLM or text encoder is required for embedding extraction. The model operates purely on visual input.

## Dependency audit

| Dependency | Overlap with existing Adept UI |
|---|---|
| PyTorch | Shared with Revision A/B — no duplicate |
| torchvision | Shared |
| transformers | Shared with Revision A/B — VJEPA2Model already available |
| Pillow | Shared |
| ffmpeg | Shared (image decode only for current scope) |
| huggingface_hub | Shared |

**No duplicate environments required.** V-JEPA can reuse the existing Python/transformers environment. An isolated worker process is recommended for GPU lifecycle management but can share the same venv.

## Adept UI treatment

- Setup catalog id: `vjepa2_world_intelligence`
- `required=False` (Advanced/Recommended)
- Category: `Co-Director World Intelligence`
- Install root under `{data_dir}/models/world_intelligence/vjepa2-vitl-fpc64-256`
- Primary model: `facebook/vjepa2-vitl-fpc64-256` (ViT-L, ~2.8GB download)
- VRAM estimate: ~2.5GB for inference (ViT-L)
- Isolated worker process (same venv)
- No ComfyUI integration
- No cloud upload

## Limitations

- This is not legal advice.
- Re-audit if the Hugging Face namespace, license tag, or repository license changes.
- V-JEPA 2.1 support pending Transformers PR #45497 merge.
- Unofficial forks with NC licenses must never be used.
