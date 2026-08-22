# FLUX CRS AUTO Route + One-Figure Gate — Grok Integration Handoff

Status: implementation slice on `feat/crs-flux-auto-one-figure`.
Not a product certification. No Vercel, no `:8758` bounce, no Comfy restart, no Korri generation.

```text
READY FOR GROK INTEGRATION — FLUX CRS AUTO ROUTE + ONE-FIGURE GATE
```

## What this slice adds

CRS AUTO can call existing `flux.txt2img` / `flux.img2img` for an isolated single-view tile, with a FLUX T5 caption (not the Qwen 13-block package). After the tile completes, a hard one-figure gate rejects proven multi-figure or collage outputs. A failed AUTO FLUX tile enqueues exactly one Qwen `qwen2512.txt2img` retry for that view. Explicit FLUX does not fallback.

## Do not rebuild

Reuse as-is:

- Registry: `flux.txt2img` Certified in `config/image-workflows/certified-registry.json`
- Builders: `studio-api/app/workflows/flux_image.py`
- Dispatch: `studio-api/app/image_runtime/workflow_execute.py`
- AUTO ranking: `_resolve_crs_auto_family()` in `visual_sheet.py` — FLUX first, Qwen only if FLUX is not advertised. Identity crop → `flux.img2img`.
- One job per camera: `_enqueue_law_view_jobs()` with `sheet_layout="crs_view"`. Extras stay off via `_skip_optional_sheet_enqueue`.

## New files (cherry-pick cleanly)

| File | Role |
| --- | --- |
| `studio-api/app/image_prompting/flux/__init__.py` | Export assembler |
| `studio-api/app/image_prompting/flux/crs_single_view.py` | FLUX CRS T5 caption; `prompt_family=flux_crs_single_view` |
| `studio-api/app/character_identity/crs_single_figure.py` | Gate + collage heuristic + fallback predicate |
| `studio-api/tests/test_crs_single_figure_gate.py` | PIL fixtures; fallback enqueue |
| `studio-api/tests/test_flux_crs_prompt.py` | FLUX vs Qwen compile + generic builder regression |
| `docs/release-gate/character-creator/FLUX_CRS_AUTO_ONE_FIGURE_HANDOFF.md` | This note |

## Dirty-tree files — inspect before merge

These were already dirty on `feat/codirector-sanitation-phase1`. **Do not `git add` them wholesale into this slice.** Integrate the hunks below.

### `studio-api/app/character_identity/visual_sheet.py`

- Import `compile_flux_crs_single_view`.
- `_is_flux_family()`.
- `_compile_visual_prompt(..., model_family=None)` — if FLUX and not four-view, use the FLUX assembler; else keep `compile_character_image_prompt`.
- `_enqueue_law_view_jobs` passes `model_family=stage1_route["modelFamilyPreference"]` and stamps `taskType: "CRS_SINGLE_VIEW"`, `autoSelect`, `fourViewSingleOutput: False`.
- Retry compile path also passes `model_family` and stamps `CRS_SINGLE_VIEW`.
- `_enqueue_txt2img` for `sheet_layout == "crs_view"` sets job `taskType` / creativeContext `CRS_SINGLE_VIEW` (pack-level `taskType` stays `CRS_GENERATION`).
- `_pin_crs_generation_job_params` accepts both `CRS_GENERATION` and `CRS_SINGLE_VIEW`.
- `_parse_local_source_entries` / `_coerce_single_crs_sources` honor `model: qwen2512|flux` as an explicit family (legacy dict shape).
- `apply_crs_single_figure_gate_to_job` + `enqueue_crs_qwen_fallback_for_job`.

### `studio-api/app/queue_worker.py`

After `validate_image_output`, in the **non-four-view** branch (local imagegen, Kie, Fal):

```python
apply_crs_single_figure_gate_to_job(db, job, params, str(tmp_path))
```

`is_crs_single_view_job` no-ops generic Image Generator jobs. Fal four-view assessment must not swallow gate `RuntimeError`.

### `studio-api/app/image_product/compile.py`

`prompt_purpose_for_expand`: treat `CRS_SINGLE_VIEW` like `CRS_GENERATION` so expand does not write `purpose: character sheet`.

### `studio-api/app/character_identity/four_view_sheet.py`

`attach_four_view_sheet_intent` skips `CRS_SINGLE_VIEW` the same as `CRS_GENERATION`. `is_single_image_four_view` already treated `CRS_SINGLE_VIEW` as a tile.

### Existing tests (assertion only)

Law-view **job bodies** are now `CRS_SINGLE_VIEW`. Pack / identity packet `task` stays `CRS_GENERATION`.

- `tests/test_crs_law_views.py`
- `tests/test_cc_single_job_sheet.py`
- `tests/test_four_view_sheet.py`
- `tests/test_character_identity_packet.py` (job body only)
- `tests/test_crs_advance_optional_coverage.py` (fake four-view polluter must also match `CRS_SINGLE_VIEW`)

## AUTO order

1. Advertised FLUX → `flux.txt2img`, or `flux.img2img` when an identity crop exists.
2. Else Qwen → `qwen2512.txt2img`.
3. Never silent-sub to zimage / illustrious / Krea. Never default `qwen2512.ref`.

## Gate

`validate_crs_single_figure`:

1. Collage heuristic (PIL 2x2 gutters) → `CRS_SINGLE_VIEW_COLLAGE`.
2. Grounding DINO person boxes when geometry models are present → count `person`.
3. `detected_figures == 1` → pass.
4. `detected_figures != 1` → `CRS_SINGLE_VIEW_MULTI_FIGURE`.
5. Neither can verify → `single_figure_pass: null`, no failure code. **Do not fake-pass. Do not fallback.**

`view_angle_pass` is always `null` (not invented).

## Fallback

`should_fallback_to_qwen` is true only when:

- hard fail (`single_figure_pass is False`)
- family is `flux`
- `autoSelect` is true
- job is not already `crsSingleFigureFallback`

Then enqueue one `qwen2512.txt2img` CRS_SINGLE_VIEW job for that view only. No extras. No second FLUX retry. Explicit FLUX does not fallback.

## Tests (measured)

```text
studio-api/.venv python -m pytest
  tests/test_character_creator_single_crs.py
  tests/test_flux_crs_prompt.py
  tests/test_crs_single_figure_gate.py
  tests/test_crs_law_views.py
  tests/test_crs_advance_optional_coverage.py
  tests/test_queue_worker_crs_four_view_pin.py
  tests/test_character_identity_packet.py
  tests/test_cc_single_job_sheet.py
  tests/test_four_view_sheet.py
-q --tb=short
```

Result: **60 passed**, 5 warnings. No Playwright. No Comfy generation.

## Out of scope (unchanged)

Approve/Reject, Korri Rev 3, SD 1.5, frontend, Vercel, `:8758` / Comfy restart, view-angle vision, new scoring engine.

## Limitation

Without DINO and without a collage hit, the tile is **unverified**. It is not accepted as a proven one-figure pass and it does not trigger Qwen fallback.
