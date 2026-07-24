# Director 2.0 — LTX 2.3 Ingredients IC-LoRA Completion Report

**Date:** 2026-07-23  
**Outcome:** **B — Architecture complete; live Ingredients weights not installed**  
**Phase 1 unrelated work:** Not started

## Final confirmation

IC-LoRA Ingredients is represented as a verified model dependency, Director can organize visual references and build a composite sheet (+ static video), and the compiler injects real ComfyUI IC-LoRA nodes discovered via `object_info`. Without `ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors` on disk, generation stays blocked with honest status (not fake Ready).

```text
pytest (full studio-api): 68 passed — exit 0
pytest (test_ic_lora_ingredients.py): 16 passed — exit 0
npx tsc -b (studio-web): exit 0
npm run build (studio-web): exit 0
```

## 1. Existing IC-LoRA support found before implementation

- Adept LTX builder hard-coded `LTXDirectorGuide.ic_lora_name: "None"` (never wired).
- No Ingredients model, setup card, or reference-sheet product path.
- ComfyUI live nodes present: `LTXICLoRALoaderModelOnly`, `LTXAddVideoICLoRAGuide`, `GetICLoRAParameters`, `LTXVAddGuide`.
- Disk had Union Control IC-LoRA only; Ingredients file missing.
- Probe notes: [`docs/audit/IC_LORA_NODE_PROBE.md`](IC_LORA_NODE_PROBE.md)

## 2. Model source and exact file selected

- HF: `Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients` (gated)
- Filename: `ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors`
- Registry id: `ltx23_ic_lora_ingredients`

## 3. Gated-access behavior

- Missing file + HF 401/403 → `ic_lora_authorization_required` with message:  
  “Authorization Required. Accept the model terms on Hugging Face and connect your Hugging Face token.”
- Token via `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` / `ADEPT_HF_TOKEN` only (never project files).
- No fabricated unrestricted download URL.

## 4. Installation path and verification

- Setup component `ltx23_ic_lora_ingredients` (path_link, verifier `ic_lora_file`)
- Category: Reference & Identity Models
- Ready only when expected filename exists with nonzero / non-stub size
- Empty directory ≠ Ready

## 5. ComfyUI nodes discovered

Preferred strategy `ltxvideo`:

- `LTXICLoRALoaderModelOnly`
- `LTXAddVideoICLoRAGuide`
- `LoadImage`

Alternate `native` / `core_guide`: `LoraLoaderModelOnly` + `GetICLoRAParameters` + `LTXVAddGuide`

## 6. Workflow ID and version

- Key: `ltx.ingredients_ic_lora`
- Version: `1.0.0`
- Registered in `studio-api/app/workflows/registry.py`

## 7. Reference-sheet builder implementation

- Pillow composite on black background (`sheet_builder.py`)
- Layouts: auto / character focus / two characters + environment / character + props + environment / environment focus / custom grid
- Static video loop ≥121 frames via ffmpeg (`static_video.py`)
- Project-scoped store under `data_dir/projects/{id}/references/`

## 8. Director 2.0 UI changes

- New **Visual References** panel in Director Prompt Timeline
- Reference methods: None / Start Frame / First-Last / Ingredients IC-LoRA / Identity (disabled)
- Role assignment, Build Reference Sheet, preview, strength presets, Advanced numeric, continuity presets
- Blockers shown when model/nodes unavailable

## 9. Compiler mappings

`compile_ingredients_workflow` probes `object_info`, injects loader filename + LoadImage reference path + guide strength, compiles two-part prompt (`Reference sheet:` / `Generated video:`), returns sanitized debug dump + provenance.

## 10. Submitted workflow proof

Mocked compiler test asserts submitted graph contains:

- `LTXICLoRALoaderModelOnly` with Ingredients filename
- `LoadImage` with uploaded reference path
- `LTXAddVideoICLoRAGuide`
- Provenance workflow version
- No tokens in sanitized debug

Live generation against real Ingredients weights was **not** run (file absent).

## 11. Continuity preset implementation

- Save/list/reuse presets in project references store
- Reuse restores sheet + strength into Director reference config

## 12. Provenance implementation

- Job `params_json` / `history_json` store IC-LoRA provenance
- Output asset `prompt_meta_json` + `used_in_director` edges to sheet/source assets
- Library **References used** block via `/assets/{id}/references-used`

## 13. Files changed (primary)

**New:** `app/references/*`, `app/workflows/ltx_ingredients_compiler.py`, `tests/test_ic_lora_ingredients.py`, `studio-web/src/components/VisualReferencesPanel.tsx`, `studio-web/src/references/types.ts`, audit docs

**Updated:** `catalog.py`, `diagnostics.py`, `registry.py`, `queue_worker.py`, `comfy_client.py`, `main.py`, `schemas.py`, `routers/api.py`, `DirectorTracks.tsx`, `LibraryPanel.tsx`, `api.ts`

## 14–17. Gates

| Check | Result |
|-------|--------|
| Backend tests | **68 passed**, exit 0 |
| IC-LoRA tests | **16 passed**, exit 0 |
| TypeScript | exit **0** |
| Production build | exit **0** |

## 18. Browser verification

Not re-run end-to-end in browser this session. UI is wired into Director; restart API/web to pick up routes.

## 19. Live generation result

**Not run** — Ingredients safetensors missing. Union Control file on disk is intentionally not treated as Ingredients.

## 20. Remaining limitations

1. Link/install `ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors` after HF terms + token
2. Full HF auto-download still gated/manual (path_link primary)
3. ID-LoRA not implemented (UI disabled)
4. Generic ImageGen LoRA stack injection remains out of scope
5. Live short generation + visual consistency QA pending once weights are Ready

## 21. Confirmation: IC-LoRA selection changes the submitted ComfyUI workflow

**Yes (compiler/unit proof).** When `reference_method=ingredients_ic_lora` (job params or `director_json.reference`), `queue_worker` calls `compile_ingredients_workflow` instead of `build_ltx_scene_workflow`, producing a graph with IC-LoRA loader + guide + reference image — not the hardcoded `ic_lora_name: "None"` path.
