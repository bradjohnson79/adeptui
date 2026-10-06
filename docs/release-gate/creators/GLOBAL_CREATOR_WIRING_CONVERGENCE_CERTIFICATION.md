# Global Character / Prop / Environment Wiring Convergence

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree includes this mission; not committed unless requested)  
**Governing:** this file. Supersedes `docs/release-gate/creators/GLOBAL_ASSET_SCOPE_CERTIFICATION.md` (checkbox-era).  
**Journey 1 before-JSON:** `docs/release-gate/creators/_JOURNEY1_GLOBAL_LIFECYCLE_BEFORE.json`

Global is **scope promotion**, not a copy. One entity id, one owning `project_id`, one canonical tag. Other projects list + read. Only the owner mutates.

---

## Verdict

**GO**

Unanimous independent review after repair loop:

| Reviewer | Model | First pass | Final |
| --- | --- | --- | --- |
| Kimi K3 Max | `kimi-k3-max` | DISAGREE — deleted characters resurrected via asset heal | **AGREE** |
| GLM 5.2 Max | `glm-5.2-max` | AGREE | **AGREE** |
| GPT-5.6 Sol | `gpt-5.6-sol-medium` | DISAGREE — foreign Global prop mutate paths; later dangling unlinks | **AGREE** |

---

## GO law (observed)

| Criterion | Result |
| --- | --- |
| Korri Global works; `@Korri` / slug `korri`; no `@NewCharacter` | PASS — id `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed`, owner Korri Anadriya |
| Cade present and persistent after reload | PASS — restored `85e37d4b-a32e-4374-888b-1389fc0b3720` Cade O'Connor, slug `cade-o-connor`, not duplicated |
| Venture remains Venture; description clean; PRS; Global; tag preserved | PASS — `2601f525-a32e-401a-bc1a-b17b1fe92817`, tag `venture-spaceship-4` (frozen; `VentureSpaceship` collides with leftover keystroke forks), description/notes empty after stripping leaked `prsAssetId=` markers, PRS `8593f29e-c028-4278-9dcf-67b7ff238862`, visible from Cade Scenes |
| Standard + Advanced Remove persist across reload | PASS — Playwright disposable project |
| WiringSmoke / GlobalTest gone and do not regenerate into owner catalogs | PASS — purged; smokes use disposable projects or delete-after; list filter last-resort |
| Character / Prop / Environment Global selectors clean | PASS — Playwright Character Creator select: Cade + Korri; no WiringSmoke / New Character |
| Project ↔ Global does not duplicate or corrupt identities | PASS |
| Co-Director + Timeline still resolve the same assets | PASS — Timeline `PromptNameBinding` / `resolve_binding_id` not reopened |
| Three-LLM unanimity | PASS after repair loop |

---

## E2E TRACE

| Step | Verdict |
| --- | --- |
| User action — promote Korri, open Cade Scenes Character Creator, inspect Venture, disposable Remove / Environment Global | PASS |
| Frontend — `characterSaveIntent` refuses placeholder name on update; Prop Description hydrates from `description` only; `groupScopeItems` unchanged | PASS |
| API — owner-aware GET/PATCH; foreign mutate 403 `OWNER_REQUIRED` | PASS |
| Backend — `creator_asset_scope` index; persist under owning `project_id` | PASS |
| Persistence — Character row / PropEntity JSON / ERS sheet; tag freeze; description sanitize | PASS |
| Runtime — no generation required for this gate | N/A |
| Result — same ids, tags, PRS, Cade present | PASS |
| Reload — GET hydrate + Playwright reload-safe Remove | PASS |
| Downstream — Co-Director selector; Timeline hydration contract unchanged | PASS |

---

## Implementation (no second Global schema)

Shared helpers in `studio-api/app/creator_scope/`:

- `load_visible_entity` / `require_owner_for_mutate` / persist under owner
- `canonical_tag` frozen on promote; rename is the only tag change
- `strip_machine_notes` — human description ≠ `prsAssetId=` / `adeptWorkingProp=` / `universalAdeptProp=`
- `is_ephemeral_creator_fixture` last-resort list filter
- `CreatorEntityTombstoneRow` — intentional delete is not healed back from Library assets

Character: ignore placeholder name/slug on update of a real identity; heal missing Cade only when this project claims `characterId` on assets/jobs **and** the id is not tombstoned.

Prop: load anywhere, mutate only as owner, `save_prop_entity` writes under `prop.project_id`. Standard Remove detaches `reference_asset_id`. Advanced angle Remove (`approve_angle(approved=False)`) clears the slot. Delete Prop unlinks `SceneReferenceBinding`, `SceneShot.prop_entity_ids`, and Spatial Map `propId` across every project when Global. Library bytes stay.

Environment: identity PATCH uses `load_visible_sheet` + owner 403; does not reset composite/views. Global delete unlinks bindings in every project.

---

## Tests

### Unit / API

`studio-api/tests/test_global_creator_wiring.py` + `studio-api/tests/test_creator_asset_scope.py`

**31 passed**

Includes: promote keeps id/tag/description; placeholder name never overwrites; tag freeze; description sanitize; owner-only mutate including generate/retry/identity/approve; detach-only Remove; fixture filter; Cade asset-heal; delete does not resurrect; Global prop delete unlinks foreign bindings.

### Frontend

`studio-web/src/components/character/useCharacterProfile.test.ts` + `studio-web/src/creatorScope.test.ts`

**58 passed** (intended files). Vitest also discovered a stale `.adept-tmp` copy that cannot import `react`; ignored.

### Playwright (live, `ADEPT_BETA_TARGET=1`, chromium)

`tests/e2e/creators/global-creator-wiring-convergence.spec.ts`

**2 passed** (14.0s last run)

- Non-destructive: Korri promote + Cade selector + Venture description/PRS
- Destructive: disposable Standard/Advanced Remove + Environment Project → Global → reload

### Runtime

- Studio API recycled only (`scripts/restart_studio_api_only.py`)
- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200

```text
COMFY BEFORE: PID 34484 / healthy (observe-only GET)
COMFY AFTER:  PID 34484 / healthy
COMFY RESTARTED?: NO
WHY?: Ordinary creator-wiring work. API recycle only. Supervisor reported comfyPid=34484 unchanged=True on every recycle.
```

MCP `system_stats` observed a Comfy Desktop argv on this machine. This mission did not adopt, kill, or restart `:8188`.

---

## Review loop (required)

1. **Kimi K3 DISAGREE** — `list_profiles` heal resurrected deleted characters because `delete_profile` kept Library assets with `characterId` and recorded no tombstone.  
   **Repair:** `mark_entity_deleted` / `is_entity_deleted`; heal skips tombstones. Test `test_deleted_character_does_not_resurrect_from_library_assets`.
2. **GPT-5.6 Sol DISAGREE** — `generate_candidates` / `retry_candidate` / `use_as_prop_identity` / `approve_candidate` used `get_prop` and could mutate a visible Global from a viewing project.  
   **Repair:** those paths + Advanced sheet cancel use `require_owned_prop`. Stopped writing `identitySource=` into notes.
3. **GPT-5.6 Sol DISAGREE** — `delete_prop` left `SceneReferenceBinding` dangling.  
   **Repair:** `_unlink_scene_bindings` (all projects when Global).
4. **GPT-5.6 Sol DISAGREE** — SceneShot / Spatial Map pointers only unlinked in the owner project.  
   **Repair:** `_unlink_scene_shots` / `_unlink_spatial_props` fan out when Global.
5. **GPT-5.6 Sol DISAGREE** — SceneCraft `SpatialProfilePointers.propIds`.  
   **Not repaired in product code.** v1.1 Spatial/SceneCraft shelf: incomplete SceneCraft must not block v1.1 GO. Reviewer then **AGREE** on the scoped creator stores.

Kimi K3 and GLM 5.2 **AGREE** on the final diff. GPT-5.6 Sol **AGREE** on the scoped creator stores.

---

## Limitations (honest, not blockers)

- Cade Scenes **Wiki** still lists historical WiringSmoke / CharacterGlobalTest names (wiki document, not the Character Creator selector).
- Dozens of leftover keystroke local Prop forks (`Venture s`, `Venture Spac`, …) remain. They are not the Global Venture and were not deleted.
- Venture human description is empty after stripping leaked machine markers. Original prose had already been overwritten before this mission.
- Venture tag stays `venture-spaceship-4` because `VentureSpaceship` collides with leftover forks. Freeze-on-promote is working as specified.
- SceneCraft `scene_production_handoff` Spatial Profile `propIds` is outside v1.1 creator-wiring scope.
- Timeline `PromptNameBinding` / `resolve_binding_id` unchanged.

---

## Manual review

1. Open `http://127.0.0.1:5173/co-director?projectId=<Cade Scenes>`
2. Character Creator → Saved Characters includes **Cade O'Connor** and Global **Korri**; no WiringSmoke / New Character
3. Korri Anadriya → Korri is Global; slug `korri`
4. Prop Creator → Global **Venture Spaceship** description has no `prsAssetId=`; Advanced PRS still present
5. Do not restart Comfy

---

## Binary

**GO**
