# Character Creator V3 — Architecture

**Status:** GOVERNING product architecture  
**Date:** 2026-08-24  
**Supersedes:** [`CHARACTER_CREATOR_V2_ARCHITECTURE.md`](./CHARACTER_CREATOR_V2_ARCHITECTURE.md) (historical)

```text
Profile + optional reference
  → selected image generator creates ONE Front (T2I or I2I)
  → Approve Front → Co-Director vision lock → @Name ACTIVE
  → Generate Character Angles (Qwen Image Edit 2509) → Side / 3/4 / Back
  → Approve useful angles → optional serialized upscale
  → Co-Director enriches the SAME character JSON (CONFIRMED_BY_MULTIVIEW)
  → Deterministic 21:9 / 2560×1080 Character Reference Sheet
Standard only: optional Close-up from the selected generator I2I after Front lock
```

Activation remains approved Front + visual lock `ok`. Close-up is never required. Multi-view is required for the V3 sheet, not for `@Name`.

## Responsibilities

| Owner | Owns |
| --- | --- |
| Image generator (Qwen / FLUX / Z-Image / Illustrious / API) | Canonical Front only. Optional Close-up. |
| Character Angles engine (`qwen_image_edit_2509`) | Side, 3/4, Back from approved Front pixels |
| Co-Director | Auto-Prompt, Front lock, `@tag`, same-file JSON enrichment |
| RealESRGAN (existing MAGI isolated runtime) | Optional serialized upscale |
| Pillow compositor | 21:9 sheet layout |

Wonder3D is **not** a Front generator dropdown option. Character Angles is a named adapter (`engine=qwen_image_edit_2509`), never `generate_view("back")` and never a silent Front-family swap.

## State

Same `CharacterProfile` + trait key `cc_v2` (schema field `cc_v3`). No second JSON file.

- `views.front` / `views.closeup` — generator jobs
- `views.back` — **legacy hydrate only**. `generate_view("back")` returns `BACK_RETIRED`
- `multiView.angles.{side,three_quarter,back}` — individual canon assets
- `multiviewEnrichment.provenance = CONFIRMED_BY_MULTIVIEW`

## GPU law

One heavyweight GPU task: Front, Close-up, Character Angles, or one upscale. Backend 409 `JOB_ACTIVE`. Buttons alone are not enough.

## Sheets

Express: Front | Side | balance · 3/4 | Back | JSON  
Standard with Close-up: Front | Side | Close-up · 3/4 | Back | JSON  
Skip Close-up → Express. Sheet is derived, never the identity source.

## Character Angles engine (current)

Production engine is official **Qwen Image Edit 2509** (`Qwen/Qwen-Image-Edit-2509`, Apache-2.0). Setup `qwen_image_edit_2509_models` is the install target. `character_multiview_engine` is the readiness view. Ready requires Installed + Runtime + GPU + Model + License Clear. Files on disk never imply Ready.

Wonder3D remains rejected: published weights `flamehaze1115/wonder3d-v1.0` are **AGPL-3.0**. Setup `wonder3d_multiview` stays `license_blocked` forever. See [`MULTIVIEW_ENGINE_LICENSE_AUDIT.md`](./MULTIVIEW_ENGINE_LICENSE_AUDIT.md) and [`WONDER3D_FEASIBILITY_AND_RUNTIME.md`](./WONDER3D_FEASIBILITY_AND_RUNTIME.md).

## Krea

Krea 2 remains a shared Image Generator / Prop / Setup family. It is removed from Character Creator multi-angle and the CC Front roster. See [`KREA_RETIREMENT_AUDIT.md`](./KREA_RETIREMENT_AUDIT.md).
