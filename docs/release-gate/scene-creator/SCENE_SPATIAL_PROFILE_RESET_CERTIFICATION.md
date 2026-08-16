# Scene Spatial Profiles + Scene Creator Reset

**Date:** 2026-08-15  
**Branch:** `beta`  
**Starting SHA:** `ad6423a`  
**Product SHA:** `a059818`  
**Hosted UI:** `https://adeptui.vercel.app` (this feature certified against production `studio-web` dist preview, not a new Vercel SHA)  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200**  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Shot 3 (preserved):** `2a58894b-b5d4-4e86-b068-7cd156199d98`

This is the single governing document for Spatial Profiles + Reset Workspace (Law 30). It is independent of Add / napkin production in `SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md`. Add remains **NO-GO**. This feature may earn a clean GO without pretending Add is solved.

Do not resurrect `:8760`. Never `POST /api/projects`. Never duplicate ERS. Never rewrite Timeline (`Scene.director_json`). `_apply_cinematic` and Image Core were not changed for this milestone.

## Verdict

```text
GO — SCENE SPATIAL PROFILES + SCENE CREATOR RESET CERTIFIED END TO END
```

Independent verifier:

```text
VERIFIED — SCENE SPATIAL PROFILES + RESET PASSED
```

## What shipped

One object: the creator-facing **Spatial Profile** *is* the `scene_production_handoff` pointer record.

- `POST /api/scene-creator/projects/{pid}/production-handoff` synchronizes canonical ERS / Spatial Map / cinematographer / shot pointers onto the existing Scene Creator scene.
- Existing shots are updated in place. Schnick already had 3 shots; Continue created **zero** new shots.
- Second Continue with no upstream ID change is a no-op except `revision` / `updatedAt` (`noop: true`, same `handoffId`, same shot IDs).
- `persistThenOpenSceneCreator()` is sequential: persist → success payload → navigate to Standard with server `sceneId` / `sheetId` / `handoffId`. Persist failure does not navigate.
- ERS footer: **Continue to Scene Creator**. Atlas footer: **Continue to Spatial Map**. Spatial Map **Use in Scene Creator** uses the same helper.
- Left inspector, above Environment: Spatial Profile dropdown (`None` + names) and **Reset Workspace** confirm (not asset-delete red).
- Reset clears selection only. Profile trait, ERS, characters, props, and Library assets remain. Reload stays clean (URL extras stripped). Reselect restores the same pointer IDs.
- Express remains a launcher only (`SceneCreatorExpressLauncher` → Open Scene Creator). It does not create a second profile.

## Live Schnick IDs (observed)

| Pointer | ID |
|---|---|
| Spatial Profile / handoffId | `792376c5-013c-51dd-8d3a-dae5834ae77e` |
| Scene | `e4550745-f0ef-44c8-99a5-ef9e20bd47d2` |
| Sheet | `db095959-5678-4f11-98d1-e93e0810d119` |
| ERS package | `1dd886bf-2ded-4ece-9f6b-6021bc1fb1f1` |
| ERS Library composite | `21927403-e090-49dc-ab03-3169d446fd1f` |
| Spatial Map | `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` |
| Character | `c49371ed-ba6b-4c16-ba98-a8b28b72118b` |
| Prop (map) | `78c5be96-cd03-4969-9f8b-655fcefd28ea` |
| Shots (unchanged) | `88539183…`, `3cb60593…`, `2a58894b…` |

Continue #1 revision **1** `noop=false`. Continue #2 revision **2** `noop=true`, same handoff and shot IDs.

## ID-identity

Handoff digest IDs matched workspace hydrate and Shot 3 pointers:

- `sceneId` / `sheetId` / `ersPackageId` / composite / character ID identical across POST payload, `GET workspace`, and `GET shot 2a58894b`.
- Unit test `test_handoff_ids_match_generation_context` compiles `creativeContext` via existing `compile_shot_prompt` + `_apply_cinematic` and asserts scene / sheet / ERS package IDs match the digest. Image Core was not retuned.

## Tests

| Gate | Result |
|---|---|
| `tests/test_scene_spatial_profile.py` + workspace hydrate | **6 passed** |
| `persistThenOpenSceneCreator.test.ts` + `sceneCreatorContracts.test.ts` | **10 passed** |
| `npm --prefix studio-web run build` | **passed** |
| Playwright `tests/e2e/scene-creator/spatial-profile-reset.spec.ts` | **2 passed** (A–C persist/hydrate/reset/reselect; D Express launcher no second profile) |

Playwright UI: production dist at `http://127.0.0.1:4173` proxied to Studio API `:8758`. Network trace during Reset: **no** `DELETE` / trash / delete asset calls.

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continue / Use in Scene Creator / Spatial Profile dropdown / Reset confirm |
| Frontend | PASS | `persistThenOpenSceneCreator()` then Standard `useSceneCreator` hydrate from server IDs |
| API | PASS | `POST .../production-handoff` 200; list/select/reset endpoints |
| Backend | PASS | Pointer trait `scene_production_handoff`; existing shots updated, none created |
| Persistence | PASS | Trait store `_upsert_trait`; second Continue same `handoffId` |
| Runtime | N/A | No new generation required; consumption proved via compile-path + shot pointers |
| Result | PASS | Workspace hydrate returns same ERS / scene / sheet / character / prop IDs |
| Reload | PASS | After Reset, URL extras stripped; dropdown stays None; reselect restores IDs |
| Downstream | PASS | Shot 3 still `2a58894b…` with same sheet / ERS package / character IDs |

## Limitations

- Hosted Vercel production SHA remains `ad6423a` until this branch is pushed and a new deployment lands. Local dist preview + live API `:8758` is the certified UI for this pass.
- Camera-angle visual cert (2–3 generations) is out of scope.
- Scene Creator Add / napkin remains **NO-GO** in its own governing doc.
- Reset does not delete shots or Library assets; it clears Spatial Profile selection and Standard workspace chrome.

## Manual review

1. Open Schnick Coffee → Scene Creator Standard (`?workspace=scenecreator`).
2. Confirm Spatial Profile dropdown above Environment.
3. Reset Workspace → confirm copy is not an asset-delete warning → Cancel is a no-op → Confirm clears selection.
4. Reselect **Schnick Coffee Spatial** (or the listed name) and confirm Environment / characters / props return.
5. From ERS complete, **Continue to Scene Creator** must wait for persist success before opening Standard.

Live URLs: Studio API `http://127.0.0.1:8758/` (healthy). Creator UI for this cert: `http://127.0.0.1:4173/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator`.
