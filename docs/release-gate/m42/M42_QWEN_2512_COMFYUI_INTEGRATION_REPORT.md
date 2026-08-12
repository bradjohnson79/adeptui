# M42 Qwen-Image-2512 ComfyUI Integration Report

## Scope

Integrated a new `qwen2512.*` image workflow family without relabeling the legacy deferred
`qwen.*` checkpoint family or disturbing the certified Z-Image path.

## Implemented

- Added dedicated split-model builders in `studio-api/app/workflows/qwen_image_2512.py`.
- Added Comfy prompt-graph JSON templates under `comfyui/workflows/qwen-image-2512/`:
  - `qwen_2512_text_to_image.json`
  - `qwen_2512_character_concept.json`
  - `qwen_2512_character_profile.json`
- Registered new workflow keys in `config/image-workflows/certified-registry.json`:
  - `qwen2512.txt2img`
  - `qwen2512.character_concept`
  - `qwen2512.character_profile`
- Added compatibility catalog entries for the new family in
  `config/image-runtime/compatibility-catalog.json`.
- Added a dedicated setup component + verifier:
  - component id: `qwen_image_2512_models`
  - verifier: `qwen_image_2512_files`
- Wired `studio-api/app/image_runtime/workflow_execute.py` and
  `studio-api/app/image_runtime/contract.py` so the new family resolves/builds via
  dedicated split loaders instead of `CheckpointLoaderSimple`.
- Added focused coverage in `studio-api/tests/test_qwen_2512_registry.py`.

## Runtime Findings

- `CLIPLoader` on the live ComfyUI node inventory supports `type: "qwen_image"`.
- `TextImageEncodeQwenVL` is installed, but the local node inventory did not expose a direct
  `QWENVL_EMBEDS -> KSampler` path. For the initial runtime graph, the executable txt2img path
  therefore uses:
  - `UNETLoader`
  - `CLIPLoader(type="qwen_image")`
  - `VAELoader`
  - `ModelSamplingAuraFlow`
  - `CLIPTextEncode`
  - `EmptyLatentImage`
  - `KSampler`
  - `VAEDecode`
  - `SaveImage`

## Weight Presence

Expected official split files were checked under the Comfy shared models root:

- `diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors`
- `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `vae/qwen_image_vae.safetensors`

Result: all three were absent at integration time.

Because the weights were not actually present on disk, the new `qwen2512.*` registry entries
were left at `Draft`, not `Certified`, and no real queue execution was attempted.

## Verification

- Focused test run passed:
  - `python -m pytest tests/test_qwen_2512_registry.py`
- Result: `4 passed`

## Evidence

- Model probe: `artifacts/m42/w43-qwen-2512/runtime/qwen_2512_model_probe.json`
- Queue attempt record: `artifacts/m42/w43-qwen-2512/runtime/qwen_2512_queue_attempt.json`
- Workflow JSON templates:
  - `comfyui/workflows/qwen-image-2512/qwen_2512_text_to_image.json`
  - `comfyui/workflows/qwen-image-2512/qwen_2512_character_concept.json`
  - `comfyui/workflows/qwen-image-2512/qwen_2512_character_profile.json`

## Outcome

- New registry keys added: yes
- Legacy `qwen.txt2img` kept deferred: yes
- Real generation succeeded: no
- Blocking reason: official split-model files were not present in the configured Comfy models
  directory
