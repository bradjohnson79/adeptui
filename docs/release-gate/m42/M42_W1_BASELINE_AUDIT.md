# M42 W1-1 — Baseline Audit

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 1 |
| **Date** | 2026-07-29 |
| **Baseline** | `phase2/wave6p-codirector-product-beta` @ `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| **Target** | `phase2/m42-image-runtime-foundation` |
| **Prerequisites** | M41 4.1A/B/B-L GO · Wave 6 consumer PASS · Wave 6P GO |
| **Verdict** | **AUDIT COMPLETE** |

---

## 1. Mission

Inventory every image-generation pathway. Eliminate ambiguity. Prepare a single canonical Image Runtime Architecture for Wave 2 certification. No new image features in this wave.

---

## 2. Canonical target path

```text
CreativeContext
→ ImageIntent
→ Workflow Resolver (modality=image)
→ Canonical Image Workflow Contract
→ QueueWorker
→ Image Runtime
→ Output Validation
→ Asset Registration
→ Project Library
```

Runtime must not import story, characters, cinematography, or Production Bible.

---

## 3. Pathway inventory (summary)

| Pathway | Status | Wave 2 |
|---|---|---|
| ImageGen txt2img | Working | Converge on resolver |
| ImageGen img2img / edit ops | Partial | Fix specialized vs generic |
| Character sheet / multi-angle | Working | Converge |
| Storyboard panel enqueue | Working | Converge |
| Executive closed-loop image | Working | Converge |
| M29 image API | Working (flagged) | Converge |
| W6P `propose_image_generate` | Broken/partial | Fix `enqueue_imagegen` |
| Storyboard propose apply | Stub (package only) | Wire or honest defer |
| Gen Tools upscale/bg/skin | Partial | Fix enqueue + real graphs |
| Chroma key | Working (OpenCV) | Utility category |
| Brand Studio | Partial | Converge |
| fal cloud image | Dead | Remain gated |
| Mock ImageGen | Disabled | Keep disabled |
| Character Creator / Environment gen | Not implemented | Later waves |

Full machine-readable list: `artifacts/m42/w1/baseline_inventory.json`.

---

## 4. Fragmentation findings

- Multiple enqueue entry points share `_imagegen` but none use Workflow Resolver contracts.
- No image Output Gate before job `done`.
- Specialized tool labels (RealESRGAN / BiRefNet / CodeFormer) do not match worker implementation.
- Product layers do **not** import Comfy builders or call `queue_prompt` (L-10B preserved).

---

## 5. Wave 2 defects recorded (not fixed here)

1. `ops.enqueue_imagegen` missing — breaks ProductionIntent txt2img.
2. `enqueue_imagegen_specialized` may not schedule the worker.
3. No fingerprint / output-gate on image completion.
4. ImageGen `refs[]` and LoRA stack not clearly applied in graph build.

---

## 6. Hard stop cleared

Authoritative path map frozen. Architecture scaffolding may proceed. Certified library and QueueWorker rewiring remain Wave 2.
