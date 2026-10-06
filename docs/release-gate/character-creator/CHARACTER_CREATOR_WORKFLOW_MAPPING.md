# Character Creator ComfyUI Workflow Mapping

**SUPERSEDED.** Current governing map: `CHARACTER_CREATOR_COMFY_WORKFLOW_MAP.md`.

**Exported:** 2026-08-24 03:42 UTC
**Live Comfy:** `http://127.0.0.1:8188` (Comfy MCP `validate_workflow`)
**Prompting:** not modified. Graph text slots use the current Character Creator Front/Back goals. Live jobs still compile the Character Profile on top of these goals.
**Certification:** not run. This is an owner-review export only.

## What existed before this export

Character Creator did **not** have dedicated stable Comfy workflow files.
It reused Image Generator execute keys and built the graph at queue time:

| Family | No-ref Front | With-ref Front | Back |
|---|---|---|---|
| FLUX | `flux.txt2img` | `flux.img2img` | `flux.img2img` |
| Qwen Image 2512 | `qwen2512.txt2img` | `qwen2512.ref` | `qwen2512.ref` |
| Z-Image | `zimage.txt2img` | `zimage.ref_edit` | `zimage.ref_edit` |
| Illustrious XL (SDXL) | `illustrious.txt2img` | Unavailable | Unavailable |

Comfy user workflows had no Character Creator graphs. Gallery templates named “character” are video/SCAIL, not these stills.

This export **created** dedicated Character Creator API-format workflows from the exact live builders, then MCP-validated them against `:8188`.

## Live settings used

- Frame: `2048 x 2048` (`crs_2k_view_pixels`, `sheet_layout=cc_v2`)
- FLUX UNET: `flux1-kontext-dev.safetensors` + `clip_l.safetensors` + `t5xxl_fp16.safetensors` + `ae.safetensors`
- Qwen UNET: `qwen_image_2512_fp8_e4m3fn.safetensors` + `qwen_2.5_vl_7b_fp8_scaled.safetensors` + `qwen_image_vae.safetensors`
- Z-Image UNET: `z_image_turbo_bf16.safetensors` + `qwen_3_4b.safetensors` + `ae.safetensors`
- Illustrious XL: `Illustrious-XL-v1.0.safetensors`
- Queue defaults before family remap: steps=`20`, cfg=`3.5`
- Live SaveImage prefix on Adept jobs: `studio/{projectId[:8]}_imagegen`
- Dedicated export prefix: `studio/character_creator/<route>`

## Route → execute key → dedicated file

| Family | Character Creator route | Execute key | Builder | Dedicated JSON | MCP valid | Graph steps/cfg/denoise | LoadImage |
|---|---|---|---|---|---|---|---|
| Qwen Image 2512 | Front, no reference (text-to-image) | `qwen2512.txt2img` | `build_qwen_2512_txt2img_workflow` | `character_qwen2512_front_t2i.json` | PASS | 20/3.5/1.0 | no |
| Qwen Image 2512 | Front, reference attached (I2I / pixel bind) | `qwen2512.ref` | `build_qwen_2512_ref_workflow` | `character_qwen2512_front_i2i.json` | PASS | 50/4.0/1.0 | yes |
| Qwen Image 2512 | Back from approved Front (I2I / pixel bind) | `qwen2512.ref` | `build_qwen_2512_ref_workflow` | `character_qwen2512_back_from_front.json` | PASS | 50/4.0/1.0 | yes |
| FLUX | Front, no reference (text-to-image) | `flux.txt2img` | `build_flux_txt2img_workflow` | `character_flux_front_t2i.json` | PASS | 20/3.5/1.0 | no |
| FLUX | Front, reference attached (I2I / pixel bind) | `flux.img2img` | `build_flux_img2img_workflow` | `character_flux_front_i2i.json` | PASS | 20/3.5/0.35 | yes |
| FLUX | Back from approved Front (I2I / pixel bind) | `flux.img2img` | `build_flux_img2img_workflow` | `character_flux_back_from_front.json` | PASS | 20/3.5/0.35 | yes |
| Z-Image | Front, no reference (text-to-image) | `zimage.txt2img` | `build_zimage_txt2img_workflow` | `character_zimage_front_t2i.json` | PASS | 8/1.0/1.0 | no |
| Z-Image | Front, reference attached (I2I / pixel bind) | `zimage.ref_edit` | `build_zimage_ref_workflow` | `character_zimage_front_i2i.json` | PASS | 8/1.0/0.72 | yes |
| Z-Image | Back from approved Front (I2I / pixel bind) | `zimage.ref_edit` | `build_zimage_ref_workflow` | `character_zimage_back_from_front.json` | PASS | 8/1.0/0.72 | yes |
| Illustrious XL (SDXL) | Front, no reference (text-to-image). This is Character Creator's SDXL path. | `illustrious.txt2img` | `build_txt2img_workflow` | `character_illustrious_xl_front_t2i.json` | PASS | 28/5.0/1.0 | no |

## Unavailable / not Comfy

| Family | Route | Status | Reason |
|---|---|---|---|
| Illustrious XL (SDXL) | Front, reference attached | Unavailable | Character Creator has no Illustrious / SDXL I2I workflow. No graph was invented. |
| Illustrious XL (SDXL) | Back from approved Front | Unavailable | Back always requires I2I from Front pixels. Illustrious has no I2I path. |
| GPT Image | Hosted API Front / Back | Not Comfy | Hosted API adapter. No ComfyUI graph. |

## Per-file notes

### `character_qwen2512_front_t2i.json`

- Route: Front, no reference (text-to-image)
- Execute key: `qwen2512.txt2img`
- Builder: `build_qwen_2512_txt2img_workflow` in `studio-api/app/workflows/qwen_image_2512.py`
- Class types: CLIPLoader, CLIPTextEncode, EmptyLatentImage, KSampler, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader
- MCP `valid`: `True`
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_qwen2512_front_t2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_qwen2512_front_t2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_qwen2512_front_t2i.json`

### `character_qwen2512_front_i2i.json`

- Route: Front, reference attached (I2I / pixel bind)
- Execute key: `qwen2512.ref`
- Builder: `build_qwen_2512_ref_workflow` in `studio-api/app/workflows/qwen_image_2512.py`
- Class types: CLIPLoader, EmptyLatentImage, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAELoader
- LoadImage filename slot: `character_creator_reference.png`
- MCP `valid`: `True`
- Execute remaps generic steps {8,20} → qwen_image_2512_steps (50) and generic cfg {1.0, imagegen_default_cfg} → qwen_image_2512_cfg (4.0).
- Graph denoise is hardcoded 1.0. Character Creator job denoise=0.35 is not applied to this Qwen I2I graph.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_qwen2512_front_i2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_qwen2512_front_i2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_qwen2512_front_i2i.json`

### `character_qwen2512_back_from_front.json`

- Route: Back from approved Front (I2I / pixel bind)
- Execute key: `qwen2512.ref`
- Builder: `build_qwen_2512_ref_workflow` in `studio-api/app/workflows/qwen_image_2512.py`
- Class types: CLIPLoader, EmptyLatentImage, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAELoader
- LoadImage filename slot: `character_creator_approved_front.png`
- MCP `valid`: `True`
- Same topology as Front I2I. LoadImage slot is the approved Front, not the original reference.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_qwen2512_back_from_front.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_qwen2512_back_from_front.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_qwen2512_back_from_front.json`

### `character_flux_front_t2i.json`

- Route: Front, no reference (text-to-image)
- Execute key: `flux.txt2img`
- Builder: `build_flux_txt2img_workflow` in `studio-api/app/workflows/flux_image.py`
- Class types: CLIPTextEncode, ConditioningZeroOut, DualCLIPLoader, EmptySD3LatentImage, KSampler, SaveImage, UNETLoader, VAEDecode, VAELoader
- MCP `valid`: `True`
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_flux_front_t2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_flux_front_t2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_flux_front_t2i.json`

### `character_flux_front_i2i.json`

- Route: Front, reference attached (I2I / pixel bind)
- Execute key: `flux.img2img`
- Builder: `build_flux_img2img_workflow` in `studio-api/app/workflows/flux_image.py`
- Class types: CLIPTextEncode, ConditioningZeroOut, DualCLIPLoader, KSampler, LoadImage, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader
- LoadImage filename slot: `character_creator_reference.png`
- MCP `valid`: `True`
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_flux_front_i2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_flux_front_i2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_flux_front_i2i.json`

### `character_flux_back_from_front.json`

- Route: Back from approved Front (I2I / pixel bind)
- Execute key: `flux.img2img`
- Builder: `build_flux_img2img_workflow` in `studio-api/app/workflows/flux_image.py`
- Class types: CLIPTextEncode, ConditioningZeroOut, DualCLIPLoader, KSampler, LoadImage, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader
- LoadImage filename slot: `character_creator_approved_front.png`
- MCP `valid`: `True`
- Same topology as Front I2I. LoadImage slot is the approved Front.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_flux_back_from_front.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_flux_back_from_front.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_flux_back_from_front.json`

### `character_zimage_front_t2i.json`

- Route: Front, no reference (text-to-image)
- Execute key: `zimage.txt2img`
- Builder: `build_zimage_txt2img_workflow` in `studio-api/app/workflows/image_tools.py`
- Class types: CLIPLoader, CLIPTextEncode, EmptyLatentImage, KSampler, ModelSamplingAuraFlow, SaveImage, TextEncodeZImageOmni, UNETLoader, VAEDecode, VAELoader
- MCP `valid`: `True`
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_zimage_front_t2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_zimage_front_t2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_zimage_front_t2i.json`

### `character_zimage_front_i2i.json`

- Route: Front, reference attached (I2I / pixel bind)
- Execute key: `zimage.ref_edit`
- Builder: `build_zimage_ref_workflow` in `studio-api/app/workflows/image_tools.py`
- Class types: CLIPLoader, CLIPTextEncode, ImageScale, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, TextEncodeZImageOmni, UNETLoader, VAEDecode, VAEEncode, VAELoader
- LoadImage filename slot: `character_creator_reference.png`
- MCP `valid`: `True`
- Execute zimage.ref_edit does not pass job denoise into the builder. Graph uses builder default denoise=0.72.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_zimage_front_i2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_zimage_front_i2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_zimage_front_i2i.json`

### `character_zimage_back_from_front.json`

- Route: Back from approved Front (I2I / pixel bind)
- Execute key: `zimage.ref_edit`
- Builder: `build_zimage_ref_workflow` in `studio-api/app/workflows/image_tools.py`
- Class types: CLIPLoader, CLIPTextEncode, ImageScale, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, TextEncodeZImageOmni, UNETLoader, VAEDecode, VAEEncode, VAELoader
- LoadImage filename slot: `character_creator_approved_front.png`
- MCP `valid`: `True`
- Same topology as Front I2I. LoadImage slot is the approved Front.
- Execute zimage.ref_edit does not pass job denoise into the builder. Graph uses builder default denoise=0.72.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_zimage_back_from_front.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_zimage_back_from_front.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_zimage_back_from_front.json`

### `character_illustrious_xl_front_t2i.json`

- Route: Front, no reference (text-to-image). This is Character Creator's SDXL path.
- Execute key: `illustrious.txt2img`
- Builder: `build_txt2img_workflow` in `studio-api/app/imagegen_workflows.py`
- Class types: CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage, KSampler, SaveImage, VAEDecode
- MCP `valid`: `True`
- There is no generic SDXL Character Creator adapter. Illustrious XL is the SDXL family.
- Front-with-reference and Back are Unavailable — no I2I workflow is routed.
- Review path: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows\character_illustrious_xl_front_t2i.json`
- Artifact path: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows\character_illustrious_xl_front_t2i.json`
- Comfy user copy: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator\character_illustrious_xl_front_t2i.json`

## How Character Creator uses these graphs

1. Creator picks a family (or AUTO) and clicks Create Front / Create Back.
2. `cc_v2.generate_view` resolves `t2iKey` or `refKey` from `cc_v2_generators.py`.
3. `_enqueue_txt2img(..., sheet_layout='cc_v2')` sets 2048², `purpose=character`, and `taskType` `CC_V2_T2I` or `CC_V2_I2I`.
4. Queue worker calls `build_leaf_graph` in `workflow_execute.py` with the execute key above.
5. The graph in the matching JSON is what Comfy `:8188` receives (`/prompt` API format).

Front I2I and Back I2I share topology per family. They differ by prompt goal and which pixels are bound (reference vs approved Front).

Close-up uses the same I2I execute key as Back (approved Front pixels). A separate Close-up JSON was not requested.

## Owner review files

- Mapping report: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\CHARACTER_CREATOR_WORKFLOW_MAPPING.md`
- Downloadable JSON: `C:\AdeptFilmWorks\AIVideoStudio\docs\release-gate\character-creator\workflows`
- Local artifact copy: `C:\AdeptFilmWorks\AIVideoStudio\artifacts\character-creator\workflows`
- Comfy Desktop copies: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\Character Creator`

No further prompt tuning or certification was run.

