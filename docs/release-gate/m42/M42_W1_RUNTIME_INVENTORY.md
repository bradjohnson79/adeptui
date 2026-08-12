# M42 W1-2 — Runtime Inventory

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m42/w1/runtime_inventory.json` |
| **Harness** | `scripts/m42_w1_inventory.py` |

## Method

Probe Comfy shared `models/` tree + `STUDIO_*` config-declared Z-Image / checkpoint names + Comfy `/object_info` when available. Inventory only what exists; missing mission families are listed as `notInstalledFamilies`.

## Summary (this machine)

Models root: `ComfyUI-Shared/models` (probed). Live counts are in `runtime_inventory.json`.

Observed at Wave 1 freeze: Z-Image Turbo diffusion weight present (`z_image_turbo_bf16.safetensors`); LoRAs present under `loras/`; checkpoint folder currently holds LTX video checkpoints (not FLUX/SDXL stills). Mission families without files are listed under `notInstalledFamilies` (e.g. pony, illustrious, juggernaut when absent).

Config-declared production still path remains **Z-Image Turbo** (`zimage_unet` / `zimage_clip` / `zimage_vae`).

## LoRA / ControlNet / Upscaler / VAE

Enumerated from filesystem under the Comfy models root. IC-LoRA and identity-preservation LoRAs are classified when present by path/name; absence is recorded honestly.

## Custom nodes

`customNodeHints` records presence of required class types from Comfy object_info (UNETLoader, CheckpointLoaderSimple, ControlNet*, Upscale*, TextEncodeZImageOmni, etc.).
