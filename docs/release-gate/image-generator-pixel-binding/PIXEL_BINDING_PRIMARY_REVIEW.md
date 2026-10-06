# Image Generator reference PIXEL BINDING — READY FOR PRIMARY REVIEW

Date: 2026-09-12 (PT)

## Root cause (confirmed)

CIS sent `referenceAssetIds`; purpose=`general` + locked `qwen2512` compiled to **`qwen2512.txt2img`**. Worker never `LoadImage`. Job bc11a72c pattern: 2 ref IDs + txt2img.

`qwen2512.ref` = single LoadImage (`TextEncodeQwenImageEdit`). Dual Character+Environment is not supported on that graph alone.

## Repair strategy chosen

**A (preferred, available on this machine):** Qwen Edit 2509 is Runtime Ready → CIS dual identity+scene routes through EditPlus `image1` + `image2`.

| Case | Before | After |
|------|--------|-------|
| CIS general + 0 refs + qwen2512 | `qwen2512.txt2img` | unchanged |
| CIS general + 1 ref + qwen2512 | silent `qwen2512.txt2img` | **`qwen2512.ref`** (Certified LoadImage) |
| CIS general + char+env (or 2+ refs) + qwen2512 | silent `qwen2512.txt2img` | **`qwen_edit_2509.edit`** with IDENTITY + SCENE slots |
| CIS general + refs + zimage | often generate | **`zimage.ref_edit`** + `IMAGE_I2I` |
| Locked illustrious + refs | silent / ambiguous | **fail-closed** (`cannot use an attached picture`) |

## Files changed

- `studio-api/app/image_product/cis_ref_binding.py` **(new)** — typed refs + bind strategy
- `studio-api/app/image_product/compile.py` — apply binding; stamp metadata; refuse silent txt2img
- `studio-api/app/image_product/resolve.py` — CIS general + refs never OK as `*.txt2img`
- `studio-api/app/image_studio/contracts.py` — `authorityReferences` + `IMAGE_I2I` stamp
- `studio-api/app/workflows/qwen_image_edit_2509.py` — optional `scene_image` → LoadImage + EditPlus `image2`
- `studio-api/app/image_runtime/workflow_execute.py` — pass `scene_image`
- `studio-api/app/image_runtime/local_comfy_adapter.py` — forward scene/character/environment refs
- `studio-api/app/image_runtime/ref_generate_pixels.py` — `scene_asset_id_from_intent`
- `studio-api/app/queue_worker.py` — upload scene plate to Comfy when multi-ref
- `studio-web/src/components/image-studio/CinematicImageStudio.tsx` — send typed `authorityReferences` + `IMAGE_I2I`
- `studio-web/src/contracts/cinematicImageStudio.ts` — typed refs on request
- `studio-api/tests/test_cis_i2i_compile.py` — aligned with production bind / fail-closed
- `studio-api/tests/test_qwen_edit_2509.py` — added multi-ref slot assert

## Dry-run proof (this wave)

```
dual  → workflowKey=qwen_edit_2509.edit  source=cami-id  scene=corridor-id  (NOT txt2img)
single→ workflowKey=qwen2512.ref
builder→ LoadImage×2 + EditPlus image1/image2
pytest tests/test_cis_i2i_compile.py + multi-ref builder → 9 passed
```

## How Brad should re-run Cami + Corridor (visual prove)

1. Restart / reload **studio-api** so the new compile path is live (Comfy does **not** need restart for this wave).
2. Rebuild or hard-refresh **studio-web** so CIS sends `authorityReferences` with kinds.
3. Open Image Generator (CIS) on the project that has Cami + Corridor library plates.
4. Attach **@Cami** (character) and **#Corridor** (environment) — confirm chips show typed kinds.
5. Lock / choose **Qwen-Image-2512**.
6. Generate. Expected compile/runtime:
   - `workflowKey` = `qwen_edit_2509.edit` (not `qwen2512.txt2img`)
   - Job params / intent metadata: `referenceBinding.strategy=qwen_edit_2509.multi_ref`
   - `sourceAssetId` = Cami asset; `sceneReferenceAssetId` = Corridor asset
   - Comfy graph: two `LoadImage` nodes; EditPlus has `image1` + `image2`
7. Visual success: Cami identity recognizable **and** Corridor environment present (not invent-from-text).

Single-ref smoke: attach only Cami → expect `qwen2512.ref` + one LoadImage.

## Deferred (called out)

- **Lighting:** still prompt text only this wave; lighting catalog parity is next wave.
- **Result modal:** untouched; follow-up OK.
- Do **not** revive Edit Studio or Scene Creator product UI.

## Product laws honored

- Actual images authoritative (pixels uploaded / LoadImage).
- Adept `@/#/%` stay creator grammar; provider gets IDENTITY/SCENE slots.
- Prefer repair existing Image Core / image_product path; CC 2509 multi-ref pattern reused.
- Fail-closed honesty: no silent txt2img when refs selected and model cannot bind.
