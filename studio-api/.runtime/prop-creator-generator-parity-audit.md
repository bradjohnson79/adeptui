# Prop Creator generator parity audit

- Status: **READY TO IMPLEMENT**
- Date: 2026-08-14 (PT)
- Scope: read-only. No files edited except this audit. Character Creator source was not modified.
- Live checked: UI http://127.0.0.1:8760 (200), API http://127.0.0.1:8758 (200), http://127.0.0.1:8761 (200)
- Important: live :8760 JS bundle is **behind Character Creator source**. Implement against **current source**, not the running bundle.

## Verdict

READY TO IMPLEMENT. Gaps are mapped. Express and Standard already share one core. Do not wait for a live Character Creator rebuild (Grok 4.6 owns that). Consume Character Creator source; do not edit it.

Caveat: `CharacterGeneratorPanel` is Character-only (hardcoded "Profile Guided", "Character Sheet", 4 views/sheet). Prop must reuse the **plan + inventory pattern**, not the 4-view product math.

---

## 1. Current Prop generator UI vs Character Creator shortlist

| Surface | Source now | Live :8760 bundle |
|---|---|---|
| Character Creator | `CharacterGeneratorPanel` — per-model checkboxes, Auto Select exclusivity, Batches 1–4, Cloud Generators master switch, hosted-discovery API rows, Generation Plan | **Stale.** Still `GeneratorSourceSelector` dropdowns. No `CharacterGeneratorPanel`, no "Cloud Generators" plural. |
| Prop Express + Standard | `GeneratorSourceSelector` — 3 master checkboxes + **dropdowns** (one local family, one cloud model) | Same dropdown selector. `purpose="prop"`, `textModeLabel="Description Guided"`. |

Prop is still the **old single-select dropdown UX**. Character source is the **new per-model shortlist**. They do not match.

Prop generator block (`PropCreatorCore.tsx` `GeneratorBlock`):

- Imports `../../generators/GeneratorSourceSelector`
- Passes `purpose="prop"`, `textModeLabel="Description Guided"`, `sectionLabel="Generator"`
- State is `{ local: { enabled, selectedId, stage2? }, api: { enabled, selectedId } }` — one id per pool, not `localModels[]` / `apiModels[]`

Character source (`CharacterCore.tsx`):

- Imports `CharacterGeneratorPanel` + `characterGeneratorPlan`
- State is `CharacterGeneratorPlan`: `localEnabled`, `apiEnabled`, `autoSelect {enabled, batchCount}`, `localFamilies[]`, `apiModels[]`, `stage2Enabled`, `stage2Family`
- Generate body uses `buildGeneratorSourcesPayload(plan)` → `{ local: [{family, enabled, batchCount}], api: [{model, providerId, modelId, enabled, batchCount}], stage2Enabled, stage2Family }`

`character/GeneratorSourceSelector.tsx` is only a re-export of the shared dropdown. Character Core no longer mounts it.

---

## 2. Is shared `GeneratorSourceSelector` enough?

**No.** Character Creator now has a newer per-model shortlist Prop does not use.

- Shared selector (`components/generators/GeneratorSourceSelector.tsx`): Local Identity Engine **dropdown**, optional Style Engine **dropdown**, Cloud Generator **dropdown**. Discovery is used, but only to fill one `<select>`.
- New Character panel (`components/character/CharacterGeneratorPanel.tsx`): local per-model checkboxes + Batches 1–4, Auto Select exclusivity, Cloud Generators master switch + per-model API checkboxes from `hostedProvidersDiscoveredModels("image")`, visible Generation Plan.
- File comment on the new panel: *"Do not use this in Prop Creator. Prop Creator keeps GeneratorSourceSelector."* That is Character-owner intent, not product law. This mission requires Prop to **match** that UX without editing Character Creator.

**Reuse rule:** consume Character files; do not edit them. Do **not** import `CharacterGeneratorPanel` as-is (Character Sheet / 4-view copy). Do **not** start a second model registry.

Correct consume path:

1. Import `characterGeneratorPlan.ts` helpers (clamp, merge, payload, discovery normalize) — or copy the **types/helpers** into `components/generators/` if importing from `character/` is too product-coupled. Prefer a new shared `generators/generatorPlan.ts` + `generators/GeneratorPlanPanel.tsx` **without touching Character files**. Character keeps its panel until Grok 4.6 migrates.
2. Inventory stays `api.imagegenModels()` + `api.hostedProvidersDiscoveredModels("image")` — same APIs Character uses. No Prop-only catalog.
3. Prop product differences only: `purpose="prop"`, "Description Guided", **one candidate image per batch (not 4-view)**, "Prop Images" not "Character Sheets".

---

## 3. Mystery checkbox — current state

**Fixed in the shared selector.** All three checkboxes are labeled:

- `Local Identity Engine` (`generator-local-enable`)
- `Style Engine (optional)` (`generator-style-enable`)
- `Cloud Generator (uses credits)` (`generator-api-enable`)

`propCreatorGenerator.test.ts` asserts those labels and that every checkbox sits in `character-core__checkbox`. Live bundle also contains `Style Engine (optional)`.

Remaining leftover: Style Engine is **labeled but inert for Prop**. `propGenerateRequest()` / `persistGeneratorPayload()` / `GenerateBody` do not send `stage2Enabled` / `stage2Family`. Checking it does nothing on generate.

There is **no** unlabeled mystery checkbox left. There is also **no** "Use as Prop Identity" checkbox (that is a missing control, not a mystery one).

---

## 4. API shortlist — does Prop consume hosted-provider discovery? Why "Not Available"?

**UI (shared selector): yes, partially.** It calls `api.hostedProvidersDiscoveredModels("image")` and maps `items` / `models` into the Cloud dropdown.

**Prop product contract: no.** Workspace still exposes `api_generation_available: hosted_image_generation_available()`, which is **not** discovery. That helper only returns true when a Certified **non-local** workflow exists in `image_runtime.certified_registry`. Comment in `scene_creator/generation.py`: hosted image inventory is Blocked (`imagen.*`); `flux-kie` maps to local flux. So the flag is almost always false.

**Generate path: hard refuse.**

1. `build_prop_candidate_plans()` raises `API Generation — Not Available` if `api_enabled` and `not hosted_image_generation_available()`.
2. `_enqueue_plans()` then **unconditionally** `raise PropCreatorError("API Generation — Not Available")` for `plan["source"] == "api"`. Even if planning allowed an API row, enqueue cannot run it.

Why the user still sees "Not Available":

- Not because the shared selector forgot discovery.
- Because Prop generate **cannot execute** a discovered cloud model. Checking Cloud + picking a discovered row still dies on enqueue.
- Frontend tests only assert the **string is absent from Prop TSX**. The error still comes from the API.
- Scene Creator still has the literal `API Generation — Not Available` in its own UI (present in the live bundle).

Character's new panel shows discovered rows or: *"No cloud image models are connected. Add a provider in Setup…"* — never a global "Not Available" banner.

---

## 5. Use as Character Identity — exact files/fields to mirror

Character path (no binary dup):

| Layer | File | What happens |
|---|---|---|
| Checkbox | `studio-web/src/components/character/CharacterReferenceControl.tsx` | `data-testid="character-use-as-identity"`. Label: "Use as Character Identity". Tip: use this image as the look, no AI. |
| Attach | same | Upload / library attach uses `api.attachCharacterReference(..., { asset_id, reference_role: "reference_image", source_type, canonical: false })`. If checkbox on, then `onUseAsIdentity(assetId, sourceType)`. |
| Core | `CharacterCore.tsx` `handleUseAsIdentity` | `api.approveCharacterCandidate(projectId, characterId, { assetId, referenceRole: "hero_identity", sourceType: "upload" \| "library", notes })` |
| Client | `studio-web/src/api.ts` | `POST /api/projects/{pid}/characters/{cid}/approve-candidate` body `{ assetId, referenceRole?, sourceType?, notes? }` |
| API | `studio-api/app/character_identity/api.py` `ApproveCandidateBody` | `assetId`, `referenceRole="hero_identity"`, `sourceType="generation"`, `notes` |
| Service | `character_identity/service.py` `approve_character_candidate` | Attaches the **existing** Library `asset_id` as canonical `hero_identity`. `generationUsed = source_type not in ("upload", "library")`. **Does not copy bytes.** |

Prop mirror (do not invent a second registry):

| Character | Prop |
|---|---|
| `assetId` (existing library/upload row) | same asset id already stored as `reference_asset_id` |
| `referenceRole: "hero_identity"` | `PropEntity.approved_asset_id` (canonical visual identity) |
| `library_asset_id` N/A | `library_asset_id` may **only mirror** `approved_asset_id` after identity is set (`ers_contracts.PropEntity`) |
| `sourceType: upload \| library` | persist on generator/notes or candidate provenance; no new blob |
| `PropEntity.id` | already authoritative prop id |

UI placement: beside Reference Image in `ReferenceBlock` (`PropCreatorCore.tsx`), same pattern as Character Reference — checkbox + existing Upload / Library / Remove. Live bundle has **no** "Use as Prop Identity".

Smallest backend: extend existing upsert (`clear_reference` / `reference_asset_id` already exist) with `use_as_identity: true`, **or** a tiny `POST /props/{id}/use-as-identity { asset_id }` that sets `approved_asset_id = asset_id` and `library_asset_id = asset_id`. Do **not** add a new endpoint family if upsert can do it. Do **not** duplicate the file.

---

## 6. Prop generation request schema — extend vs new endpoint

**Extend the existing generate endpoint. Do not add a new one.**

Current contract:

```
POST /api/prop-creator/projects/{pid}/props/{prop_id}/generate
GenerateBody: local_enabled, api_enabled, local_family, api_model, candidate_count=4
```

Client: `propGenerateRequest(sources)` sends those five fields only. No `localModels[]`, `apiModels[]`, `styleEngine`, `stage2*`.

Persist: `GeneratorSourceSelection` = `{ local_enabled, api_enabled, local_family, api_provider, api_model }`. No batch counts, no multi-select.

Character generate payload (consume this shape):

```
generatorSources: {
  local: Array<{ family, enabled, batchCount }> | null
  api: Array<{ model, providerId, modelId, enabled, batchCount }> | null
  stage2Enabled?: boolean
  stage2Family?: string
}
candidateCount: number  // sum of batches; Character uses this as sheet count
```

Prop extension (same POST):

- Accept `generatorSources` (or `localModels` / `apiModels` / `styleEngine`) **in addition to** the old scalars so old clients do not break.
- `candidate_count` becomes derived: sum of enabled batchCounts (clamp 1–4 **per source**).
- Each enabled batch = **one still image**, not a 4-view sheet.
- Style Engine: optional. If checked, persist `stage2Enabled` + `stage2Family` and run a real img2img/edit **or** hide the control until that path exists. Do not leave a working-looking leftover.

Planner today (`prop_creator/generation.py`): if local is on, **every executable local family** is a source, selected family is only sorted first, then `sources[i % len(sources)]` fills `candidate_count`. That is multi-family round-robin, not "the checked model".

---

## 7. Express vs Standard — same core?

**Yes.** Confirmed.

- Express: `PropCreatorPanel` → `<PropCreatorCore variant="express" />`
- Standard: `PropCreatorWorkspace` → `<PropCreatorCore variant="standard" />`
- Both use `usePropCreator` + the same `GeneratorBlock` / `ReferenceBlock` / `ActionsBlock`.
- Standard is a layout shell (browser / preview / inspector / take strip) over the same blocks.
- `PropEntity.id` is the workspace key (`selectProp`, generate, approve, delete).

One generator/identity change covers both surfaces.

---

## 8. Live :8760 Prop Creator UI

Reachable. Bundle: `/assets/index-6gpd03hm.js`.

Observed in the running bundle:

- `prop-creator-generators` mounts shared selector `yge` with `Description Guided`.
- `Local Identity Engine` + `<select generator-local-select>` + Auto Select option.
- `Style Engine (optional)` — labeled.
- `Cloud Generator (uses credits)` — singular dropdown, not per-model checkboxes.
- `Use as Character Identity` present (Character).
- `Use as Prop Identity` **absent**.
- `CharacterGeneratorPanel` **absent** (live Character Creator is also still the old dropdown).
- `API Generation` / `Not Available` present in the bundle via **Scene Creator**, not Prop TSX.

So live Prop matches current Prop **source** (old selector). It does **not** match current Character **source** (new panel). After Grok 4.6 ships Character, the live gap will widen unless Prop is updated from source now.

---

## Gap list vs Character Creator (consume, do not edit)

1. Per-model local checkboxes + Batches 1–4 (one image per batch). Prop has one dropdown + global `candidate_count=4`.
2. Auto Select exclusivity (explicit family unchecks Auto). Prop Auto is an empty dropdown value and still fans out all families.
3. Cloud Generators **master** switch + per-discovered-model checkboxes/batches. Prop has one Cloud dropdown.
4. Dynamic API shortlist from hosted-provider discovery that can actually **run**. Prop discovery fills a select; enqueue always refuses API.
5. Honest empty-cloud copy ("Add a provider in Setup…"), not `API Generation — Not Available`.
6. Style Engine optional and either real or hidden. Prop shows it and drops it on the wire.
7. Use as Prop Identity beside Reference Image (pointer to existing `asset_id` → `approved_asset_id`). Missing.
8. Generation Plan summary (N prop images, not N×4 views). Missing.
9. User Control Law: unchecked source = zero jobs. Prop planner still round-robins **all** local families.
10. Leftover NO-GO: silent zimage → other-family execution. **Still present** (see below).

---

## Shared files to reuse (read only)

Do not edit these:

- `studio-web/src/components/character/CharacterGeneratorPanel.tsx` — UX template
- `studio-web/src/components/character/characterGeneratorPlan.ts` — plan types, batch clamp, discovery normalize, payload builder
- `studio-web/src/components/character/CharacterReferenceControl.tsx` — identity checkbox
- `studio-web/src/components/character/CharacterCore.tsx` — `handleUseAsIdentity` + `approveCharacterCandidate`
- `studio-web/src/components/generators/types.ts` — `GeneratorOption` (already has `providerId`, `modelId`, `capabilities`)
- `studio-web/src/components/generators/generatorSource.css` — existing classes
- `studio-web/src/api.ts` — `hostedProvidersDiscoveredModels`, `imagegenModels`, `approveCharacterCandidate`
- `studio-api/app/hosted_providers/router.py` — `GET /api/hosted-providers/discovered-models?modality=image`
- `studio-api/app/character_identity/service.py` — `approve_character_candidate` (no binary dup)

Shared **Prop may add** (new files, not CC edits):

- `studio-web/src/components/generators/generatorPlan.ts` (optional extract of plan helpers)
- `studio-web/src/components/generators/GeneratorPlanPanel.tsx` (parameterized shortlist: purpose, textModeLabel, imageNoun)

---

## Prop files to change

Frontend:

- `studio-web/src/components/CoDirector/PropCreator/PropCreatorCore.tsx` — `GeneratorBlock`, `ReferenceBlock` (identity checkbox)
- `studio-web/src/components/CoDirector/PropCreator/usePropCreator.ts` — plan state, generate/persist payload
- `studio-web/src/components/CoDirector/PropCreator/propGenerator.ts` — request builder; stop sending only `local_family` / `candidate_count=4`
- `studio-web/src/components/CoDirector/PropCreator/types.ts` — generator persist shape; workspace can drop `api_generation_available` as the product gate
- `studio-web/src/components/CoDirector/PropCreator/propCreatorApi.ts` + `studio-web/src/api.ts` `propCreator.generate` body type
- `propCreatorGenerator.test.ts` / `propCreatorContracts.test.ts` — assert per-model shortlist, no family swap, identity checkbox
- Express/Standard shells: **no logic change** (`PropCreatorPanel.tsx`, `prop-creator/PropCreatorWorkspace.tsx`)

Backend:

- `studio-api/app/prop_creator/router.py` — extend `GenerateBody` / `UpsertBody.generator`
- `studio-api/app/prop_creator/generation.py` — **replace all-family round-robin** with checked sources × batchCount
- `studio-api/app/prop_creator/service.py` — `_enqueue_plans` must execute API via hosted path or fail **that row** honestly; add use-as-identity pointer write; persist multi-model generator
- `studio-api/app/spatial_map/ers_contracts.py` — extend `GeneratorSourceSelection` (or store plan JSON on `PropEntity.generator`)

Do not create a second PropEntity registry. `PropEntity.id` stays the key.

---

## Identity path reuse

```
Reference asset (upload or library, already an Asset row)
    → checkbox Use as Prop Identity
    → set PropEntity.approved_asset_id = asset_id
    → set PropEntity.library_asset_id = asset_id  (mirror only)
    → do not copy bytes
    → do not enqueue generation
```

Character equivalent: `approveCharacterCandidate({ assetId, referenceRole: "hero_identity", sourceType: "upload"|"library" })`.

Prop already has `approve_candidate()` for **generated** looks (sets `approved_asset_id` + `library_asset_id` from `candidate.asset_id`). Reuse that field write. Add a reference-identity path that does the same with `reference_asset_id` / picker `asset_id`.

---

## Generation contract: extend vs new endpoint

**Extend** `POST /api/prop-creator/projects/{project_id}/props/{prop_id}/generate`.

Keep old fields as fallback for one release. Prefer Character-shaped `generatorSources`. No new route.

Also extend upsert `generator` so Standard/Express persist the same plan.

---

## Leftover NO-GO: silent zimage → qwen still present?

**Yes. Still present in Prop planner.**

`studio-api/app/prop_creator/generation.py` `build_prop_candidate_plans`:

- If local is enabled, **every** executable local family is appended as a source.
- Selected `local_family` is only moved to the front.
- Then `for i in range(candidate_count): src = sources[i % len(sources)]`.

So "zimage + 4 candidates" still schedules zimage, then qwen/illustrious/flux/… That is the dishonest swap. User Control Law is violated.

Related (not Prop-only, but hits Prop jobs):

- `enqueue_imagegen_job` defaults missing preference to `"zimage"`.
- `image_product/compile.py` silently falls back to certified Z-Image when the preferred family is not Certified **unless** `forceWorkflowKey` is set. Prop does not pin a workflow key, so a requested qwen/illustrious job can still become zimage. Opposite direction of the named leftover, same class of lie.
- `recommend_image_family` remaps a non-executable preferred family to zimage.

Character visual-sheet code explicitly refuses silent family substitute when a workflow is pinned. Prop generate does not pin.

Repair: emit one plan per (enabled source × batch index) using **only** the checked family/model. If that family cannot run, fail that candidate visibly. Never fill the batch from the rest of the registry.

---

## Smallest repair plan

1. **Do not edit Character Creator.** Do not bounce APIs. Do not wait for the :8760 bundle to catch up.
2. Add a parameterized `GeneratorPlanPanel` under `components/generators/` (consume `characterGeneratorPlan` + `generators/types` + the same two inventory APIs). Prop-only labels: Description Guided, one image/batch, "Prop Images".
3. Swap `GeneratorBlock` from `GeneratorSourceSelector` → that panel. Express and Standard pick it up automatically.
4. Extend `usePropCreator` / `propGenerateRequest` / `GenerateBody` with `generatorSources` (local[] / api[] / styleEngine). Keep old scalars as fallback.
5. Rewrite `build_prop_candidate_plans` + `_enqueue_plans`:
   - checked local family × N batches = N local jobs of **that** family
   - checked API model × N batches = N hosted jobs of **that** model (use discovery ids: `providerId` + `modelId`)
   - unchecked = zero jobs
   - delete all-family round-robin (kills zimage→qwen)
   - API: execute or fail the row; delete the global `API Generation — Not Available` raise
6. Style Engine: persist `stage2Enabled` / `stage2Family`. Wire a real edit pass **or** hide until wired. No inert checkbox.
7. Add "Use as Prop Identity" beside Reference. Pointer write: `approved_asset_id` + `library_asset_id` = existing `asset_id`. No binary dup. Reuse `approve_candidate` field semantics.
8. Tests: planner (zimage-only never emits qwen), discovery shortlist (no "Not Available" copy), identity pointer, Express===Standard core.

Out of scope: Character 4-view sheets, Character file edits, new Prop registry, new generate URL, bouncing :8758/:8761/:8760.

---

## READY TO IMPLEMENT

Yes. Shared dropdown is not the target. Character source already has the shortlist to consume. Prop contract can be extended in place. The leftover family swap is still in `build_prop_candidate_plans` and must be removed in the same pass.
