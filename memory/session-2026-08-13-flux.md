# Session Memory: 2026-08-13 — FLUX.1 Kontext [dev] Restore + Character Creator Two-Stage Pipeline

## Branches
- Working branch: `beta` (HEAD at start: `c3bd4ba`)
- Final SHA: `ba9b4a6`
- GitHub remote: https://github.com/bradjohnson79/adeptui.git
- Vercel project: `adeptui` (anoint team)

---

## 1. Objective

Restore FLUX.1 Kontext [dev] to the Adept UI local Image Generator roster with live certification, and implement a two-stage Character Creator pipeline (Stage 1 identity lock via reference-capable workflow, optional Stage 2 style refinement via real img2img/edit).

---

## 2. Implementation

### Backend: FLUX model download & integration
- Downloaded `flux1-kontext-dev.safetensors` (22.16 GB) and `clip_l.safetensors` from HuggingFace.
- Moved the diffusion transformer from `checkpoints/` to `models/diffusion_models/` so ComfyUI `UNETLoader` resolves it.
- Created **`studio-api/app/workflows/flux_image.py`** with `build_flux_txt2img_workflow` and `build_flux_img2img_workflow` ComfyUI builders.
- Wired the FLUX builders in **`studio-api/app/image_runtime/workflow_execute.py`** dispatch.
- Added FLUX config settings (model names, default steps/CFG) in **`studio-api/app/config.py`**.

### Backend: Registry certification
- Updated **`config/image-workflows/certified-registry.json`**:
  - `flux.txt2img`: status `Deferred → Draft → Certified`, builder path `app.workflows.flux_image:build_flux_txt2img_workflow`, required nodes `UNETLoader/VAELoader/DualCLIPLoader/CLIPTextEncode/ConditioningZeroOut/EmptySD3LatentImage/KSampler/VAEDecode/SaveImage`.
  - `flux.img2img`: status `Deferred → Draft → Certified`, builder path `app.workflows.flux_image:build_flux_img2img_workflow`, required nodes include `LoadImage/VAEEncode`.
  - Live-test fingerprints recorded (real 1024×1024 txt2img and img2img generations verified via ComfyUI API).
- Registry sync (`registry_sync.py`) promoted FLUX entries from Deferred to Draft upon weight discovery; manual promotion to Certified with evidence.

### Backend: Two-stage routing
- Extended **`studio-api/app/character_identity/visual_sheet.py`**:
  - Two-stage routing plan (`_build_candidate_routing_plan`) with `stage1`/`stage2` keys.
  - Stage 2 enabled for both reference-locked and no-reference generation (previously only reference-locked).
  - `_stage2_workflow_key` resolves Certified editing workflows (e.g. `flux.img2img`).
  - `_family_supports_stage2` guard prevents offering Stage 2 without a real certified editing workflow.
- Extended **`studio-api/app/imagegen_workflows.py`**:
  - Added `flux` to `_FAMILY_LABELS` ("FLUX.1 Kontext [dev]") and `_FAMILY_ORDER`.
  - Added `supportsEditing` capability field (family-level, aggregated from Certified editing workflows).
- Updated **`studio-api/app/routers/extra.py`** `imagegen_models` endpoint to use live `build_local_generator_models()` instead of stale `IMAGEGEN_MODELS` constant.

### Frontend: Identity Engine / Style Engine UI
- **`studio-web/src/components/character/types.ts`**: Added `supportsEditing` to `GeneratorOption`, `stage2Enabled`/`stage2SelectedId` to `GeneratorSourceState`.
- **`studio-web/src/components/character/GeneratorSourceSelector.tsx`**: Split local generator into:
  - **Identity Engine** (Stage 1) — all Certified local generators.
  - **Style Engine (optional)** (Stage 2) — only editing-capable generators with a real img2img/edit workflow. Shown/hidden reactively based on available engines.
- **`studio-web/src/components/character/CharacterSheetGenerator.tsx`**: Passes `stage2Family`/`stage2Enabled` to the API.
- **`studio-web/src/api.ts`**: Updated `startCharacterVisualSheet` body type to include `generatorSources` with `stage2Family`/`stage2Enabled`.

### Tests updated
- **`tests/test_character_candidate_routing.py`**: Updated all routing plan assertions to use `stage1`/`stage2` nested structure.
- **`tests/test_illustrious_routing.py`**: Same nested-structure update.
- **`tests/test_m42_w2_image_runtime.py`**: Updated FLUX assertions (now Certified) and added `test_resolve_flux_production_mode_certified`.
- **`tests/test_m42_w4_image_edit.py`**: Updated `test_kontext_blocked` to `test_kontext_draft_or_blocked` (flux.kontext_edit is Draft with weights present).
- **`tests/test_generator_roster.py`**: Added `test_flux_present_certified_and_editing_capable`; removed FLUX from non-certified exclusion list; added `supportsEditing` assertion.

---

## 3. Build

```powershell
npm --prefix studio-web run build
```

Result: PASS (tsc -b && vite build, 0 TypeScript errors, 3963 modules transformed).

---

## 4. Tests

Backend targeted test suite (244 selected):

```
tests/test_character_candidate_routing.py ........................
tests/test_generator_roster.py .......
tests/test_illustrious_routing.py .....................
tests/test_krea2_* ... (all pass)
tests/test_m41_41b_certified_workflows.py .
tests/test_m42_w2_image_runtime.py ...........
tests/test_m42_w43_character_creator.py ...........
tests/test_m42_w44_*.py ....................
tests/test_m42_w46_*.py ....................
tests/test_m42_w47_docker_runtime.py .........
tests/test_m42_w4_image_edit.py ..............
tests/test_m42_w4b_*.py ................
tests/test_m42_w4c_timeline_rename.py ..
```

Result: **244 passed** (excluded 1 pre-existing failure: `test_identity_registry_draft_not_enforced`).

Playwright (1 test):
```
npx playwright test tests/e2e/character-creator-simplification.spec.ts -g "qwen image dropdown"
```
Result: **1 passed (18.0s)**.

---

## 5. Git

```
c3bd4ba docs(memory): session 2026-08-13 Library all-media selection + sticky toolbar refinement (previous)
...
ba9b4a6 feat: restore FLUX.1 Kontext [dev] to local roster + two-stage Character Creator identity/style pipeline
```

Pushed to `origin/beta`. Local HEAD matches remote.

---

## 6. Deployment

- Vercel production deploy: https://vercel.com/anoint/adeptui/FhpfPLsYdGR9FwXZJxXnAgetRSRN
- Deploy URL: https://adeptui-cstpdcn5d-anoint.vercel.app
- Build status: **Ready** (55s)
- Live alias (pre-existing): https://adeptui.vercel.app

Note: The local Studio API (PID 27844, running as SYSTEM) was NOT restarted because it runs under a security context inaccessible from the user session. Backend code changes are on disk but not hot-reloaded into the running process. A system reboot or manual `taskkill /F /PID 27844` from an elevated admin prompt is required to load the new backend code.

---

## 7. Known Limitations / Deferred

- **Studio API restart deferred**: PID 27844 on port 8758 is a SYSTEM-level process that cannot be terminated from the current user session. The user was asked to run `taskkill /F /PID 27844` from an elevated admin PowerShell window to pick up the new backend code.
- **Playwright certification skipped**: User requested skip of full Playwright suite.
- **Spatial map V1 changes left unstaged**: Camera blocking and grid geometry UI commits were already in the log (`6f37d74`, `ab7cf4c`); no further spatial map work in this session.

---

## 8. Final Verdict

**GO** — FLUX.1 Kontext [dev] is restored to the local generator roster with live certification, two-stage Character Creator pipeline is implemented end-to-end, frontend builds and deploys, backend tests pass. The single remaining action is restarting the local Studio API to load new backend code.
