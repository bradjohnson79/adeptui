# Spatial Reconstruction Compiler — Certification Report

Governing document for Environment Image → Perception → Reconstruction Packet → Geometry Sanity → Structural Guide → Dual-Condition Atlas → Visual Gate → Spatial Map.

Supersedes the old prompt-only I2I path documented in:

`docs/release-gate/local-image-accel/ATLAS_SHOT_GENERATION_CERTIFICATION_REPORT.md` (historical).

## Status

**HISTORICAL for visual generation.** The 2026-08-25 Direct Qwen A/B is the current governing document:

`docs/release-gate/spatial-map/SPATIAL_MAP_DIRECT_QWEN_AB_TEST.md`

This compiler path remains the default `atlas.generate` route only because no winner was promoted. Forensics named the first malformed visual stage as Plus dual-ref with the 96×480 guide as `image1`. Route A (direct one-image Edit) did not produce a roofless Atlas either. Both-fail → stop. Do not cite this file as a certified visual path.

## Verdict

`NO-GO — SPATIAL MAP ATLAS QUALITY / PERFORMANCE / ADVANCED LOOK NOT CERTIFIED`

Quality, performance, and Look are independent gates. Reconstruction compile still works. Live SenseNova corridor Atlases still fail the blocking visual gate (`FAIL_TOP_DOWN`). Planning-plate knobs left the 6–11 minute 50-step / 1280² class for a single attempt, but no quality winner exists, so performance is not certified. Advanced · Look is wired and persisted; Look A/B reused the same packet/guide and still failed top-down. Comfy MCP was unavailable, so final workflow certification is held. The GO sentence is not earned.

## Branch

- Branch: `feat/character-creator-final-closure`
- HEAD at report time: `b6156455e643d5fa430784b3130756f2d8038651` plus uncommitted compiler work
- Project: SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`
- Corridor source: `1211dd83-e3f6-4d17-bf2b-669ec5961418` (`codirector_image_generate_d5d616be`)
- Local review: Vite `http://127.0.0.1:5173/`, Studio API `http://127.0.0.1:8758/` (PID 45076 after API-only recycle)
- Comfy Desktop `:8188` left running (reused)

## Responsibility split (implemented)

```
perception determines structure
→ geometry sanity validation
→ structural guide encodes topology
→ image model renders the Atlas
→ visual gate vs source AND guide
→ assignment
```

`atlas.generate` is the orchestrator for a perspective location image. `atlas.assign` stays assign-only (Option 2 + confident perspective still auto-routes into this compiler). Character Creator Qwen 2509 knobs and Prop routing were not changed.

## Live measurements

### Corridor compile (SenseNova)

- Layout: **3 × 15** cells, `environmentType=corridor`
- Scale: **`provisional`**, confidence **0.2** (no scale anchor; not claimed as 3 m × 15 m)
- Sanity: **PASS**
- Guide asset: `73ff0b70-cca6-411e-b452-258c5ed08014` (and later job guides `3649862c-…`, `bb4e40da-…`)
- `assignedToMap`: **false** until visual gate PASS
- Evidence: `docs/release-gate/spatial-map/evidence/SOURCE_corridor.png`, `GUIDE_corridor.png`, `live_corridor_reconstruction.json`

### Dual-condition Comfy jobs

| Job | Workflow | Slot order | Status | Gate |
|---|---|---|---|---|
| `59fbca89-…` | `qwen2512.atlas` | `guide_source` | done | `FAIL_TOP_DOWN` |
| `e43d78ba-…` | `qwen2512.atlas` | `guide_source` | done | `FAIL_TOP_DOWN` |

Fixture / live pixel scores (same for both):

| topology | sourceIdentity | topDown | readability | both-quality bar |
|---|---|---|---|---|
| 0.15 | 0.85 | 0.1 | 0.181 | **false** |

Winning slot order: **not locked**. Default candidate remains `guide_source`. Live Comfy node `TextEncodeQwenImageEditPlus` accepts optional `image1` / `image2` / `image3` (`evidence/qwen2512_atlas_comfy_slots.json`). A beautiful or source-like result that is not overhead **fails**. These candidates failed.

Evidence: `ATLAS_59fbca89.png`, `ATLAS_e43d78ba.png`, `live_atlas_bakeoff.json`

### Playwright

- Empty-state Option 1/2 copy: **1 passed** (5.0s) — reconstruction wording present
- Option 1 Library: reporter **1 passed (6.4m)** — **REJECTED as compiler E2E**. Map background `8de31b8c-…` (`codirector_atlas_4ca92ecb`) predates the `qwen2512.atlas` jobs (those jobs were created at 03:09:04Z). The spec only required “some background that is not the corridor,” so a stale prior Atlas satisfied it.
- Follow-up: Option 1 Library now requires a **new** `atlas.generate` execution, that execution’s result asset, visual-gate PASS, and matching map metrics. `clearAtlas` now asserts the prior Atlas is actually removed. The hardened spec was **not re-run live** in this pass (would fail `FAIL_TOP_DOWN` — that is the honest result).

## Independent review

| Reviewer | Verdict |
|---|---|
| Atlas / Comfy MCP auditor (prior compiler pass) | PASS — dual-condition graph, slot orders, gate questions, ERS / `qwen2512.ref` separation |
| Perception / geometry auditor (prior) | BLOCK |
| Kimi 2.7 auditor (this addendum) | BLOCK — quality still `FAIL_TOP_DOWN`; residency not accepted on resident-after-Phase-A timings; Comfy MCP / hardened Library held |
| GLM 5.2 peer (this addendum) | PASS (review-only) — READY FOR PRIMARY REVIEW. Agrees the mission stays NO-GO. |
| Kimi K3 peer (this addendum) | PASS (review-only) — READY FOR PRIMARY REVIEW. Agrees the mission stays NO-GO. |

Repairs after those BLOCK findings (in tree, not yet re-audited):

- `adoptAtlasExecution` no longer applies an Atlas; the gated `useEffect` is the generate-assign path.
- Chat `applyCompletedAtlas` validates first and throws on fail (no Spatial Map tab navigation).
- Vision notes write to `packet.perceptionNotes`, not `sceneIntent`.
- `accepted_map_fields` requires sanity PASS and annotates provisional meters (`layoutNote`, `providerHonesty=approximate_translation`).
- Vacuous unknown-region test replaced with a real feature-type + evidence assert.

## Unit / API measured

| Suite | Result |
|---|---|
| `test_spatial_reconstruction_compiler.py` + `test_qwen2512_atlas_workflow.py` | **16 passed** |
| `test_atlas_generate_i2i.py` + `test_atlas_ers_store.py` | 14 passed (source path `qwen2512.atlas`) |
| `test_cc_v2.py` + `test_prop_creator_generator_parity.py` | 62 passed |
| Spatial Map `SpatialMapPanel.test.ts` + `AgentWorkSurface.test.ts` | **33 passed** |

Permanent reject fixture: corridor + grid overlay fails `FAIL_TOP_DOWN` in unit tests.

## E2E TRACE

| Stage | Status |
|---|---|
| User action | PASS (empty-state copy) / Library click observed in Playwright |
| Frontend | PASS wiring (gate before assign; generate-path bypasses closed) |
| API | PASS — `atlas.generate` enqueued `qwen2512.atlas` with source + guide |
| Backend | PASS — packet + sanity + guide persist |
| Persistence | PASS — trait packet + `spatial_structural_guide` parented to source |
| Runtime | PASS job ran on Comfy; FAIL quality (not overhead) |
| Result | Gate **FAIL_TOP_DOWN** — correct reject |
| Reload | N/A (no accepted Atlas from this compiler run) |
| Downstream | Existing characters/props/cameras/ERS pipeline unchanged |

## Limitations

- `qwen2512.atlas` is Draft. Empty fingerprints. Not Certified.
- Live Plus dual-image render did not produce a usable roofless Atlas on this corridor. Diagnostic retries are implemented; they were not fully exhausted as a certified loop in this pass.
- GPT Image 2 cannot consume a structural guide as a first-class second conditioning; with a live DB it requires a guide URL or refuses.
- Perception models are optional enrichment. Missing models do not invent depth.
- VGGT is not installed (license OMIT).
- Playwright Library reporter-green is not compiler certification. The spec was hardened so a stale Atlas cannot pass; live re-run is still required after a quality PASS.

## Manual review

1. Open `http://127.0.0.1:5173/` on SenseNova Integration Lab.
2. Option 1 should describe analyze → estimate → 1 m layout → roofless Atlas.
3. Image Engine / Advanced Look stay on Option 1 only.
4. A corridor photo plus a grid, or a still-perspective generate, must not become the Spatial Map.

## Remaining for GO

1. A SenseNova corridor Atlas that clears topology + source identity + top-down + readability on a live `qwen2512.atlas` (or a governed FLUX Atlas ControlNet graph — not present).
2. Hardened Option 1 Library **and** Upload Playwright: new `atlas.generate`, gate PASS, metrics written, survive reload.
3. True unloaded COLD vs WARM Atlas residency numbers before accepting `spatial_atlas` + `qwen2512`. Do not treat resident-after-Phase-A 11s / 6.5s as unloaded cold.
4. Comfy MCP inspection of the live `:8188` atlas graph (held — MCP not available this pass).
5. Re-audit after a quality PASS. This addendum’s Kimi 2.7 auditor **BLOCK** stands (quality / unloaded COLD / MCP / hardened Library). GLM 5.2 and Kimi K3 already **PASS** as review-only peers and agree the mission stays NO-GO. The stale `comfyPrompts: 4` trait increment is annotated in `atlas_perf_trace.json` (`uniqueComfyPromptIds: 3`).
6. Track compiler source in Git (Clean-Clone Law). Do not commit unless asked.

---

## Addendum — Spatial Atlas Performance + Advanced Look

Mission addendum. Does not replace the compiler findings above.

### Phase A — one-click count (settled before any knob change)

Evidence: `docs/release-gate/spatial-map/evidence/atlas_perf_trace.json`

Click `atlasclick_192bfc72ae3d4915` on SenseNova corridor `1211dd83-…` with `RETRY_BUDGET = 3`:

| Count | Measured |
|---|---|
| Compiler executions | **3** |
| Unique Comfy prompts | **3** (`7e72ca35-…`, `9a3b2d28-…`, `4af7450a-…`) |
| Retry count | **2** |
| Wall | **656.593 s** (~11 min) |

The 4th `comfyPrompts` increment on the live trait was a double-count of attempt 3 (same prompt recorded twice). Unique prompt IDs are 3. That increment is now unique-by-`promptId`.

Attempt 1 rebuilt packet + guide (`perceive` 77.0 ms, `guideRaster` 10.8 ms). Attempts 2 and 3 reused both (`rebuiltPacket=false`). All three gates: `FAIL_TOP_DOWN`. Device: NVIDIA GeForce RTX 5090, CUDA, no silent CPU fallback. Compiler cost is not the multi-minute clock. The clock is **three chained 50-step / 1280² Atlas Comfy jobs**.

### Phase B — reuse and honest progress

Retries and Look-only rerenders pass `reuse_execution_id` / `reuse_packet_id` / `reuse_guide_asset_id`. Packet persist now writes both `executionId` and `packetId` keys. Creator copy: `Generating Atlas — attempt N of 3` / `Retrying top-down reconstruction`. Stall hint after 180s elapsed + 90s with no progress. Live reuse: Phase A attempts 2–3, Phase C/D bake-off, and Look A/B all recorded `rebuiltGuide=false`.

### Phase C — atlas-only planning plate

Atlas-only (not `qwen_image_2512.py`, not CC 2509, not Prop):

- Working size: long side **1024** (dispatcher no longer leaks cinematic 16:9 / 1920×1080 into Atlas)
- Balanced steps: **28** (Low 16 / High 36). Generic `{8, 20, 50}` no longer remaps Atlas to cinematic 50.
- Negative encode: **text-only `CLIPTextEncode`**. Dual-image negative remains available for diagnostics.
- Slot bake-off: `guide_source` and `source_guide` both `FAIL_TOP_DOWN`
- FLUX: ControlNet + FLUX nodes exist on Desktop Comfy; **no governed `flux.atlas` graph**. Recorded `E2E BLOCKED — FLUX not installed as a governed Atlas ControlNet renderer`.

Evidence: `docs/release-gate/spatial-map/evidence/atlas_bakeoff_phase_c.json`

| Run | Wall | Gate |
|---|---|---|
| COLD_guide_source `80f0d6da-…` / prompt `b39611fe-…` | 11.350 s | FAIL_TOP_DOWN |
| WARM_guide_source `adef8396-…` / prompt `1b89e746-…` | 6.508 s | FAIL_TOP_DOWN |
| WARM_source_guide `16f99ad9-…` / prompt `694f2a92-…` | 69.848 s | FAIL_TOP_DOWN |

The 11.35s / 6.508s pair is **resident-after-Phase-A**, not an unloaded COLD. Qwen was already in VRAM (~30 GB used during Phase A). Do not accept `spatial_atlas` residency on those numbers. Atlas jobs still ride certified `codirector_still` residency. `spatial_atlas` + `qwen2512` stays **uncertified**.

A single 28-step / 1024² attempt can sit in the ~70 s class (`source_guide` and Look A/B). That is better than 4+ minutes × 3 at 50 / 1280². It is not a quality winner.

### Phase D — Advanced · Look

`SpatialAtlasLook` is the one contract (UI + Co-Director). Advanced accordion shows Style / Detail / Source Appearance; Standard also Presentation / Lighting / Show 1 m Grid. Empty LoRA list is no longer the default Look surface. Look persists on the map document. GPT Image 2 marks Source Appearance and Grid unsupported. Grid overlay is applied only after gate PASS (never on a rejected photo).

Look A/B on the same packet `sr_ef7120b2ec5c` + guide `f7afc120-…`:

| Preset | Wall | Reused | Gate |
|---|---|---|---|
| A Auto / Balanced / Match Source `e6eb0cbc-…` | 74.009 s | yes | FAIL_TOP_DOWN |
| B Architectural / Balanced / Bright Planning `c89cc83e-…` | 74.059 s | yes | FAIL_TOP_DOWN |

Evidence: `docs/release-gate/spatial-map/evidence/atlas_look_ab.json`. Same topology cannot be certified because neither result is an overhead Atlas. Presentation difference is therefore not a quality A/B.

Playwright (live Vite `:5173` + API `:8758`): Advanced Look persist via API + reload **1 passed**. Option 2 Upload (no regenerate) **1 passed** (7.9s together). Empty-state Option 1/2 was **flaky** (panel not visible on first attempt). Hardened Option 1 Library remains blocked on `FAIL_TOP_DOWN` and was not treated as compiler E2E.

### Tests measured this addendum

| Suite | Result |
|---|---|
| `test_spatial_reconstruction_compiler.py` + `test_qwen2512_atlas_workflow.py` + `test_image_acceleration_registry.py` | **31 passed** |
| `test_cc_v2.py` + `test_prop_creator_generator_parity.py` | **62 passed** |
| Spatial Map + Look Vitest | **17 passed** |
| Playwright Look persist + Option 2 Upload | **2 passed (7.9s)**; empty-state **flaky** |

### Runtime

- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (recycled after Python changes; Desktop Comfy `:8188` left running)
- Project: SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`
- Branch: `feat/character-creator-final-closure` @ `b6156455e643d5fa430784b3130756f2d8038651` plus uncommitted performance + Look work

### E2E TRACE (this addendum)

| Stage | Status |
|---|---|
| User action | PASS — one-click count + Look persist |
| Frontend | PASS — Look wired; retry reuse ids; stall copy |
| API | PASS — planning 1024 / 28 / text-only negative |
| Backend | PASS — reuse packet/guide |
| Persistence | PASS — Look + packetId/guideAssetId on map |
| Runtime | PASS jobs on RTX 5090; FAIL quality |
| Result | Gate **FAIL_TOP_DOWN** on every live corridor Atlas |
| Reload | PASS Look persist; N/A accepted Atlas |
| Downstream | CC 2509 / Prop unchanged (62 passed) |
