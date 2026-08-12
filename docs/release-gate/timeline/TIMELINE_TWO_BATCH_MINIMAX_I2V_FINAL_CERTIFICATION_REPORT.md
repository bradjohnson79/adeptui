# Timeline Two-Batch MiniMax Image-to-Video Final Certification Report

**Date:** 2026-08-05 (UTC)  
**Branch:** `feature/ai-guided-setup`  
**HEAD (at cert run):** `fa09c99d6395c29461cdec4555055faad116c435`  
**Beta UI:** `http://127.0.0.1:8760/`  
**Studio API:** `http://127.0.0.1:8758/`  
**Protected project (untouched):** `77a4b96c-8e3f-4501-897c-51bab99bedb7`

---

## Verdict

```text
GO — TIMELINE TWO-BATCH MINIMAX IMAGE-TO-VIDEO PLAYWRIGHT CERTIFICATION PASSED
```

---

## Previous-run disclaimer

The prior MiniMax **text-to-video** two-batch Playwright run is **not** the authoritative final certification for the original image-to-video requirement. It remains non-authoritative evidence of batching/lineage/placement only. See [`TIMELINE_TWO_BATCH_FINAL_CERTIFICATION_REPORT.md`](TIMELINE_TWO_BATCH_FINAL_CERTIFICATION_REPORT.md).

Phase 1 audit (pre-implementation): [`TIMELINE_MINIMAX_I2V_PATH_AUDIT.md`](TIMELINE_MINIMAX_I2V_PATH_AUDIT.md).

---

## Engine lock

| Field | Value |
| --- | --- |
| Generator | `minimax-h3-i2v-local` |
| Workflow | `route-a-experimental-private-i2va` |
| Mode | `image_to_video` / `one-frame` |
| Fallback | `fallbackAllowed=false` — no LTX / Seedance / Kling / T2V substitute |
| Runtime | Isolated ComfyUI Route A `:8192` |
| Profile | Experimental Private Profile (480×256, length 5, steps 4, native audio) |

---

## Batch matrix

| Batch | Start image | SHA256 (prefix) | Comfy filename | Prompt theme | Output asset |
| --- | --- | --- | --- | --- | --- |
| 1 | `source-batch1-subject.png` (red circle / dark teal) | `0820cf67…` | `studio/h3_i2v_7cc7089d.png` | Identity-preserving red circular subject | `b198bd65-…` |
| 2 | `source-batch2-subject.png` (blue triangle / cream) | `537c30b3…` | `studio/h3_i2v_2949de40.png` | Identity-preserving blue triangular subject | `bcd1db98-…` |

Hashes and Comfy filenames differ across batches (hard gate).

---

## Gate matrix

| Gate | Result |
| --- | --- |
| MiniMax Route A ready (GPU) | **PASS** |
| Fresh disposable project (not protected) | **PASS** |
| Generator locked to `minimax-h3-i2v-local` | **PASS** |
| Normalized request `generationMode=image_to_video` + `startImageAssetId` per batch | **PASS** |
| Submitted Comfy graph has `LoadImage` | **PASS** |
| Uploaded Comfy filename bound on `LoadImage` | **PASS** |
| `MiniMaxH3ImageToVideo.first_frame` → LoadImage | **PASS** |
| Distinct image hashes + Comfy filenames across batches | **PASS** |
| Workflow id `route-a-experimental-private-i2va` (not T2VA) | **PASS** |
| No LTX / API / silent T2V downgrade | **PASS** |
| Two Library assets + Timeline `bbclip_*` placement [B1][B2] | **PASS** |
| Lineage keeps `startImageAssetId` after reload | **PASS** |
| Visual conditioning (frame B1 ≠ Image 2; frame B2 ≠ Image 1) | **PASS** |
| Unit/API regression suite | **PASS** (56 tests) |

---

## Playwright evidence

```text
npx playwright test tests/e2e/timeline/timeline-two-batch-minimax-i2v-final-certification.spec.ts
  --project=chromium --retries=0 --workers=1
Result: 1 passed (3.2m)
ADEPT_BETA_TARGET=1 · UI http://127.0.0.1:8760 · API http://127.0.0.1:8758
```

**Artifact run:**  
`docs/release-gate/timeline/artifacts/timeline-two-batch-minimax-i2v-final-certification/2026-08-05T16-57-10-955Z/`

Key artifacts:

- `submitted-comfy-graph-batch-1.json` / `submitted-comfy-graph-batch-2.json`
- `minimax-i2v-input-binding.json`
- `source-batch1-subject.png` / `source-batch2-subject.png`
- `first-frame-batch-1.png` / `first-frame-batch-2.png`
- `output-batch-1.mp4` / `output-batch-2.mp4`
- `i2v-conditioning-review.md`
- `VERDICT.json`

### Visual conditioning review

- Batch 1 first frame: red oval / dark teal family matching Image 1 — **not** cream/blue triangle.
- Batch 2 first frame: blue triangle / warm cream / yellow center matching Image 2 — **not** red circle / teal.

---

## Implementation summary

- Route A: `build_i2va_graph`, Comfy `upload_image`, `submit_i2va`, persisted `submittedGraph`
- Preflight/capability: private Route A allows `one-frame` with start frame; T2V-only honesty retained on `minimax-h3-t2v-local`
- Timeline adapter: `minimax-h3-i2v-local` (UI: MiniMax H3 Image-to-Video (Local))
- Shared completion lineage includes `startImageAssetId` / sha256 / comfy binding

---

## Limitations

- Experimental Private Profile remains short (5 frames / 4 steps) — draft motion quality, not production length.
- Three-frame / start-end / PoseCraft / ERS remain unsupported on Route A.
- `npm run test:e2e:beta` spawn helper hit Windows `EINVAL` in this environment; cert was run with equivalent env + `npx playwright test` (same ADEPT_BETA_TARGET / URLs / retries=0 / workers=1).

---

## Manual review

1. Open Beta: `http://127.0.0.1:8760/`
2. Inspect artifacts under the run folder above (source vs first-frame PNGs, submitted graphs).
3. Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never mutated.
