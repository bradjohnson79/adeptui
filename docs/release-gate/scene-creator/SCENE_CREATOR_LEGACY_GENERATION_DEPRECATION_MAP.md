# Scene Creator Legacy Generation Deprecation Map

**Date:** 2026-08-15  
**Branch:** `beta`  
**Governing cert:** `SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md`

This map classifies Scene Creator generation ownership after the Adept Image Generation Core cutover. Character Creator and Prop Creator `enqueue_imagegen_job` paths are **KEEP** and are not deleted here.

## KEEP

| Item | Why |
|---|---|
| Standard three-zone Scene Creator UX | Production editor |
| Cinematographer, 3D orientation, mask drawing | Scene product surface |
| Output Gate | Product quality after Core result |
| Candidate lineage fields, take labels, approval | Scene persistence |
| `_job_is_live` / frontend `inFlightRef` | Duplicate-submit guard (Core also keys idempotency) |
| Express launcher + compact Co-Director popup | Launcher only; not a second editor |
| `compile_camera_context` structured JSON | Scene sends camera; Core/adapter may render prose |
| ERS `ersPackageId` / `ers_composite_asset_id` / `reference_image_ids` | Structured context, not prompt-only |
| Character/Prop `enqueue_imagegen_job` | Out of scope for this cutover |

## MIGRATE (landed this pass)

| Item | Destination |
|---|---|
| Preview / Final enqueue | `image_core.preflight` then `image_core.generate` when `SCENE_IMAGE_CORE=1` |
| `region_edit_shot` | Same Core path (`purpose=region_edit` / `final_region_edit`). Flag-ON does **not** call `_enqueue_compiled` |
| Workflow key / certified resolution | Core pins after resolve (`generate.py` `forceWorkflowKey`). Scene must not send these as intent |
| Recommend Modify/Replace → FLUX | `GET /api/image-core/recommend` is the registry. Frontend fallback in `regionEdit.ts` must stay lockstep |
| Capability / visual-edit path | `studio-api/app/image_core/capability.py` |
| Preview 512×288 / certified size | `studio-api/app/image_core/resolution.py` |

## DEPRECATE (flag-OFF emergency rollback only)

Set `SCENE_IMAGE_CORE=0` only to roll back. Certification uses the ON path.

| Item | Rule |
|---|---|
| `_honest_t2i_instead_of_strategy_a` | Never used when `SCENE_IMAGE_CORE=1` **and** Final. No automatic Core-failure fallback onto this path |
| `_compile_region_edit_runtime` + `_enqueue_compiled` | Flag-OFF region-edit only |
| Scene `forceWorkflowKey` / `{family}.txt2img` / certified 1024×1024 as enqueue intent | Flag-OFF only. Core may still pin `forceWorkflowKey` internally after resolve |
| `_region_edit_workflow` as Scene-chosen keys | Flag-OFF compile helper; flag-ON delegates through Core preflight |

## DELETE (confirmed unused)

| Item | Status |
|---|---|
| ExpressLayout / Express generate handlers | Removed from `SceneCreatorCore.tsx` |
| `scene_creator_express_generate` route | Must 404 — never create |

## Law

Core failure = FAIL. No silent family swap. No silent Core → legacy T2I fallback.
`qwen.edit` stays unpublished.
