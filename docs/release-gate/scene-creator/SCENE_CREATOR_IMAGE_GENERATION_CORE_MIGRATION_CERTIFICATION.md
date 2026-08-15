# SCENE CREATOR → ADEPT IMAGE GENERATION CORE MIGRATION

**Date:** 2026-08-15  
**Branch:** `beta`  
**HEAD SHA:** `3bbc696ed2f68b9bdf2e46a56d80b2ffa977d1b2`  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **ok** after restart (script reported FAILED then Recovered). ComfyUI ready on RTX 5090; free VRAM observed **3424 MB** at cert time.  
**Hosted UI:** deploy required for Playwright A–E against the new bundle (`index-AQs8WY7O.js` local build).  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Shot:** `2a58894b-b5d4-4e86-b068-7cd156199d98` (Shot 3)

This is the single governing document for this milestone (Build Law 30).

Prior GOs remain historical:

- `SCENE_CREATOR_CINEMATOGRAPHER_SYSTEM_CERTIFICATION.md`
- `SCENE_CREATOR_3D_CAMERA_ORIENTATION_CERTIFICATION.md`

Finishing NO-GO remains historical and is **not redefined away**:

- `SCENE_CREATOR_FINISHING_RELIABILITY_CERTIFICATION.md`

`SCENE_CREATOR_EXPRESS_STANDARD_AUDIT.md` is **historical / superseded** for Express-as-editor. Express is a launcher only.

`qwen.edit` stays unpublished. Do not resurrect `:8760`. Never `POST /api/projects`.

## Product law

> **Scene Creator Standard is the single authoritative Scene Creator workspace. Express exists only as an introduction and launch point into Standard.**

Required architecture:

`Express launcher` → `Standard Scene Creator` → `Adept Image Generation Core`

Do **not** certify Scene Creator Express generation.

## Verdict

```text
NO-GO — SCENE CREATOR ADEPT IMAGE GENERATION CORE MIGRATION NOT CERTIFIED END TO END
```

Architecture and Express launcher are implemented. Binary GO is blocked until hosted Playwright A–E plus finishing quality gates (valid Modify path, valid Replace path, completed inherited Final) are live-verified on the Image Core path. Silent Z-Image→FLUX swap remains forbidden.

## Scope implemented

| Area | Status |
|---|---|
| Express launcher (no production controls) | IMPLEMENTED |
| Open Scene Creator → workspace `scenecreator` | IMPLEMENTED |
| Compact Co-Director pop-up on Standard entry | IMPLEMENTED |
| `studio-api/app/image_core` facade | IMPLEMENTED |
| Scene preview/final enqueue via `image_core.generate` when `SCENE_IMAGE_CORE=1` (default ON) | IMPLEMENTED |
| Region-edit workflow chosen by core (`zimage.inpaint` / `flux.img2img`, never `flux.edit` Draft) | IMPLEMENTED |
| Recommend FLUX for Modify/Replace (UI, not silent routing) | IMPLEMENTED |
| Unit tests `test_image_core.py` + Scene Creator region/express | TESTED (53 passed) |
| Frontend contracts + region-edit recommend | TESTED (31 passed) |
| Hosted Playwright Express A–E | NOT VERIFIED (requires deployed bundle) |
| Qwen region-edit live API refuse | LIVE VERIFIED — POST region-edit `local_family=qwen2512` → HTTP 400 `This generator cannot edit a region. Choose Z-Image for Native Inpaint.` |
| FLUX Modify/Replace pixel proof on Image Core | NOT VERIFIED — finishing NO-GO carried; GPU free VRAM was 3.4 GB at cert time, not a clean GPU-first run |
| Inherited Final complete on Image Core | NOT VERIFIED — finishing NO-GO carried |

## Feature flag

`SCENE_IMAGE_CORE` defaults **ON**. Set `SCENE_IMAGE_CORE=0` only to roll back to the legacy Scene `forceWorkflowKey` path. Certification must use the ON path.

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PARTIAL — Express launcher + Standard navigation implemented; hosted A–E not yet run against the new bundle |
| Frontend | PASS (source) — Express is launcher; Standard three-zone remains |
| API | PASS (unit) — `image_core.preflight` / `generate` |
| Backend | PASS (unit) — Scene enqueue uses core when flag ON |
| Persistence | N/A for launcher; Standard still uses SceneShot candidates |
| Runtime | NOT VERIFIED — no new live GPU Image Core job IDs in this cert |
| Result | NOT VERIFIED |
| Reload | NOT VERIFIED hosted |
| Downstream | N/A until Final inheritance is live-proven |

## Limitations

- Finishing pixel quality on default Z-Image Modify/Replace remains FAIL from the prior cert. This migration does not claim that routing solved quality.
- Preferred Modify/Replace cert path remains recommended capable model (FLUX) with honest Keep Current.
- Hosted Playwright and independent verifier are required before GO.
