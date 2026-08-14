# PROP CREATOR E2E WIRING AUDIT (READ-ONLY)

**Date:** 2026-08-14 (PT)  
**Branch:** `beta` @ `0c38e3c` (`feat(prop-creator): add Co-Director prop generation workflow`)  
**Mode:** Audit only. No implement / commit / push / deploy / bounce :8758. Timeline/DirectorTracks not edited.  
**Verdict:** **AUDIT ONLY — not READY FOR MANUAL BETA.** This pass does not certify product GO.

Live API: `http://127.0.0.1:8761` (OpenAPI 200, `/api/health` 200).  
Creator UI overlay: `http://127.0.0.1:8760` (not exercised; Playwright out of scope).

---

## Executive report

| Question | Answer |
|---|---|
| Live `/api/prop-creator` mounted? | **yes** |
| propId survival | **PARTIAL** — survives Prop Creator → Library (mirror only) → Spatial Map → Scene Creator Express/Standard. **Breaks at Timeline export ledger** (`magi/timeline_handoff.py` `_record_ledger` drops `prop_ids`). |
| Attachment sections 8 / 12 | **NOT AVAILABLE** |
| Audit path | `studio-api/.runtime/prop-creator-e2e-audit.md` |

**propId break point:** Scene Creator handoff *intends* to carry `prop_ids` on the clip dict (`scene_creator/timeline_handoff.py`), but the certified MAGI ledger writer persists only `clipId` / `w46ClipId` / `assetId`. Frozen W46 `BatchClip` has no metadata dict. Continuity WIP (`director_timeline_w46/continuity.py`, untracked) has no prop fields.

**Note on mission assumption:** Prop Creator is **no longer untracked**. It landed in `0c38e3c` after being DROP'd from `34d00e6`. Live `:8761` OpenAPI lists all six `/api/prop-creator/...` routes. Attachment is the remaining dirty/untracked contract (`spatial_map/attachment.py` untracked; `schemas.py` dirty locally; **live OpenAPI SpatialPropPlacementBody has no attach fields**).

---

## Canonical law (inspected)

- Project Prop identity: `PropEntity.id` = `propId` (`ers_contracts.py` PropEntity docstring).
- Canonical visual: `approved_asset_id`.
- Reference: `reference_asset_id` (unlink must not delete approved).
- `library_asset_id` may **mirror** `approved_asset_id` after Use This Prop only.
- Library stores binaries (`Asset` rows). Tag `#coffee-cup` is friendly reference, not DB identity.
- Spatial Map binds `SpatialPropPlacement.propId`.
- Scene Creator resolves `SceneShot.prop_entity_ids` / `ShotRequest.prop_entities`.
- Timeline metadata **should** reference the same prop identity — **not proven on the persisted ledger**.
- `character_props` / `CharacterPropRow` is a **separate SQL table**. Do not merge.

**States that must not collapse**

| State | Law | Proven? |
|---|---|---|
| DRAFT | no Spatial Map picker | YES — `list(..., approved_only=True)` + picker calls `api.propCreator.list(projectId, true)` |
| APPROVED | picker eligible | YES — `is_approved` = non-empty `approved_asset_id` |
| PLACED | independent placement | YES — placement row with `propId`; default `placementMode` independent in local dirty schema only |
| ATTACHED | semantic, no independent marker | **NOT AVAILABLE** — contract exists locally, not live, not UI-wired |

---

## Live API

Probed 2026-08-14 PT against `127.0.0.1:8761`:

- `GET /api/health` → 200
- `GET /openapi.json` → 200, 1118 paths
- Prop Creator paths present:
  - `/api/prop-creator/projects/{project_id}/workspace`
  - `/api/prop-creator/projects/{project_id}/props`
  - `/api/prop-creator/projects/{project_id}/props/{prop_id}`
  - `/api/prop-creator/projects/{project_id}/props/{prop_id}/generate`
  - `/api/prop-creator/projects/{project_id}/props/{prop_id}/approve`
  - `/api/prop-creator/projects/{project_id}/props/{prop_id}/candidates/{candidate_id}/retry`
- `GET /api/prop-creator/projects/95795d16-fc09-4bb6-8523-0269ab27be91/workspace` → 200  
  `{"props":[],"selected_prop":null,"api_generation_available":false,"local_families":[qwen2512,zimage,illustrious,flux,...]}`
- Live `SpatialPropPlacementBody` properties: `label, propId, assetId, ... visible` — **no** `placementMode` / `attachedCharacterSlot` / `relationship` / `attachmentPoint`.
- Character-prop routes remain separate: `/api/projects/{project_id}/characters/{character_id}/props`.

`main.py` mounts the router:

```
from .prop_creator.router import router as prop_creator_router
app.include_router(prop_creator_router, prefix="/api")
```

---

## Sections 1–25

Classification key: **PASS** (proven by source AND/OR live) | **FAIL** (proven defect with file:evidence) | **NOT WIRED** | **NOT AVAILABLE** | **NEEDS LIVE GENERATE**

### 1. Canonical identity contract — PASS

`PropEntity.id` is created as UUID and is the only project-prop primary key. Persistence keys `ProjectTraitRow` by `prop.id` (`ers_persistence.save_prop_entity`, category `prop_entity`). Legacy tag-keyed rows are migrated away on save.

Evidence: `studio-api/app/spatial_map/ers_contracts.py` (PropEntity docstring + `id` field); `ers_persistence.py` `key=prop.id`.

### 2. Prop Creator Express API + live mount — PASS

Router prefix `/prop-creator` under `/api`. Live OpenAPI + live workspace GET prove the process has the router (not a stale DROP'd `main.py`).

Evidence: `studio-api/app/prop_creator/router.py`; live OpenAPI paths; live workspace 200.

### 3. DRAFT persist (no Spatial Map picker) — PASS

`create_or_update_prop` saves name/style/description/reference without `approved_asset_id`. `list_props(..., approved_only=True)` returns `[]` for drafts. Spatial Map picker calls `api.propCreator.list(projectId, true)`.

Evidence: `prop_creator/service.py` `is_approved` / `list_props`; `test_prop_creator_express.py` `test_draft_saves_without_approval`; `SpatialMapPanel.tsx` line 132.

### 4. Reference vs approved unlink — PASS

`clear_reference` sets `reference_asset_id = None` only. Test asserts approved + library mirror survive.

Evidence: `service.py` `create_or_update_prop`; `test_clear_reference_keeps_approved_identity`.

### 5. Generation honesty + identity compiler — PASS (source). NEEDS LIVE GENERATE for pixels.

- Local OFF + API OFF → `ValueError` (zero jobs).
- API ON without hosted path → `API Generation — Not Available` (also raised if API plan is enqueued).
- Reference-capable family + reference → `reference_conditioned` + `source_asset_id`.
- Illustrious / Qwen stay `description_guided`; pixels not attached.
- Compiler is identity still (centered complete prop; negative: held-prop / environment / four-view).
- Jobs tag `purpose: project_prop` and `creativeContext.propId = prop.id`.

Evidence: `generation.py`, `prompt.py`, `service.py` `_enqueue_plans`; tests `test_compiler_*`, `test_no_reference_*`, `test_reference_keeps_txt2img_*`, `test_local_off_*`, `test_api_on_*`, `test_generate_attaches_pixels_only_on_reference_conditioned`.

Did **not** start paid/local generate jobs.

### 6. Approval (Use This Prop) — PASS

`approve_candidate` requires complete candidate with `asset_id`. Sets `approved_asset_id = library_asset_id = candidate.asset_id`. Previous approved asset is unmarked. Asset labels get `approved_prop`.

Evidence: `service.py` `approve_candidate`; `test_library_asset_id_mirrors_approved_only`.

### 7. Library stores binaries (not a second identity) — PASS

Generated looks are `Asset` rows via `enqueue_imagegen_job`. Delete returns `library_assets_kept: True` and does not delete files. `library_asset_id` is a mirror after approval, not a competing registry.

Spatial Map library fallback lists assets whose tag contains `prop` or starts with `#`, but approved project-prop visuals are de-duped via `seen.add("library:"+visual)` so the approved PropEntity is not also offered as a generic Library item.

Evidence: `service.py` `delete_prop`; `SpatialMapPanel.tsx` lines 132–177.

### 8. Attachment APIs / fields — NOT AVAILABLE

Local dirty/untracked contract exists:

- `studio-api/app/spatial_map/attachment.py` (**untracked**)
- dirty `schemas.py` adds `placementMode`, `attachedCharacterSlot` (1–4), `attachedCharacterId`, `relationship`, `attachmentPoint` + validators
- dirty `SpatialMap/types.ts` mirrors the same names

**Live `:8761` OpenAPI `SpatialPropPlacementBody` does not include those fields.** No dedicated attach router. `SpatialMapPanel.handleAddProp` does not set attach fields (its `placementMode` state is the place/move ghost cursor, a different type). Scene Creator / Timeline do not consume attach.

Per mission: missing attach APIs/fields → **NOT AVAILABLE**, not FAIL.

### 9. Spatial Map picker (approved project props first) — PASS

Order: approved project props → character props → tagged Library. Drafts excluded by `approved_only=true`. Project option `id` is `PropEntity.id`, `assetId` is approved visual.

Evidence: `SpatialMapPanel.tsx` lines 129–177.

### 10. Spatial Map place binds propId (no Library downgrade) — PASS

```
propId: isProjectProp || isCharacterProp ? option.id : null
```

Project Prop placements keep `propId = PropEntity.id` and `assetId = approved visual`. Library items get `propId: null`. Backend `place_prop` writes `body.propId` onto `SpatialPropPlacement.propId`.

**Does Spatial Map ever downgrade a Project Prop into a generic Library item?** **No** on the project-prop path. Library fallback is a third lane with `propId: null`.

**Caveat (not a downgrade):** character props also write their `CharacterPropRow.id` into the same `propId` field (namespace collision). Scene Creator then `load_prop_entity_by_id` and skips unknown ids. See §22.

Evidence: `SpatialMapPanel.tsx` 498–518; `spatial_map/service.py` `place_prop`; `spatial_map/schemas.py` `SpatialPropPlacement.propId`.

### 11. PLACED is independent of ATTACHED — PASS (PLACED) / NOT AVAILABLE (ATTACHED)

A placed project prop is a `SpatialPropPlacement` row. Coordinates / slot / visibility are independent of approval. Local dirty schema defaults `placementMode="independent"` and clears attach fields. Live process has no attach mode, so every live placement is effectively independent.

### 12. Attached relationships structured — NOT AVAILABLE

No live fields, no UI to set `held|carried|worn|...`, no Scene Creator / ERS / Timeline consumer of `relationship` / `attachmentPoint`. Contract-freeze only (local dirty). Not a FAIL.

### 13. Scene Creator Express receives approved Prop identity — PASS (source). NEEDS LIVE GENERATE for pixels.

Chain:

1. Workspace hydrates placements via `_hydrate_prop` → `{prop_id, approved_asset_id, description, ...}`.
2. `useSceneCreator` seeds `propIds` from `workspace.props[].prop_id` or `shot.prop_entity_ids`.
3. Express chips toggle `prop_id` (`SceneCreatorCore.tsx`).
4. `create_or_update_shot` accepts `prop_entity_ids`; if empty, fills from `_placed_project_prop_ids` (approved PropEntity only).
5. Generate calls `_ensure_placed_project_props` (union placed approved ids onto the shot — chip-off cannot drop a placed approved prop).
6. `_shot_request_from_scene_shot` copies `shot.prop_entity_ids` → `ShotRequest.prop_entities`.
7. `compile_shot_prompt` / `_prop_metadata` resolve by `PropEntity.id`, put name+description in the prompt, and append `approved_asset_id` to `reference_image_ids`.
8. Take memory `blocking.prop_entity_ids` stores the same ids.

Test: `test_scene_creator_resolves_approved_prop_visual`.

**Pixel caveat (not a propId break):** `compile_shot_prompt` sets `referenceImage` to `reference_image_ids[0]` (characters first, then props). Generate then forces `creativeContext.workflowKey = "{family}.txt2img"`. Approved prop identity is on the shot and in `creativeContext.prop_entities`; whether pixels are consumed as ref_edit is **NEEDS LIVE GENERATE**.

### 14. Standard Scene Creator — PASS (shared resolver)

`studio-web/src/components/scene-creator/SceneCreatorWorkspace.tsx` mounts `SceneCreatorCore` `variant="standard"`. Same `useSceneCreator` / same API / same `prop_entity_ids` path. Co-Director tab uses Express (`SceneCreatorPanel` → `variant="express"`). No second prop resolver.

### 15. ERS projection — PASS

Runtime ERS package dumps Spatial Map `placement.model_dump()` (includes `propId`) into `EnvironmentReferencePackage.placements`. Scene Creator workspace hydrates those placements through `_hydrate_prop`. `_placed_project_prop_ids` prefers ERS snapshot placements, then latest map props. Amendment #3: generate does not write back to the map.

Evidence: `scene_creator/ers_resolver.py` `_build_runtime_package`; `scene_creator/service.py` workspace + `_placed_project_prop_ids`.

ERS `metadata.continuity_summary` is sheet continuity text, **not** prop identity.

### 16. Timeline handoff clip.prop_ids — PARTIAL (intent PASS, persist FAIL)

`send_approved_shot_to_timeline` sets `"prop_ids": list(shot.prop_entity_ids)`.  
`build_scene_shot_clips` sets `"prop_ids": list(shot.prop_entities)`.

Those keys never reach a durable Timeline record. See §17.

Evidence: `scene_creator/timeline_handoff.py` lines 137, 201.

### 17. Continuity / export ledger persistence of propId — FAIL

`magi/timeline_handoff.py` `_record_ledger` writes only:

```
{"clipId", "w46ClipId", "assetId"}
```

`_place` passes W46 `kind/assetId/label/start/length/legacyClipId` only. Frozen `BatchClip` has no metadata dict. Untracked `director_timeline_w46/continuity.py` has **zero** `prop` matches.

**This is the chain break.** Scene-shot provenance comment claims the ledger records prop IDs; the ledger writer does not.

Evidence: `magi/timeline_handoff.py` `_record_ledger` lines 275–284; `scene_creator/timeline_handoff.py` lines 194–197 (comment vs reality).

### 18. character_props remains separate — PASS

`CharacterPropRow.__tablename__ = "character_props"` (SQL). Project props are `ProjectTraitRow` category `prop_entity` (JSON). Prop Creator does not call `generate_character_prop`. Picker lists the two stores as separate sources (`source: "project" | "character"`). `project_cleanup.py` deletes `character_props` by character profile; it does not treat them as PropEntity.

Evidence: `character_identity/models.py`; `prop_creator/service.py`; `SpatialMapPanel.tsx`; `project_cleanup.py` line 80.

### 19. State machine DRAFT / APPROVED / PLACED / ATTACHED — PARTIAL

DRAFT, APPROVED, PLACED do not collapse in source. ATTACHED is not a live state. No single enum field; states are derived (`approved_asset_id` empty/non-empty; presence of a placement with matching `propId`).

### 20. Reload reproduces the same state — PASS (persist path). NEEDS LIVE GENERATE for post-generate.

- Prop Creator workspace GET returns persisted `PropEntity` (id, draft fields, approved visual, candidates). `usePropCreator.refresh` re-applies `selected_prop`.
- Spatial Map document is persisted; `propId` is a field on the placement.
- Scene shots persist `prop_entity_ids` in `ProjectTraitRow` category `scene_shot`.
- No live approved PropEntity existed on the probed project (`props: []`), so reload-after-approve was not live-proven.

### 21. Deletion + dangling references — FAIL (shots / timeline) / PASS (Spatial Map + binaries)

`delete_prop`:

1. `_unlink_spatial_props` sets matching `item.propId = None` (keeps the placement marker, unlinks identity).
2. `delete_prop_entity` removes the trait row (and leftover tag-keyed row).
3. Library assets kept.

**Does not** scan `list_scene_shots` to drop `prop_entity_ids`. **Does not** touch Timeline ledger / clips. After delete, a saved shot can still list the dead id; `_prop_metadata` silently omits unknown ids (prompt loses the prop without error). ERS snapshot placements may still contain the old `propId` until regenerated.

Evidence: `prop_creator/service.py` `delete_prop` / `_unlink_spatial_props` (no shot cleanup).

### 22. Duplicate source of truth — PARTIAL (no third project-prop store; shared propId field)

Project-prop SoT is `PropEntity` only. Library is binaries. `library_asset_id` is a mirror, not a second registry.

Duplicate-identity risk: **Spatial Map `propId` is reused for `CharacterPropRow.id`**. Those ids are not PropEntity ids. Scene Creator skips them. A future consumer that treats every `propId` as `PropEntity.id` will mis-resolve.

### 23. Frontend Express UI + nav — PASS

- `CONTENT_NAV`: Prop Creator tab immediately after Character Creator.
- `CoDirectorProjectContent.tsx` mounts `PropCreatorPanel` at `tab === "prop_creator"`.
- `PropCreatorPanel` → `PropCreatorCore variant="express"`.
- `api.propCreator.*` client matches router paths.
- Standard Prop Creator is **not built** (Express only) — expected.

Evidence: `navEntries.ts`; `CoDirectorProjectContent.tsx` 567–574; `PropCreatorPanel.tsx`; `api.ts` 4267–4324; `propCreatorContracts.test.ts`.

### 24. Automated tests — PASS (exist; not re-run this pass)

- `studio-api/tests/test_prop_creator_express.py` — draft, approve mirror, reference unlink, compiler, honesty, pixel attach, retry, Scene Creator resolve.
- Web vitest `propCreatorContracts.test.ts` + Scene Creator contract additions in `0c38e3c`.
- Completion report claimed 12 / 16 / 11 passed. This audit did not re-execute pytest/vitest.

No Playwright. No live generate.

### 25. Verifier challenge answers — see below

---

## Verifier challenge

### Is propId preserved across the entire chain?

**PARTIAL.**  
Preserved: Prop Creator (`PropEntity.id`) → Spatial Map (`SpatialPropPlacement.propId`) → ERS placements → Scene Creator (`prop_entity_ids` / `ShotRequest.prop_entities` / take-memory blocking) → handoff clip dict `prop_ids`.  
**Lost:** MAGI `exportLedger` and W46 `BatchClip`. Timeline/continuity metadata do not retain prop identity.

### Does Spatial Map ever downgrade a Project Prop into a generic Library item?

**No** on the approved project-prop path. Picker binds `propId` + approved visual. Library lane is `propId: null` and de-dupes the approved asset id. Unapproved candidate images tagged `prop_*` can still appear as generic Library items (not the approved identity).

### Does Scene Creator actually receive approved Prop identity?

**Yes in source** (ids + approved visual + description). Express chips and generate union are wired. Standard shares the same hook. **Pixel consumption** of the approved still is not live-proven (`referenceImage` is first of characters-then-props; workflowKey forced to `txt2img`). **NEEDS LIVE GENERATE.**

### Are attached relationships structured?

**Not built yet (NOT AVAILABLE).** Local uncommitted contract only. Live API/UI/Scene Creator/Timeline do not carry `placementMode=attached` or `relationship`.

### Does reload reproduce the same state?

**Yes for persisted draft/approved/placed/shot ids** (trait + map document + scene_shot). Not live-proven after generate/approve on an empty probed project. ATTACHED cannot reload (not available).

### Any duplicate Prop source of truth?

**No third project-prop registry.** `character_props` is a separate product. Risk: one Spatial Map `propId` field serving both PropEntity ids and character-prop ids.

### Does deletion leave dangling references?

**Yes.** Spatial Map `propId` is nulled; binaries kept (correct). `SceneShot.prop_entity_ids` and Timeline ledger/clips are not cleaned.

---

## Top defects

| # | Class | File | One-line evidence |
|---|---|---|---|
| D1 | **NEEDS PRIMARY AGENT** | `studio-api/app/magi/timeline_handoff.py` `_record_ledger` | Ledger entries are only `clipId/w46ClipId/assetId`; `prop_ids` from Scene Creator handoff are dropped. Frozen W46 / Timeline — do not auto-edit. |
| D2 | **SAFE AUTO-REPAIR** | `studio-api/app/prop_creator/service.py` `delete_prop` | Unlinks Spatial Map `propId` only; does not strip `SceneShot.prop_entity_ids`. |
| D3 | **NEEDS PRIMARY AGENT** | `SpatialMapPanel.tsx` `handleAddProp` | Character-prop ids written into `SpatialPropPlacement.propId` (same field as `PropEntity.id`). |
| D4 | **NOT AVAILABLE** (not FAIL) | live OpenAPI `SpatialPropPlacementBody` vs local `spatial_map/attachment.py` | Attach fields exist only as dirty/untracked contract; live process + UI + SC + Timeline do not implement ATTACHED. |
| D5 | **NEEDS PRIMARY AGENT** | `entity_resolver.py` `compile_shot_prompt` + `scene_creator/service.py` `_enqueue_shot_candidates` | Approved prop visual is in `reference_image_ids` / `prop_entities`, but primary `referenceImage` is `[0]` (characters first) and workflowKey is forced to `txt2img`. |
| D6 | related, not prop-identity | `scene_creator/timeline_handoff.py` `build_scene_shot_clips` | `"source_scene": batch.project_id` (project id, not scene id). Out of Timeline-edit scope. |

SAFE AUTO-REPAIR means isolated Prop Creator / Scene shot cleanup with no Timeline/DirectorTracks edits.  
NEEDS PRIMARY AGENT means frozen contracts, Timeline/W46, or product-law choices.

---

## What was not done

- No code changes, commits, pushes, deploys, or `:8758` bounce.
- No `git add -A`.
- No Timeline / DirectorTracks edits.
- No paid or local generate jobs.
- No Playwright / Manual Beta A–N.
- Did not re-run pytest/vitest this pass.

---

## Sources inspected

`studio-api/app/prop_creator/{router,service,generation,prompt}.py`  
`studio-api/app/spatial_map/{ers_contracts,ers_persistence,schemas,service,attachment}.py`  
`studio-api/app/scene_creator/{service,timeline_handoff,ers_resolver}.py`  
`studio-api/app/codirector/entity_resolver.py`  
`studio-api/app/magi/timeline_handoff.py`  
`studio-api/app/main.py`  
`studio-api/app/character_identity/models.py`  
`studio-api/app/project_cleanup.py`  
`studio-api/tests/test_prop_creator_express.py`  
`studio-web/src/components/CoDirector/PropCreator/*`  
`studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx` + `types.ts`  
`studio-web/src/components/CoDirector/SceneCreator/{useSceneCreator,SceneCreatorCore}.ts(x)`  
`studio-web/src/api.ts` `propCreator`  
`studio-web/src/components/CoDirector/navEntries.ts`  
`docs/release-gate/prop-creator/*`  
Live `:8761` OpenAPI + workspace GET.

Copies used when `ExternalRead` blocked `C:\AdeptFilmWorks`: `C:\Users\bradj\agent-tools\prop-creator-audit\`.
