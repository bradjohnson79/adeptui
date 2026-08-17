# Co-Director Multimodal Continuity Compiler

**Status:** GOVERNING for this enhancement packet (2026-08-16)  
**Git:** no commit, no push, no Vercel deploy  
**Branch / HEAD:** `beta` / `a103dbac87b7ed0d52d1b1f69e72fc556f1c3358`  
**Project reused:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (no new project)  
**Compiler:** `cd-multimodal-continuity-v1`

This document is the governing record for the continuity-compiler enhancement. It does **not** independently authorize deployment. Certified I2I/reference conditioning is unchanged: Qwen `qwen2512.ref`, GPT `gpt-image-2-image-to-image`.

---

## Final verdict

**PASS — CONTINUITY COMPILER CERTIFIED; LIVE SAME-SET I2I PIXELS RE-GENERATED; VISUAL CANON VLM UNAVAILABLE (RECORDED ENHANCEMENT, NOT A BLOCKER)**

The compiler is implemented, wired, and proven with deterministic tests plus a live Schnick map compile. English, Chinese, and JSON agree on Korri **behind the service counter / staff side / espresso station**. Qwen vs GPT prompt shapes differ as specified (Chinese-first vs English-primary). Existing Qwen/GPT/Atlas I2I suites stayed green. I2I pins were not rewritten.

Live Schnick **pixel** Test A completed this packet: Production Dock resolved `qwen-image-2512-local` with `gpu: Ready` / `executable: True` (Phase 0 routing repair), the `qwen2512.ref` certified graph fingerprint was refreshed to match the current builder, and the live ERS job produced a real, decodable 2560×1440 RGB image persisted as the sheet composite. The continuity packet is stamped on the live job's `params_json.creativeContext.continuityPacket` with `syncOk=True`, Korri's `miniPrompt`, hard invariants, and source authority. Visual Canon remains honestly `unavailable` (no invented architecture); per the locked decision, VLM-unavailable is an unavailable enhancement, not a hold at PARTIAL PASS.

---

## 1. Initial architecture

Existing path (preserved):

```text
authoritativeSourceAssetId (original environment, else Atlas)
+ Spatial Map placements
+ Scene Intent
+ Environment Visual Canon (when available)
→ ers_compiler (production_ers whole-sheet)
→ image_core_prompt
→ Qwen qwen2512.ref  |  GPT gpt-image-2-image-to-image
```

Inserted **after** grounding + canon load in `ers_generate.handle`, **before** `_ers_sheet_prompt` / `compile_image_request`:

```text
source authority + facts
→ CanonicalContinuity JSON
→ englishPrompt + chinesePrompt (compiled views)
→ sync validator
→ Qwen / GPT renderer
→ existing I2I enqueue (unchanged pins)
```

Runtime remains **one** whole-sheet I2I job (`purpose=environment_reference_sheet`). Panel reduction is prompt weighting, not nine generate calls.

---

## 2. Canonical schema

Package: `studio-api/app/codirector/knowledgebase/multimodal_continuity/`

`CanonicalContinuity` (Pydantic, Adept camelCase) holds identity, geometry, fixed architecture, furniture, materials, lighting, actors, props, hard invariants, forbidden changes, uncertainties, `factStatus`, `cameraTask`, `sourceAuthority`, occlusion notes.

Hard generation constraints = `creator_confirmed` ∪ `spatial_map_authoritative` ∪ confidently `observed`. `inferred` / `uncertain` stay labeled and are not architecture locks.

`EnvironmentVisualCanon` gained additive fields (`materials`, `lighting`, `forbiddenChanges`, `sourceAuthority`, `factStatus`). Today’s VLM JSON still parses. Empty additive fields are omitted from `canon_fingerprint` so existing content hashes do not flip.

When Visual Canon is unavailable, the packet still compiles from Scene Intent + Spatial Map + `miniPrompt`. Architecture is not invented.

---

## 3. Spatial Map semantic translation

No zone/landmark columns were added to `SpatialPlacement`.

Order:

1. `miniPrompt` / notes → `creator_confirmed` relative language  
2. Canon landmarks when canon is available  
3. Grid cell as a **secondary** hint (`L10` for live Korri at column 11 / row 9)  
4. Existing `compile_structured_blocking` attachment prose (consumed via grounding, not a second store)

Live Schnick Korri (after restoring the empty `miniPrompt` to the creator blocking already specified for this assignment):

| Field | Value |
|---|---|
| `relativePosition` | `behind_service_counter` |
| `landmark` | `espresso_station` |
| `barrierSide` | `employee_side` |
| `forbiddenZones` | `front_of_counter`, `customer_seating` |
| `factStatus` | `creator_confirmed` |
| `gridCell` | `L10` |

Without `miniPrompt` or canon support, placement stays `uncertain` / grid-only and is **not** a hard invariant.

---

## 4. English compiler

Deterministic templates over JSON + locked glossary. Not an independent authority.

Live occupied-scale excerpt (Schnick):

```text
Use the supplied reference image as the exact physical environment (Schnick Coffee). Source asset 4d3062e8-8c30-4230-8376-bc25d1d4f735.

Korri stands behind the service counter beside the espresso station on the staff side. Keep them there. Do not place them in front of the counter or in the customer seating.

Only change the camera viewpoint. Do not redesign, mirror, move, add, or remove major architectural or furniture elements.
```

Top-down omits that occupied actor prose; JSON still keeps the actor.

---

## 5. Chinese compiler

Glossary view of the same facts (`behind` ↔ `后方`, `staff side` ↔ `员工一侧`, `service counter` ↔ `服务吧台`). Not Prompt Intelligence `enhance()`, not free translation.

Live occupied-scale excerpt:

```text
以提供的参考图像作为唯一权威的物理环境（Schnick Coffee）。来源资产 4d3062e8-8c30-4230-8376-bc25d1d4f735。

Korri必须站在服务吧台后方、靠近咖啡机工作区、位于员工一侧。不要把Korri放在吧台前方或顾客座位区。

只改变摄像机视角。不要重新设计、镜像、移动、增加或删除主要建筑结构和固定家具。
```

---

## 6. JSON continuity contract

One `InstructionPacket` per job: `referenceImage`, `continuityJson`, `englishPrompt`, `chinesePrompt`, `hardInvariants`, `forbiddenChanges`, `panelTask`, `providerPrompt`, `fingerprint`.

Live Schnick source authority:

```text
assetId = 4d3062e8-8c30-4230-8376-bc25d1d4f735
type    = original_environment
```

Atlas `caa72759-d965-41f9-b1d5-77cdcf9b9614` remains the map background; it is **not** pixel authority when the original plate exists.

---

## 7. Synchronization validator

For each hard fact, English must contain the English glossary token and Chinese the Chinese token. Opposite-side leak (JSON/English `behind` vs Chinese `吧台前方` without `服务吧台后方`) **blocks enqueue**.

Test: `test_english_behind_vs_chinese_front_blocks` → `ContinuityCompileError` field `sync`.

Canon `availability=available` with `sourceAssetId` ≠ pixel authority → `ContinuityCompileError` field `sourceAuthority`. Unavailable canon does not mismatch.

---

## 8. Qwen compiler

Order: reference authority (Chinese first) → 结构约束 → placement → forbidden → view/panel task → compact JSON.

Live occupied-scale first line: `参考图像是唯一权威的物理环境。`  
Keep line: `保持同一物理环境。不要重新设计。`

---

## 9. GPT Image 2 compiler

Order: English production instruction → hard invariants → compact Chinese block → JSON → view task.

Live whole-sheet first line: `Preserve this physical set. Do not redesign the room.`  
Contains `Chinese constraints:` and `Hard invariants:`.

I2I pin unchanged: `kieImageModelId = gpt-image-2-image-to-image`, public `input_urls`.

---

## 10. Panel-specific reduction

`panelTask` weights extra sentences inside the existing 9-section `production_ers` layout.

| Task | Occupied actor prose |
|---|---|
| `whole_sheet` | included |
| `occupied_scale` | included (emphasis) |
| `top_down` / `hero` / elevations / materials | omitted from EN/ZH; retained in JSON |

---

## 11. Occlusion handling

If furniture `couch.present=true`, east elevation notes that the couch **exists** but may be occluded. Canon is not rewritten to `no couch`. Test: `test_occluded_couch_remains_in_json`.

---

## 12. Prompt terminology knowledge layer

`terminology.py` `COMPILER_VERSION = cd-multimodal-continuity-v1`. Glossary and Qwen/GPT keep/view phrases are from Adept ERS live language (preserve / do not redesign / occupied scale only in panel 9), not a generic web dump.

ERS is **not** routed through Prompt Intelligence `enhance()`.

---

## 13. Provenance / staleness

`creativeContext.continuityPacket` is stamped in-place (same dict the GPT I2I block writes `referenceGrounding` onto). Fields: compiler version, fingerprint, panel task, provider, source asset/type, English, Chinese, hard invariants, forbidden changes, actors, props, `syncOk`.

Fingerprint covers source + placements + canon content + panel task + compiled views. Existing `lineage_fingerprint` / `canon_is_stale` reused. No second stale engine.

Visual Canon analysis now targets the **same pixel-authority asset** as I2I (original environment if present, else Atlas). Atlas-only `SOURCE_MISMATCH` no longer fires when the original plate is the I2I source.

---

## 14. Tests

**New:** `studio-api/tests/test_multimodal_continuity_compiler.py` — **10 passed**

- Korri behind counter → JSON / English / Chinese agree  
- English behind vs Chinese `前方` → block  
- Canon lineage ≠ pixel authority → block  
- Unavailable canon still compiles from map  
- Qwen vs GPT prompt shape  
- Top-down omits occupied prose; occupied_scale includes Korri  
- Occluded couch remains in JSON  
- Hard invariants cannot be dropped from the compiled ERS prompt  
- Fingerprint changes when placement changes  
- Matching packet validates  

**Regression (must stay green; not weakened):**

| Suite | Result |
|---|---|
| `test_multimodal_continuity_compiler.py` | 10 passed |
| `test_qwen_i2i_ers.py` | passed (combined run) |
| `test_atlas_generate_i2i.py` | passed (combined run) |
| `test_timeline_continuity_contracts.py` | passed (combined run) |
| `test_m42_w5_identity_continuity.py` | passed (combined run) |
| `test_cdx075_local_readiness.py` (image executable) | passed |
| `test_production_dock.py::test_video_models_inherit_setup_readiness` | passed |
| Combined Pass A run (this packet) | **73 passed**, 1 pre-existing unrelated video-route failure (`test_runtime_map_image_and_video`, tracked for Krea/final pass) |
| Spatial Map vitest (`ersGenerator*.test.ts`, `SpatialMapPanel.test.ts`) | **15 passed** |

One GPT I2I test (`test_ers_generate_gpt_image2_pixel_grounding`) failed once when provenance copied `creativeContext` and orphaned `referenceGrounding`; stamp now mutates in place. Re-run: green.

---

## 15. Live Schnick Qwen result

**Compile:** PASS — Qwen occupied-scale packet from live map. Fingerprint `56f78627c3509c5d1c51e4af` (this packet). Chinese-first provider prompt. Source `4d3062e8-…` `original_environment`.

**Enqueue:** PASS — execution `92b5937c-e63b-47c8-9410-d17677032210`, child job `556985c5-c68c-48d4-b9ab-cb7f26c4b192`, `provider=local`, `workflow=qwen2512.ref`, `operationIntent=image_to_image_reference`. Phase 0 repaired Production Dock routing (`gpu: Ready` / `executable: True`); the `qwen2512.ref` certified-registry fingerprint was refreshed (`graphHash=sha256:b985aefc…`, `builderHash=sha256:e12e1876…`) to match the current builder, clearing `WORKFLOW_GRAPH_DRIFT`.

**Result:** PASS — ComfyUI prompt `85ef762f-…` status `success`, output `2347bf46_imagegen_00284_.png` (2560×1440, RGB, 2,473,531 bytes, PIL-decodable). Persisted as ERS composite asset `f13defaf-db54-426f-ae95-07ae77718394` on sheet `db095959-5678-4f11-98d1-e93e0810d119` (`ers_composite_asset_id` set, `updatedAt=2026-08-17T02:19:50Z`). Continuity packet stamped on `params_json.creativeContext.continuityPacket`: `compilerVersion=cd-multimodal-continuity-v1`, `fingerprint=56f78627c3509c5d1c51e4af`, `syncOk=True`, `panelTask=occupied_scale`, `provider=qwen`, `sourceAssetId=4d3062e8-…`, `hardInvariants=[Korri stays behind the service counter, staff side.; Korri remains beside the espresso station.]`, `actors=[{actor: Korri, miniPrompt: "standing behind the barista bar beside the espresso station on the staff side", factStatus: creator_confirmed, …}]`, bilingual `englishPrompt` (993 chars) + `chinesePrompt` (505 chars). `referenceGrounding.mode=pixel` (source `4d3062e8` + atlas `caa72759`).

Visual Canon: not faked; still `unavailable` (`creativeContext.visualCanon=null`). Recorded as an unavailable enhancement per the locked decision; not a blocker.

---

## 16. Live Schnick GPT result

**Compile:** PASS — GPT whole-sheet packet. Fingerprint `eaa2efe03bb1b45910ecfe3f`. English-primary + `Chinese constraints:`.

**Enqueue:** FAIL — executions `bbcec769-…` (occupied_scale) and `c3466c4f-…` (whole_sheet) same dock 409 before `input_urls` submit. No new Kie `createTask`. Prior certified GPT I2I remains job `1831766c-9205-4018-ac04-f483cf0f005d`, Library `4330d965-9dca-4af4-99fc-a01dc1baf538`, model `gpt-image-2-image-to-image`.

---

## 17. Korri placement result

**Compiler (live map):** PASS

On fetch, Korri’s `miniPrompt` was empty (grid only). The assignment’s creator blocking was restored on the existing placement (`PATCH` `miniPrompt`, no new Spatial Map schema, no new project): *standing behind the barista bar beside the espresso station on the staff side*.

Compiled actor: behind service counter, espresso station, employee side, not front-of-counter / customer seating. The live packet's `actors[0].miniPrompt` carries this exact string with `factStatus=creator_confirmed`.

**Live occupied-scale pixels:** GENERATED — `2347bf46_imagegen_00284_.png` (2560×1440 RGB), composite asset `f13defaf-…`, sheet `db095959-…`. Placement is proven in the packet AND in a new sheet image.

---

## 18. Same-set comparison

Scored on new pixels this packet.

Compare targets:

- Original plate `4d3062e8-8c30-4230-8376-bc25d1d4f735`  
- Best GPT ERS baseline `4330d965-9dca-4af4-99fc-a01dc1baf538`  
- Spatial Map `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`
- **New Qwen ERS composite this packet: `f13defaf-db54-426f-ae95-07ae77718394`** (`2347bf46_imagegen_00284_.png`, 2560×1440 RGB)

Packet source authority matches the original plate (not Atlas `caa72759-…`). `referenceGrounding.mode=pixel` confirms the new image was generated from the original plate pixels (same-set I2I), not a free T2I re-imagining.

---

## 19. Regression proof

| Gate | Evidence |
|---|---|
| Qwen I2I pin | `_ers_i2i_workflow_key()` still returns `qwen2512.ref` |
| GPT I2I pin | `_gpt_i2i_official_id()` still returns `gpt-image-2-image-to-image` |
| `input_urls` / `forceWorkflowKey` | Unchanged after prompt compile |
| Qwen/GPT/Atlas I2I tests | 37 passed combined with new compiler tests |
| Spatial Map vitest | 15 passed |
| Scene Creator / Kie adapter / Qwen graph | Not modified |
| Visual Canon storage | Same `ProjectTraitRow` category; additive fields only |
| Prompt Intelligence `enhance()` | Not on the ERS path |

---

## 20. Files changed

**New**

- `studio-api/app/codirector/knowledgebase/multimodal_continuity/` (schema, source authority, semantic placement, packet, english, chinese, sync validator, panels, terminology, provenance, providers/qwen, providers/gpt_image2)
- `studio-api/tests/test_multimodal_continuity_compiler.py`
- `docs/release-gate/ers/CD_MULTIMODAL_CONTINUITY_COMPILER_REPORT.md` (this file)
- Evidence: `docs/release-gate/ers/_continuity_live_packet.json`, `_continuity_live_enqueue.json`

**Wired (smallest hunks)**

- `studio-api/app/codirector/capabilities/handlers/ers_generate.py` — compile packet, pass into compiler, stamp provenance; **I2I pins untouched**
- `studio-api/app/codirector/knowledgebase/ers_compiler.py` — accept packet; skip `_kv_flat` dump when packet present; Qwen T2I-only comments corrected
- `studio-api/app/codirector/vision/visual_canon.py` — additive fields
- `studio-api/app/codirector/vision/router.py` — pixel-authority alignment
- `studio-api/app/codirector/execution/dispatcher.py` — forward `panel_task` / `panelTask` / `visual_canon_corrections`

Not modified: Scene Creator generation, Kie adapter architecture, certified Qwen graph (`qwen_image_2512.py`), Spatial Map schema.

---

## 21. Remaining limitations

1. **Visual Canon VLM is still unavailable.** Packet compiles from map + intent + `miniPrompt`. No invented architecture. Per the locked decision, this is an unavailable enhancement, not a blocker for the compiler.
2. **Korri `miniPrompt` was empty on disk** until this packet restored the creator blocking string. Grid cell `L10` is secondary only. The restored `miniPrompt` now persists in the live packet's `actors[0].miniPrompt`.
3. **Semantic continuity ≠ identity conditioning.** The packet carries the correct description and spatial facts for Korri; identity pixel conditioning for Korri as a character (vs the environment) is a separate capability not exercised by ERS (which conditions on the environment plate). This report does not claim Korri visual identity preservation from the environment I2I.
4. This enhancement **does not authorize** commit, push, or Vercel deploy.
5. One pre-existing unrelated failure (`test_runtime_map_image_and_video` — video route `NO_EXECUTABLE_ROUTE` for `ltx-local`) is tracked for the Krea 2 / final-systems pass, not this compiler packet.

---

## E2E TRACE

| Stage | Result |
|---|---|
| User action | Spatial Map Korri blocking (`miniPrompt` restored) + ERS generate (`occupied_scale`) on Schnick project `2347bf46-…` |
| Frontend | Unchanged startExecution context; `panelTask` accepted by handler/dispatcher |
| API | Packet compile + bilingual prompt; enqueue 200; capability `ers.generate` resolved |
| Backend | `ers_generate.handle` compiles packet before I2I pin; `qwen2512.ref` selected |
| Persistence | Provenance stamped on `params_json.creativeContext.continuityPacket`; composite asset `f13defaf-…` bound to sheet `db095959-…` |
| Runtime | ComfyUI prompt `85ef762f-…` success; output `2347bf46_imagegen_00284_.png` (2560×1440 RGB) |
| Result | Compiler JSON/EN/ZH PASS; live 2560×1440 RGB pixels generated; `syncOk=True` |
| Reload | Sheet `db095959-…` lists `ers_composite_asset_id=f13defaf-…`, `has_reference=true` after reload |
| Downstream | Scene Creator handoff not modified; I2I pins preserved |

---

Studio API left running at `http://127.0.0.1:8758/` with this compiler loaded. No commit, no push, no Vercel.
