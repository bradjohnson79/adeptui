# Krea Retirement Audit — Character Creator V3

**Scope:** Inventory every live-product reference to `krea` / `krea2` / `Krea` across `studio-web`, `studio-api`, `config`, `docs`, and `tests`. Classify each hit as safe to remove from the Character Creator V3 normal path, required by shared product surfaces (Image Generator, Prop Creator, Production Control, Setup), or needing an owner decision. Do **not** delete production Krea Image Generator / Prop / Setup code.

**Exclusions:** `.runtime/verify-copy` and historical evidence dumps are ignored unless they prove a live product path.

**Owner lock (already decided):**
- Retire Krea from Character Creator **multi-angle / Back-from-Front** role.
- Keep Krea 2 as optional **Front / Image Generator** unless unused.
- Expected Gate 1 verdict: **PARTIAL — KREA RETAINED FOR <Front/Image Generator>; REMOVED FROM CHARACTER CREATOR multi-angle path.**

---

## 1. High-level answers

### Q1. Does Character Creator currently use Krea for Back / Side / 3/4 generation?

**No — in the normal CC V3 path.**

The 4-view CC enqueue path reuses a single `stage1_route` for every view. If Krea 2 were selected it would technically run for all views (front, side, back, close-up), but the CC surface prevents that selection today:
- `_build_candidate_routing_plan` in `studio-api/app/character_identity/visual_sheet.py` never auto-selects Krea; it resolves Auto to `flux` → `qwen2512` only.
- The Character Creator local-generator roster (`imagegen_workflows.py::_character_creator_local_models`) suppresses `krea2` unless its workflow is `Certified`; the registry currently marks it `Draft`.
- The Back-from-Front / multi-angle role is documented as FLUX-only (`flux.img2img` binds front pixels for the back view) in `docs/release-gate/character-creator/CHARACTER_CREATOR_V2_ARCHITECTURE.md` and `CHARACTER_CREATOR_V2_CERTIFICATION.md`.

Relevant functions:
- `studio-api/app/character_identity/visual_sheet.py` `_build_candidate_routing_plan` (line 1586) — Auto resolution.
- `studio-api/app/character_identity/visual_sheet.py` `_enqueue_law_view_jobs` (line 2763) — same route per view.
- `studio-api/app/imagegen_workflows.py` `_character_creator_local_models` (line 199) — Certified-only filter for `krea2`.
- `config/image-workflows/certified-registry.json` — `krea2.turbo_txt2img` / `krea2.raw_txt2img` status is `Draft`.

### Q2. Does the CC Front dropdown include `krea2`?

**No, not today.**

- The Character Creator panel calls `api.imagegenModels("character")` (`studio-web/src/components/character/CharacterGeneratorPanel.tsx`, line 78).
- The backend endpoint (`studio-api/app/routers/extra.py` line 955) dispatches to `build_local_generator_models(surface="character")`.
- `build_local_generator_models` → `_character_creator_local_models` explicitly drops `krea2` when its workflow status is not `Certified` (`studio-api/app/imagegen_workflows.py`, line 237).
- The certified registry lists both Krea workflows as `Draft` (`config/image-workflows/certified-registry.json`, lines 1169 and 1299).

Note: the e2e test `tests/e2e/character-creator/character-single-crs.spec.ts` (line 69) still lists `krea2` among allowed default values, which is now inconsistent with the live dropdown and should be updated as part of retirement.

### Q3. Recommended exact CC-only removals vs. what must stay

**CC-only removals (safe to remove from Character Creator V3 normal path):**
1. Remove `krea2` from `_HONORED_CRS_LOCAL_FAMILIES` in `visual_sheet.py` (line 337) — stops CC from accepting an explicit `krea2` generator source.
2. Remove `krea2` from the CC fallback order in `studio-web/src/components/character/characterGeneratorPlan.ts` (line 174) — stops Auto Select from falling back to Krea.
3. Remove `krea2` from `LOCAL_FAMILY_LABELS` in `characterGeneratorPlan.ts` (line 262) — only if the CC dropdown is fully purged.
4. Remove `krea2` from the CC-specific provenance mapping in `studio-web/src/components/character/types.ts` (`LOCAL_FAMILY_PROVENANCE`, line 202) and the Krea model-name helper — only if no CC candidate will ever carry a Krea provenance.
5. Update / remove CC tests that assert Krea as a selectable CC source:
   - `studio-api/tests/test_character_creator_single_crs.py` `test_krea2_is_kept_as_crs_source` (line 90).
   - `studio-api/tests/test_character_candidate_routing.py` tests that route local Krea through the CC plan (e.g., `test_local_krea2_is_profile_guided_no_silent_zimage`, line 532; Krea medium/large hosted tests, line 558).
   - `tests/e2e/character-creator/character-single-crs.spec.ts` line 69 allowed default values.
6. Remove or repurpose the `krea: False` pack metadata and `kreaInvoked: False` gate stamps in `visual_sheet.py` / `crs_law_view_gates.py` once CC no longer needs to prove Krea was not invoked.

**What must stay (shared contracts):**
- `config/image-workflows/certified-registry.json` Krea workflow entries (shared by Image Generator / Prop Creator / Setup).
- `config/image-runtime/provider-registry.json` `comfyui` `supportedModelFamilies` including `krea2` (shared runtime contract).
- `studio-api/app/workflows/krea2_image.py` workflow builders (shared image generation implementation).
- `studio-api/app/image_runtime/contract.py` Krea family normalization and workflow resolution (shared image runtime).
- `studio-api/app/image_core/capability.py` `GENERATE_WORKFLOW["krea2"]` and `NO_I2I_PROFILE_GUIDED` set (shared capability routing).
- `studio-api/app/image_runtime/workflow_execute.py` Krea execution branch (shared executor).
- `studio-api/app/image_product/recommend.py` Krea family status/why strings (shared recommendation engine, note says "Never the Auto Select default" already).
- `studio-api/app/image_studio/providers.py` Krea local/hosted model descriptors (shared Image Studio / Prop Creator provider surface).
- `studio-api/app/production_control/model_registry.py` and `runtime_map.py` Krea model IDs → family mapping (shared Production Control).
- `studio-api/app/prop_creator/generation.py` Krea alias handling and Krea plan generation (Prop Creator support).
- `studio-api/app/setup/catalog.py` and `setup/diagnostics.py` `krea2_models` component and verifier (Setup / Source Manager).
- `studio-api/app/comfy_health.py` `krea2_models` in `MODEL_COMPONENT_IDS` (shared Comfy health model inventory).
- `studio-api/app/capabilities/registry.py` and `service.py` `models.image.krea2.ready` capability (shared readiness surface).
- `studio-api/app/schemas.py` optional Krea model fields (shared health schema).
- `studio-api/app/image_runtime/model_discovery.py` Krea 2 detection logic (shared model discovery).
- `studio-api/app/config.py` Krea 2 settings (shared configuration).
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/krea2.py` and related terminology (Co-Director multi-shot / ERS Krea renderer).
- `studio-web/src/components/character/types.ts` `kreaModelNameFromCandidate` and `characterSheetProvenanceLabel` API-Krea branch — used for any hosted Krea candidate (Image Generator / Prop / API paths), not just CC.
- `studio-web/src/components/character/characterGeneratorPlan.ts` `providerDisplayName("krea")` — used for any API provider, not CC-specific.
- `studio-api/tests/test_prop_creator_generator_parity.py` Krea test fixtures (Prop Creator coverage).
- `studio-api/tests/test_cdx075_local_readiness.py` Krea readiness test (Setup-verification coverage).
- `studio-api/tests/test_runtime_diagnostics_refinement.py` Krea optional component tests (Comfy health coverage).

**Owner decision required:**
- `studio-api/app/character_identity/crs_view_generation.py` currently **refuses** `krea2` explicitly (line 280). If the owner intends "optional Front" to mean a single CC front view may still use Krea, this refusal should be removed or narrowed. If "Front" instead means the general Image Generator / Prop front image, leave the refusal as-is.
- `studio-api/app/character_identity/visual_sheet.py` `_txt2img_workflow_key` and `_hosted_family_for_model` Krea branches are used by both CC and non-CC API paths. The CC-specific usage can be excised by removing `krea2` from `_HONORED_CRS_LOCAL_FAMILIES`, which makes these branches unreachable for CC while preserving them for Image Generator / Prop / API use.

---

## 2. Hit-by-hit inventory and classification

### `studio-api/app/character_identity/visual_sheet.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 209-215 | CRS AUTO comment: "Never silent-sub to zimage / illustrious / Krea" | **DELETE** (CC-only comment) | Comment is about CC auto routing. |
| 337-338 | `_HONORED_CRS_LOCAL_FAMILIES["krea2"] = "krea2"` / `krea` alias | **DELETE** | CC source coercion. Remove to stop CC accepting Krea. |
| 347-355 | `KREA_LOCAL_TXT2IMG_KEY`, `KREA_HOSTED_MODEL_LABELS` | **USED ELSEWHERE** | Also used by image_core, image_runtime, Prop, and API paths. Keep; only unreachable for CC after `_HONORED_CRS_LOCAL_FAMILIES` removal. |
| 696-700 | `_resolve_crs_auto_family` docstring: "Never Krea" | **DELETE** (CC-only comment) | CC auto family comment. |
| 943-947 | `_build_stage1_route` docstring: "(qwen_edit_2509, qwen2512, flux, krea2, illustrious) are kept" | **DELETE** (CC-only comment) | Update after removing Krea from CC honor list. |
| 1187-1191 | `_hosted_family_for_model` Krea mapping | **USED ELSEWHERE** | Used by any hosted API Krea model, including Prop/Image Generator. |
| 1199-1200 | `_normalize_local_family` Krea aliases | **USED ELSEWHERE** | Shared normalization; CC will stop reaching it via `_HONORED_CRS_LOCAL_FAMILIES`. |
| 1211-1214 | `_txt2img_workflow_key` Krea branch | **USED ELSEWHERE** | Shared key resolver. Keep for non-CC. |
| 1218-1233 | `_krea_model_display` | **USED ELSEWHERE** | Used for API-Krea provenance across products. |
| 1245 | `_PROVENANCE_FAMILY_NAMES["krea2"]` | **USED ELSEWHERE** | Used for any local Krea provenance, including Prop. |
| 1271-1273 | `_candidate_provenance_label` API Krea branch | **USED ELSEWHERE** | API Krea provenance for any product. |
| 1289-1291 | `_hosted_provider_label` Krea branch | **USED ELSEWHERE** | API provider label for any Krea call. |
| 2969 | "Provider-neutral identity packet BEFORE any Qwen/Krea routing" | **DELETE** (CC-only comment) | CC-specific comment. |
| 3185 | `_krea_model_display` call for API Krea provenance | **USED ELSEWHERE** | CC uses the same helper; keep helper. |
| 3509-3510, 3659 | `pack["krea"] = False` | **DELETE** | CC pack metadata asserting Krea not used. Can be retired once CC no longer needs it. |
| 3969 | `crsLawViewGate["kreaInvoked"] = False` | **DELETE** | CC gate metadata. Retire once CC Krea path is gone. |

### `studio-api/app/character_identity/crs_view_generation.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 124-125 | `normalize_crs_view_family` returns `krea2` for `krea*` prefix | **OWNER DECISION** | If "Front" means single CRS view, Krea should stay allowed here. If CC single-view is also retired, this becomes DELETE. |
| 280-281 | `resolve_crs_view_generation_workflow` raises `ValueError` for explicit `krea2` | **OWNER DECISION** | Currently refuses Krea for any CRS single view. Narrow or remove if Front Krea is desired. |

### `studio-api/app/character_identity/crs_law_view_gates.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 14 | Docstring: "Does not call Krea" | **DELETE** (CC-only comment) | Retire with CC Krea removal. |
| 547 | `kreaInvoked: False` | **DELETE** | CC gate result field. Retire once CC Krea path is gone. |

### `studio-web/src/components/character/characterGeneratorPlan.ts`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 174 | `fallbackOrder = [..., "krea2", ...]` | **DELETE** | CC Auto Select fallback. |
| 262 | `LOCAL_FAMILY_LABELS["krea2"] = "Local Krea 2"` | **DELETE** | CC local dropdown label. |
| 282 | `providerDisplayName("krea")` | **PRESERVE SHARED** | General API provider label; not CC-specific. |
| 606 | Test fixture `krea2-turbo-fal` | **DELETE** | CC test only. |

### `studio-web/src/components/character/characterSheetGenerate.ts`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| None | No direct Krea references | N/A | Consumes `characterGeneratorPlan` and `types.ts`. |

### `studio-web/src/components/character/CharacterSheetGenerator.tsx`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| None | No direct Krea references | N/A | Uses plan-driven APIs. |

### `studio-web/src/components/character/CharacterGeneratorPanel.tsx`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 78 | `api.imagegenModels("character")` | N/A | This is the CC surface; the backend already filters Krea out. No Krea code to remove here. |

### `studio-web/src/components/character/types.ts`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 202 | `LOCAL_FAMILY_PROVENANCE["krea2"]` | **DELETE** | CC candidate provenance label. |
| 205-213 | `kreaModelNameFromCandidate` | **USED ELSEWHERE** | Also used for API Krea candidates in any product. Keep. |
| 226-241 | `characterSheetProvenanceLabel` API Krea branch | **USED ELSEWHERE** | API Krea provenance; keep. |

### `studio-api/app/imagegen_workflows.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 16 | `_FAMILY_LABELS["krea2"]` | **PRESERVE SHARED** | Shared generator label. |
| 22 | `_FAMILY_ORDER` includes `krea2` | **PRESERVE SHARED** | Used for non-CC surfaces. CC roster filters it out by Certified status. |
| 28 | `_CHARACTER_FAMILY_ORDER` includes `krea2` | **DELETE** | CC-specific ordering. |
| 44 | `_FAMILY_INSTALL_COMPONENTS["krea2"]` | **PRESERVE SHARED** | Setup component binding for Krea 2. |
| 147-167 | `krea_entry` special-case append for CC roster | **DELETE** | This block is the only place that could override the Certified filter and expose Krea in CC. Remove it. |
| 237 | `_character_creator_local_models` `krea2` Certified filter | **DELETE** | Remove the now-dead branch once the special-case append is gone. |

### `studio-api/app/routers/extra.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 955-961 | `imagegen_models(surface)` endpoint | **PRESERVE SHARED** | No change; the `surface=character` path will naturally stop returning Krea after the backend purge. |

### `studio-api/app/image_core/capability.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 45 | `GENERATE_WORKFLOW["krea2"]` | **PRESERVE SHARED** | Shared generate workflow key. |
| 81 | `NO_I2I_PROFILE_GUIDED` includes `krea2` | **PRESERVE SHARED** | Shared reference-mode honesty. |
| 107 | `normalize_family` Krea aliases | **PRESERVE SHARED** | Shared family normalization. |

### `studio-api/app/image_runtime/contract.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 241-242 | `_normalize_family` Krea aliases | **PRESERVE SHARED** | Shared image workflow contract. |
| 271 | Docstring: "Supports ... krea2.*" | **PRESERVE SHARED** | Shared contract surface. |
| 340-343 | `resolve_image_workflow` Krea generate branch | **PRESERVE SHARED** | Shared image workflow resolver. |

### `studio-api/app/image_runtime/workflow_execute.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 321-410 | Krea workflow execution branch | **PRESERVE SHARED** | Shared executor path for any Krea job. |

### `studio-api/app/image_product/recommend.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 44 | `_family_status` Krea workflow keys | **PRESERVE SHARED** | Shared recommendation. |
| 115-116 | `_why` Krea strings | **PRESERVE SHARED** | Already says "Never the Auto Select default." |
| 178, 244 | Preferred/routing Krea handling | **PRESERVE SHARED** | Shared routing; CC-specific removal is upstream. |

### `studio-api/app/image_studio/providers.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 17-18, 24-26 | `_FAMILY_FALLBACK` Krea mappings | **PRESERVE SHARED** | Shared provider mapping. |
| 58-77 | Krea hints (`krea2-turbo-local`, `krea2-raw-local`) | **PRESERVE SHARED** | Shared Image Studio / Prop Creator hints. |
| 108-125 | Hosted Krea hints (`krea2-turbo-fal`, etc.) | **PRESERVE SHARED** | Shared hosted provider surface. |
| 200-201, 219-220 | `_COMPONENT_GATE_BY_MODEL` / `_CAPABILITY_WORKFLOW_BY_MODEL` | **PRESERVE SHARED** | Shared readiness/workflow mapping. |
| 224-228 | `_CAPABILITY_REASON` | **PRESERVE SHARED** | Shared capability note. |
| 509, 512 | `family_catalog()` Krea label and family tuple | **PRESERVE SHARED** | Shared family catalog. |

### `studio-api/app/production_control/runtime_map.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 22-23, 29-31 | `IMAGE_FAMILY_BY_MODEL` Krea mappings | **PRESERVE SHARED** | Shared dock model → family mapping. |
| 162-171 | `_family_executable` | **PRESERVE SHARED** | General helper. |

### `studio-api/app/production_control/model_registry.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 321-333, 349-361, 588-619 | Krea local/hosted model descriptors | **PRESERVE SHARED** | Production dock catalog. |
| 790 (approx) | `_SETUP_COMPONENT_BY_MODEL` Krea mapping | **PRESERVE SHARED** | Shared executable gating. |

### `studio-api/app/prop_creator/generation.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 23-25 | `_FAMILY_ALIASES` Krea aliases | **PRESERVE SHARED** | Prop Creator normalization. |
| 130-131 | `_hosted_family_for_model` Krea mapping | **PRESERVE SHARED** | Prop Creator hosted model mapping. |
| 167 | Comment: "illustrious / krea2 have no I2I key" | **PRESERVE SHARED** | Prop Creator mode honesty. |
| 214-221 | Test asserts Krea workflow key | **PRESERVE SHARED** (test) | Prop coverage. |

### `studio-api/app/setup/catalog.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 52 | `krea2_files` verifier → `DEPENDENCY_TYPE_MODEL` | **PRESERVE SHARED** | Setup component taxonomy. |
| 183-191 | `krea2_models` component definition | **PRESERVE SHARED** | Still Image Models catalog entry. |

### `studio-api/app/setup/diagnostics.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 113-125 | `_krea2_roots` | **PRESERVE SHARED** | Krea model discovery. |
| 128-152 | `_krea2_find` | **PRESERVE SHARED** | Krea file discovery. |
| 261-310 | `_verify_krea2_files` | **PRESERVE SHARED** | Krea component verifier. |
| 606-607 | `verify_component` dispatcher for `krea2_files` | **PRESERVE SHARED** | Verifier router. |

### `studio-api/app/comfy_health.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 43 | `MODEL_COMPONENT_IDS` includes `krea2_models` | **PRESERVE SHARED** | Shared Comfy health inventory. |

### `studio-api/app/capabilities/registry.py` & `service.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 662-675 | `models.image.krea2.ready` capability | **PRESERVE SHARED** | Shared readiness capability. |
| 428-430, 857 | `_eval_models_image_krea2` / evaluator map | **PRESERVE SHARED** | Shared readiness evaluator. |

### `studio-api/app/schemas.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 521-522 | `missing_optional_models` comment mentions Krea | **PRESERVE SHARED** | Shared health schema. |

### `studio-api/app/config.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 65-91 | Krea 2 settings (`krea2_model_root`, checkpoints, encoder, VAE, clip_vision, ipadapter, steps, cfg, mu) | **PRESERVE SHARED** | Shared configuration. |

### `studio-api/app/image_runtime/model_discovery.py`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 102-133 | `_detect_krea2` | **PRESERVE SHARED** | Krea 2 model discovery. |
| 182, 230-241 | `discover_modern_image_models` Krea family entry | **PRESERVE SHARED** | Shared discovery output. |

### `studio-api/app/codirector/...`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| `tools/definitions.py` 5878-5907 | Multi-Shot Krea 2 tool definitions | **PRESERVE SHARED** | Co-Director multi-shot / ERS path. |
| `knowledgebase/multimodal_continuity/providers/krea2.py` | `render_krea2` | **PRESERVE SHARED** | Co-Director Krea 2 prompt renderer. |
| `knowledgebase/multimodal_continuity/terminology.py` | `KREA2_KEEP`, `KREA2_VIEW_WHOLE` | **PRESERVE SHARED** | Co-Director Krea terminology. |
| `knowledgebase/multimodal_continuity/packet.py` | Provider dispatch for `krea2` | **PRESERVE SHARED** | Co-Director provider dispatch. |
| `tools/handlers/multi_shot_tools.py` | Default `krea2-turbo-local` provider | **PRESERVE SHARED** | Multi-shot planning default. |

### `config/image-workflows/certified-registry.json`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 1164-1291, 1293-1423 | `krea2.turbo_txt2img` and `krea2.raw_txt2img` workflow entries | **PRESERVE SHARED** | Shared certified registry. Currently `Draft`. |

### `config/image-runtime/provider-registry.json`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| 20 | `comfyui` `supportedModelFamilies` includes `krea2` | **PRESERVE SHARED** | Shared runtime provider contract. |

### `docs/release-gate/character-creator/...`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| `CHARACTER_CREATOR_V2_CERTIFICATION.md` 31 | "Never-default: SenseNova, MiniMax H3, Krea, Z-Image silent remap" | **PRESERVE** | Historical/certification doc; already reflects the intent. |
| `CHARACTER_CREATOR_V2_ARCHITECTURE.md` 31 | Same never-default | **PRESERVE** | Architecture doc. |
| `FLUX_CRS_AUTO_ONE_FIGURE_HANDOFF.md` 85 | "Never silent-sub to zimage / illustrious / Krea" | **PRESERVE** | Architecture doc. |

### `tests/e2e/character-creator/...`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| `character-single-crs.spec.ts` 69 | Allowed default values include `krea2` | **DELETE** | Update to match the live CC dropdown. |
| `character-creator-v2-assets.spec.ts` 391-392 | Back-from-Front I2I check (not Krea-specific) | N/A | No Krea code; retained. |

### `studio-api/tests/...`

| Line(s) | Code / Reference | Classification | Notes |
|---------|------------------|----------------|-------|
| `test_character_creator_single_crs.py` 90-94 | `test_krea2_is_kept_as_crs_source` | **DELETE** | CC-specific Krea acceptance test. |
| `test_character_candidate_routing.py` 465-503, 532-547, 558-572, 576-608 | Krea API/local routing tests | **DELETE** | CC routing tests that exercise Krea. |
| `test_crs_view_generation.py` 518-521 | `test_explicit_krea2_is_refused` | **OWNER DECISION** | Keep if CRS single-view Krea is retired; narrow if Front Krea is allowed. |
| `test_crs_view_generation.py` 312 | `pack["krea"] is False` | **DELETE** | CC pack metadata assertion. |
| `test_crs_law_view_gates.py` 101 | `kreaInvoked` False | **DELETE** | CC gate metadata. |
| `test_runtime_diagnostics_refinement.py` 221-223, 308-331, 365-369, 396-397 | Krea optional component tests | **PRESERVE SHARED** | Comfy health / Setup coverage. |
| `test_prop_creator_generator_parity.py` 26, 205, 214, 221, etc. | Krea in Prop catalog / plans | **PRESERVE SHARED** | Prop Creator coverage. |
| `test_cdx075_local_readiness.py` 137-148 | Krea local readiness | **PRESERVE SHARED** | Setup / disk verification coverage. |

---

## 3. Proposed CC V3-only removal checklist (do not implement wiring)

- [ ] `studio-api/app/character_identity/visual_sheet.py`
  - Remove `krea2` / `krea` from `_HONORED_CRS_LOCAL_FAMILIES`.
  - Remove/update Krea-only CC docstrings (lines 209-215, 696-700, 943-947).
  - Remove `pack["krea"]` and `crsLawViewGate["kreaInvoked"]` once the backend no longer needs to prove Krea was not invoked.
- [ ] `studio-api/app/character_identity/crs_law_view_gates.py`
  - Remove `kreaInvoked` field and "Does not call Krea" docstring once Krea is fully excised from CC.
- [ ] `studio-api/app/imagegen_workflows.py`
  - Remove `krea2` from `_CHARACTER_FAMILY_ORDER`.
  - Remove the `krea_entry` special-case append and the `fam == "krea2"` Certified guard in `_character_creator_local_models`.
- [ ] `studio-web/src/components/character/characterGeneratorPlan.ts`
  - Remove `krea2` from `fallbackOrder` and `LOCAL_FAMILY_LABELS`.
  - Update test fixtures.
- [ ] `studio-web/src/components/character/types.ts`
  - Remove `krea2` from `LOCAL_FAMILY_PROVENANCE` (keep `kreaModelNameFromCandidate` and API provenance branch for shared use).
- [ ] `studio-api/tests/test_character_creator_single_crs.py`
  - Delete or update `test_krea2_is_kept_as_crs_source`.
- [ ] `studio-api/tests/test_character_candidate_routing.py`
  - Delete or update Krea-specific CC routing tests.
- [ ] `tests/e2e/character-creator/character-single-crs.spec.ts`
  - Remove `krea2` from the allowed default value list.
- [ ] `studio-api/tests/test_crs_view_generation.py`
  - Decide with owner: keep `test_explicit_krea2_is_refused` (CC/CRS single-view also retired) or delete/narrow it (Front Krea allowed).

---

## 4. Gate 1 verdict

**PARTIAL — KREA RETAINED FOR Image Generator / Prop Creator / Setup / Co-Director Multi-Shot; REMOVED FROM CHARACTER CREATOR.**

Applied CC-only removals:
- `_HONORED_CRS_LOCAL_FAMILIES` no longer accepts `krea` / `krea2`.
- `_character_creator_local_models` always skips `krea2`.
- Auto fallback order no longer includes `krea2`.
- Local `krea2` generator sources coerce to AUTO.
- Character Creator tests and the single-CRS e2e default list no longer treat Krea as a CC family.

Shared Krea 2 remains in Image Generator, Prop Creator, Setup (`krea2_models`), Production Control, certified-registry Draft workflows, and Co-Director Multi-Shot.

**No production Krea Image Generator / Prop / Setup code was deleted by this audit.**
