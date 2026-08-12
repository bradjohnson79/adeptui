# MiniMax H3 — Route A Official Source Gate

**Run:** `RUN-20260803-181526`  
**Captured:** 2026-08-03 (local)  
**Worktree:** `C:\AdeptFilmWorks\AIVideoStudio-h3`  
**Branch:** `spike/minimax-h3-33b-rtx5090` @ `c932214`  
**Purpose:** Verify official ComfyUI-compatible optimized H3 checkpoints before any large download.

## Source hierarchy applied

1. MiniMax official repository — original model + licence (`MiniMaxAI/MiniMax-H3`)
2. **Accepted for Route A weights:** Comfy-Org official packaging (`Comfy-Org/MiniMax-H3`)
3. Official ComfyUI T2V template links resolve to Comfy-Org files
4. No community mirrors, Discord, YouTube, or anonymous HF uploads used

## Official repositories

| Role | Repository | Owner | Revision pinned |
|---|---|---|---|
| ComfyUI optimized checkpoints | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) | Comfy-Org | `0543966fbdce5ba05709a8f2031c94bdba629b4a` |
| Original model + licence | [MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) | MiniMaxAI | Previously pinned for Canada clearance (`5d9b308a…`) |
| Official T2V workflow | [Comfy-Org/workflow_templates `video_minimax_h3_t2v.json`](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json) | Comfy-Org | Local pin under `runtime/minimax-h3/workflow_templates/templates/` |
| Native H3 nodes | ComfyUI `comfy_extras/nodes_minimax_h3.py` (PR `#15224` lineage; VAE cast fix `#15268`) | Comfy-Org | Isolated ComfyUI `16e3f303` |

## Licence

| Field | Value |
|---|---|
| Licence name | MiniMax H3 Community License Agreement |
| Card licence | `other` / `minimax-h3-community-license-agreement` |
| Licence link | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE |
| Canada private-dev clearance | Accepted with conditions (`H3_CANADA_LICENSE_CLEARANCE.md`) |
| Route A download permission | Permitted for Canadian private local development under existing clearance |

## Required Route A checkpoint inventory

| Filename | Repo path | Role | Format / precision | Size (bytes) | SHA-256 (LFS oid) | ComfyUI dir | Required | Workflow |
|---|---|---|---|---|---|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `diffusion_models/…` | H3 FL2VA transformer | safetensors / pruned INT8 + convrot | 20,970,379,616 | `e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a` | `models/diffusion_models/` | **required** | `video_minimax_h3_t2v.json` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders/…` | Qwen3-VL-32B text/vision encoder | safetensors / NVFP4 AWQ | 15,687,142,551 | `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6` | `models/text_encoders/` | **required** | same |
| `minimax_h3_video_vae_fp16.safetensors` | `vae/…` | Visual VAE | safetensors / FP16 | 5,207,808,496 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` | `models/vae/` | **required** | same |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae/…` | Audio VAE | safetensors / FP32 | 605,254,808 | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` | `models/vae/` | **required** | same |

**Pack total:** 42,470,585,471 bytes (~39.6 GiB / ~42.5 GB)

### Direct official resolve URLs

- https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
- https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
- https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors
- https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors

## Companion components (nodes / workflow — not separate weight downloads)

| Component | Source | Status |
|---|---|---|
| `EmptyMiniMaxH3LatentAV` | Native ComfyUI extras | Present in isolated `16e3f303` |
| `MiniMaxH3ImageToVideo` | Native ComfyUI extras | Present |
| `MiniMaxH3ReferenceToVideo` | Native ComfyUI extras | Present (Ref2VA — not Route A media target) |
| `MiniMaxH3SigmaShift` | Native ComfyUI extras | Present |
| `SaveVideo` / mux | Native ComfyUI | Present in template |
| Scheduler / sampler | Template + native nodes | Template-driven |
| Tokenizer / processor | Bundled with Comfy MiniMax text encoder path | No separate HF download for Route A pack |
| Diffusers FL2VA shards | `MiniMaxAI/MiniMax-H3` already on disk | **Incompatible with Route A Comfy loaders** — retain for Route B only |

## Template cross-check

Local file: `runtime/minimax-h3/workflow_templates/templates/video_minimax_h3_t2v.json`

| Expected filename | Present in template |
|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | YES |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | YES |
| `minimax_h3_video_vae_fp16.safetensors` | YES |
| `minimax_h3_audio_vae_fp32.safetensors` | YES |

## Explicit exclusions

- Do **not** use Diffusers-sharded `FL2VA/` weights as drop-in replacements
- Do **not** download Ref2VA / BF16 / non-template variants for this first proof
- Do **not** use anonymous mirrors or community conversions

## Storage destination (Addendum A)

Canonical download root for Route A weights:

```text
D:\01_Models\Video\MiniMax-H3\ComfyUI\
  diffusion_models\
  text_encoders\
  vae\
```

Runtime/venv remain under `C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\`.

## Gate A verdict

All four official ComfyUI T2V checkpoint files are located on `Comfy-Org/MiniMax-H3` with pinned revision, LFS SHA-256 oids, sizes, licence inheritance, Comfy directory mapping, matching official template filenames, and native H3 nodes present in the isolated ComfyUI revision.

```text
GO — OFFICIAL ROUTE A CHECKPOINTS VERIFIED
```
