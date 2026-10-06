# Character Creator — Character Profile not found repair

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure` @ `99665cf7` plus this working tree  
**Project:** Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`  
**Verdict:** **GO**

## Root cause

Cade was not a missing local profile. Cade Scenes had **no local Character Profile**. List returned only a foreign Global leftover from Global-scope certification:

| Field | Value |
| --- | --- |
| id | `c557e79f-2b43-43b4-8fc3-2f965cd2df43` |
| name | `TestGlobalCharacterf2dc3af3` |
| owner | `4e621501-cd80-498c-85f0-67c7ba9dd921` |
| `is_global` | true |

Express then:

1. Auto-selected `list[0]` (the foreign Global).
2. Hid **Create Character** once any listed character existed.
3. Let the creator type “Cade O'Connor” onto that foreign record.

Runtime before repair (live):

- `GET /characters/{id}` → 200 (visible Global)
- `PATCH` → 403 `OWNER_REQUIRED` (“Global characters can only be edited from the project that created them.”)
- `GET /cc-v2` → 404 `NOT_FOUND` (“Character Profile not found.”) because `_profile` required `row.project_id == request project_id`

The ownership warning was legitimate. The “Profile not found” banner was a **false 404** on a visible-but-unowned Global. Cade was never classified as Global; he had not been created as a local profile at all.

## Data-contract correction

- **Read** remains visibility: local to this project **or** `is_global`.
- **Mutate / generate / cc-v2** requires ownership: `row.project_id == request project_id`, else `403 OWNER_REQUIRED`.
- Express/Standard **never auto-select** a foreign Global.
- **Create Character** stays available even when Globals exist.
- New Character → `POST /characters` → returned id becomes the active Character Creator id → subsequent GET/PATCH/cc-v2 use that id, not name match.
- If a local canonical id still has versions/refs/assets but the profile row is gone, `get_profile` / `require_owned_profile` **reconcile the same id** (no duplicate Cade). Foreign Globals are never re-homed.

## Files

- `studio-api/app/character_identity/service.py`
- `studio-api/app/character_identity/cc_v2.py`
- `studio-api/app/character_identity/visual_sheet.py` (Flux compile call no longer passes unknown `role`/`view` kwargs — this 500’d Front generate)
- `studio-web/src/creatorScope.ts`
- `studio-web/src/components/CoDirector/characters/CharacterCompactView.tsx`
- `studio-web/src/components/CharacterProfileWorkspace.tsx`
- `studio-web/src/components/character/CharacterCore.tsx`
- `studio-web/src/components/character/CharacterV2Studio.tsx`
- `studio-web/src/components/character/useCharacterProfile.ts`
- Tests: `test_creator_asset_scope.py`, `creatorScope.test.ts`, `useCharacterProfile.test.ts`, `tests/e2e/character-creator/character-creator-cade-profile-bind.spec.ts`

## Tests

| Suite | Result |
| --- | --- |
| `pytest tests/test_creator_asset_scope.py` | 9 passed |
| `pytest tests/test_flux_crs_prompt.py` | 4 passed |
| vitest creatorScope + useCharacterProfile + V2 presence | 41 passed |
| Playwright `character-creator-cade-profile-bind.spec.ts` (live :5173/:8758) | 1 passed (8.5s) |
| Independent review ([Review](26e788bf-85d9-473c-b1d7-3dda278888bc)) | READY FOR PRIMARY REVIEW — no blockers, guard intact, no band-aids |

## Live chain (Cade Scenes)

| Step | Evidence |
| --- | --- |
| Create / Save Cade | id `85e37d4b-a32e-4374-888b-1389fc0b3720`, `project_id` = Cade Scenes, `is_global=false` |
| Reload / reopen | Playwright + Standard workspace restore Cade by id |
| Profile GET | 200, same id, not name-matched |
| Front generate | job `84839d2d-…`, asset `d54a365d-…`, approved, vision lock `ok` |
| Angles | side `f6a82fbf-…`, 3/4 `58a5b67b-…`, back `398c575d-…`, all approved |
| Character Sheet | asset `65b25f99-…`, phase `SHEET_READY` |
| CRS persist | `character_id=85e37d4b-…`, approved reference = sheet, `canon_status.approved`, revision 2 |
| Foreign Global | `GET /cc-v2` and `PATCH` still **403 OWNER_REQUIRED**; UI form disabled + ownership copy; no “Profile not found” |

Review URLs: `http://127.0.0.1:5173/` (Character Creator on Cade Scenes), `http://127.0.0.1:8758/`.

## Runtime

- `COMFY BEFORE:` PID 34484 / health 200  
- `COMFY AFTER:` same PID 34484 / health 200  
- `COMFY RESTARTED?:` **NO**  
- Studio API recycled only (`24104` → `21868` → `38080`) to load the repair.

## Limitations

- Cade Front is a Flux txt2img from a short written profile (no photo reference). The first Front showed more than one figure. That is a generator-quality issue, not the profile-bind defect. Angles and the composed sheet still attached to Cade’s canonical id.
- Gender was patched as `man`; the form options use `male`, so Gender may show “Select…” until the creator picks an option.
- Leftover cert Global `TestGlobalCharacterf2dc3af3` remains listed under Global and stays correctly read-only in Cade Scenes.

## Verdict

**GO** — local Cade profile persists, binds by canonical id, reloads, generates Front / angles / sheet onto that same record, and a legitimate foreign Global still cannot be edited from Cade Scenes.
