# Adept UI v1.1 Essentials Manifest (Revision A–D audit)

> **SUPERSEDED 2026-08-26** for Spatial Intelligence / VGGT classification. Current Essential registration is [`docs/setup/ESSENTIAL_COMPONENT_REGISTRY.md`](../../setup/ESSENTIAL_COMPONENT_REGISTRY.md). `vggt_1b_commercial` is ESSENTIAL (gated). This Revision A–D table remains a historical audit of Co-Director intelligent-selection packing.

**Law 30:** Supporting table for Revision D. Governing file: [00-GOVERNING.md](./00-GOVERNING.md).

This is the authoritative v1.1 intelligence-model list from repository audit. Creative asset zips (`pack_essential_photoreal` / `_anime` / `_cinematic`) are **not** this pack.

## Classification

- **ESSENTIAL (pack)** — Install Missing Essentials includes this. Does **not** block generation unless already `required=True` (VideoChat3 only).
- **RECOMMENDED (pack)** — Shown in Details. Does not block Setup completion.
- **OPTIONAL / EXCLUDED** — Not in the pack.

`REQUIRED_FOR_GENERATION` is unchanged. Missing SAM/DINO/JEPA/InternVideo3/DA-V2 must not block image or video generate.

## Manifest

| Revision | Component | Version / pin | Role | Classification | License | Source | Approx size | Install path (logical) | Health |
|---|---|---|---|---|---|---|---:|---|---|
| A | VideoChat3-4B (`videochat3_4b`) | `MCG-NJU/VideoChat3-4B` @ `37fa901ec5913f84bc31108ebc1e60ad1903634c` | Timeline visual review | ESSENTIAL (also catalog `required=True`) | Apache-2.0 | Hugging Face | ~8.5 GB | `video_understanding/videochat3-4b` | files + worker probe |
| A | InternVideo3-8B (`internvideo3_8b`) | `yanziang/InternVideo3-8B-Instruct` @ `c4602918b65225650d152db2850fe34e01d21fcd` | Deep sequence review | RECOMMENDED (VRAM-gated) | Apache-2.0 | Hugging Face | catalog bytes | `video_understanding/internvideo3-8b` | files (+ optional worker) |
| A | TimeLens | — | Temporal grounding | **EXCLUDED** | Academic-only | — | — | never | never |
| B | Grounding DINO Tiny (`grounding_dino_tiny`) | `IDEA-Research/grounding-dino-tiny` @ `a2bb814dd30d776dcf7e30523b00659f4f141c71` | Text/box prompts for SAM | ESSENTIAL (pack) | Apache-2.0 | Hugging Face | ~1.5 GB | `stills_perception/grounding_dino_tiny` | markers |
| B / D | SAM 2.1 Hiera Tiny (`sam21_hiera_tiny`) | `facebook/sam2.1-hiera-tiny` @ `de431c4043854a71d8101e17995dfe596bf101a5` | Masks + video track | ESSENTIAL (pack) | Apache-2.0 | Hugging Face | ~0.4 GB | `stills_perception/sam21_hiera_tiny` | markers + worker health |
| B / D | Depth Anything V2 Small (`depth_anything_v2_small`) | `depth-anything/Depth-Anything-V2-Small-hf` @ `5426e4f0f36572d16453bbda7a8389317b1bef99` | Near/far spatial | RECOMMENDED | Apache-2.0 Small only | Hugging Face | ~0.2 GB | `stills_perception/depth_anything_v2_small` | markers |
| C | V-JEPA 2 (`vjepa2_world_intelligence`) | `facebook/vjepa2-vitl-fpc64-256` @ `b3c1679b7c34d3255ef3547f27c7b226aefab26f` | Advisory world-state | RECOMMENDED | MIT | Hugging Face | ~2.8 GB | `world_intelligence/vjepa2-vitl-fpc64-256` | markers + CUDA worker |
| C Phase 2 | PoseCraft | — | Babylon blocking studio | No model download. Reuses V-JEPA if present. | — | — | 0 | — | N/A |
| D | VGGT | — | Metric 3D / cameras | **OMIT / NOT PACKAGED** | See VGGT memo | — | — | never | never |

## Named Setup decision (2026-08-20)

Promote SAM 2.1 + Grounding DINO Tiny to **Essentials Pack ESSENTIAL** without setting catalog `required=True` and without adding them to `REQUIRED_FOR_GENERATION`. Prepare My Studio must not force-download them as boot-critical generation deps.

License memos remain `required=False` for generation.
