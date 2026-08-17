# Qwen I2I + ERS Phase 2 Closure Report

**Status:** GOVERNING for this Phase 2 closure (2026-08-16)  
**Agent:** independent Cursor closure (do not treat DeepSeek’s PARTIAL PASS as certified)  
**Git:** no commit, no push, no deploy

---

## Final verdict

**PARTIAL PASS — ERS CONSISTENCY NOT CERTIFIED; VISUAL CANON VLM UNAVAILABLE**

Hard gate **did not fire**: Schnick job `588fc5ac-252e-4b12-89d2-0d7a35dd183d` consumed source pixels in Comfy (`LoadImage` → `TextEncodeQwenImageEdit`). This is **not** `REJECTED — ERS REMAINS TEXT-ONLY`.

Pixel review **failed** the acceptance question: the 2K Qwen I2I sheet is not the Schnick Coffee set. Live Visual Canon did not produce structured architecture (Kie TLS to `gemini-3-pro`). Tests and contracts hold. Bounded repairs did not recover café geometry; ERS v2 was not created.

---

## 1. Initial state

| Item | Value |
|---|---|
| Branch | `beta` |
| HEAD | `3980b6051269514b5b3c38eb066c005a1a5fe850` (`docs(scene-creator): record hosted grounding deployment closure`) |
| Working tree | Dirty. Phase 2 files uncommitted on disk. Concurrent dirty work **protected** (not stashed, reset, reverted, committed, pushed, or deployed). |
| Live data DB | `C:\AdeptFilmWorks\AIVideoStudio\data\studio.db` |

**Schnick Coffee (reused; no new project):**

| Role | ID |
|---|---|
| Project | `2347bf46-3762-4763-86c5-4a6032522278` |
| Spatial Map | `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` |
| Sheet | `db095959-5678-4f11-98d1-e93e0810d119` |
| Original source | `4d3062e8-8c30-4230-8376-bc25d1d4f735` (`Korri Coffee House.png`, Comfy name `studio/atlas_shot.png`) |
| Atlas | `caa72759-d965-41f9-b1d5-77cdcf9b9614` |
| Plan composite `f7f9a822-...` | missing from DB |
| Product Qwen I2I job | `588fc5ac-252e-4b12-89d2-0d7a35dd183d` **done** |
| Comfy prompt | `496c9b44-d7f6-4259-91b8-cb6c09d17224` |
| Library ERS asset | `c1b26209-0480-432e-8328-b1cb8e10bc85` (2560×1440) |

**Concurrent work left untouched:** Avatar Studio, Scene Creator / Nano Banana / region-edit, Timeline leftovers, Beta backend scripts, `studio-api/app/main.py` thread-hook, `.runtime` probes, Scene Creator certification docs.

---

## 2. Independent implementation audit

| Claim | Verdict |
|---|---|
| `build_qwen_2512_ref_workflow` wires `LoadImage` 5 → `TextEncodeQwenImageEdit` 6/7 (`image: [5,0]`) → `KSampler` pos=6 neg=7 → `VAEDecode`/`SaveImage` | **CONFIRMED** (source + live Comfy history) |
| Registry `qwen2512.ref` Certified; fingerprint matches runtime graph of job `588fc5ac` | **CONFIRMED** `sha256:cd87c8625857c081fb88eed40bb9c9535f8337ffbf5acf853d4972e82d19677d` |
| `qwen2512.ref` requires `reference_image\|source_image` | **CONFIRMED** (`workflow_execute.py`) |
| ERS Qwen path pins `forceWorkflowKey=qwen2512.ref` + `sourceAssetId` | **CONFIRMED** |
| ERS is no longer T2I on the Qwen path | **CONFIRMED** for enqueue/runtime. Residual: `_choose_operation` still documents “ERS is always T2I” and is unused. |
| GPT path still calls `_force_ers_honest_t2i`; pixels via `input_urls` | **CONFIRMED** (hosted exception; not broadened) |
| `source_pixels = grounding_ids[0]` prefers original then Atlas | **CONFIRMED**. Live `LoadImage` was the **original café photo** (`studio/atlas_shot.png` = `4d3062e8-...`). Prompt text claimed Atlas `caa72759-...` as pixel authority. Visual Canon router requires Atlas (`SOURCE_MISMATCH` otherwise). |
| Negative encode also consumes the source image | **CONFIRMED** wiring. Live 20-step job with image on both encodes produced a dark void, not a cancelled-but-readable café. Replacing negative with `CLIPTextEncode` produced **pure black** and was **reverted**. |
| Frontend `isQwenT2IReady` vs `isQwenI2IReady` (`metadata.supports` must include `"reference"`) | **CONFIRMED** |
| Scene Creator Qwen reference was not globally enabled | **CONFIRMED**. `REGION_EDIT_FAMILY_CAPS["qwen2512"]` remains Unsupported. `list_local_generator_families` still special-cases Illustrious for references. `GENERATE_WORKFLOW["qwen2512"]` remains `qwen2512.txt2img`. |
| FLUX / Nano-Banana / generic Image Core cannot silently satisfy ERS | **CONFIRMED** (handler + `test_ers_generate_blocks_t2i_only_local_family`) |
| Panel strategy is one whole-sheet Image Core job (`direction="sheet"`) | **CONFIRMED** |
| Visual Canon reuses `chat_kie`, persists `ProjectTraitRow` (`environment_visual_canon`), creator corrections outrank inference, staleness = fingerprint mismatch | **CONFIRMED** in source + deterministic tests. Live VLM **unavailable**. |
| DeepSeek live output is a consistent Schnick ERS | **REJECTED** (pixel review) |

---

## 3. Qwen I2I graph proof

Independent Comfy history for prompt `496c9b44-d7f6-4259-91b8-cb6c09d17224` (job `588fc5ac`):

1. `LoadImage.image` = `studio/atlas_shot.png` (real file; original café photo, not the Atlas floor plan).
2. Positive `TextEncodeQwenImageEdit.image = ["5", 0]`, `vae=["3",0]`, `clip=["2",0]`.
3. Image is encoded into Qwen Image Edit conditioning (`reference_latents` path as implemented by that node).
4. Positive prompt is the whole-sheet ERS compile (~5.6k chars, `purpose=environment_reference_sheet`).
5. Negative is also `TextEncodeQwenImageEdit` with the same image. It did **not** prove to “cancel” reference into a readable café; output was a dark field with yellow scribbles. A later `CLIPTextEncode` negative recert was worse (black) and was reverted.
6. `KSampler` model=`["4",0]`, positive=`["6",0]`, negative=`["7",0]`, latent=`["8",0]` (`EmptyLatentImage`, denoise 1.0).
7. `VAEDecode` → `SaveImage` (`studio/2347bf46_imagegen_00281_.png`).
8. `graph_hash` matched certified `qwen2512.ref`. Current disk builder still hashes to the same value after the negative revert.

Job metadata: 2560×1440, purpose `environment_reference_sheet`, `referenceGrounding.mode=pixel`, `resolvedWorkflowKey=qwen2512.ref`. `visualCanon` was **None** on that job. Provenance `settings.checkpoint` still shows leftover `flux1-kontext-dev.safetensors` while the Comfy graph loaded Qwen — label debt, not a silent Comfy fallback.

Evidence: `docs/release-gate/ers/artifacts-phase2/graph_proof.json`

**Hard gate: PASS — pixels reached the encoder.**

---

## 4. Capability / readiness truth

- `isQwenT2IReady`: Qwen provider ready.
- `isQwenI2IReady`: ready **and** `metadata.supports` contains `"reference"`.
- ERS Qwen eligibility uses I2I, not T2I-alone (`ersGenerator.eligibility.test.ts`).
- Registry lists `supportsReferences` / reference intents on `qwen2512.ref`.
- Scene Creator `qwen2512` region-edit remains **Unsupported**. Qwen ERS I2I ≠ global Scene Creator Qwen reference.

---

## 5. ERS provider contract

ERS requires image input + instruction.

| Provider | Behavior |
|---|---|
| Qwen I2I | Required local path: `qwen2512.ref` + source asset |
| GPT Image 2 | Explicit hosted exception via `input_urls` only |
| FLUX local | Refused honestly (`RuntimeError` matching `image-to-image`) |
| Nano-Banana / generic Image Core | Not silently used as ERS T2I substitute |

Provider support was **not** broadened.

---

## 6. Visual Canon verification

Trace: request → `codirector/vision/router.py` → `analyze_environment_visual_canon` → `get_secret("kie_api_key")` → `chat_kie(gemini-3-pro)` → parse → `ProjectTraitRow` category `environment_visual_canon`.

| Check | Result |
|---|---|
| Reuses existing `chat_kie` | CONFIRMED |
| No second vision DB | CONFIRMED |
| Creator corrections outrank inference | CONFIRMED (`merge_visual_canon` test) |
| Staleness = lineage fingerprint mismatch | CONFIRMED (`canon_is_stale`) |
| Live structured canon for Schnick | **NOT PRODUCED** |

Classification of the live failure:

- **A (implementation):** HTTP 500 from `from ..spatial_map` and wrong `build_scene_intent(db, project, doc)` signature — **repaired**. Generic “vision did not complete” when `chat_kie` omitted `error` — **repaired** to surface `message` / `httpStatus`.
- **B (credentials):** Kie key **present** (length 32). Not a missing-secret failure.
- **C:** No other already-canonical Adept VLM was adopted. No new VLM installed.

After A, in-process analysis against Atlas `caa72759-...` returned `availability=unavailable`, reason `[SSL: SSLV3_ALERT_BAD_RECORD_MAC]` to Kie. Honest unavailable persisted. Fingerprint used: `a759c5d50d02741a`. Studio API `:8758` was **not** restarted to pick up the import fix; product HTTP Visual Canon was not re-probed after the repair.

Evidence: `docs/release-gate/ers/artifacts-phase2/visual_canon_live.json`

Bar/couch/windows/entrance/tables/orientation/materials were **not** live-verified because no structured canon was returned.

---

## 7. Backend tests

Executed (cwd `studio-api`; repo-root pytest cannot import `app`):

```text
studio-api\.venv\Scripts\python.exe -m pytest tests/test_qwen_i2i_ers.py tests/test_ers_image_product.py -q
```

**Measured: 22 passed, 5 warnings** (reconfirmed after negative-encode revert).

First-run defects (fixed, assertions not weakened):

1. `test_ers_generate_gpt_image2_pixel_grounding` — GPT `operationIntent` stayed T2I after `_force_ers_honest_t2i` even with `input_urls`. Restored `image.generate` when URLs attach.
2. `test_compile_ers_qwen2512_plate_stays_t2i` — Phase 1 expectation (strip source, `qwen2512.txt2img`) was wrong for Phase 2. Compile/resolve now pin `qwen2512.ref`; test renamed to `test_compile_ers_qwen2512_source_stays_i2i_not_edit`.

Staleness: `test_visual_canon_fingerprint_stable_and_staleness` (`canon_is_stale`). Schnick identity was not mutated for this proof.

---

## 8. Frontend tests / build

```text
npx --prefix studio-web vitest run src/components/CoDirector/SpatialMap/ersGenerator.eligibility.test.ts src/components/CoDirector/SpatialMap/useErsGeneration.test.ts
npx --prefix studio-web tsc -b --pretty false
```

**Measured: 7 passed.** `tsc -b` **exit 0**.

Cursor did not repair `studio-web`. No Beta `:8760` rebuild. No Vercel deploy.

---

## 9. Live vision result

| Field | Value |
|---|---|
| Provider / model | Existing Kie `chat_kie` / `gemini-3-pro` |
| Credentials | Present |
| Result | `availability=unavailable` |
| Reason | TLS `SSLV3_ALERT_BAD_RECORD_MAC` |
| Fingerprint | `a759c5d50d02741a` (lineage input); stored `fingerprint` empty because unavailable |
| Key invariants | None (no structured geometry) |
| Persistence | `project_traits.environment_visual_canon` key = map `6bc36d92-...` |

No fake vision success.

---

## 10. Schnick visual consistency review

Acceptance: **could these views be the same physical set?** Not semantic similarity.

| View | Asset | Pixels | Observation |
|---|---|---|---|
| Source | `4d3062e8-...` | 1536×1024 | Korri’s Coffee House: sofa left, long bar center, tables right, EXIT/windows left, brick + “COFFEE. FOCUS. CREATE.” right, industrial ceiling |
| Atlas | `caa72759-...` | 1280×1280 | Top-down multi-room **light-wood** floor plan. Different building than the photo |
| Product Qwen I2I ERS | `c1b26209-...` | 2560×1440 | Dark circular void, olive noise, neon yellow scribbles. Not a café. Not a 9-panel sheet |

Continuity checks (bar, couch, windows, entrance, tables, orientation, materials, no redesign): **FAIL** on the product ERS. Atlas already fails same-set vs source.

Bounded recerts (same project, no new project):

| Run | Prompt | Result |
|---|---|---|
| `e38c7ad9-7285-432c-b928-a9f99ba54b31` | 50 steps / cfg 4.0 / `CLIPTextEncode` negative | Pure black 2560×1440. **Reverted** |
| `6c88b866-399d-43d8-a42d-33beb61d17f4` | Native 1328, short “preserve this café” prompt, dual `TextEncodeQwenImageEdit` | Near-black mean RGB (1,1,0) |

**FAIL — ERS CONSISTENCY NOT CERTIFIED.**

Root cause (proven enough to stop, not to redesign): whole-sheet 9-panel prompt + `EmptyLatentImage` denoise 1.0 + original-vs-Atlas mismatch + missing canon. Per-panel ERS v2 was not created.

Previews: `docs/release-gate/ers/artifacts-phase2/{source,atlas,ers}_preview.jpg`  
Record: `docs/release-gate/ers/artifacts-phase2/visual_consistency.json`

---

## 11. Lineage / persistence / staleness proof

```text
original 4d3062e8 (LoadImage studio/atlas_shot.png)
+ Atlas caa72759 (prompt/lineage; Visual Canon requires this id)
→ compile (qwen2512.ref, sourceAssetId = original first)
→ job 588fc5ac / Comfy 496c9b44
→ Library c1b26209 (tag codirector_ers_*_sheet, parent 4d3062e8)
→ Scene Creator resolve_ers_for_sheet(persist_runtime=False)
   package 0104e6aa-3492-412a-9176-5a0c4c29bc0c
   atlas caa72759
   composite c1b26209
   directional N/E/S/W all null
```

Sheet HTTP status remains `views_pending`. Package identity and Library binding **resolve**. Pixel content of the composite is not a usable ERS.

Staleness contract: deterministic tests only. Live Schnick map/sheet/source IDs were not rewritten.

---

## 12. Regression proof

Spot-check of Phase 2 diffs vs neighboring surfaces:

| Surface | Phase 2 impact |
|---|---|
| Scene Creator Production Grounding | Not edited in this closure |
| Scene Creator Qwen rules | `qwen2512` region-edit still Unsupported; generate key still `qwen2512.txt2img` |
| Character / Prop / Timeline / Add | Not in Phase 2 file set; concurrent dirty files left intact |
| Spatial Map persistence | Unchanged category `spatial_ers` |
| ERS Library identity | Product asset stayed on Schnick project |
| Scene Creator handoff | Still resolves package + composite id |

**Qwen ERS I2I ≠ global Qwen reference support** — remains separate.

---

## 13. Repairs made by Cursor

DeepSeek already had the Phase 2 architecture on disk. Cursor repairs (bounded, uncommitted):

| Defect | Root cause | Files | Verification |
|---|---|---|---|
| GPT pixel jobs labeled T2I | `_force_ers_honest_t2i` overwrote intent after `input_urls` | `ers_generate.py` | `test_ers_generate_gpt_image2_pixel_grounding` |
| Unpinned Qwen ERS compile stayed T2I | resolve/compile used `.txt2img` | `image_product/compile.py`, `resolve.py`; test rewrite in `test_ers_image_product.py` | `test_compile_ers_qwen2512_source_stays_i2i_not_edit` |
| I2I preamble omitted visual authority | `has_source_image` tied to GPT exemplars | `ers_compiler.py` | compile tests |
| Visual Canon HTTP 500 | `from ..spatial_map` | `vision/router.py` | import path; live still TLS-blocked |
| `build_scene_intent` TypeError | wrong signature | `vision/router.py` → `coerce_scene_intent` | in-process analyze no longer TypeError |
| Opaque VLM failure | `chat_kie` HTTP errors lack `error` | `visual_canon.py` | live reason is TLS string |
| Generic 8/20 steps and 1.0/3.5 cfg on Qwen ref | Image Core defaults | `workflow_execute.py` | code; product job `588fc5ac` still ran 20/3.5 because API was not restarted |
| CLIPTextEncode negative | hypothesized inversion | `qwen_image_2512.py` then **reverted** | recert `e38c7ad9` black; graph unit test restored to `TextEncodeQwenImageEdit` |

**Not repaired (needs architecture, stopped):** whole-sheet I2I that actually preserves Schnick geometry; original-vs-Atlas same-set; live Kie TLS; leftover `flux1-kontext-dev` checkpoint label in Image Core settings.

---

## 14. Diff integrity

**DeepSeek (already on disk before this closure):**

- `studio-api/app/workflows/qwen_image_2512.py` — `build_qwen_2512_ref_workflow`
- `studio-api/app/image_runtime/workflow_execute.py` — `qwen2512.ref` dispatch
- `config/image-workflows/certified-registry.json` — `qwen2512.ref` Certified entry
- `studio-api/app/image_product/compile.py`, `resolve.py`
- `studio-api/app/storyboard_jobs.py`
- `studio-api/app/codirector/capabilities/handlers/ers_generate.py`
- `studio-api/app/codirector/knowledgebase/ers_compiler.py`
- `studio-api/app/codirector/vision/router.py`
- `studio-api/app/codirector/vision/visual_canon.py` (new)
- `studio-web/src/components/CoDirector/SpatialMap/ersGenerator.ts`, `useErsGeneration.ts`, `ERSGenerationMonitor.tsx`
- Tests: `studio-api/tests/test_qwen_i2i_ers.py` (untracked), `test_ers_image_product.py`, `ersGenerator.eligibility.test.ts`, `useErsGeneration.test.ts`

**Cursor (this closure, still uncommitted):** bounded edits inside the files above (GPT intent, compile pin, compiler preamble, vision import/error, Qwen default steps/cfg, negative-encode attempt + revert). New governing report + artifacts under `docs/release-gate/ers/`.

**Concurrent work remaining intact:** Avatar Studio, Scene Creator generation/region-edit, Timeline, Beta backend scripts, `main.py`, `.runtime/*`.

**Runtime mutations on Schnick:**

- Persisted honest-unavailable Visual Canon trait for map `6bc36d92-...`
- Direct Comfy submits `e38c7ad9-...` and `6c88b866-...` (not Library / not sheet persist)
- No new project. No product Image Core re-enqueue after API-side repairs (API not restarted)

**Tests run:** pytest **22 passed**; vitest **7 passed**; `tsc -b` **exit 0**

**Restarts:** none of Studio API, Beta web, or Vercel. Comfy `:8188` reused.

**Krea Phase 1:** not touched.

---

## 15. Remaining limitations

1. **Pixel ERS is not Schnick Coffee.** Product 2K sheet is an abstract void. Native 1328 smoke was near-black. Consistency not certified.
2. **Visual Canon live VLM unavailable** (Kie TLS). No structured bar/couch/window canon. Honest `unavailable` only.
3. **Authority split:** LoadImage used the original photo; Visual Canon requires Atlas; Atlas is a different building than the photo.
4. **Whole-sheet strategy** remains one Image Core job. Per-panel generation would be ERS v2 (out of scope).
5. **Studio API `:8758` was not restarted** after vision/compile repairs; live HTTP Visual Canon was not re-proven on the product process.
6. **`_choose_operation` leftover T2I comments**; unused.
7. **`DEFAULT_WORKFLOW_REGISTRY` does not list `qwen2512.ref`** (certified-registry does). Direct `queue_prompt(..., workflow_key="qwen2512.ref")` is not the product path.
8. Image Core provenance may still label `checkpoint=flux1-kontext-dev.safetensors` on Qwen jobs (settings leftover; Comfy graph was Qwen).
9. Sheet stays `views_pending`; directional assets null. Handoff resolves the failed composite.
10. No hosted/Vercel verification (explicitly out of scope). No Beta UI rebuild.

---

## Source / Canon / Job / Visual / Downstream (Phase P)

### Source

- Original `4d3062e8-8c30-4230-8376-bc25d1d4f735` (1536×1024)
- Atlas `caa72759-d965-41f9-b1d5-77cdcf9b9614` (1280×1280)

### Visual Canon

- Provider/model: Kie `gemini-3-pro`
- Result: unavailable (TLS)
- Fingerprint input: `a759c5d50d02741a`
- Key invariants: none

### Qwen I2I job (product)

- Job `588fc5ac-252e-4b12-89d2-0d7a35dd183d`
- Comfy `496c9b44-d7f6-4259-91b8-cb6c09d17224`
- Source image path: `studio/atlas_shot.png` = original café
- Graph: LoadImage → TextEncodeQwenImageEdit ×2 → KSampler → VAEDecode
- Steps 20 / cfg 3.5 / 2560×1440
- Result asset `c1b26209-0480-432e-8328-b1cb8e10bc85`

### Visual result

- FAIL — not the same physical set

### Downstream

- ERS package `0104e6aa-3492-412a-9176-5a0c4c29bc0c`
- Library binding: asset `c1b26209-...` on Schnick
- Scene Creator handoff still resolves (composite id present; content unusable as a set bible)

---

## Final verdict

**PARTIAL PASS — ERS CONSISTENCY NOT CERTIFIED; VISUAL CANON VLM UNAVAILABLE**
