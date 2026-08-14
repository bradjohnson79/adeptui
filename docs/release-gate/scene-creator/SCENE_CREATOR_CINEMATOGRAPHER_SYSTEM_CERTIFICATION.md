# SCENE CREATOR CINEMATOGRAPHER SYSTEM — FINAL END-TO-END CERTIFICATION

**Date:** 2026-08-14  
**Branch:** `beta`  
**HEAD SHA:** `e5a2dbeff11b00a21a00b3ac638f981986e2d8a2`  
**Deployed SHA:** not pushed this increment  
**Studio API:** `http://127.0.0.1:8758/` (live, cinematographer routes mounted)  
**Creator UI (hosted):** `https://adeptui.vercel.app` — **stale** (no Cinematographer panel in the live bundle)  
**Local web build:** `studio-web` production build passed (`dist/assets/index-xju9SkB2.js`)

## Verdict

```text
NO-GO — SCENE CREATOR CINEMATOGRAPHER SYSTEM NOT CERTIFIED END TO END
```

Independent verifier ([Verify cinematographer live E2E](116643cc-e594-4cad-a97d-f94f7cc331db)) returned `VERIFIED — FULL-STACK E2E PASSED` for **local API → Studio API → Comfy → Library → reload**, and **HOSTED UI NOT VERIFIED**. Hosted Vercel does not include the Cinematographer panel. Local-only does not close that hosted defect.

API preview: models were discovered (Kie FLUX, Nano Banana) and labeled **Standard-Cost Preview Only**. No paid cloud preview was fired.

```text
API RUNTIME CERTIFICATION BLOCKED BY PROVIDER AVAILABILITY
```

(narrow capability line: economy/draft preview is not offered by the discovered hosted adapters; local economy preview **was** run.)

## Architecture

Authoritative cameras remain `SpatialCamera` on `SpatialMapDocument` (`cameraSlot` 0–3 → C1–C4). Scene Creator stores **adjusted** state in `ProjectTrait` category `scene_cinematographer` (key = `scene_id`). `SAVE_CAMERA_BACK_TO_SPATIAL_MAP = False`. Live proof: Spatial Map document `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` still has C1/C2/C3 at cells 11,11 / 13,11 / 9,11 with `shotType=medium` after Scene Creator ECU/lock/final.

## Tests measured

- Frontend Vitest: **12 passed** (`cameraCommandEngine.test.ts`, `sceneCreatorContracts.test.ts`)
- Backend pytest: **30 passed** (`test_cinematographer.py`, `test_scene_creator_express.py`)
- `studio-web` production build: **passed**

## Live Schnick Coffee / Korri

Project `2347bf46-3762-4763-86c5-4a6032522278`, scene `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`, Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`, coffee cup `a8d48a46-ce0d-4b53-8a47-330779346eb0` (Held By, right hand).

| Item | Value |
|---|---|
| Camera 1 | `1a8198ec-8c40-4608-9b9f-0d4544aabe5c` locked v3 hash `cf0bccd81ec13ef0` |
| Shot | `88539183-6fd2-495a-aa48-e406a3653cd5` |
| Preview job | `ce67cc8a-c7b1-44ff-8f92-9d4362ba04b7` done, 512×288, `allow_draft_cert_harness=true`, tag `scene_preview_88539183_c1` |
| Preview asset | `4ab6df9b-0967-4f82-9233-44d3065ef7e7` → `imagegen_edit_d1736b7c.png` |
| Final job | `01dbe716-8c35-4387-a90d-f2adf7d98ffe` done, 1280×720, tag `scene_shot_88539183_c1` |
| Final asset / Take A | `54774aad-56b4-4f07-840f-4ea19d431cce` / candidate `8df4ba42-ff75-44d6-a4ef-b2e042c906fd` approved |
| Evidence | `docs/release-gate/scene-creator/evidence/c1-preview-ecu.png`, `c1-final-ecu.png` |

## Certification scenarios A–P

| ID | Result | Notes |
|---|---|---|
| A Handoff | PASS | Workspace hydrates C1–C3 from Spatial Map. C4 is not on this map (honest Off tile). |
| B Command | PASS | Live ECU: `CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1, Korri with PROP 1, Coffee Cup included in composition.` |
| C Step back | PASS | C11R11 → C11R12; FOV stayed medium; target preserved. |
| D High angle | PASS | Pitch −28, height 2.2; cell unchanged. |
| E Local preview | PASS | Draft 512×288, purpose `scene_shot_preview`. Image is a low-res ECU of the held cup. |
| F API economy | BLOCKED | Standard-Cost Preview Only. No hidden paid preview. |
| G Undo | PASS | Zoom → high → step undone; C1 restored to ECU v3. |
| H Lock | PASS | Lock at v3/hash. Reload still locked. Missing preview asset does not unlock (unit). |
| I Final render | PASS | One production candidate Take A, approved, `source_camera_id`=C1, version 3. |
| J Preview vs final | PASS | Preview: draft cup ECU. Final: higher-res Korri face ECU with held cup. Same locked contract. |
| K Prop target | PASS | C2 `CAMERA 2 take CLOSE-UP on PROP 1, Coffee Cup.` C1 lock unchanged. |
| L Held By | PASS | Preview prompt includes `Prop is held the character (right hand).` Cup was not relocated on the map. |
| M Camera independence | PASS | C1 mutations left C2 at v1/medium until the later C2 prop command. No exclusive-toggle. C4 absent. |
| N Model switch | PARTIAL | Camera pack is provider-agnostic. Live jobs executed **Qwen 2512** while the take label said Z-Image. `lockModelFamily` is now applied on local plans so a later run cannot silently retarget. Not re-fired. |
| O Failure honesty | IMPLEMENTED | Preview failure stamps `failed` without rolling camera (code + unit). Not live-failed. |
| P Reload | PASS | Second GET: C1 `locked=true` v3. Pack in ProjectTrait. |

## One-candidate regression

Take A approved with `candidates.length === 1`, then Re-Take appended Take B (approved Take A kept). Take-strip progress uses actual candidate count. After the C2 prop command, live Take B stamped C2; retake now prefers the **approved** `source_camera_id`.

## Independent verifier E2E TRACE

| Stage | Status |
|---|---|
| User action | PASS |
| Frontend | N/A (hosted bundle has no panel; local browser not clicked) |
| API | PASS |
| Backend | PASS |
| Persistence | PASS |
| Runtime | PASS (Comfy / CUDA 5090) |
| Result | PASS |
| Reload | PASS |
| Downstream | PASS (Spatial Map not overwritten) |

## Limitations

- Hosted Vercel frontend does not include this UI until `beta` is pushed.
- Schnick Coffee has three Spatial Map cameras, not four.
- Live preview/final executed Qwen 2512 despite a Z-Image picker value; family lock is repaired in source for the next run.
- Co-Director HTTP context still used Spatial Map `sceneId=None` on the running process; `list_packs` repair is in source (DB read of the new path shows C1 locked ECU).
- Natural-language camera parsing is out of scope.
- Save-back-to-Spatial-Map is an extension point only.

## Manual review

1. Push `beta` and confirm `https://adeptui.vercel.app` contains Cinematographer.
2. Open Schnick Coffee → Scene Creator.
3. Camera 1 is locked Extreme Close-Up on Korri + coffee cup.
4. Confirm take strip (Take A approved, Take B present), Re-Take, Send to Timeline.
5. Confirm Spatial Map cameras were not rewritten.

## GO criteria remaining

Hosted Cinematographer panel on Vercel against this live Studio API. Until then the governing verdict stays NO-GO.
