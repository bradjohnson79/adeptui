# ERS Character Identity Grounding Certification

**Governing document for this milestone.**

Spatial Map placements must resolve by Character Creator `characterId` into approved pixels + canon JSON, then GPT Image 2 occupied generation, identity gate, and occupied-only retry. Environment-only ERS panels stay.

**Verdict:** `GO — ERS SPATIAL MAP → CHARACTER CREATOR CANON → GPT IMAGE 2 IDENTITY GROUNDING LIVE E2E CERTIFIED`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes isolation repair + tests) |
| Named Jacob project | SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Character | Special Agent Jacob Barnes `10303eba-ed95-49fe-a86b-e5493b7a1c75` (`APPROVED`) |
| Approved hero | `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` (CRS revision 1) |
| Map | Observatory Control Room `477b450c-734d-49ae-a40a-51402e0a832f` |
| Placement | `71924495-3f24-4b47-962b-7fb696190231` — `characterId` matches Jacob |
| Isolation execution | `f6ebe88c-b2f4-4f77-b20f-b108a64d16b3` |
| Occupied job | `6b2bfdfb-c5ee-406e-bb22-5978c0da0aae` |
| Occupied asset | `144daa69-65cf-47fd-8291-aeb0c19f5551` |
| Composite | `2a8158ff-027e-4d38-9700-a7ce7a5aa791` |
| Machine JSON | `cdfacc5b-cf2e-49eb-82ce-11ff20942c0c` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| LLM review | Composer 2.5 review-only **PASS** ([Composer isolation review](39ea0827-799e-49ca-9a9e-e22259ad4d37)) |

Success string: `GO — ERS SPATIAL MAP → CHARACTER CREATOR CANON → GPT IMAGE 2 IDENTITY GROUNDING LIVE E2E CERTIFIED`

Failure string: `NO-GO — ERS CHARACTER IDENTITY GROUNDING NOT CERTIFIED`

---

## Live IDs (Jacob, not recreated)

| Link | ID |
| --- | --- |
| Spatial `characterId` | `10303eba-ed95-49fe-a86b-e5493b7a1c75` |
| Approved reference | `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` |
| GPT Image 2 `input_urls[0]` | `…/api/assets/90e8c04a-…/file` (`character_identity`) |
| GPT Image 2 `input_urls[1]` | environment `62888b73-…` (`environment`) |
| Identity gate | `PASS` — same face, hair, skin, body type, wardrobe |

Prompt head: `Create ONE occupied-scale production still of Observatory Control Room. The visible character is the approved saved character Special Agent Jacob Barnes.`

---

## Repair

1. Shared `resolve_character_for_generation` is ID-primary. Name is last-resort. Rejected/deleted references never win.
2. Mini and ERS call that resolver with no silent `except`.
3. Occupied is a first-class component. Collage-only sheets replace panel 9 (`COLLAGE_OCCUPIED_REGION`).
4. `_component_body` attaches character pixels as GPT Image 2 slot 1. Collage compiler is skipped when `ersComponent` is a tile.
5. Occupied VLM gate `FAIL_CHARACTER_IDENTITY`. Occupied-only retry sets `occupiedOnly` and composes after identity PASS. It does not call `next_component` to fill missing cardinals or 3D.

---

## Tests

| Gate | Result |
| --- | --- |
| Identity + Mini concurrency + Local attention | **30 passed** (prior mission; Mini/CC not reopened) |
| Occupied-only isolation | **3 passed** — `studio-api/tests/test_ers_occupied_only_isolation.py` |
| Playwright Mini camera production | **3 passed** — take `5770d67b-…` (Mini frozen; not rerun) |
| Composer 2.5 isolation review | **PASS** |
| Live occupied Jacob identity | **PASS** (prior) |
| Live occupied-only sibling isolation | **PASS** — execution `f6ebe88c-…` |

Isolation tests cover: occupied-only enqueue, compose-after-occupied with no cardinal jobs, identity FAIL with no sibling enqueue, sibling asset ID reuse, identity gate preserved.

---

## Final Occupied-Only Isolation Reproof

Evidence: `docs/release-gate/ers/evidence/occupied-only-isolation-before.json`, `occupied-only-isolation-start.json`, `occupied-only-isolation-poll.json`, `occupied-only-isolation-after.json`, `occupied-only-isolation-sheet-reload.json`, `isolation-visuals/`.

| Item | Value |
| --- | --- |
| Execution ID | `f6ebe88c-b2f4-4f77-b20f-b108a64d16b3` |
| Occupied job ID | `6b2bfdfb-c5ee-406e-bb22-5978c0da0aae` |
| Occupied asset ID | `144daa69-65cf-47fd-8291-aeb0c19f5551` |
| Identity reference asset | `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` |
| Identity gate | `PASS` |
| Composite ID | `2a8158ff-027e-4d38-9700-a7ce7a5aa791` |
| Machine JSON ID | `cdfacc5b-cf2e-49eb-82ce-11ff20942c0c` |
| Compose mode | `collage_panel_9` (deterministic restitch) |
| Paid generations | Occupied only |
| Composer 2.5 | **PASS** |

### Before sibling IDs

| Component | Asset ID |
| --- | --- |
| Package | `ce289fb6-41b1-470a-a783-72109c6fd046` |
| Master | `32cfec5b-5110-43bc-bd0f-96e089f287d0` |
| North | `f4769798-da41-496f-b6b8-44e8505e8285` |
| East | `776ad997-9ade-40b9-aac9-6c0eb9aff080` |
| South | *(none)* |
| West | *(none)* |
| 3D Environment Representation | *(none)* |
| Occupied | `1b880ee8-8b4d-4932-8caf-6249ead02f98` |
| Composite | `6b32e322-31a9-41f1-a666-77b227055879` |
| Machine JSON | `c22375bc-b9b1-4f08-a31c-7016c5d4e87c` |

### After sibling IDs

| Component | Asset ID | Changed |
| --- | --- | --- |
| Master | `32cfec5b-5110-43bc-bd0f-96e089f287d0` | no |
| North | `f4769798-da41-496f-b6b8-44e8505e8285` | no |
| East | `776ad997-9ade-40b9-aac9-6c0eb9aff080` | no |
| South | *(none)* | no |
| West | *(none)* | no |
| 3D Environment Representation | *(none)* | no |
| Occupied | `144daa69-65cf-47fd-8291-aeb0c19f5551` | yes (allowed) |
| Composite | `2a8158ff-027e-4d38-9700-a7ce7a5aa791` | yes (allowed) |
| Machine JSON | `cdfacc5b-cf2e-49eb-82ce-11ff20942c0c` | yes (allowed) |

`previousCompositeAssetId` = `6b32e322-31a9-41f1-a666-77b227055879`  
`newCompositeAssetId` = `2a8158ff-027e-4d38-9700-a7ce7a5aa791`

### Child job list

Start and complete both showed exactly one child:

```text
Occupied scale  6b2bfdfb-c5ee-406e-bb22-5978c0da0aae  completed
```

Persisted Job rows created at or after that occupied job: **occupied only**. `siblingLeaks = []`. No Master/North/East/South/West/3D job was created, queued, submitted, cancelled, or completed.

Polls every 15s (`occupied-only-isolation-poll.json`): `newComponentJobs = []`, `leak = null`, then `pipeline_status = complete` and execution `completed`.

### Prompt excerpt

```text
Create ONE occupied-scale production still of Observatory Control Room.
The visible character is the approved saved character Special Agent Jacob Barnes.
Use the supplied character reference as the authoritative identity.
… Do not substitute a generic person, anonymous stand-in, alternate actor,
or newly invented character.
```

Package metadata during the run: `occupiedOnly = true`, `retryComponent = occupied`. After identity PASS the pipeline composed; it did not call `next_component` to fill missing South/West/3D.

### Machine JSON provenance (reload)

- `characterId` `10303eba-ed95-49fe-a86b-e5493b7a1c75`
- `approvedRevision` 1
- `referenceAssetId` `90e8c04a-c9c0-4016-85e6-95dc7d1a967e`
- `occupiedScaleAssetId` `144daa69-65cf-47fd-8291-aeb0c19f5551`
- `identityRequired` true
- sibling asset IDs reused (Master/North/East unchanged; South/West/3D still empty)
- `composeMode` `collage_panel_9`

### Reload proof

GET `/api/environment-reference-sheets/projects/0ffe56e2-…/93c89cd1-…`:

- `summary.has_reference` = `true`
- `summary.ers_composite_asset_id` = `2a8158ff-027e-4d38-9700-a7ce7a5aa791`
- sheet composite matches
- Jacob identity provenance remains on the package and machine JSON
- sibling IDs unchanged

Studio API was recycled **before** this retry so the `occupiedOnly` branch was live. Healthz 200, Vite `:5173` 200, Jacob character GET 200. Comfy was not `--force` restarted.

### Owner visual verdict

Yes, this is visibly Special Agent Jacob Barnes.

Occupied `144daa69-…` matches approved hero `90e8c04a-…`: same face, salt-and-pepper beard, black suit, white shirt, burgundy tie, pocket square. Not a generic stand-in.

### Composer 2.5 verdict

**PASS** — [Composer isolation review](39ea0827-799e-49ca-9a9e-e22259ad4d37)

---

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — occupied-only retry |
| Frontend | PASS — `retry_component=occupied` |
| API | PASS — execution `f6ebe88c-…` created |
| Backend | PASS — `occupiedOnly` branch |
| Persistence | PASS — one occupied child only |
| Runtime | PASS — GPT Image 2 Jacob-conditioned request (slot 1 = hero) |
| Result | PASS — identity gate PASS |
| Isolation | PASS — no N/E/S/W/3D child jobs |
| Compose | PASS — existing siblings + new occupied (`collage_panel_9`) |
| Reload | PASS — corrected ERS persists (`has_reference` + new composite) |
| Downstream | PASS — package coherent; machine JSON keeps Jacob provenance |

---

## Predecessor

The first occupied-only retry (`a2bac726-…` / job `af63c692-…`) proved identity pixels, prompt, gate PASS, and provenance, then incorrectly advanced to North (`f4769798-…`) because `advance_ers_component` called `next_component`. East was cancelled after enqueue. That leak is closed by this reproof.

Scene Creator Mini remains:

`GO — SCENE CREATOR MINI CAMERA FIDELITY + API CONCURRENCY + LOCAL SEQUENTIAL + INPAINT + APPROVAL PIPELINE LIVE E2E CERTIFIED`

See `docs/release-gate/scene-creator/SCENE_CREATOR_MINI_CAMERA_PRODUCTION_CERTIFICATION.md`. This closure did not modify Mini, Character Creator, Spatial Map placements, or Atlas.

---

## Original sheet restore

The visible ERS is the original SenseNova Integration Lab collage (`32cfec5b-…`), not the later component dashboard. Approved GPT Image 2 Jacob (`144daa69-…`) is placed only in panel 9 (Contextual Production / Occupied Scale). Hero, spatial, 3D greybox, elevations, materials, lighting, Environment DNA, and Continuity Rules are unchanged.

| Item | ID |
| --- | --- |
| Original collage | `32cfec5b-5110-43bc-bd0f-96e089f287d0` |
| Restored composite | `6cc54dc4-bf85-493a-807f-8c1120b70f42` |
| Jacob occupied still | `144daa69-65cf-47fd-8291-aeb0c19f5551` |

`collageAssetId` is pinned to the original so a later occupied retry restitches that sheet, not the dashboard.

## Limitations

- Identity FAIL isolation is covered by unit test, not a second paid live FAIL run.
- If a later provider request rejects two reference URLs, keep character identity pixels over the optional environment reference.

---

## Verdict

`GO — ERS SPATIAL MAP → CHARACTER CREATOR CANON → GPT IMAGE 2 IDENTITY GROUNDING LIVE E2E CERTIFIED`

---

## Addendum — Panel 9 compositor + Spatial Map Regenerate

**This addendum does not reopen** Character Creator, Scene Creator Mini, Spatial Map placements, or Atlas certifications. Mini remains:

`GO — SCENE CREATOR MINI CAMERA FIDELITY + API CONCURRENCY + LOCAL SEQUENTIAL + INPAINT + APPROVAL PIPELINE LIVE E2E CERTIFIED`

### What was broken

1. Panel 9 used the 3×3 gallery box `{left: 2/3, top: 2/3}` and letterboxed onto `(20,24,30)` — wrong region (Continuity Rules) plus black pad / spill.
2. Monitor **Regenerate** called `ers.retry()` (failed-component retry). `start()` could silent-return. `occupiedOnly` leaked onto full start whenever `collageAssetId` was set, or leftover `occupiedOnly=true` survived a full start.

### Repair

| Item | Binding |
| --- | --- |
| Template | `sensenova-integration-lab-ers-v1` contract version 1 |
| Template asset | `32cfec5b-5110-43bc-bd0f-96e089f287d0` (1672×941) |
| Panel 9 content | `(1048, 496, 1660, 632)` exclusive — title stays outside |
| Fit | Cover-fit only; fail closed if contract missing or size mismatches |
| Gallery 3×3 | Only `gallery-3x3-v1` |
| Occupied still | `144daa69-65cf-47fd-8291-aeb0c19f5551` (reused, not regenerated) |
| Latest composite | `cf2718c5-8562-4716-8fc7-6b0e760fd6b2` |
| Sheet fingerprint | `e24f7e25a28e5d14` (matches live Observatory map) |
| `occupiedOnly` after full start | unset |

Monitor **Regenerate** → `startErsGeneration()` → `ers.start()` with no `retry_component`. Failed **Retry** stays `ers.retry()`. Dirty maps Save Gate then start. `start()` never silent-returns. `occupiedOnly` only when `retry_component == occupied`; leftover flag is cleared on full start.

### Tests

| Gate | Result |
| --- | --- |
| Panel 9 compose + no 3×3 fallback + occupied isolation | **11 passed** — `test_ers_panel9_compose.py` + `test_ers_occupied_only_isolation.py` |
| Frontend regenerate / retry / silent-start | **34 passed** — `useErsGeneration.test.ts` + `SpatialMapPanel.test.ts` |
| Playwright owner E2E | **1 passed** — `tests/e2e/ers-panel9-regenerate.spec.ts` |
| Composer 2.5 review-only | **PASS** ([Composer Panel 9 review](c62456c2-6657-421d-8301-c180e6293d69)) |

Restitch pixel proof vs original collage: size 1672×941, **0** outside-box mismatches, **0** letterbox pad pixels, destination mid-pixel changed (Jacob present).

### Playwright honesty

Regenerate POSTed `ers.generate` with **no** `retry_component`, showed queued/generating, completed, cleared stale, and survived reload. Because the sheet fingerprint already matched the live map after the honest stamp, the backend **recomposed** Panel 9 onto the original collage (~5s) instead of enqueueing a 7-job paid schedule. Full component schedule remains the path when lineage is stale. The click was not skipped.

### E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — Monitor Regenerate |
| Frontend | PASS — `start()` no `retry_component`; progress visible |
| API | PASS — POST `/api/codirector/projects/…/executions` `ers.generate` |
| Backend | PASS — collage contract cover-fit; `occupiedOnly` not set |
| Persistence | PASS — composite `cf2718c5-…`; fingerprint stamped |
| Runtime | N/A — lineage-matched recompose; Jacob still reused |
| Result | PASS — original layout, Panel 9 bounded, no black/spill |
| Reload | PASS — same composite + fingerprint after reload |
| Downstream | PASS — template `sensenova-integration-lab-ers-v1` v1 on package |

### Addendum limitations

- Full stale-lineage 7-job paid schedule was not re-run in this addendum (sheet was no longer stale).
- Identity FAIL isolation remains unit-covered only.

### Addendum verdict

`GO — ORIGINAL ERS PANEL 9 COMPOSITION + SPATIAL MAP REGENERATE ACTION LIVE E2E CERTIFIED`
