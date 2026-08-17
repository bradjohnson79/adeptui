# Image Generator — Cinematic Color Grade Certification

**Date:** 2026-08-17  
**Branch:** `beta`  
**HEAD at cert:** recorded at commit time  
**Scope:** Creator-facing Storyboard category removed; Cinematic Color Grade presets compile into Image Plan / provider prompts. No LUT engine.

## Verdict

**GO — IMAGE GENERATOR CINEMATIC COLOR GRADE REFINEMENT CERTIFIED**

## What changed

- Category dropdown no longer lists Storyboard. Default category is **General**.
- Internal `ImageCategory` still includes `"storyboard"` for Storyboard Studio generate.
- Lighting & Color **Color** select removed. One **Cinematic Color Grade** dropdown lives in Image Plan.
- Presets in `studio-api/app/image_studio/color_grades.py` compile to a short `Color grade:` clause.
- Natural / missing / unknown → no extra prompt tokens.
- Provenance stores `colorGradePreset` beside existing `colorTreatment`.

## Tests

```text
studio-api/.venv/Scripts/python.exe -m pytest tests/test_color_grade_compile.py tests/test_m48_m49_contracts.py tests/test_m42_w3_image_product.py -q
```

Playwright (Beta `:8760` / API `:8758`, Schnick Coffee):

```text
npx playwright test tests/e2e/storyboard/storyboard-production-workflow.spec.ts --project=chromium
2 passed
```

Live compile-preview on Schnick Coffee:

- Natural: `Korri tastes Schnick Coffee. Purpose: general.` (no Color grade clause)
- Teal & Orange: includes `Color grade: Teal & Orange — cool teal shadows; warm skin and highlights; cinematic contrast; restrained saturation.`

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | Category General; Color Grade Teal & Orange |
| Frontend | PASS — Storyboard absent from Category; grade dropdown visible |
| API | PASS — compile-preview stores `colorGradePreset=teal_orange` |
| Backend | PASS — `expand_prompt` injects clause |
| Persistence | PASS — provenance field on cinematic metadata |
| Runtime | N/A (no extra GPU jobs required for grade) |
| Result | PASS — Natural vs Teal prompts differ |
| Reload | N/A |
| Downstream | N/A |

## Limitations

- Grade is prompt-time only. No LUT, CSS filter, or per-provider grade fork.
