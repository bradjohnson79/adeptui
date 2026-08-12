# M3.2a — Generation Tools Audit Report

**Date:** 2026-07-28  
**Scope:** Approved 10 tools + full lifecycle matrix  
**Companion:** [M32A_GENERATION_CAPABILITY_MATRIX.md](./M32A_GENERATION_CAPABILITY_MATRIX.md), `artifacts/m32a/capability-matrix.json`

## Policy

- COMPLETE only when UI → Co-Director → API → provider → queue → Library → lineage → reload all work with **real** outputs.
- Mock / stub / UI-only / registry-only is never COMPLETE.
- Non-destructive by default; no silent paid cloud.
- De-lighting must not be sold as ordinary color correction.
- Video upscale must not be certified from per-frame image upscale alone.

## Approved-10 status (pre-implementation baseline → post-M3.2a target)

| # | Tool | Baseline | Target / honesty |
|---|---|---|---|
| 1 | Video Upscaler | MISSING | Wire SeedVR2 or BLOCKED if weights/nodes absent |
| 2 | Image Upscaler | PARTIAL (img2img stub) | RealESRGAN/SeedVR2 image path |
| 3 | Background Remover + chroma | PARTIAL / MISSING | BiRefNet matte + OpenCV chroma |
| 4 | Lighting Removal | MISSING | BLOCKED unless production OSS found |
| 5 | Scriptwriter | PARTIAL (CRUD) | Generative persist + Co-Director |
| 6 | Music | PARTIAL (ACE-Step sandbox) | Product UI + Asset + Library + CD |
| 7 | SFX | PARTIAL (MMAudio sandbox) | Same as music |
| 8 | Video Extender | MISSING | Generative continuation via I2V; label honestly |
| 9 | Portrait Skin Enhancer | PARTIAL (face_refine stub) | CodeFormer/GFPGAN path |
| 10 | Brand Studio | MISSING | Locked-ref generate module |

## Evidence anchors (baseline)

- ImageGen stubs: `studio-web/src/components/ImageGenPanel.tsx` `EDIT_OPS`
- Job path: `studio-api/app/queue_worker.py` `_imagegen` / `imagegen_edit`
- Audio: `studio-api/app/codirector/m29/audio/service.py`, adapters ACE-Step / MMAudio
- Script: `studio-web/src/components/ScriptStoryboardWorkspace.tsx`
- CD tools: `studio-api/app/codirector/tools/definitions.py` (no media enhance tools at baseline)
- Library: `studio-api/app/project_library/taxonomy.py`

## Cross-cutting gaps addressed in M3.2a

1. Tools hub with Create / Enhance / Remove and Replace / Extend and Reframe / Finish
2. Shared non-destructive asset registration + lineage
3. Co-Director propose tools for approved ops
4. Library taxonomy assignment on generate/enhance completion
5. Local-vs-cloud disclosure; paid cloud blocked unless explicit BYOK

## Certification

See Playwright `tests/e2e/m32a/generation-tools.spec.ts` (GEN-TOOLS-01..24 coverage; core gates green) and matrix finalization in the capability matrix doc.

### Slice result

| Gate | Result |
|---|---|
| Capability matrix (full lifecycle) | PASS — SHIP / PRESENT / DEFERRED |
| Tools hub IA | PASS |
| Non-destructive lineage contract | PASS |
| Approved-10 wired (honest PARTIAL/BLOCKED) | PASS |
| De-lighting not faked | PASS (BLOCKED) |
| Co-Director propose/read tools | PASS |
| Unit tests `test_m32a_generation_tools.py` | PASS (6) |
| Playwright m32a generation-tools | PASS (6 core specs) |

**Overall M3.2a slice:** **PASS with PARTIAL production readiness** for Comfy-weight-dependent tools until SeedVR2/BiRefNet/CodeFormer weights are installed on the operator machine.
