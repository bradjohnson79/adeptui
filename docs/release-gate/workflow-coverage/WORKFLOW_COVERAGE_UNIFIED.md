# Workflow Coverage Unified Report

Governing document for **Adept UI Generation Workflow Coverage** (scoped certification).

**This GO certifies only bucket A.** It does not certify the dirty branch, Character Creator, Scene AUTO, or ERS AUTO.

`EXCLUSION — CHARACTER CREATOR REMAINS UNCERTIFIED`

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `1c865606571664ed3c06dffdf468f643cd9a3da8` (`1c86560`) — clean commit; working tree is mixed  
**Date:** 2026-08-22  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (no `POST /api/projects`)  
**Live Studio API:** `http://127.0.0.1:8758/` **200**, process started `2026-08-22T18:06:03Z`  
**Creator UI:** `http://127.0.0.1:5173/` (Vite current source). `:8760` was not started and is retired from the normal path.  
**Comfy:** `http://127.0.0.1:8188/` ready — `cuda:0 NVIDIA GeForce RTX 5090`. Queue running=0 pending=0 after reconfirm.

`apiRevision` still prints `1c86560` because these edits are uncommitted. Load was proven by live compile: `workflowKey=zimage.ref_edit`, `operation=image.edit`, `sourceAssetId=362fddcb-502e-40ff-a8c8-7a70cf5fa493`.

**Do not commit. Do not reset/discard owner work. Do not edit Character Creator.**

---

## Dirty-tree classification (HEAD `1c86560` vs working tree)

HEAD is clean. The working tree is mixed sanitation / Character Creator Final Closure / Spatial Map / coverage. This GO may describe **only bucket A** as certified.

### A — Generation workflow coverage (certified set)

These are the only files this GO may describe as certified:

**Shared routing**

- `studio-api/app/image_core/capability.py` — `resolve_family_image_route` / family T2I+I2I table
- `studio-api/app/image_product/compile.py` — CIS-like purposes stamp I2I (`sourceAssetId` + real key). File also contains pre-existing CRS / four-view helpers; those purposes are skipped and are **not** certified here.
- `studio-api/app/image_studio/contracts.py` — compile-preview stamps `IMAGE_T2I` / `IMAGE_I2I`

**Prop**

- `studio-api/app/prop_creator/generation.py`
- `studio-api/app/prop_creator/service.py`

**Brand**

- `studio-api/app/generation_tools/ops.py`
- `studio-web/src/components/GenerationTools/BrandStudioWorkspace.tsx`

**Fingerprint guard**

- `studio-api/app/image_runtime/fingerprints.py` — `zimage.txt2img` width/height volatile
- `config/image-workflows/workflow-fingerprints.json` — hash hunk only
- `config/image-workflows/certified-registry.json` — **mixed file.** Certified hunk is only `zimage.txt2img` `graphHash` / `builderHash` (`sha256:352f7ca2…` / `sha256:31313e7a…`). The rest of the +376 (Draft CRS / `qwen_edit_2509` insertions) is pre-existing dirty work and is **not** certified.

**CIS / PoseCraft**

- `studio-web/src/components/image-studio/CinematicImageStudio.tsx`
- `studio-web/src/components/image-studio/cisFailClose.ts`
- `studio-web/src/components/image-studio/cisFailClose.test.ts`
- `studio-web/src/components/image-studio/posecraftHandoff.ts`
- `studio-web/src/components/image-studio/posecraftHandoff.test.ts`

**Avatar / Voice / Audio honesty**

- `studio-web/src/avatar/types.ts`
- `studio-web/src/avatar/types.test.ts`
- `studio-web/src/components/AvatarStudioWorkspace.tsx`
- `studio-web/src/components/AvatarStudioCreatePanel.tsx`
- `studio-web/src/components/voiceStudio/VoiceIdentityPanel.tsx`
- `studio-web/src/components/voiceStudio/voiceIdentityRoute.ts`
- `studio-web/src/components/voiceStudio/voiceIdentityRoute.test.ts`
- `studio-web/src/components/audio-studio/AudioStudioWorkspace.tsx`
- `studio-web/src/components/audio-studio/MusicPanel.tsx`
- `studio-web/src/components/audio-studio/SfxPanel.tsx`
- `studio-web/src/components/audio-studio/AmbiencePanel.tsx`

**Tests / spec / report**

- `studio-api/tests/test_family_image_routes.py`
- `studio-api/tests/test_cis_i2i_compile.py`
- `studio-api/tests/test_brand_image_pin.py`
- `studio-api/tests/test_prop_creator_generator_parity.py`
- `studio-api/tests/test_m42_w2_image_runtime.py` — **hash / width-height guard hunk only**
- `studio-api/tests/test_library_reference_compile.py` — CIS qwen2512+refs fail-closed hunk (not CC AUTO)
- `tests/e2e/workflow-coverage/workflow-coverage-wiring.spec.ts`
- `tests/e2e/image-generator/library-refs-accordion.spec.ts` — listed in the certified set; **not re-run** this finalize (defaults to `:8760`)
- `docs/release-gate/workflow-coverage/**` (this report + measured JSON). Helper `evidence/*.py` scripts are bucket D.

**Not in the certified set (residual, disclosed):** `studio-api/app/image_product/edit_compile.py` unguarded zimage fallback at lines 188–202. Finding, not a CIS silent fallback.

### B — Character Creator (explicitly uncertified)

Left untouched this pass. Present in the dirty tree and **excluded** from the GO:

- `studio-api/app/character_identity/` (`visual_sheet.py` AUTO chooser, `crs_*`, `four_view_sheet`, api, fidelity, compose)
- `studio-api/app/codirector/tools/handlers/character_creator.py`
- `studio-api/app/codirector/capabilities/handlers/character_generate_visual_sheet.py`
- `studio-api/app/image_prompting/flux/crs_single_view.py`
- `studio-api/app/image_prompting/qwen_2512/character_sheet_grammar.py` (CC prompt compiler)
- `studio-web/src/components/character/`
- `studio-web/src/components/CoDirector/characters/`
- `docs/release-gate/character-creator/` and `docs/release-gate/character-creator-final-closure/`
- `tests/e2e/character-creator/`
- CC / CRS tests (`test_cc_*`, `test_character_*`, `test_crs_*`, `test_four_view_sheet.py`, `test_flux_crs_*`, `test_sd15_crs_control.py`, `test_visual_sheet_pack_reconcile.py`)

GLM/Kimi CC AUTO “must-fix” = this exclusion, **not** a coverage FAIL.

### C — Unrelated pre-existing dirty work

Out of scope. Includes sanitation / Spatial Map / capabilities / Co-Director execution / scene_creator / setup / production_control / queue_worker / most of `studio-web/src/api.ts` / AgentWorkSurface / MAGI / movement / timeline / env-picker / hosted-provider leftovers. Examples of modified tracked files in this bucket: `studio-api/app/capabilities/*`, `studio-api/app/codirector/execution/*`, `studio-api/app/spatial_map/*`, `studio-api/app/scene_creator/*`, `studio-api/app/setup/*`, `studio-api/app/production_control/*`, `studio-api/app/queue_worker.py`, `studio-web/src/components/CoDirector/AgentWorkSurface/*`, `studio-web/src/components/CoDirector/SpatialMap/*`.

`studio-api/app/image_product/edit_compile.py` lives here as a residual finding (unguarded zimage fallback on generic edit compile). CIS compile does not use that path for the certified I2I jobs.

### D — Generated / runtime artifacts

Not certification source: `.runtime/**`, `studio-api/.runtime/**`, beta pid/state files, screenshots, `docs/release-gate/workflow-coverage/evidence/*.py`, probe/`tmp_*` helpers, `studio-web/.runtime/`.

---

## Product law

Every generation action has a **concrete execution route**.

Image / Prop / Brand reuse:

`UI → compile_image_request / compile_edit_request → resolve_image_workflow → enqueue_imagegen_job / enqueue_edit → build_leaf_graph`

Audio / Voice / Avatar isolated GPU workers **are** the route. Do not wrap them in fake Comfy.

PoseCraft joints / snapshots stay Babylon + Library. Comfy only when the snapshot is sent to Image Generator as a picture.

---

## Live UI → registry → runtime matrix

| System | Action | Classification | Route | This-pass verdict |
| --- | --- | --- | --- | --- |
| Image Generator (CIS) | T2I Choose / All Models | ALREADY COMPLETE if Certified + ready | Comfy `*.txt2img` / `krea2.turbo_txt2img` | **GO — IMAGE GENERATOR T2I ROUTE OPERATIONAL** |
| Image Generator (CIS) | Generate with library refs | WAS MISWIRED — refs stayed T2I | Family I2I table → `zimage.ref_edit` live | **GO — IMAGE GENERATOR I2I WORKFLOW OPERATIONAL** |
| Image Generator | ImageGenPanel | Orphan, not mounted | — | Left orphan |
| Prop Creator | zimage T2I | WAS blocked by stale graphHash | `zimage.txt2img` live COMPLETED | **GO — PROP CREATOR GENERATION WORKFLOW OPERATIONAL** |
| Prop Creator | Krea T2I / FLUX–Qwen I2I | WAS MISWIRED invented `{fam}.ref_edit` / `krea2.txt2img` | `krea2.turbo_txt2img`, `flux.img2img`, `qwen2512.ref` | **GO — PROP CREATOR KEY MAPPING OPERATIONAL** (Krea remains Draft: fail-closed at enqueue) |
| Brand Studio | Generate artwork | WAS PARTIAL silent pin; button enabled with no lock | Pin `zimage.ref_edit` + lock gate + live COMPLETED | **GO — BRAND STUDIO GENERATION WORKFLOW OPERATIONAL** |
| PoseCraft | Joints / Snapshot | NON-COMFY BY DESIGN | Babylon + Library | **GO — POSECRAFT JOINTS NON-COMFY BY DESIGN** |
| PoseCraft | Send to Image Generation | WAS MISWIRED — CIS ignored handoff | CIS reads `adept.posecraft.handoff.{projectId}` | **GO — POSECRAFT HANDOFF WIRED** |
| Avatar | Generate Avatar Video | WAS MISWIRED always `PROVIDER_NOT_CERTIFIED` | Isolated InfiniteTalk/LongCat; Plan vs Generate | **GO — AVATAR HONESTY ROUTE OPERATIONAL** — `NON-COMFY BY DESIGN — REAL EXECUTION ROUTE EXISTS, CERTIFICATION BLOCKED` |
| Voice Identity Generate | Clone / Upload cards | WAS MISWIRED always Qwen Design | Design / Clone / Upload existing APIs | **GO — VOICE IDENTITY METHOD ROUTING OPERATIONAL** |
| Voice Generate Takes | IndexTTS2 | ALREADY COMPLETE (runtime-gated) | Isolated worker | **GO — VOICE TAKES NON-COMFY BY DESIGN — REAL EXECUTION ROUTE VERIFIED** |
| Audio Generate 3 Tracks / Sounds / Beds | ACE-Step / MMAudio | ALREADY COMPLETE (runtime-gated) | Isolated worker + Setup/Retry | **GO — AUDIO STUDIO NON-COMFY BY DESIGN — REAL EXECUTION ROUTE VERIFIED** |

### Family table (do not invent keys)

| Family | T2I | I2I | Notes |
| --- | --- | --- | --- |
| zimage | `zimage.txt2img` | `zimage.ref_edit` | CIS + Prop + Brand. Live proven. |
| flux | `flux.txt2img` | `flux.img2img` | Certified edit; do not invent `flux.ref_edit` |
| qwen2512 | `qwen2512.txt2img` | `qwen2512.ref` | Prop / ERS only. General CIS + refs **fail closed** (do not steal ERS) |
| qwen_edit_2509 | none | `qwen_edit_2509.edit` | I2I only |
| krea2 | `krea2.turbo_txt2img` | none | Honest PROFILE_GUIDED T2I if a picture is attached. Registry status Draft — enqueue fail-closed |
| illustrious | `illustrious.txt2img` | none | Honest PROFILE_GUIDED T2I if a picture is attached |
| sd15 | `sd15.txt2img` | `crs.sd15.control` | Not a CIS beauty I2I this pass |

Task types stamped on the **existing** compile path: `IMAGE_T2I`, `IMAGE_I2I`, `IMAGE_EDIT`, `PROP_GENERATION`, `PROP_REFERENCE_GENERATION`, `BRAND_IMAGE`, `POSE_CONDITIONED_IMAGE` (handoff only).

Live Prop key mapping reconfirm (no invented `{fam}.ref_edit`):

| Family | refs=false | refs=true |
| --- | --- | --- |
| zimage | `zimage.txt2img` | `zimage.ref_edit` |
| flux | `flux.txt2img` | `flux.img2img` |
| qwen2512 | `qwen2512.txt2img` | `qwen2512.ref` |
| krea2 | `krea2.turbo_txt2img` | PROFILE_GUIDED T2I (no I2I key) |
| illustrious | `illustrious.txt2img` | PROFILE_GUIDED T2I (no I2I key) |

---

## Live GPU proof (Schnick Coffee only)

Evidence: [`docs/release-gate/workflow-coverage/evidence/live-smokes.json`](evidence/live-smokes.json)

| Surface | Job | Workflow | Status | Library asset | File after reload |
| --- | --- | --- | --- | --- | --- |
| CIS I2I | `fd3e2519-9324-42c7-ac87-f04f2935f7bb` | `zimage.ref_edit` | done | `e9d4b5af-5779-4902-8027-b939589301a2` (`workflow_coverage_cis_i2i`) | `/api/assets/{id}/file` **200** PNG 844831 B |
| Prop T2I | `b060a3d1-e44f-4038-85b4-516f6f7edf30` | `zimage.txt2img` | done | `4f141034-53b8-4138-bb26-f2feb7e51e00` (`prop_e2e-standard-cup_c1`) | **200** PNG 886046 B |
| Brand locked edit | `dd2715cb-fb21-41fc-b883-1fc025974970` | `zimage.ref_edit` | done | `0d8bde43-a4fd-4f5b-8654-51c2b7e9bff4` (`imageedit`) | **200** PNG 950512 B |

Brand product lock for the GPU job was the Prop T2I cup `4f141034-…` (the older Coffee Cup id was missing on disk — backend fail-closed; no invented lock). Schnick `settings_json.brandStudio` currently has empty `logoAssetId` / `productAssetId`, so the Brand **UI** generate button stays disabled until a lock is chosen again.

**Finalize reconfirm (2026-08-22, no new GPU jobs):** API health ok, Comfy `cuda:0 NVIDIA GeForce RTX 5090` vramFree=11258, compile still `zimage.ref_edit` + `sourceAssetId=362fddcb-…`, all three Library assets present + file **200**, Comfy queue empty, Vite `:5173` **200**. GPU was not re-run because compile and library reload held.

Accelerator: Comfy `cuda:0 NVIDIA GeForce RTX 5090`. No CPU fallback. No Comfy zombies after the three jobs.

`zimage.txt2img` first attempt `867dcc17-…` failed `WORKFLOW_GRAPH_DRIFT` (stale certified hash `0364d2dd…` vs builder `bc3d2714…`). Repair: width/height are runtime-volatile for `zimage.txt2img`; certified `graphHash` is now `sha256:352f7ca262bc61d42f9bde28897a13ffb9452a9a5f792116c3985b36f1a82e60`. Retried Prop T2I completed.

---

## What changed this pass (bucket A only)

### Image Generator
- [`studio-api/app/image_core/capability.py`](../../../studio-api/app/image_core/capability.py) — `resolve_family_image_route` / `i2i_workflow_key`
- [`studio-api/app/image_product/compile.py`](../../../studio-api/app/image_product/compile.py) — CIS-like purposes with refs pin `sourceAssetId` + real I2I key; Scene / CRS / ERS / Prop skipped
- [`studio-api/app/image_studio/contracts.py`](../../../studio-api/app/image_studio/contracts.py) — compile-preview stamps `IMAGE_T2I` / `IMAGE_I2I`
- CIS 30s queued-no-hydrate fail-close in [`CinematicImageStudio.tsx`](../../../studio-web/src/components/image-studio/CinematicImageStudio.tsx)

### Prop Creator
- [`generation.py`](../../../studio-api/app/prop_creator/generation.py) + [`service.py`](../../../studio-api/app/prop_creator/service.py) use the same table. No invented `{fam}.ref_edit`.

### Brand Studio
- [`ops.py`](../../../studio-api/app/generation_tools/ops.py) pins `zimage.ref_edit`, `lockModelFamily`, `BRAND_IMAGE`
- Generate artwork disabled until logo or product lock (`data-testid="brand-lock-required"`)

### PoseCraft
- CIS consumes `adept.posecraft.handoff.{projectId}` and attaches the snapshot as a picture reference / `POSE_CONDITIONED_IMAGE`

### Avatar / Voice / Audio
- Avatar: **Plan Sections** vs **Generate Video**; `startImmediately: true` only if `certifiedReady`. Next-Best-Step Plan Sections gated on `canPlan` (not `canGenerate`).
- Voice Identity: Design → `voice/design/generate`; Clone → `voice/clone/generate`; Upload → `voice/upload/register`
- Audio: Setup / Retry when ACE-Step / MMAudio is not ready; no Comfy audio graphs

### Fingerprint repair (necessary for Prop T2I)
- [`fingerprints.py`](../../../studio-api/app/image_runtime/fingerprints.py) — `zimage.txt2img` width/height volatile
- [`certified-registry.json`](../../../config/image-workflows/certified-registry.json) + [`workflow-fingerprints.json`](../../../config/image-workflows/workflow-fingerprints.json) graph/builder hashes updated to the current builder (**hash hunk only** is certified)

---

## Tests (measured this finalize pass)

**API** (from `studio-api`):

`pytest tests/test_family_image_routes.py tests/test_cis_i2i_compile.py tests/test_brand_image_pin.py tests/test_prop_creator_generator_parity.py tests/test_m42_w2_image_runtime.py tests/test_library_reference_compile.py -q`

**52 passed**, 5 pydantic deprecation warnings. `test_library_reference_compile.py` was not blocked by CC dirty-tree.

**Web** (from `studio-web`):

`vitest run src/components/image-studio/cisFailClose.test.ts src/components/image-studio/posecraftHandoff.test.ts src/components/voiceStudio/voiceIdentityRoute.test.ts src/avatar/types.test.ts`

**16 passed** (4 files).

**Playwright** against Vite `:5173` + live `:8758` with `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173` (so config does not flip to retired `:8760`): [`tests/e2e/workflow-coverage/workflow-coverage-wiring.spec.ts`](../../../tests/e2e/workflow-coverage/workflow-coverage-wiring.spec.ts) — **6 passed (50.0s)** with console + required-request 500/404 capture:
1. CIS compile-preview stamps `IMAGE_I2I` and compile pins `zimage.ref_edit`
2. Brand Generate stays disabled with no logo/product lock (`brand-lock-required` visible). Schnick `brandStudio` locks are empty, so this is the no-lock branch — not a vacuous pass.
3. PoseCraft handoff is consumed by CIS as a reference
4. Avatar Plan Sections is visible and separate; Generate Video is disabled (`certifiedReady` false)
5. Voice Identity Clone and Upload routes (open Korri from Voice Studio shell, then method cards)
6. Audio Studio workspace loads; no Comfy `:8188` traffic

zimage.txt2img width/height hash guard remains in `test_m42_w2_image_runtime.py`: 1024 and 1280×720 share `graph_hash(..., workflow_key="zimage.txt2img")` with certified `352f7ca2…`. Guard present and passing; no new test added.

---

## E2E TRACE

| Step | Image I2I | Prop T2I | Brand | PoseCraft handoff | Avatar | Voice | Audio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| User action | PASS | PASS | PASS (product lock on GPU job) | PASS Playwright | PASS honesty | PASS Playwright | PASS readiness |
| Frontend | PASS | PASS | PASS lock gate (UI unlocked only with lock) | PASS | PASS Plan vs Generate | PASS method cards | PASS Setup/Retry |
| API | PASS compile `zimage.ref_edit` | PASS `zimage.txt2img` | PASS pin `zimage.ref_edit` | N/A | isolated | existing APIs | isolated |
| Backend | PASS | PASS | PASS | N/A | honesty | existing APIs | existing workers |
| Persistence | PASS asset `e9d4b5af-…` | PASS asset `4f141034-…` | PASS asset `0d8bde43-…` | sessionStorage | N/A | N/A | N/A |
| Runtime | PASS Comfy CUDA RTX 5090 | PASS Comfy CUDA RTX 5090 | PASS Comfy CUDA RTX 5090 | NON-COMFY | CERTIFICATION BLOCKED | isolated | isolated |
| Result | PASS PNG 200 | PASS PNG 200 | PASS PNG 200 | CIS ref attached | N/A | N/A | N/A |
| Reload | PASS still in Library (reconfirm) | PASS still in Library (reconfirm) | PASS still in Library (reconfirm) | PASS Playwright | N/A | N/A | N/A |
| Downstream | Library | Prop candidate complete | Brand artwork in Library | CIS I2I path | none | none | none |

---

## Peer review (review-only, scoped coverage)

Prior pair only returned `READY FOR PRIMARY REVIEW` and is superseded:

- [GLM 5.2](44c521fd-b977-458d-a63a-08f5cafbecfd)
- [Kimi K3](f25ec729-42fb-429d-ab5d-e66ec5934d9a)

This finalize review-only pass (no file edits by reviewers):

- [GLM 5.2](9b0e8cea-dd84-42e1-b2c6-b122768d6ecf) — **PASS WITH FINDINGS**
- [Kimi K3](3bddfe15-f197-4475-b51f-a63dc1c0da09) — **PASS WITH FINDINGS**

Both restated Character Creator remains uncertified. Neither found a scoped FAIL (invented keys, silent CIS zimage fallback, Brand generate without lock, unread PoseCraft handoff, Voice Clone/Upload posting design, Avatar `startImmediately: true` into a guaranteed fail).

Agreed interpretation:

- CC AUTO “must-fix” = dirty-tree **exclusion**, not a coverage FAIL. Kimi noted the only dynamic `{family}.ref_edit` construction is `character_identity/visual_sheet.py` (bucket B).
- Avatar Plan Sections `canGenerate` bug remains repaired to `canPlan` at both Next Best Step and Create Panel.
- Residuals stay **findings**, not CC absorption: Krea Draft enqueue fail-closed; CIS AUTO+refs fail-closed on qwen2512; `compile_edit_request` unguarded zimage fallback; Avatar `certifiedReady` hardcoded false.

---

## Stop rules honored

- No new custom node packs
- No new heavyweight model downloads
- No fake Comfy success
- Avatar talking-head **not** certified
- This pass did not change Character Creator / Scene / ERS AUTO choosers
- ImageGenPanel not revived
- No new project — Schnick Coffee only
- No commit / no dirty-tree cleanup
- `:8760` not started

---

## Limitations

- `apiRevision` string remains the git SHA until these files are committed.
- Krea 2 T2I key is real (`krea2.turbo_txt2img`) but Draft — creator-visible generate fails closed until that leaf is Certified.
- CIS Best Match + refs still fail closed if AUTO lands on qwen2512; creator must pick Z-Image or Flux.
- Avatar `certifiedReady` is hardcoded `false` until the isolated talking-head program certifies.
- `compile_edit_request` still has an unguarded zimage fallback (generic edit path). CIS I2I compile used in this cert pins `zimage.ref_edit` explicitly and does not take that fallback.
- Prior dirty-tree Character Creator / sanitation / Spatial Map edits are **not** part of this coverage verdict.
- This GO does **not** claim the whole dirty branch is certified.

---

## Final language

- `GO — IMAGE GENERATOR T2I ROUTE OPERATIONAL`
- `GO — IMAGE GENERATOR I2I WORKFLOW OPERATIONAL`
- `GO — PROP CREATOR GENERATION WORKFLOW OPERATIONAL`
- `GO — BRAND STUDIO GENERATION WORKFLOW OPERATIONAL`
- `GO — POSECRAFT JOINTS NON-COMFY BY DESIGN`
- `GO — POSECRAFT HANDOFF WIRED`
- `GO — AVATAR HONESTY ROUTE OPERATIONAL` — `NON-COMFY BY DESIGN — REAL EXECUTION ROUTE EXISTS, CERTIFICATION BLOCKED`
- `GO — VOICE IDENTITY METHOD ROUTING OPERATIONAL`
- `GO — AUDIO STUDIO NON-COMFY BY DESIGN — REAL EXECUTION ROUTE VERIFIED`

**Overall (scoped):**

`GO — ADEPT UI GENERATION WORKFLOW COVERAGE CERTIFIED`

`EXCLUSION — CHARACTER CREATOR REMAINS UNCERTIFIED`

This does **not** certify the dirty branch, Character Creator, Scene AUTO, or ERS AUTO.

Compare: original coverage task (concrete execution route per surface) vs live Schnick jobs vs bucket A files vs 52 API / 16 web / 6 Playwright vs both reviewers `PASS WITH FINDINGS` vs CC exclusion — all hold. No commit.
