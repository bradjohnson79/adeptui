# Image Generator — Library References + Accordion UX Certification

**Date:** 2026-08-17  
**Branch:** `beta`  
**HEAD at cert:** recorded at commit time  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`

## Verdict

**GO — IMAGE GENERATOR LIBRARY REFERENCES + ACCORDION UX CERTIFIED END TO END**

Independent: **VERIFIED — IMAGE GENERATOR LIBRARY REFERENCES + ACCORDION UX PASSED**

## Law

Library owns the image. Image Generator references it by canonical `assetId`. The selected generator consumes those pixels or tells the creator it cannot. Upload uses existing `POST /api/projects/{id}/assets`. Remove reference does not delete Library media.

## Tests

```text
studio-api/.venv/Scripts/python.exe -m pytest tests/test_library_reference_compile.py tests/test_color_grade_compile.py -q
10 passed
```

Playwright (Beta `:8760` / API `:8758`):

```text
npx playwright test tests/e2e/image-generator/library-refs-accordion.spec.ts --project=chromium
1 passed (7.1s)
```

Compile-preview on Schnick Coffee sent two Library `assetId`s and received the same IDs on `imageProductBody.referenceAssetIds` and `creativeContext.reference_image_ids`:

- `f13defaf-db54-426f-ae95-07ae77718394`
- `2acb4449-ff83-439e-abbb-ce75dd178668`

## Certification matrix

| Gate | Verdict |
| --- | --- |
| Upload Image to Library | PASS |
| Canonical Library asset | PASS |
| No duplicate upload store | PASS |
| Browser two-row / internal scroll | PASS |
| Search | PASS (existing search kept) |
| Multi-select | PASS |
| Add Reference | PASS |
| Active reference confirmation | PASS |
| Duplicate reference prevention | PASS (already-added cards disabled) |
| Remove preserves Library | PASS |
| Character / prop / location identity | PASS (Library `characterId` / `propId` / `sceneId`) |
| Provider capability honesty | PASS (chip ✓/⚠ from `metadata.capabilities.supportsReferences`; IDs not dropped) |
| No silent reference drop | PASS |
| Image Plan / References / Camera / Lighting / Hosted API / Continuity / Prompt Intelligence accordions | PASS |
| Hosted API visual formatting | PASS (when card present) |
| Prompt Intelligence visual formatting | PASS |
| General default / Color Grade regression | PASS |
| Open Storyboard untouched | PASS |
| Reload | PASS (Library upload remains; accordion layout sane; refs remain ephemeral per existing CIS state) |
| Playwright | PASS |
| Independent visual | PASS |

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | Upload → select 3 → Add Reference → remove 1 → accordions → compile-preview |
| Frontend | PASS |
| API | PASS — compile-preview carries Library `assetId`s |
| Backend | PASS — `compile.py` merges `referenceAssetIds` into `intent.referenceIds` |
| Persistence | PASS — upload remains Library media after reload |
| Runtime | N/A (no extra GPU job; compile inspection) |
| Result | PASS |
| Reload | PASS |
| Downstream | N/A |

## Limitations

- Active reference chips are session state (same as prior `refIds`); they are not a new backend store.
- No invented max-reference count: certified capabilities currently expose boolean `supportsReferences` only.
- `studio-web` `tsc -b` is still blocked by unrelated dirty Timeline/Magi files; this milestone built dist with `vite build`.
