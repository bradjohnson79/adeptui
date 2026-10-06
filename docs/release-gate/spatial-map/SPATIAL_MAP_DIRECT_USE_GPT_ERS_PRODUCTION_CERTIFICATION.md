# Spatial Map Direct-Use + GPT Image 2 ERS Production Certification

**Governing document for this milestone.**

Do not cite Local Atlas reports as current production truth. Frozen GPT Atlas generate/gate/hosted IDs stay frozen.

**Verdict:** `GO — SPATIAL MAP DIRECT-USE + GPT IMAGE 2 ERS MASTER/N/E/S/W + 3D REPRESENTATION + JSON + 2K TIMELINE PIPELINE LIVE E2E CERTIFIED`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Starting / HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes this mission; not committed unless requested) |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Direct-use Playwright map | Direct Use Playwright Cert |
| Live ERS map | ERS Production Cert `d7c721c3-9377-4eca-bea7-3c2be2e5e5fc` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` · Comfy `:8188` reused (no supervisor `--force`) |

Evidence: `docs/release-gate/spatial-map/evidence/direct-use-gpt-ers/`.

Success string: `GO — SPATIAL MAP DIRECT-USE + GPT IMAGE 2 ERS MASTER/N/E/S/W + 3D REPRESENTATION + JSON + 2K TIMELINE PIPELINE LIVE E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP DIRECT-USE / GPT IMAGE 2 ERS PRODUCTION PIPELINE NOT CERTIFIED`

---

## PART A — Direct-use checkbox

- Checkbox `Use this image as the Spatial Map` appears only when a Library/upload reference exists (`spatial-map-use-as-atlas`).
- Clicking the checkbox only changes intent. No classify/assign/job.
- Unchecked primary: **Generate Spatial Map** → GPT Image 2. Never silent auto-assign.
- Checked primary: **Use Spatial Map** → classify `assign`. PASS → `applyAtlasToMap` (`geometrySource: supplied`). FAIL stays on the form with `DIRECT_USE_NOT_ATLAS`. No GPT POST.
- Playwright (`:5173`, cert project): **1 passed** — `tests/e2e/codirector/spatial-map-direct-use.spec.ts` (re-run after API recycle: **1 passed**, 6.1s).

---

## PART B–G — ERS production pipeline

Live Spatial Map **Generate Environment Reference Sheet** sends `ers_pipeline: components`.

Sequence: parent execution → Master → North → East → South → West → 3D Environment Representation → deterministic 2K compose + machine JSON.

- Reuses frozen `EnvironmentReferencePackage` fields (`atlas_asset_id`, `master_environment_asset_id`, `directional_assets`, `ers_composite_asset_id`, `placements`).
- Additive metadata: `threeDRepresentationAssetId` (illustrative image, never MESH), `machineJsonAssetId`, revision stamps.
- Direction yaws: N=0, E=90, S=180, W=270 (atlas-north-up).
- Compose is code (`ers_compose_2k.py`). Live 16:9 is **2560×1440**.
- Labels: SPATIAL MAP, MASTER, NORTH, EAST, SOUTH, WEST, 3D ENVIRONMENT.
- Spatial Map panel is a rendered grid snapshot, not a GPT redraw.
- Collage one-shot remains only when `ers_pipeline=collage` (legacy Qwen unit tests). GPT with omitted pipeline now resolves to `components`.
- Targeted retry sends `retry_component`. Handler reuses the richest existing package for the map so accepted siblings stay.

### Live IDs (ERS Production Cert)

| Item | ID |
| --- | --- |
| Execution (completed) | `0e86ed60-fbb9-4677-93ac-bec2fe66b458` |
| Package | `e2aba517-a7fc-4802-8bfc-5914b8b5eb30` |
| Sheet | `cf1f8b8d-9b26-421d-9e82-29e991f4dc60` |
| Master | `760dcab9-5378-4d98-aa09-8f9ba74f57b9` |
| North | `a8236a7b-90f9-42eb-9ff0-3dbc0dd109de` |
| East | `a35165f8-62dd-4697-8342-4f4253429347` |
| South | `df3b2a78-5681-4f07-97de-6fdb63255255` |
| West | `564b442d-16a0-4209-b6b0-7594141e7521` |
| 3D representation | `003c39fa-d679-4516-9c4c-b836084da850` |
| 2K composite | `872347bd-4425-4482-9aec-8a2eeb883bc8` |
| Machine JSON | `3a3e2e75-c9d5-4dd0-9862-1f2c72095e7e` |
| Handoff | `a4cb7f6f-7193-5fe0-aa3a-1ce0fc2186f8` revision 2 |

First attempt (`f838ba0b-…` / package `8f973dc7-…`): Master, North, East completed; South failed `GENERATION_FAILED` (Kie transient). Targeted retry continued. Before package-reuse landed, the retry started a new package and regenerated Master/N/E after South; source now reuses the richest package. Live still produced a complete sequential GPT Image 2 sheet.

Manual inspect of `evidence/direct-use-gpt-ers/ers-composite-2k.png`: unique labeled cardinals, rendered Spatial Map grid with character + camera, 3D ENVIRONMENT (not mesh), human summary. No duplicated/mislabeled panels.

---

## PART H–J — Handoff and invalidation

- Scene Creator Mini prefers `master_environment_asset_id` when the component pipeline produced one; legacy collage crop remains fallback only.
- Production handoff pointers include master, directional assets, 3D representation, machine JSON, composite, and `ersRevision`.
- Structure/Atlas/sceneIntent change (`lineageFingerprint`) → full regen. Placement-only → recompose map panel + JSON + stitch; keep Master/N/E/S/W.

---

## Tests

| Gate | Result |
| --- | --- |
| Spatial Map vitest | **153 passed** |
| ERS component/compose/packet + Mini master + Qwen collage + 2K + Atlas i2i + layout compiler + reconstruct + Prop | **143 passed** in the protected batch; 1 pre-existing CC SenseNova roster fail (`test_character_roster_hides_non_executable_and_auto_stays`) — not this mission |
| ERS pipeline unit after prompt/reuse | **5 passed** |
| Playwright direct-use | **1 passed** (`:5173` + `:8758`) |
| Live ERS Master/N/E/S/W/3D/JSON/2K | **completed** — `live-ers-retry.json` |
| Standard reconstruct chooser | covered in Spatial Map vitest (`SpatialMapStartChooser.test.ts`) |

Protected: no Qwen workflow edits. Frozen GPT Atlas generate untouched. Local Atlas remains deferred.

---

## Isolation

- No `POST /api/projects`.
- Production map Atlas remained `9f7d4571-…` on `e6f64c3b-…` after live + Playwright.
- Live cert map `d7c721c3-…` reused Library pixels of that Atlas asset as `backgroundAssetId`. That is not writing Atlas onto the production map.
- Historical Local cert map `a6176a4c-…` not overwritten.
- Studio API recycled without `--force` Desktop Comfy. Vite `:5173` 200. API `:8758` 200.
- Production restored as most-recent (`getMostRecentMap` default).

---

## Auditors

- Kimi 2.7 ERS generation auditor: **PASS — ERS GENERATION** ([ERS generation](3ebd9065-810b-474e-9e03-48a8420b60df))
- Kimi 2.7 ERS composition/Timeline auditor: **PASS — ERS COMPOSITION / TIMELINE** ([composition/Timeline](fba2acd9-9fe1-498b-b9da-7b672e4fa032))
- Composer 2.5 (`composer-2.5-fast`) peer review: **PASS** ([Composer 2.5](4abb4a23-2da1-467a-9459-00a9becce7c7)) after prior BLOCK repairs (stages on poll; pack-complete only; GPT preferred over silent Qwen).

---

## E2E TRACE

| Stage | Verdict | Evidence |
| --- | --- | --- |
| User action | PASS | Express checkbox + Use Spatial Map (Playwright). Create ERS on ERS Production Cert (live script / Spatial Map **Generate Environment Reference Sheet**). |
| Frontend | PASS | `SpatialMapExpressForm` / `SpatialMapPanel` opt-in assign. `useErsGeneration` sends `ers_pipeline: components` and `retry_component`. Stages refresh every poll. |
| API | PASS | `POST /api/codirector/projects/…/executions` capability `ers.generate`. Advance until `completed`. |
| Backend | PASS | Sequential GPT Image 2 I2I Master/N/E/S/W/3D then code compose. |
| Persistence | PASS | Package, sheet composite, machine JSON Library assets survive. |
| Runtime | PASS | Kie GPT Image 2 I2I (`gpt-image-2-image-to-image`). No silent Qwen/CPU fallback. |
| Result | PASS | 2560×1440 stitch + machine JSON + all component asset IDs. |
| Reload | PASS | Sheet `ers_composite_asset_id` `872347bd-…` after complete. Production Atlas unchanged after restore. |
| Downstream | PASS | Production handoff revision 2 includes master, N/E/S/W, 3D, machine JSON, composite. Mini prefers `master_environment_asset_id`. |

Independent verifier: **VERIFIED — FULL-STACK E2E PASSED** (Kimi generation + composition auditors + Composer 2.5 PASS).

---

## Limitations (honest)

- No approved project prop was available; live placements were 1 character + 1 camera (0 props).
- Historical live retry (before reuse fix) created package `e2aba517-…` instead of continuing `8f973dc7-…`. Source now reuses the richest package. Documented; not re-run.
- Some GPT component images still look like technical sheets; Master prompt now forbids multi-panel sheets (unit-tested). Live pixels were not regenerated after that prompt tweak.
- ERS generator dropdown default remains Qwen Image; the live cert path sent GPT Image 2 explicitly. Auto-select prefers GPT I2I when the current choice is disabled.
- Pre-existing `test_character_creator_final_closure.py::test_character_roster_hides_non_executable_and_auto_stays` fails on SenseNova Draft (not introduced here).

---

## Manual review

1. Open `http://127.0.0.1:5173/` → Adept Stability Cert → Spatial Map.
2. Default map is **Supplementary View Assist Cert** (production). Do not overwrite its Atlas.
3. Switch to **ERS Production Cert** to inspect the live sheet / Library composite.
4. Express: pick a Library image → checkbox **Use this image as the Spatial Map** → primary becomes **Use Spatial Map**.
5. Studio API `http://127.0.0.1:8758/api/healthz` must stay 200. Do not supervisor `--force` Desktop Comfy.

---

## Final verdict

`GO — SPATIAL MAP DIRECT-USE + GPT IMAGE 2 ERS MASTER/N/E/S/W + 3D REPRESENTATION + JSON + 2K TIMELINE PIPELINE LIVE E2E CERTIFIED`
