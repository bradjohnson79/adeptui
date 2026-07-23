# ComfyUI Inventory (Phase 0)

Date: 2026-07-22  
GPU: NVIDIA GeForce RTX 5090 (~32 GB VRAM)  
ComfyUI: v0.28.2 @ http://127.0.0.1:8188  
Install: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI`  
Models: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models`  
Input: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input`  
Output: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output`

## Custom nodes present
- WhatDreamsCost-ComfyUI (LTX Director)
- ComfyUI-LTXVideo
- ComfyUI-WanVideoWrapper
- comfyui-kjnodes
- comfyui-videohelpersuite
- comfyui-easy-use, comfyui-impact-pack, comfyui_essentials, rgthree-comfy, ComfyMath, comfyui-manager

## Models present (LTX)
- ltx-2.3-22b-dev-fp8.safetensors
- ltx-2.3-22b-distilled-fp8.safetensors
- ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors
- LTX23 video/audio VAEs, text projection, IC-LoRA, ID-LoRA, spatial upscaler

## Models present (WAN-related)
- Wan2_1_SkyreelsA2_fp8_e4m3fn.safetensors (not full Wan 2.2 I2V pair)
- Wan2_1_VAE_bf16.safetensors
- Missing for full WAN 2.2 FLF2V: wan2.2_i2v high/low noise 14B + umt5 + Lightning LoRAs

## LatentSync
- Not installed yet. Studio ships workflow template; install nodes/models before lip-sync jobs succeed.

## Smoke-test
- `/system_stats` OK on port 8188
- LTX Director path ready
- WAN templates ready; download Wan 2.2 weights for full quality
