# Global Character / Prop / Environment Asset Scope

> **SUPERSEDED (2026-09-16).** Historical checkbox-era report. Current governing evidence for Global Character / Prop / Environment identity: `docs/release-gate/creators/GLOBAL_CREATOR_WIRING_CONVERGENCE_CERTIFICATION.md`. Voice-progress pairing remains historical in `docs/release-gate/voice/VOICE_PROGRESS_AND_GLOBAL_ASSET_SCOPE_CERTIFICATION.md`.

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7`  
**Governing contract:** one `isGlobal` / `is_global` field. Global means cross-project visibility inside this Adept workspace. It does not copy records, drop owning `projectId`, or change tags.

---

## DATA FIELD

Canonical: `isGlobal` (JSON / Pydantic) and `is_global` (SQL / snake_case).  
Index table: `creator_asset_scope` (M036).  
Owning `projectId` is always retained.

## DEFAULT

OFF (`false`) for new and existing assets. Existing rows are not auto-promoted.

## CHARACTER CREATOR

`[ ] Global (?)` next to Name in `CharacterProfileForm`.  
Create/PATCH persist `is_global`. List = owning project OR `is_global`.

## PROP CREATOR

Same checkbox in Name / Style (Standard) and Name (Advanced).  
`POST /api/prop-creator/.../props` accepts `is_global` / `isGlobal`.

## ENVIRONMENT CREATOR

Name + Global on the planning surface.  
Generate context carries `name` / `isGlobal`.  
`PATCH /api/environment-reference-sheets/projects/{id}/{sheetId}/identity` saves Name / Global on an existing sheet.

## PROJECT QUERY

`project_id = :current` (characters SQL; props local traits; environments local sheet files).

## GLOBAL QUERY

`OR is_global = true`, plus `creator_asset_scope` index for props/environments (no N-project fan-out). Deduped by entity id.

## DROPDOWNS

Image Generator, Entity Picker, Character Compact, Prop saved-select include project + global items. Other-owner globals labeled `Global` or grouped.

## GROUPING

PROJECT = owned by the current project (even if also global).  
GLOBAL = other owners. No duplicate if the current project owns the row.

## TAG COLLISION

Visible-scope collision is blocked (`TAG_COLLISION` / 409).  
Local-vs-local in different projects is allowed. A new Global tag may not match any visible tag.

## EDIT OFF→ON

PATCH / upsert / identity persist `isGlobal=true`. Live: character and environment toggled ON after OFF.

## EDIT ON→OFF

Same path. Live: after OFF, Project B lists no longer include the asset; Project A GET still returns the same id.

## REFERENCE DURABILITY

`get_profile_by_id`, `load_entity_for_reference`, and `resolve_readable_asset` resolve by canonical id after Global is turned off. Existing scene `identity_id` bindings are not rewritten on OFF. New pickers outside the owner hide the asset.

## DELETE SAFETY

Global delete calls `require_delete_safety`. Cross-project scene bindings → `409 GLOBAL_IN_USE` until `confirm_cross_project=true`. UI confirms. Project-local delete unchanged (plus in-project reference checks).

## TIMELINE

Character / Prop / Environment pickers use the same list APIs that now return project + global. Once selected, generation uses the canonical entity id (no special path). `resolve_asset_file` and project asset file serving can read owner-project identity files for visible or already-bound globals.

## IMAGE GENERATOR

`AuthorityReferencePanel` lists project + global Character / Prop / Environment with PROJECT / GLOBAL optgroups.

## CO-DIRECTOR

`list_profiles`, `resolve_character_by_name`, project context, and ERS list include globals and `isGlobal`. Create draft character / create ERS accept `isGlobal`. “Make this environment global” persists through the Creator identity PATCH (no second registry).

## SAVE/RELOAD

Persisted on the canonical entity + scope index. Live PATCH OFF→ON→OFF survived list/get.

## PROJECT SWITCH

Live against Studio API `:8758` (`.runtime/_global_scope_e2e.json`):

| Check | Result |
| --- | --- |
| Character global visible in B, local not | PASS |
| Prop global visible in B, local not | PASS |
| Environment global visible in B, local not | PASS |
| Both visible in A | PASS |
| Character Global OFF hides from B, id remains on A | PASS |
| Environment Global OFF hides from B | PASS |

Projects: `Global Scope Project A` / `Global Scope Project B`.

## SECURITY

Global is workspace visibility, not public internet. Mutations stay on the owning project. File serving allows a viewing project only when the asset is a visible global identity or already referenced.

## PERFORMANCE

Globals are queried from `is_global` / `creator_asset_scope`, not by iterating every project.

## TESTS

- `studio-api/tests/test_creator_asset_scope.py` — 6 passed
- `studio-web/src/creatorScope.test.ts` — 3 passed
- Environment Creator Name/Global surface contract — 1 passed

## LIVE URLS

- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (`/api/healthz` 200)

## COMFY

- COMFY BEFORE: `:8188` HTTP 200
- COMFY AFTER: `:8188` HTTP 200, PID `34484` unchanged through API recycle
- COMFY RESTARTED?: NO
- WHY?: Ordinary API recycle only (`restart_studio_api_only.py`)

## LIMITATIONS

- Full Timeline GPU generate of a clip using a Global Character + Global Environment was not run (picker/query path live-verified; generation uses the same IDs).
- Library All / Project / Global filters were not added (optional; dropdown grouping is present).
- Environment first-create without Generate uses planning state + generate context; existing sheets use identity PATCH.

## FINAL VERDICT

**GO — GLOBAL CHARACTER / PROP / ENVIRONMENT ASSET SCOPE CERTIFIED**
