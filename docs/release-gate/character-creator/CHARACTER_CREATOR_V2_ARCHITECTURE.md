# Character Creator V2 — Architecture

**Status:** GOVERNING product architecture  
**Date:** 2026-08-23

```text
JSON Rev 1 → Front (one job) → Approve Front → Co-Director vision lock → @Name ACTIVE
→ optional Back (JSON + lock + Front pixels) → JSON Rev 2 → optional 21:9 sheet
Standard only: optional Close-up (same-file face merge)
```

Activation = approved Front + Front vision lock `ok`. Back is required only for Rev 2 and the sheet. Close-up is never required.

## Layers

- **Save:** existing `create_profile` / `update_profile` (JSON revision 1, DRAFT)
- **Views:** `POST .../views/{front|back|closeup}/generate|approve` in `cc_v2.py`
- **Vision:** `chat_vision` on approved Front (lock), Front+Back (revision 2), optional Close-up
- **Canon store:** same `CharacterProfile` + `crs_canon` + trait `cc_v2` — no second JSON file
- **@Name:** `entity_resolver.resolve_character` + compact alias (`@MiraVale` = `Mira Vale`)
- **Sheet:** `compose_v2_character_sheet` — 2560×1080 PIL, FRONT | BACK | table; Standard close-up bottom-center
- **Downstream pixels:** approved Front (`visual_reference`), never the stitched sheet

## AUTO adapter

One locally ready Certified pair:

- Front: `flux.txt2img` (`character/flux/front` graph shape)
- Back from Front pixels: `flux.img2img` (`character/flux/back_from_front` — LoadImage + VAEEncode, denoise 0.35)

Never-default: SenseNova, MiniMax H3, Krea, draft/experimental edit. No silent Z-Image remap. If the selected adapter cannot bind Front pixels: `BACK_UNSUPPORTED`.

## Retired

Four-view / collage Character Creator default. `collapse_retired_required_views` maps old four-view requests to Front only. Leftover `start_visual_sheet_generation` does not auto-compose a collage from a Front-only pack.

## Express vs Standard

- Express (`CharacterCompactView` `mode=express`): Front, Back, sheet. No Close-up. No generator chrome.
- Standard (`CharacterProfileWorkspace` `mode=standard`): same + optional Close-up helper copy.
