# Qwen2512RuntimeIntegration Handoff

## Delivered

- Dedicated builder module: `studio-api/app/workflows/qwen_image_2512.py`
- Workflow JSON family:
  - `comfyui/workflows/qwen-image-2512/qwen_2512_text_to_image.json`
  - `comfyui/workflows/qwen-image-2512/qwen_2512_character_concept.json`
  - `comfyui/workflows/qwen-image-2512/qwen_2512_character_profile.json`
- Registry keys:
  - `qwen2512.txt2img`
  - `qwen2512.character_concept`
  - `qwen2512.character_profile`
- Setup component:
  - `qwen_image_2512_models`
- Focused tests:
  - `studio-api/tests/test_qwen_2512_registry.py`

## Important Behavior

- The new family uses split loaders and does not reuse `CheckpointLoaderSimple`.
- Legacy `qwen.txt2img` remains deferred and untouched as the old checkpoint-style family.
- Default routing now resolves `engine/model_family = qwen-image-2512 | qwen2512` to
  `qwen2512.txt2img` for generation intents.
- Character concept/profile keys are force-selectable and build through the dedicated Qwen
  split-model module.

## Live Runtime Result

- Real generation was **not** executed.
- Blocking reason: official Qwen-Image-2512 split weights were **not present on disk** under:
  - `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models\qwen_image_2512_fp8_e4m3fn.safetensors`
  - `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\text_encoders\qwen_2.5_vl_7b_fp8_scaled.safetensors`
  - `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\vae\qwen_image_vae.safetensors`

## Evidence

- `artifacts/m42/w43-qwen-2512/runtime/qwen_2512_model_probe.json`
- `artifacts/m42/w43-qwen-2512/runtime/qwen_2512_queue_attempt.json`
- `docs/release-gate/m42/M42_QWEN_2512_COMFYUI_INTEGRATION_REPORT.md`

## Suggested Next Step

Once the three official split-model files finish downloading into the configured Comfy shared
models directory, rerun one real `qwen2512.txt2img` queue and update the registry status from
`Draft` to `Certified` only if the live evidence succeeds.
