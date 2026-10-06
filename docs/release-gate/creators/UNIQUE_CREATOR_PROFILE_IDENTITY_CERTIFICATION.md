# UNIQUE CREATOR PROFILE IDENTITY / ZERO DUPLICATES

Governing certification for Character / Prop / Environment canonical name uniqueness.

Date: 2026-09-16  
Branch: `feat/character-creator-final-closure`  
Studio API: `http://127.0.0.1:8758/` (PID 13744 after recycle)  
Creator UI: `http://127.0.0.1:5173/`  
Comfy `:8188`: PID 34484, health 200, **not restarted**

## NAME NORMALIZER

Shared `normalize_profile_name` / `normalizeProfileName`:

- trim
- collapse internal whitespace
- case-insensitive (`casefold` / `toLowerCase`)

Display names keep the creator's capitalization. Comparison only uses the key.

One implementation:

- `studio-api/app/creator_scope/contract.py`
- `studio-web/src/creatorScope.ts`

## BACKEND UNIQUE GUARD

`require_unique_profile_name` on create / rename / Local↔Global transition.

Conflict:

- HTTP **409**
- `PROFILE_NAME_ALREADY_EXISTS`
- `existingId`, `existingName`, `scope`, `type`

Wired through:

- Character `create_profile` / `update_profile`
- Prop `create_or_update_prop` (runs **before** `unique_tag`, so tag auto-suffix can no longer mint a second same-name Prop)
- Environment `check_environment_tag_collision` + create-without-id no longer silent-reuses by name

## DATABASE UNIQUE GUARANTEE

`creator_asset_scope.name_normalized` plus unique indexes:

- local: `(entity_type, owning_project_id, name_normalized)`
- global: `(entity_type, name_normalized) WHERE is_global = 1`

Live `CREATE UNIQUE INDEX` is skipped while leftover collisions remain in **other** projects (notably `beffd3d8` Venture typing-spam). Application 409 is the live authority. Live race test still produced exactly one success + one 409.

## LOCAL SCOPE

Name must be unique among visible profiles of that type in the current project (locals + visible globals).

## GLOBAL SCOPE

A second Global with the same normalized name is blocked.

## LOCAL/GLOBAL COLLISION

Live: Global `GlobalCollisionTest *` in Project A, then local same name in Project B → **409**.

## CHARACTER

Create + different capitalization → 409. Self-rename allowed.

## PROP

`Cade's Starfighter` and ` cade's starfighter ` → 409 against `6868078f-cda7-4427-8f85-fd318cf4a141`.

## ENVIRONMENT

Create then same name without `sheetId` → 409 (no silent overwrite).

## CO-DIRECTOR

Create tools reuse a visible canonical profile. They do not auto-suffix (`2`, `Copy`, `(1)`).

Live reuse:

> Cade's Starfighter already exists. I'll use the existing Prop profile.  
> existingId = `6868078f-cda7-4427-8f85-fd318cf4a141`

Tools:

- `character_creator.create_from_brief` / `create_from_script`
- `character.create_draft_character_profile`
- `prop_creator.create_profile`
- `ers.create_sheet`

## MANUAL CREATE

Inline collision UI on Prop (`Open Existing` / `Choose Another Name`). Character and Environment show the 409 message. Backend remains authoritative.

## UPLOAD/IMPORT

Upload binds to the selected existing Prop. A new profile still goes through `create_or_update_prop` uniqueness. No second same-name insert.

## RACE TEST

Two simultaneous POSTs, same Prop name, same project:

- statuses: **200**, **409**
- successes: **1**
- conflicts: **1**

## DELETE/RECREATE

Name is reserved until backend delete succeeds. After delete, the name may be used again.

## DRAFTS

Draft names reserve the canonical key. `New Character` cannot be created twice.

## EXISTING DUPLICATES FOUND

Cade Scenes (`fb24ff0f-8772-4d50-a602-ac69d14b5a6b`):

### CADE STARFIGHTER A

- ID: `8a79697b-4ecf-4428-a314-4f15370bf3df`
- scope: local (historical)
- assets: production Primary `8c07b994-…` (from prior live dump)
- references: **already gone** from the live store before this uniqueness merge
- status: **already deleted** (not present in `prop_entity` / `creator_asset_scope`)

### CADE STARFIGHTER B

- ID: `6868078f-cda7-4427-8f85-fd318cf4a141`
- tag: `cade-s-starfighter-2` (created by the old tag auto-suffix)
- scope: local, Project A
- assets: approved Primary `4d3a1e66-…`, PRS `6e8da820-…`, uploaded optional views present
- references: 0 scene bindings, 0 shots

### CANONICAL SURVIVOR

`6868078f-cda7-4427-8f85-fd318cf4a141`

A was already absent, so there was no second row to migrate. Library assets from A remain (profile delete does not wipe Library).

### REFERENCES MIGRATED

None required (A had no remaining bindings).

### DUPLICATE REMOVED

A already removed. Live list now has **exactly one** `Cade's Starfighter`.

Project A Character / Environment: **no** normalized name collisions.

Other-project leftover: many `Venture*` / typing-spam Props in `beffd3d8`. Not shown in Cade Scenes. New creates there will 409; historical rows were not mass-deleted.

## PROJECT DROPDOWN

One `Cade's Starfighter` under Project.

## GLOBAL DROPDOWN

Owned globals stay in Project (existing `groupScopeItems` ID dedupe). No second Cade row.

## SAVE/RELOAD

List after recycle still has one Cade's Starfighter. Create still 409.

## CONSOLE / NETWORK

Expected 409s only. No duplicate POST retry loop in the save path. Smoke leftovers deleted.

## TESTS

- API: `test_creator_asset_scope.py` uniqueness + `test_environment_creator_save.py` — **10 passed**
- Frontend: `src/creatorScope.test.ts` — **6 passed**
- Live smoke: Prop exact/spaced, Character, Environment, Global×Local, race

## COMFY

- BEFORE: PID 34484 healthy
- AFTER: PID 34484 healthy
- RESTARTED?: **NO**

## FINAL VERDICT

**GO — UNIQUE CREATOR PROFILE IDENTITY / ZERO DUPLICATES CERTIFIED**
