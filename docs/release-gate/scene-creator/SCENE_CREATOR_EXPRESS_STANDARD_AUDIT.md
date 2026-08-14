# SCENE CREATOR EXPRESS + STANDARD — ARCHITECTURE AUDIT

**Date:** 2026-08-14  
**Branch:** `beta`  
**Starting SHA:** `8b6ddf9850fcb461ea9facc5e910ae8a62664b34`  
**Status:** APPROVED — IMPLEMENTING  
**Governing for this milestone until the completion report ships.**

Labels: **CONFIRMED** unless marked **INFERENCE**. Binding amendments 1–15 are law for this build.

Do not cite Scene Master Sheet as Scene Creator. They are different products.

Playwright is out. Final live gate is Manual Beta (Express A–O + Standard A–G).

---

## Product

Co-Director Scene Creator Express is the fast scene-shot creation surface. Production **Scene Creator** is the Standard workspace. Both share one core: `useSceneCreator` / `SceneCreatorCore` over the existing `scene_creator` backend.

There is **no symbol named Scene Creator Express** today. The Co-Director tab `scene_creator` is the only UI. This milestone creates the Express/Standard split without a second backend.

---

## Confirmed architecture

**CONFIRMED.** Express UI: [`studio-web/src/components/CoDirector/SceneCreator/SceneCreatorPanel.tsx`](../../../studio-web/src/components/CoDirector/SceneCreator/SceneCreatorPanel.tsx). Backend: [`studio-api/app/scene_creator/router.py`](../../../studio-api/app/scene_creator/router.py) (`/api/scene-creator`). Frozen types: [`studio-api/app/spatial_map/ers_contracts.py`](../../../studio-api/app/spatial_map/ers_contracts.py). Persistence: [`ers_persistence.py`](../../../studio-api/app/spatial_map/ers_persistence.py). Generation: [`scene_generate.py`](../../../studio-api/app/codirector/capabilities/handlers/scene_generate.py) → `compile_shot_prompt` → `enqueue_imagegen_job`. Timeline: [`timeline_handoff.py`](../../../studio-api/app/scene_creator/timeline_handoff.py).

**CONFIRMED.** Production menu Pre-Production lists Continuity + Scene Master Sheet + Spatial Map + PoseCraft. Scene Creator is Co-Director-only.

**CONFIRMED dual ERS identity (binding defect).** Canonical sheet `sheetId` (file store) vs `EnvironmentReferencePackage.id` (trait store, `metadata.sheet_id`). Express passes `selectedSheetId` as `ers_package_id`. Lookup misses. Jobs still enqueue without directional refs.

**CONFIRMED.** Hosted image workflows (`imagen.txt2img`) are **Blocked**. Mapping `flux-kie` → local `flux` family would fake API-as-local. Scene Creator must not copy Character Creator’s Cloud checkbox.

---

## Binding amendments (frozen)

1. **ERS first.** Creator identity = `sheetId`. Resolve to existing package via `metadata.sheet_id` / `scene_layout_id`. If no package but a valid sheet exists: non-destructive runtime package from approved views, Atlas, Spatial placements, cameras, continuity/material/light. Never regenerate because lookup failed.
2. **True shared core.** `useSceneCreator` / `SceneCreatorCore` → Express + Standard. Not two UIs that separately call the same API.
3. **Scene ≠ Shot ≠ Candidate.** Four candidates must not create four Shots. Approval promotes Candidate → Approved Take.
4. **Take Law.** Same Timeline memory: Original Take Intent + Scene/ERS + Character Identity + Blocking + Camera + Approved Take State + User Correction Delta. Correction is a delta. Take A stays until Take B is approved.
5. **Express stays light.** Environment, Characters/Props, Camera, Shot Prompt, Generator, Generate, Candidates, Approve/Re-Take, Send to Timeline. No Standard dumped into Co-Director accordions.
6. **Standard is a production tool.** Left Scene/Shot browser, center preview, bottom take strip, right inspector (Environment, Characters & Props, Camera, Shot, Generation, Re-Take, Advanced).
7. **Generator source law.** Local OFF = zero local jobs. API OFF = zero API jobs. API ON = real hosted path. If not wired: `API Generation — Not Available`. Never an enabled API option that still routes through local ComfyUI.
8. **Candidate diversity.** Prefer distinct families. One eligible model → different seeds. Do not fake multi-model diversity.
9. **Camera authority.** Spatial Map = WHERE (slot, orientation, FOV). Scene Creator = HOW (Medium Wide / Static / Two Shot). No silent Spatial writes.
10. **Approved media law.** Only approved Take is eligible for Approved Library, Send to Timeline, canonical shot image, downstream continuity.
11. **Timeline requires valid `sceneId`.** Bind `SceneShot` to a Studio Scene row. Never `sceneId = ""`. Create/select through existing Scene ownership.
12. **Production menu.** Replace Scene Master Sheet with Scene Creator. Remove Continuity from navigation. Do not delete those backends.
13. **Availability warnings.** Unrelated Production readiness repairs are out of scope.
14. **Testing.** No Playwright. Required: contracts, ERS resolver, shot/candidate, reference authority, local/API routing, approval, Re-Take, Timeline handoff, frontend tests, TypeScript, production build, Manual Beta, independent verifier.
15. **Order.** Audit → contracts → ERS resolver → SceneShot backend → shared core → Express → Standard → approval/Re-Take → Library → Timeline → menu → tests → verify → Beta → commit + push `beta`.

---

## Out of scope

- Co-Director chat rewrite
- Spatial Map Cartesian redo
- Wiki
- Inventing API prices
- Continuity Score
- WAN/Hunyuan Timeline adapters
- Playwright
- 1 Frame / 3 Frame Extend UIs
- Deleting continuity / master-sheet backends
- Unrelated Production availability copy repairs
