# Krea 2 ComfyUI Workflow

## Authoritative Workflows

Certified registry keys (see `config/image-workflows/certified-registry.json`):

- `krea2.turbo.txt2img`
- `krea2.turbo.img2img`
- `krea2.turbo.reference`
- `krea2.raw.txt2img`
- `krea2.raw.img2img`

All builders live in `studio-api/app/workflows/krea2_image.py`.

## Turbo Defaults

Based on official Krea 2 guidance:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Steps | 8 | Distilled fast inference |
| CFG | 0.0 | Turbo disables CFG under recommended settings |
| `mu` / timestep shift | 1.15 | Controls noise schedule shift |
| Resolution | creator-selectable | 1024×1024, 1536×1024, 1024×1536, 1920×1080, 2K-class where valid |

## RAW Defaults

| Parameter | Value | Notes |
|-----------|-------|-------|
| Steps | 52 | Base undistilled model |
| CFG | 3.5 | Standard guidance for base model |
| Resolution | creator-selectable | Same divisibility rules as Turbo |

## Builder Dispatch

`app/image_runtime/workflow_execute.py` routes family `krea2` to `app/workflows/krea2_image.py`. The builder receives:

- `prompt` (creator-written, natural language)
- `negative_prompt`
- `width`, `height`
- `steps`, `cfg`
- `seed`
- `mu` (Krea-specific, only for Turbo)
- `reference_images` (list of `AssetRef` with role)
- `loras` (list of `{loraId, strength}`)

The builder constructs a fresh ComfyUI graph per request and returns it for fingerprint validation.

## Reference Images

Krea 2's open ComfyUI path exposes generic reference-image nodes. The builder maps Adept semantic roles onto those nodes:

- `style` / `palette` / `lighting` → style reference node
- `identity` / `character` / `wardrobe` → identity reference node
- `environment` / `location` / `architecture` → environment reference node (role preserved in metadata)
- `moodboard` / `mood` → moodboard reference node

Unsupported roles remain upstream planning metadata and are not incorrectly sent to the model.

## LoRA

LoRA spec carries:

- `loraId`
- `baseModelFamily = krea2`
- `trainingBase = krea2-raw`
- `recommendedInference = krea2-turbo`
- `strength` (default 0.8)

The builder resolves the LoRA path from the shared model root and applies it with the correct strength.

## Workflow Export

Developer mode can export the built graph (API JSON + bindings) without queueing generation, gated by `ADEPT_TIMELINE_WORKFLOW_EXPORT=1` or the image-pipeline equivalent. This lets creators inspect the actual Krea ComfyUI graph before manual generation.

## See Also

- `KREA2_INTEGRATION_ARCHITECTURE.md`
- `config/image-workflows/certified-registry.json`
- `app/workflows/krea2_image.py`
