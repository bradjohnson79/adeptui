# STANDARD PROP CREATOR — READ-ONLY ARCHITECTURE AUDIT

**Date:** 2026-08-14 (PT)
**Branch:** `beta` @ `0c38e3c` (`feat(prop-creator): add Co-Director prop generation workflow`)
**Mode:** Audit only. No implement / commit / push / deploy / bounce APIs.
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Live Express:** Co-Director tab `prop_creator` → `PropCreatorPanel` → `:8761` `/api/prop-creator`

Working-tree notes (do not fight):
- Shared `studio-web/src/components/generators/` is **untracked** (GeneratorSourceSelector extracted).
- Express is already wired to it in dirty `PropCreatorCore.tsx` / `usePropCreator.ts` plus untracked `propGenerator.ts`.
- `studio-api/app/prop_creator/service.py` is dirty (E2E repairs: SceneShot unlink, spatial unlink).
- Attachment UI remains uncertified. Timeline ledger `prop_ids` is a separate repair — not required to ship Standard shell.

---

## Existing Shared Prop Core

Single identity. No second registry.

| Layer | Location | Role |
|---|---|---|
| Canonical entity | `studio-api/app/spatial_map/ers_contracts.py` `PropEntity` | `id` = propId. `approved_asset_id` = visual identity. `library_asset_id` mirrors approved only. `reference_asset_id` is source (unlink must not delete approved). `candidates[]`, `generator`, `description`/`notes`, `visual_style`, `tag`, `created_at`/`updated_at`. **No variant / material / condition fields.** |
| Persistence | `spatial_map/ers_persistence.py` `save_prop_entity` / `list_prop_entities` / `load_prop_entity_by_id` / `delete_prop_entity` | Same rows Spatial Map and Scene Creator already read. Timestamps stamped on save. |
| Backend service | `studio-api/app/prop_creator/service.py` | `workspace`, `list_props` (`approved_only`), `create_or_update_prop`, `generate_candidates`, `approve_candidate`, `retry_candidate`, `delete_prop`. Delete unlinks Spatial Map `propId` and SceneShot `prop_entity_ids`; keeps Library assets. Unused helper `_spatial_placements_for_prop` already counts placements. |
| REST | `studio-api/app/prop_creator/router.py` mounted at `/api/prop-creator` | workspace / list / upsert / get / generate / approve / retry / delete. **No history, usage, or variants endpoints.** |
| Client API | `studio-web/src/api.ts` `api.propCreator` (committed in `0c38e3c`) | Typed against `PropCreator/types.ts`. Delete returns `{ ok, prop_id, library_assets_kept, spatial_unlinked }`. Dirty tree also returns `shots_unlinked`. |
| Hook | `usePropCreator.ts` | Shared controller: load/select/new, persist, generate+poll, approve, retry, setReference, reset, remove. `PropCreatorVariant = "express" \| "standard"`. |
| Core view | `PropCreatorCore.tsx` | Shared blocks over the hook. `variant === "standard"` already exists and **currently renders `ExpressLayout`** (same stub pattern Scene Creator used before StandardLayout). |
| Thin API wrapper | `propCreatorApi.ts` | Forwards to `api.propCreator` only. |
| Generator math | committed: inline in core/hook; dirty: untracked `propGenerator.ts` | Persist payload, generate request, block reason, candidate labels. |
| Shared generator UI | untracked `studio-web/src/components/generators/` | `GeneratorSourceSelector` `purpose="prop"`, labels "Description Guided" / Reference Conditioned. Express dirty tree already imports this. |
| Types | `PropCreator/types.ts` | `PropEntity`, `PropCandidate`, `PropCreatorWorkspace`, `candidateProgress`. |

**Do not create:** a second backend, a second PropEntity table, a second generator, a second Library, or a second candidate/approval path.

**Do not merge** with `character_props` / `PropsWorkspace.tsx` (character-associated, max 4, `/api/projects/.../characters/.../props`). That is a different registry.

---

## Express Components

Co-Director only. Stays there.

| Piece | File | What Standard reuses |
|---|---|---|
| Express shell | `PropCreatorPanel.tsx` | Thin: `<PropCreatorCore variant="express" />`. Do not change its contract. |
| Co-Director mount | `CoDirectorProjectContent.tsx` `tab === "prop_creator"` | Already live. `navEntries.ts` `CONTENT_NAV` already lists Prop Creator. |
| Saved Prop + Create New | `SavedPropBlock` | Becomes the Standard **browser** list. Same `pc.workspace.props` / `pc.selectProp` / `pc.newProp`. |
| Name + Image Style | `NameStyleBlock` | Inspector accordion. `CHARACTER_STYLE_OPTIONS`. |
| Description | `DescriptionBlock` | Inspector accordion. |
| Reference | `ReferenceBlock` | Library picker = `CharacterReferenceAssetPicker` (project Library images). Upload = `api.uploadAsset(..., "prop_reference")`. Remove = `pc.setReference(null)`. **Reuse as-is.** |
| Generator | `GeneratorBlock` | Shared `GeneratorSourceSelector` (dirty) or whatever Express ships. `purpose="prop"`. |
| Save / Reset / Delete / Generate | `ActionsBlock` | Same `pc.persist` / `pc.reset` / `pc.remove` / `pc.generate`. Delete already confirms Spatial unlink + Library keep. |
| Candidates + approve | `CandidateGrid` | Same `pc.approve` / `pc.retry`. Standard **preview + strip** are a layout of this data, not new logic. |
| CSS | `propCreator.css` | Express stacked layout. Add Standard grid classes here (mirror Scene Creator). |

Downstream consumers already keyed on `PropEntity.id` (do not replace):

- **Spatial Map production picker:** `SpatialMapPanel.tsx` `api.propCreator.list(projectId, true)` — approved-only. `SpatialPropPlacement.propId` = `PropEntity.id`. PlacementSlot labels Project vs Character vs Library.
- **Spatial Map EntityPicker `kind: "prop"`:** still Library-image + tag (legacy create-in-map path). Not Standard's job. Do not invent a third picker.
- **Scene Creator resolver:** `useSceneCreator` persists `prop_entity_ids`. Workspace `props` come from Spatial placements. Chips toggle the same ids. Express + Standard Scene Creator already share this.
- **Library:** binaries only. Tag is friendly, not identity.

---

## Standard Workspace Reuse Plan

Copy the **Scene Creator** pattern exactly. Scene Creator Standard is the proven Production shell over a shared core:

- Express: `SceneCreatorPanel` → `SceneCreatorCore variant="express"`
- Standard: `scene-creator/SceneCreatorWorkspace.tsx` (18 lines) → `SceneCreatorCore variant="standard"`
- `ProjectEditor` `tab === "scenecreator"` renders the thin workspace
- `StandardLayout` = browser | large preview | inspector | candidate strip
- Same hook, same APIs

Prop Creator already has the variant stub. Standard is a **layout + route**, not a product rewrite.

**StandardLayout composition (all existing blocks):**

1. **Browser (left):** `SavedPropBlock` as a vertical list (draft vs approved). Create New.
2. **Large approved preview (center):** `pc.prop.approved_asset_id` else first complete candidate. `api.assetUrl`. Same hero pattern as Scene Creator `scene-creator-standard__preview`.
3. **Candidate strip (bottom):** `CandidateGrid` as a strip (approve / retry stay on `pc.approve` / `pc.retry`).
4. **Inspector (right) accordions:** Name/Style, Description, Reference (`CharacterReferenceAssetPicker`), Generator (`GeneratorSourceSelector`), Actions (Save / Reset / Delete / Generate), Status, then identity history + usage (derived — see below).
5. **Delete safety:** keep `usePropCreator.remove()` confirm; Standard may prepend derived usage counts in the same confirm string. No new delete API.

**Variants and material/condition notes: DEFER.** `PropEntity` has no such fields. Adding them is a schema change. Out of scope.

**WIP generator:** Standard must import `../../generators/GeneratorSourceSelector` the same way dirty Express does. Do not resurrect `character/GeneratorSourceSelector` and do not fork a prop-only selector. Commit `components/generators/` + `propGenerator.ts` in the same change set that Standard first imports them (see Vercel).

---

## Production Route / Menu Entry

### Where the Production dropdown lives

`studio-web/src/components/dashboard/AppChrome.tsx` (project chrome menubar), rendered from `ProjectEditor` via `AppStudioChrome`.

```
<ProductionMenu
  open={openMenu === "production"}
  onSelectWorkspace={goWorkspace}
  ...
/>
```

Catalog is declarative in `studio-web/src/core/productionMenu.ts` `PRODUCTION_MENU_CATALOG`.
Selecting an entry calls `onSelectWorkspace(entry.workspace)` → `ProjectEditor.go()` → `?workspace=<EditorTab>` on `/project/:id`.

This is **not** a new React Router path. `App.tsx` has no per-workspace routes. Scene Creator did not add `/scene-creator`.

### Can Production menu add "Prop Creator" without shipping Timeline WIP?

**Yes.** Timeline Generator is already a **Create** catalog entry (`workspace: "timeline"`) and an existing `EditorTab`. Adding Prop Creator is a new catalog row + new `EditorTab`. It does not import `timeline-master`, DirectorTracks, or MAGI ledger code.

Recommended catalog slot: **Profiles**, immediately after Character Creator (same identity-profile family). Alternative: Pre-Production next to Spatial Map / Scene Creator. Do not put it under Create (that is where Timeline lives).

Local dirty `TimelineInspector.tsx` is unrelated and must not be in the Standard commit.

### Would adding a route break Vercel the way untracked PropCreator + missing `api.propCreator` did before?

**Not if Standard follows Scene Creator routing and commits every import.**

Previous break (from E2E audit + git history):
- Prop Creator was DROP'd from `34d00e6`, then landed in `0c38e3c`.
- Vercel builds `studio-web` (`studio-web/vercel.json`: Vite, SPA rewrite `/((?!api/).*)` → `/index.html`).
- A frontend import of `api.propCreator` or `./PropCreator/...` while those files/exports were **untracked or missing** failed the Vercel TypeScript build.

Current committed baseline (`0c38e3c`) already has `api.propCreator` and the PropCreator module. **Do not add an `App.tsx` `<Route>`.** Add:

1. `WORKSPACES.propcreator` in `core/workspaces.ts` (`labelKey: "propCreator"` — **already present** in `i18n/locales/en/navigation.json`)
2. `PRODUCTION_MENU_CATALOG` entry `workspace: "propcreator"`
3. `ProjectEditor` branch `tab === "propcreator"` → thin `PropCreatorWorkspace`
4. Thin `studio-web/src/components/prop-creator/PropCreatorWorkspace.tsx`

Vercel-safe rules:
- No new App route, no `vercel.json` change, no availability key required (Scene Creator / Character Creator have none).
- **Must commit** any newly imported file in the same PR: especially untracked `components/generators/**` and `propGenerator.ts` if Standard/Express import them. Shipping the Standard shell while leaving those untracked is the same class of break as before.
- Other locales lack `propCreator`; `ProjectEditor` already uses `t(labelKey, { defaultValue: workspaceLabel(tab) })` so EN-only is not a build break.
- `ProjectEditor` ends in "Unknown workspace." — the tab branch is required or the menu will open an empty page (not a Vercel break, a product break).

Scene Creator contract test (`sceneCreatorContracts.test.ts`) asserts Production catalog membership. Add the same assertion for Prop Creator.

---

## Additional Production Features

Mission: browser, large approved preview, candidate strip, inspector accordions, identity history, usage, delete safety.

| Feature | New endpoint? | Smallest path |
|---|---|---|
| Browser / preview / strip / inspector | No | Layout-only over `usePropCreator` + existing blocks. CSS analog of `.scene-creator-standard*`. |
| Identity history | **No** | `PropEntity.candidates[]` is the look history (take_label, provenance, status, asset_id, conditioning). Current identity = `approved_asset_id`. `created_at` / `updated_at` already persisted. Render an inspector accordion from `pc.prop`. Do not add `/history`. |
| Usage | **No new endpoint** | Derive client-side before delete / in inspector: (1) Spatial Map documents — count placements where `propId === prop.id` (same walk as `_spatial_placements_for_prop`); (2) Scene Creator shots — count `prop_entity_ids` containing the id (same walk as `_unlink_scene_shots`). Optional later: add `usage: { spatial, shots }` onto existing `GET workspace` / `GET prop` (extend, do not add `/usage`). Timeline ledger `prop_ids` is a separate E2E repair — **do not block Standard** on it; omit Timeline from v1 usage or show "not available". |
| Delete warning | **No** | `usePropCreator.remove()` already confirms Spatial unlink + Library keep. Standard: fetch the two counts above, then `window.confirm(\`Remove …? Used on N Spatial placements and M Scene shots. Placements will be unlinked. Library images stay.\`)`. Post-delete payload already returns `spatial_unlinked` (and dirty `shots_unlinked`). Do not add `/delete-preview`. |

Attachment UI: **out of scope** (uncertified, not live on `:8761` OpenAPI).

---

## READY TO IMPLEMENT | BLOCKED

**READY TO IMPLEMENT**

No schema blocker. No missing backend. No second registry required. `PropCreatorCore` already accepts `variant="standard"`. Scene Creator Standard is the file-level template. Production menu can add Prop Creator without Timeline WIP and without a new Vercel route.

Smallest file reuse map:

**Standard imports (do not copy logic):**
- `../CoDirector/PropCreator/PropCreatorCore` (`variant="standard"`)
- `../CoDirector/PropCreator/usePropCreator` (via Core only)
- `../CoDirector/PropCreator/propCreatorApi` + `types` (via hook)
- `../CoDirector/characters/CharacterReferenceAssetPicker` (via Core ReferenceBlock)
- `../generators/GeneratorSourceSelector` (via Core; commit this package with the PR)
- `../../api` `api.propCreator` / `api.assetUrl` only

**New shell-only files:**
- `studio-web/src/components/prop-creator/PropCreatorWorkspace.tsx` — ~18 lines, clone of `scene-creator/SceneCreatorWorkspace.tsx`

**Edit existing (routing / Standard layout only):**
- `PropCreatorCore.tsx` — add `StandardLayout` (browser / preview / inspector / strip) from existing blocks; keep ExpressLayout for Co-Director
- `propCreator.css` — add `.prop-creator-standard*` grid (mirror Scene Creator CSS, do not import Scene CSS)
- `core/workspaces.ts` — `propcreator` EditorTab (`menuGroup: "characters"`, `labelKey: "propCreator"`, aliases `prop-creator`, `propCreator`)
- `core/productionMenu.ts` — Profiles entry `{ id: "propcreator", label: "Prop Creator", action: "workspace", workspace: "propcreator" }`
- `pages/ProjectEditor.tsx` — `tab === "propcreator"` → `<PropCreatorWorkspace project={project} onGo={go} />`
- `PropCreator/propCreatorContracts.test.ts` — assert Standard uses `variant="standard"` and Production catalog contains Prop Creator

**Do not add:**
- App.tsx route, vercel.json change, new FastAPI router, new PropEntity fields, variants/material UI, character `PropsWorkspace` reuse, Attachment UI, Timeline files, `/history` or `/usage` endpoints

**Ship-together reminder (Vercel):** if Standard/Express import untracked `components/generators/` or `propGenerator.ts`, those files must be in the same commit as the first import. `api.propCreator` is already committed — that half of the old break is gone.
