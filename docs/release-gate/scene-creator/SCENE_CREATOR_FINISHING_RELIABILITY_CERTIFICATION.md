# SCENE CREATOR FINISHING & RELIABILITY — GOVERNING CERTIFICATION

**Date:** 2026-08-14  
**Branch:** `beta`  
**Governing for:** Scene Creator finishing, reliability, and production polish  
**Does not supersede:** `SCENE_CREATOR_CINEMATOGRAPHER_SYSTEM_CERTIFICATION.md` or `SCENE_CREATOR_3D_CAMERA_ORIENTATION_CERTIFICATION.md` (those GOs remain historical).

This is the single governing document for this milestone (Build Law 30).

## Verdict

```text
NO-GO — HOSTED PLAYWRIGHT / VISUAL REVIEW / INDEPENDENT VERIFIER PENDING
```

Implementation and unit/integration tests are in. Hosted Playwright, pixel review, and independent verification have not yet closed the gate. Final language after those gates:

`GO — SCENE CREATOR FINISHING & RELIABILITY CERTIFIED END TO END`  
or  
`NO-GO — <blocker>`

## Scope

Operation-specific inpaint profiles, structured cinematographer on job params, candidate lineage, duplicate-submit guards, T2I preflight, creator-facing Output Gate copy, Expand/Feather presets, labels/compare/failed cards. No 3D/inpaint architecture rewrite. `qwen.edit` stays unpublished. Do not resurrect `:8760`.

**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`

**Topology:** `https://adeptui.vercel.app` → `https://api-beta.adeptui.org` → Studio API `:8758` → Comfy

## Implementation

| Area | Status |
|---|---|
| Operation profiles (Remove/Modify/Add/Replace denoise+grow+prompt) | IMPLEMENTED |
| Mask coverage gate `< 0.4%` | IMPLEMENTED |
| Expand Tight/Normal/Wide → `grow_mask_by` 2/6/14 | IMPLEMENTED |
| Feather Hard/Soft → export 0/8 | IMPLEMENTED |
| Output Gate creator copy (threshold still 2.0) | IMPLEMENTED |
| Structured `creativeContext.cinematographer` | IMPLEMENTED |
| Candidate lineage IDs + superseded-not-deleted | IMPLEMENTED |
| In-flight frontend + backend idempotency | IMPLEMENTED |
| T2I preflight / Z-Image+FLUX recommend / no `qwen.edit` | IMPLEMENTED |
| Labels, compare-with-source, failed Retry/Details | IMPLEMENTED |

## Unit / integration

| Suite | Result |
|---|---|
| `pytest tests/test_scene_creator_region_edit.py tests/test_cinematographer.py tests/test_cinematographer_orientation3d.py` | **49 passed** |
| `vitest` Scene Creator regionEdit + contracts + cameraCommandEngine | **39 passed** |

## Certification matrix

| Gate | Result |
|---|---|
| Unit tests | PASS |
| Backend integration | PASS |
| Playwright Scene Creator UI | PENDING |
| Playwright real local runtime | PENDING |
| Camera / 3D synchronization | PENDING |
| Region Edit operations | PENDING |
| Duplicate-submit protection | PASS (unit) / PENDING (hosted) |
| Model guard | PASS (unit) / PENDING (hosted) |
| Final inheritance | PASS (unit) / PENDING (hosted) |
| Persistence/reload | PENDING |
| Library | PENDING |
| Timeline | PENDING |
| Manual visual review | PENDING |
| Independent verifier | PENDING |

## Playwright

Suite: `tests/e2e/scene-creator/scene-creator-finishing-reliability.spec.ts`

```text
PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app
STUDIO_API_BASE=https://api-beta.adeptui.org
```

Do **not** use `ADEPT_BETA_TARGET=1` (maps to retired `:8760`).

## Remaining before GO

1. Production `studio-web` build + Studio API restart  
2. Scoped push to `beta` and hosted bundle SHA confirmation  
3. Hosted Playwright creator-flow (real runtime)  
4. Cursor-ide-browser visual review (expression, Add, Replace, cascade Final)  
5. Independent verifier
