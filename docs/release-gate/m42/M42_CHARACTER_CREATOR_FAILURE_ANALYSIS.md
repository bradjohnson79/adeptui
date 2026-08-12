# M42 Character Creator Failure Analysis

**Sprint:** Character Creator Correction — Korri Identity Lock  
**Date:** 2026-07-31  
**Mock data:** false

---

## Summary

Two platform-blocking failures prevented Korri production sheets. Both are corrected and verified by a live cert run (`passed: true`, 15 roles, `OWNER_APPROVED`).

---

## F-1 — Omni + EmptyLatent latent shape crash

| Field | Detail |
|---|---|
| **Symptom** | `ComfyUI job failed: shape '[1, 14, 14, 1280]' is invalid for input of size 328960` on `character_sheet` / `zimage.ref_edit` |
| **Root cause** | `build_zimage_ref_workflow` fed the reference image into `TextEncodeZImageOmni` while also using `EmptyLatentImage`, producing incompatible latent geometry |
| **Affected subsystem** | Workflow Builder → ComfyUI execution (`workflows/image_tools.py`) |
| **Corrective action** | Rebuild ref path as `LoadImage → ImageScale → VAEEncode → KSampler(denoise≈0.72)` with **text-only** Omni (no `image1`) |
| **Verification** | Unit: `studio-api/tests/test_zimage_ref_edit_latent_fix.py`. Live: details + performance phases completed (8× `zimage.ref_edit` jobs done) |

---

## F-2 — WORKFLOW_GRAPH_DRIFT after fix

| Field | Detail |
|---|---|
| **Symptom** | Details phase failed: `WORKFLOW_GRAPH_DRIFT: zimage.ref_edit@1.0.0 graphHash mismatch` |
| **Root cause** | Certified fingerprint still hashed the old Omni+EmptyLatent graph (`sha256:d7a2dcff…`); builder produced `sha256:c8c2c11c…`. Registry is fail-closed (`lru_cache` load + drift assert before queue) |
| **Affected subsystem** | Image Runtime drift gate + `config/image-workflows/certified-registry.json` |
| **Corrective action** | Recompute fingerprints; update `zimage.ref_edit` entry (`CERT-IMG-ZIMAGE-REF-001-20260731-006`); restart Beta to clear registry cache |
| **Verification** | Live cert advanced through details → performance → `READY_FOR_OWNER` without drift errors |

---

## F-3 — Coverage path previously blocked by F-1 (mitigated)

| Field | Detail |
|---|---|
| **Symptom** | Earlier visual sheet attempts failed mid-pack when using character_sheet/ref_edit for turnaround |
| **Root cause** | Same as F-1 when coverage depended on broken ref_edit |
| **Affected subsystem** | `visual_sheet.advance_visual_sheet_pack` |
| **Corrective action** | Coverage pack uses certified `zimage.txt2img` per role with Korri lock prompts; details/performance use fixed ref_edit from hero. One retry per failed coverage role |
| **Verification** | Coverage completed 6/6 roles in live cert (~roles 1→7) |

---

## Non-blocking quality notes (correction loop, not NO-GO)

Per `M42_RESILIENT_GENERATION_CERTIFICATION_ADDENDUM.md`, generative variance is iterative refinement:

| Observation | Assessment |
|---|---|
| Occasional single ponytail vs twin on side/back | Minor hair construction drift — refine prompts/seeds later |
| Footwear / wrap vs skirt variance across turnaround | Wardrobe continuity refinement |
| `expression_sheet` sometimes single portrait vs multi-panel | Prompt/layout refinement |

Core locked traits (black twin tails on hero/front/closeups, purple eyes, pale skin, pointed ears, circuitry, wooden earrings, black handmade aesthetic) held on primary sheets.

---

## Issue log format (required)

1. **F-1** — root cause: Omni+EmptyLatent; subsystem: workflow; action: VAEEncode img2img; verification: live ref_edit ×8 done  
2. **F-2** — root cause: stale graphHash; subsystem: certified registry; action: re-fingerprint + restart; verification: no drift in cert  
3. **F-3** — root cause: dependency on F-1; subsystem: visual sheet coverage; action: txt2img coverage_pack; verification: 6 coverage roles done  
