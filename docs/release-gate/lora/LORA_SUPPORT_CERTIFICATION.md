# Adept UI — LoRA Support Certification

**Branch:** `feat/lora-support` · **Base:** `beta` (HEAD 31e6e48)
**Date:** 2026-08-18 · **Status:** CERTIFIED (see final verdict)

## 1. Architecture (centralized, shared)

One authoritative **LoRA Registry** (`studio-api/app/lora_registry/`) backs every surface:

```
Setup Wizard / Model Manager  (LoRASetupSection)
          |
          v
      LoRA Registry  (data/lora_registry.json + /api/loras/*)
          |
          v
   Compatibility Filtering  (compat.py — data-driven family/modality)
          |
          v
   Advanced Accordion Selectors  (shared LoRASelector component)
          |
          v
   Generator Adapters  (image build_leaf_graph / video ltx_builder)
          |
          v
   ComfyUI LoraLoader / LoraLoaderModelOnly nodes
```

- No per-surface registries (Image Generator, Scene Creator, Timeline,
  Character, Prop, Mini all query `/api/loras/compatible`).
- Registry state: `data/lora_registry.json` (one JSON store, atomic writes).
- Curated downloads: `config/lora_catalog.json` (optional, user-initiated,
  checksum-verified when published; downloads require explicit approval).

## 2. Registry record (LoraRecord)

id, name, file_path, model_family, compatible_model_families, category,
modality, version, enabled, recommended_strength, strength_min/max,
source_url, license, download_size_bytes, checksum_sha256, install_status,
last_validated_at, detected, catalog_id, installed_at, comfy_name, notes.

## 3. Compatibility (mandatory, data-driven)

`compatible_loras(model_family, modality)` is the ONLY filter the UI and the
generation adapters use. Deterministic family taxonomy in `compat.py`:

| App family | LoRA families |
|---|---|
| illustrious / sdxl | sdxl |
| flux | flux |
| qwen2512 | qwen-image |
| zimage | zimage |
| krea2 | krea2 |
| ltx / ltx-2.5 | ltx |
| wan / hunyuan | (none — no LoRA support) |
| fal / kie / cloud | (none — closed providers) |

`resolve_lora_for_generation()` refuses disabled / incompatible / missing
selections with a clear error — **no silent substitution ever**.

## 4. Runtime loading (image + video)

**Image (SDXL/Illustrious, FLUX, Z-Image, Qwen-Image-2512, Krea 2):**
- `image_product/service.py` threads `lora` into job params;
- `queue_worker._imagegen` resolves the selection through the registry and
  passes `lora_name`/`lora_strength` into `local_comfy_adapter.submit`;
- `workflow_execute.build_leaf_graph` wires `LoraLoader` (checkpoint/SDXL) or
  `LoraLoaderModelOnly` (FLUX/Z-Image/Qwen transformer paths) via the shared
  `wire_lora_nodes` helper; Krea 2 keeps its existing `LoraLoader` path.
- Certified baseline graphs stay fingerprint-checked; a graph with an
  explicitly selected LoRA exercises the declared optional inputs
  (`loraId`/`loraStrength` in the certified registries) and is covered by
  dedicated graph tests instead of the baseline hash.

**Video (LTX 2.3):**
- `workflows/ltx_builder.py` (`build_ltx_scene_workflow`,
  `build_ltx_simple_i2v`) accept `lora_name`/`lora_strength` and emit
  `LoraLoaderModelOnly` after the checkpoint — baseline graphs unchanged
  when no LoRA is selected.
- Threaded: Timeline W46 batch config (`BatchBlock.lora`, `PatchBatchBody`,
  request_builder → `ltx_local` adapter → job params) and legacy scene
  render (`RenderRequest.lora`, `scene.director_json.lora` fallback).
- WAN/Hunyuan refuse LoRAs (registry returns nothing; worker raises an
  honest error if a selection arrives).

**VRAM:** the registry is metadata-only; LoRA weights load exclusively via
ComfyUI LoraLoader at generation time (no eager GPU loading, no startup
VRAM penalty).

## 5. Provenance

`ImageProvenance.lora` block (and video job history `lora`) records:
loraId, name, version, modelFamily, compatibleModelFamilies, strength,
baseGenerator, sourceTool, filePath, category, modality. Flows into the
existing asset `prompt_meta_json` (Library) — no separate LoRA history
system. Historical references survive removal (registry removal never
touches assets); reload shows "LoRA unavailable: <name>" (non-destructive).

## 6. UI surfaces

- **Setup Wizard**: `LoRASetupSection` — detected files (register), local
  file registration, installed list (status/family/category), Enable/Disable,
  Remove (confirm), curated downloads (confirm; size/license shown).
- **Shared selector**: `src/components/lora/LoRASelector.tsx` (+ single-
  flight cached client `loraClient.ts`) — dropdown + strength slider +
  "Manage LoRAs" link; renders NOTHING when the active family has no
  compatible enabled LoRAs (no clutter, no alarming warnings).
- **Image Generator** (CinematicImageStudio) Advanced: LoRASelector for a
  single active family; hidden for mixed-family batches and hosted-only
  modes.
- **Scene Creator** full: Advanced → LoRASelector; persisted on the shot
  (all preview/final/retake flows share it).
- **Timeline right drawer** Advanced: video LoRASelector (LTX family) —
  persists to every W46 batch via patchBatch.
- **Scene Creator Mini**: documented limitation — stays Mini; the full
  Scene Creator is the LoRA surface (spatial-map mini path has no LoRA
  contract). Character/Prop creators route through the shared imagegen
  contract (lora-ready) without duplicated Advanced controls.

## 7. Tests

Backend pytest (`tests/test_lora_registry.py`): **12 passed** (register/
validate, deterministic compatibility filter, disable/re-enable,
incompatible+missing refusal, removal safety, persistence, detection,
validation, baseline-graph equivalence, lora graph emission, catalog/
approval, router endpoints).

Regression: **206 passed** across image_runtime, image_product, adapters,
engine ownership, director-timeline W46, timeline adapters, Krea2 lora,
generator roster, illustrious routing, LTX 2.5/WAN builders, drift gates.

Frontend (`loraClient.test.ts`, node:test): **4 passed** (per-family
filtering relay, single-flight caching, failure retry, closed-provider
empty relay).

Playwright live certification (`tests/e2e/lora/`):
- `lora-cert.spec.ts` — **7 passed**: compatibility disjointness; ImageGen
  Advanced selector (Cinematic XL visible, no LTX leakage, strength
  slider); Setup Wizard LoRA section; disable/re-enable; image generation
  with LoRA (Comfy graph LoraLoader node + strength 0.7 + asset
  provenance); baseline LoRA=None (no node, no provenance); Timeline
  drawer video selector.
- `lora-video-cert.spec.ts` — **1 passed**: LTX batch render with LoRA
  (Comfy graph LoraLoaderModelOnly + strength 0.6 + video output +
  provenance).
- `lora-screenshots.spec.ts` — captures the evidence screenshots.

## 8. Evidence artifacts

- Screenshots: `artifacts/lora-cert-screenshots/` (Setup Wizard section,
  Image Generator Advanced, Timeline Advanced).
- Playwright JSON: `artifacts/functional-audit/playwright-results.json`.
- Comfy executed-graph evidence: LoraLoader node payloads quoted in the
  runtime-load gates (see below).

## 9. Independent certification

Subagent C (independent, fresh agent) — **CERTIFICATION: PASS**.
All 8 gates certified live (registry API + determinism, install/detect
idempotency + register/remove, enable/disable, image runtime load with Comfy
LoraLoader node evidence, video runtime load with LoraLoaderModelOnly node
evidence, provenance persistence, UI smoke in a fresh Playwright spec, and
code/architecture review). One non-blocking finding (video library asset
provenance only in job params) was fixed and re-certified — see below.

## 10. Post-review fixes (Subagent C finding closed)

- queue_worker: pre-existing bare `uuid4()` NameError silently skipped the
  Timeline batch output Asset registration (the W46 fallback then created
  the asset without provenance). Fixed to `uuid.uuid4()`; the batch asset now
  carries `prompt_meta_json` with the LoRA/engine/workflow provenance block.
- `ltx_local._ensure_output_asset_ids` fallback now attaches the LoRA
  provenance block to the library asset as well (image/video parity).
- `lora-video-cert.spec.ts` asserts the library asset carries the LoRA
  provenance — re-run: PASS (48.2s, live LTX render).

## 11. Final verdict

**GO — ADEPT UI LoRA SUPPORT CERTIFIED**

Evidence recap: 12 backend registry tests, 206 regression tests, 279/280
full-suite (1 pre-existing unrelated failure), 4 frontend client tests, live
Playwright certification 7/7 UI + 1/1 video (image + video runtime loads,
provenance, disable/remove, baseline regression, compatibility
disjointness), independent Subagent C PASS, deployed to
https://adeptui.vercel.app from the tested revision.