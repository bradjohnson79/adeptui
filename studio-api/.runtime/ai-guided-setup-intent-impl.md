# AI-Guided Setup intent implementation

**Date:** 2026-08-14 14:54 PT  
**Scope:** smallest copy + mapping extension on the existing recommender. No new intelligence layer. No Character Creator edits. No commit/push/deploy. :8758 not bounced.

---

## Files changed

| Path | Change |
|---|---|
| `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx` | Production-first copy; film/commercial/presenter/storyboard reason branches; intent-aware top-4 ranking |
| `studio-api/app/setup/lifecycle/service.py` | `bestFor` + tags on existing video/avatar/voice/image IDs; `recommendation_reason` branches; `fal_key` no longer owns "commercial" |
| `studio-api/tests/test_setup_lifecycle.py` | Intent table for the six production prompts plus keep-image cases |
| `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` | New placeholder; keep anime assertion; add short-film reason |
| `docs/setup/ai-guided-setup/certified-image-catalog.md` | One recommendation paragraph for film/video/presenter/storyboard |
| `docs/setup/ai-guided-setup/codirector-catalog-truth.md` | Three catalog-truth example rows |
| `studio-web/dist/` | Rebuilt so :8760 serves the new copy |

Not edited: Character Creator, catalog.py, status.py, verify_component, router, Co-Director tools, SetupWizard.tsx.

Workspaces that are **not** setup catalog IDs (Scriptwriter, Character Creator, Prop Creator, Spatial Map, Scene Creator, Timeline, MAGI, Brand Studio) were not invented. Mapping uses only IDs that already exist in `setup/catalog.py`.

---

## New visible copy

| Surface | New string |
|---|---|
| Heading | `AI-Guided Setup` (unchanged) |
| Support | `Tell Adept UI what you want to create. We'll recommend the tools, models, and production setup you need.` |
| Label | `What are you trying to create?` (unchanged) |
| Default input | `make a short film` (replaces `photoreal character`) |
| Placeholder | `Describe the film, video, scene, or production you want to create...` |
| Helper | `Try prompts like "make a short film", "make a commercial", or "make a branded product video".` |
| No chip UI | none added |

Image-only examples remain matchable (`photoreal character`, `anime poster`, `fast preview`, `product mockup`) even though they are no longer the default helper.

---

## Sample recommendation lists

From in-process `search_components` (new `service.py`). Live `GET /api/setup/lifecycle/components?query=` on :8758 still serves the **old** process because the API was not bounced.

### Make a short film (7)

| ID | statusLabel | reason |
|---|---|---|
| `hunyuan_video_15` | Ready | Best fit for short-film and cinematic video generation. |
| `hunyuan_video_13b` | Ready | Best fit for short-film and cinematic video generation. |
| `wan_models` | Ready | Best fit for short-film and cinematic video generation. |
| `ltx_checkpoint` | Ready | Best fit for short-film and cinematic video generation. |
| `index_tts2` | Ready | Matches the requested capability tags and certified setup posture. |
| `ace_step_local` | Ready | Matches the requested capability tags and certified setup posture. |
| `pack_essential_cinematic` | Ready | Matches the requested capability tags and certified setup posture. |

### Make a commercial (3)

| ID | statusLabel | reason |
|---|---|---|
| `wan_models` | Ready | Best fit for commercial and branded product video. |
| `index_tts2` | Ready | Matches the requested capability tags and certified setup posture. |
| `ace_step_local` | Ready | Matches the requested capability tags and certified setup posture. |

`fal_key` is **not** in this set. Query `commercial` alone also excludes `fal_key` (bestFor narrowed to `hosted image APIs`).

### Make a branded product video (3)

| ID | statusLabel | reason |
|---|---|---|
| `wan_models` | Ready | Best fit for commercial and branded product video. |
| `flux1_dev_local` | Ready | Matches the requested capability tags and certified setup posture. |
| `mmaudio_local` | Ready | Matches the requested capability tags and certified setup posture. |

This set differs from commercial: product stills (`flux1_dev_local`) + product SFX (`mmaudio_local`), no character-specific IDs.

### Other mapped prompts (for the test table)

- **Make an anime episode:** `hunyuan_video_15` (anime episode video) + `sana_15_local` / `qwen_image_2512_models` / `zimage_models` / `pack_essential_anime`
- **Create a talking presenter:** `longcat-video-avatar-1-5-local` Repair Required, `infinitetalk-local` Repair Required, `musetalk-1-5-local` Repair Required, `echomimic-v2-local` Not Installed, `index_tts2` Ready. Honest lifecycle labels; not treated as missing.
- **Make a storyboard:** `flux1_dev_local`, `pack_essential_cinematic`, `ltx_checkpoint`, `ltx_2_5_checkpoint` (existing previs IDs; no fake storyboard installer)
- **photoreal character:** `flux1_kontext_dev_local` Ready (kept)
- **anime poster:** Sana / Qwen / Z-Image / anime pack (phrase now in bestFor)
- **fast preview:** `flux1_schnell_local` (kept)
- **product mockup:** `flux1_dev_local` + `qwen_image_2512_models` (image-only, not video)

---

## Readiness

Unchanged path: catalog → `verify_component` → `lifecycle_state`. Empty `bestFor` means unmapped, not missing. Video models that were already Ready stay Ready. Avatar Repair Required / Not Installed stay visible.

---

## Tests

```
studio-api/.venv python -m pytest tests/test_setup_lifecycle.py -q
18 passed in 49.56s
```

New coverage: short film, commercial (not fal_key), branded product video (differs from commercial), anime episode, talking presenter, storyboard, plus keep-image photoreal / anime poster / fast preview. `statusLabel` asserted to come from `lifecycle_state`.

Playwright not run (per mission). E2E placeholder/example assertions were updated in source.

`tsc -b` still fails on a pre-existing `SetupWizard.tsx` error (untouched). Dist was produced with `vite build` only.

---

## :8760 bundle

- Previous: `index-6gpd03hm.js`
- **Now serving:** `index-m-23d3b1.js`
- Confirmed `http://127.0.0.1:8760/` HTML references the new hash and the bundle contains the new copy (not the old image-only placeholder).

:8758 was not restarted. Live lifecycle search will pick up the new mappings only after the next API start.
