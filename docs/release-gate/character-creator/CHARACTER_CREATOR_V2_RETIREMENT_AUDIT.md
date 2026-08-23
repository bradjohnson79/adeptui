# Character Creator V2 — Retirement Audit

**Status:** GOVERNING for Character Creator V2 retirement  
**Date:** 2026-08-23  
**Branch:** `feat/character-creator-final-closure`

Four-view / collage / contact-sheet generation is retired as the Character Creator **default**. Shared character identity, Library, JobQueue, entity resolver, and CRS persist are preserved.

## Classification key

- `DELETE` — stop using as Character Creator default; remove or rewrite callers/tests that encode four-view-as-complete
- `PRESERVE SHARED INFRASTRUCTURE` — keep
- `PRESERVE DATA CONTRACT ONLY` — keep types/roles; do not keep four-view generate behavior
- `USED ELSEWHERE — DO NOT DELETE`

## Frontend

| Item | Classification |
|---|---|
| `studio-web/src/components/character/CharacterCore.tsx` | PRESERVE SHARED — add `mode: express\|standard`; replace four-view generate |
| `CharacterSheetGenerator.tsx` / `characterSheetGenerate.ts` | DELETE as default generate path — V2 per-view cards replace it |
| `characterGeneratorPlan.ts` `VIEWS_PER_SHEET = 4` | DELETE default math |
| `CharacterCandidateGrid.tsx` | USED ELSEWHERE / unused by Core — do not resurrect |
| `CharacterProfileForm.tsx` / `useCharacterProfile.ts` / `CharacterActions.tsx` | PRESERVE SHARED |
| `CharacterCompactView.tsx` | PRESERVE SHARED — Express mount (`mode=express`) |
| `CharacterProfileWorkspace.tsx` Visual Gates four-view POST | DELETE default — point at V2 or disable |
| `TimelineCharacterCreatorPanel.tsx` four-view POST | DELETE default |

## Backend generate

| Item | Classification |
|---|---|
| `start_visual_sheet_generation` four-view enqueue | DELETE as CC default — collapse retired four-view requests to Front-only |
| `start_crs_view_generation` | PRESERVE SHARED — one view job |
| `_enqueue_txt2img` / JobQueue / prompt-ID bind | PRESERVE SHARED |
| `FOUR_VIEW_SHEET_PROMPT` / collage strengthen | DELETE as CC default |
| `four_view_sheet.py` layout assess | PRESERVE DATA CONTRACT ONLY (diagnostics; not identity) |
| `character_sheet_compose.py` 5-view labeled | PRESERVE SHARED for isolated law; V2 adds 21:9 preset |
| `approve_character_candidate` / `persist_crs_in_session` | PRESERVE SHARED |
| `create_profile` / `update_profile` | PRESERVE SHARED |
| `entity_resolver.resolve_character` | PRESERVE SHARED — add `@MiraVale` alias |
| `register_character_canon` | PRESERVE DATA CONTRACT — extend to require vision lock |
| `chat_vision` | USED ELSEWHERE (ERS/Scene) — reuse, do not clone |
| `propose_visual_sheet` 4-candidate / four-view pack | DELETE as default |

## Tests that encoded four-view-as-complete

Rewrite to V2 (Front-only ACTIVE; sheet after Front+Back+Rev 2). Do not keep them green by faking four views.

- `studio-web/src/components/character/characterSheetGenerate.test.ts`
- `characterSheetStage.test.ts`
- `activeCrsCard.test.ts`
- `studio-api/tests/test_cc_single_job_sheet.py`
- `test_character_creator_4view_json.py`
- `test_four_view_sheet.py` (CC default assertions)
- `test_character_identity_packet.py` (CC default requiredViews)

## Docs superseded (Law 30)

Mark HISTORICAL / SUPERSEDED BY CHARACTER CREATOR V2:

- `CHARACTER_CREATOR_SIMPLIFICATION_COMPLETION_REPORT.md`
- `CHARACTER_CREATOR_CRS_SHEET_CERTIFICATION.md`
- `CHARACTER_CREATOR_SINGLE_CRS_CERTIFICATION.md`
- `CHARACTER_SHEET_UNBLOCK_COMPLETION_REPORT.md`
- `PER_GENERATOR_SHEET_BATCHES_COMPLETION_REPORT.md`
- `crs-sheet-audit.md`
- `FLUX_CRS_AUTO_ONE_FIGURE_HANDOFF.md`

Keep as process (not V2 product contract): `FULL_STACK_CERTIFICATION_ADDENDUM.md`  
Lifecycle controls report remains historical unless V2 changes save/reset/delete.

## Do not delete

Character CRUD, Library, jobs, CRS persist, `@` resolver, Supervisor, ERS, Scene, Spatial, Timeline architecture, certified Qwen/FLUX/Illustrious/Z-Image builders.
