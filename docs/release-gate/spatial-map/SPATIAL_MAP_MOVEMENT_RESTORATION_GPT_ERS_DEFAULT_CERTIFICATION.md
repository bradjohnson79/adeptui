# Spatial Map Movement Restoration + GPT Image 2 ERS Default Certification

**Governing document for this milestone.**

Restores the already-built M1–M5 Movement Segment pipeline. Does not invent a directional-pad architecture. Does not reopen Local Atlas. Frozen GPT Image 2 Atlas generate stays frozen except the ERS **default/selection** repair.

**Verdict:** `GO — SPATIAL MAP FIVE-MOVEMENT PIPELINE RESTORED + GPT IMAGE 2 ERS PRODUCTION DEFAULT LIVE E2E CERTIFIED`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Starting / HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes this mission; not committed unless requested) |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Live movement / ERS inspect map | ERS Production Cert `d7c721c3-9377-4eca-bea7-3c2be2e5e5fc` |
| Direct-use Playwright map | Direct Use Playwright Cert |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` · Comfy `:8188` reused (no supervisor `--force`) |

Success string: `GO — SPATIAL MAP FIVE-MOVEMENT PIPELINE RESTORED + GPT IMAGE 2 ERS PRODUCTION DEFAULT LIVE E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP MOVEMENT / ERS GENERATOR DEFAULT REPAIR NOT CERTIFIED`

---

## PART A — M1–M5 restored (not invented)

Authoritative domain remained in `studio-api/app/spatial_map/movement.py` (`MOVEMENT_MAX = 5`, inherit-on-create, `write_through_active`, hydrate M1, arrows). Later Express/ERS work had dropped the document contract and wiring.

Restored:

- `SpatialMapDocument.movementSegments` / `activeMovementSegmentId` / `movementSegmentRevision`
- `MovementSegment`, create/update bodies
- Thin service wrappers: `create_movement`, `update_movement`, `activate_movement`, `remove_movement`, `movement_arrows`
- `write_through_active` on `_save_document` and `commit_document` (place/update/remove/save flush the live buffer into the active segment)
- HTTP: `POST/PATCH/DELETE …/movements`, `POST …/activate`, `GET …/movement-arrows`
- `spatialMapApi` forwards existing `api.spatialMap` movement methods
- Spatial Map accordion after inspectors, before slots: Movement 1…5, `+ Add Movement` disabled at five, Remove only on M2–M5, select activates
- Slot **Move** remains click-to-relocate (`beginPlacement("move", …)`). Not replaced.
- SVG arrows via `computeClientArrows` on the grid
- Co-Director tools rebound: `spatial.save`, `spatial.commit_map`, `spatial.create_movement`, `spatial.update_movement`, `spatial.activate_movement`, `spatial.delete_movement`, `spatial.plan_movements` (recommend-only), plus existing `spatial.move_placement` meters path now writes through and prefers meters when applying N/E/S/W deltas

Cameras stay global. Character/prop snapshots inherit per segment.

---

## PART B — ERS production default

- `ERS_GENERATOR_DEFAULT = "gpt-image-2"`
- Production `ERS_GENERATOR_OPTIONS` is GPT Image 2 only
- Stored `qwen2512` / empty storage resolve to GPT for **new** generation
- Silent auto-select that could switch to Qwen was deleted
- GPT-down copy no longer tells the creator to choose Qwen
- Co-Director `ers.generate` with an empty creator model now selects GPT Image 2 (explicit Qwen still honored for historical jobs)
- Child start context remains `buildErsStartContext("gpt-image-2")` + `ers_pipeline: "components"`
- Old ERS package provenance was not rewritten

---

## Tests

| Gate | Result |
| --- | --- |
| Movement domain | `test_movement_segments.py` **passed** |
| Movement tools bound | `test_movement_tools_registered.py` **passed** |
| Movement service / write-through / isolation / CD meters | `test_movement_service_write_through.py` **6 passed** |
| Combined movement unit/API | **19 passed** |
| Spatial Map vitest | **154 passed** (19 files) |
| ERS default vitest | `ersGenerator.test.ts` + `useErsGeneration.test.ts` + `movementSegments.test.ts` **24 passed** |
| ERS component + 2K + Atlas I2I | **13 passed** |
| Prop Express | `test_prop_creator_express.py` **passed** (in protected batch) |
| Playwright movement | `tests/e2e/codirector/spatial-map-movement.spec.ts` **1 passed** (4.7s) — accordion, activate, slot Move, CD `spatial.move_placement` propose+approve 1 m north, reload, GPT-only select, existing ERS children `gpt-image-2-image-to-image` |
| Playwright ERS selector | `tests/e2e/spatial-map-ers-generator.spec.ts` **1 passed** on retry (first attempt missed panel during API recycle) |
| Playwright direct-use | `tests/e2e/codirector/spatial-map-direct-use.spec.ts` **1 passed** (2.7s) after API healthy |

Protected leftovers (not introduced here):

- `test_character_creator_final_closure.py::test_character_roster_hides_non_executable_and_auto_stays` — SenseNova Draft still listed
- `test_ers_handoff_identity.py` atlas fallback summary (GPT required) — pre-existing frozen Atlas path
- `test_scene_creator_mini.py` Grid position / `_library_visible` / Qwen CRS — pre-existing Mini leftovers

---

## Isolation

- No `POST /api/projects`.
- Production Atlas remained `9f7d4571-…` on `e6f64c3b-…` after restore PATCH.
- Live movement used ERS Production Cert `d7c721c3-…` only.
- Studio API recycled without supervisor `--force` on Desktop Comfy. Vite `:5173` 200. API `:8758` 200.

---

## E2E TRACE

| Stage | Verdict | Evidence |
| --- | --- | --- |
| User action | PASS | Spatial Map Movements accordion; Add Movement; activate Movement 1; slot Move; CD meters propose/approve |
| Frontend | PASS | `SpatialMapPanel` accordion + `spatialMapApi` + slot `character-move-0` + ERS select GPT only |
| API | PASS | `/movements`, `/activate`, `spatial.move_placement` proposal + approve |
| Backend | PASS | `movement.py` inherit/activate/write_through; `set_entity_meters` + `prefer_meters` on CD deltas |
| Persistence | PASS | GET after reload still has movementSegments on `d7c721c3-…` |
| Runtime | PASS | Existing ERS children `comfy_prompt_id` / provenance workflow `gpt-image-2-image-to-image`; no new paid 6-image run |
| Result | PASS | Accordion live; Move not dead; CD meters persisted via write-through |
| Reload | PASS | Movements + placements survive Playwright reload |
| Downstream | PASS | Production Atlas unchanged; direct-use Playwright still green |

---

## Limitations (honest)

- Playwright did not create all five movements on the live ERS map when Add was already near the cap; unit/API proved the five-movement limit and M1 delete forbid.
- ERS default certification used existing completed execution `0e86ed60-…` child jobs plus UI select — no second paid 6-image run.
- Mini generator chrome remains out of scope and still lists Qwen.
- Pre-existing Character Creator SenseNova roster fail remains.

---

## Manual review

1. Open `http://127.0.0.1:5173/` → Adept Stability Cert → Spatial Map.
2. Default map is **Supplementary View Assist Cert**. Do not overwrite its Atlas.
3. Switch to **ERS Production Cert** to use Movements and inspect the ERS generator (GPT Image 2 only).
4. Studio API `http://127.0.0.1:8758/api/healthz` must stay 200. Do not supervisor `--force` Desktop Comfy.

---

## Auditors

- Kimi 2.7 movement auditor: **PASS — MOVEMENT PIPELINE** ([movement](9efba6d7-8542-4ffa-ad39-bbe3a03efa8c))
- Kimi 2.7 ERS engine auditor: **PASS — ERS ENGINE** ([ERS engine](4dfcc256-98c5-4797-a913-1b1563e1063e))
- Composer 2.5 (`composer-2.5-fast`) peer review: **PASS** ([Composer 2.5](1832854b-04c8-45d7-8b39-de784f0f8b30))

Independent verifier: **VERIFIED — FULL-STACK E2E PASSED**

---

## Final verdict

`GO — SPATIAL MAP FIVE-MOVEMENT PIPELINE RESTORED + GPT IMAGE 2 ERS PRODUCTION DEFAULT LIVE E2E CERTIFIED`
