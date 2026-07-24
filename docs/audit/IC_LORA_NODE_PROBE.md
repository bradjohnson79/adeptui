# IC-LoRA Node Probe (ComfyUI @ 127.0.0.1:8188)

Probed: 2026-07-23 against live ComfyUI `object_info`.

## Discovered class names

| Class | Role |
|-------|------|
| `LTXICLoRALoaderModelOnly` | Load Ingredients/IC-LoRA onto MODEL; outputs `(MODEL, FLOAT latent_downscale_factor)` |
| `LTXAddVideoICLoRAGuide` | Preferred guide node; IMAGE (or video frames) → condition LATENT |
| `LoraLoaderModelOnly` | Generic model-only LoRA loader (alternate path) |
| `GetICLoRAParameters` | Extract `IC_LORA_PARAMETERS` from a loaded IC-LoRA MODEL |
| `LTXVAddGuide` | Alternate guide; optional `iclora_parameters` |
| `ImagePrepForICLora` | Prep reference IMAGE to target WxH (+ MASK) |
| `LoadImage` | Load reference sheet PNG |
| `VHS_LoadVideo` | Load static reference video → IMAGE batch |

## Preferred strategy: `ltxvideo`

When **both** are present:

1. `LTXICLoRALoaderModelOnly` — `lora_name=ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors`, `strength_model` from preset
2. `LTXAddVideoICLoRAGuide` — wire `latent_downscale_factor` from loader output `[1]`; `image` from reference video frames (or sheet PNG)

## Alternate strategy: `core_guide`

When preferred pair is incomplete but all of these exist:

1. `LoraLoaderModelOnly`
2. `GetICLoRAParameters` ← loaded MODEL
3. `LTXVAddGuide` with optional `iclora_parameters`

## Reject

If neither mapping is available → error code `ic_lora_nodes_missing`.

## Notes

- Ingredients IC-LoRA is **reference conditioning**, not a style LoRA picker.
- Prompt format is two-part: `Reference sheet: …` / `Generated video: …`.
- Guide strength on `LTXAddVideoICLoRAGuide` is capped at `1.0`; IC-LoRA strength presets (`0.8` / `1.4` / `1.8`) apply primarily to loader `strength_model` (and to `LTXVAddGuide.strength` on the alternate path).
- Model file must exist under Comfy `models/loras` (empty folders are **not** Ready).
