# PROJECT_ENTRY_CONTRACT_CLOSURE

WHOLE-APPLICATION PROJECT ENTRY CONTRACT: **GO**

Live Beta target: `http://127.0.0.1:8760/`  
API target: `http://127.0.0.1:8758/`  
Closure date: `2026-08-03`

## Executive Summary

The application-side project-entry contract is materially repaired and revalidated on live Beta:

- `AppChrome`, `ProjectMenu`, and Co-Director project creation now route through the shared Home entry contract instead of silently calling `POST /api/projects`
- forced create cancellation now preserves the originating in-app context via `pendingReturnTo`
- direct root `/?setupMode=ai_guided...` waits for the Home project inventory to load before deciding whether to reuse an existing project or open the shared drawer
- the required live Beta Home audit passed after the fixes, backend name-validation coverage passed, and focused TypeScript entry tests passed
- after the handoff-loss investigation, live Beta now contains exactly one protected handoff project created through the Home UI flow: `Manual Beta Handoff` (`77a4b96c-8e3f-4501-897c-51bab99bedb7`)

The only closure blocker was handoff integrity. That blocker is now cleared: the originally protected handoff UUID `a7f665ce-c2d1-4e77-8aa0-b217cc977b56` was confirmed missing, one fresh replacement handoff was created on live Beta through the Home create flow, and the replacement now returns `GET 200` with the expected empty-ish scaffold state (`sceneCount = 1`, `assetCount = 0`, `chatCount = 0`, `wikiCount = 0`, `planCount = 0`, `proposalCount = 0`, `approvalCount = 0`, `jobCount = 0`, `exportCount = 0`).

## Scope Completed

### Inventory

- `studio-web/src/components/dashboard/AppChrome.tsx`
  - `Project -> Create project` routes to `buildHomeCreateProjectPath(...)`
  - now passes a `pendingReturnTo` path so cancel can return to the originating screen
- `studio-web/src/components/ProjectMenu.tsx`
  - inventoried as a legacy/unmounted surface in the current tree
  - aligned with the same `pendingReturnTo` create contract anyway because it was explicitly requested in scope
- `studio-web/src/codirector/execute.ts`
  - `createProject` no longer creates immediately
  - redirects into the shared Home flow with suggested name and `pendingReturnTo`
- `studio-api/app/schemas.py`
  - `ProjectCreate.name` trims and rejects blank names with `Project name is required.`
- `studio-web/src/pages/Home.tsx`
  - wired to `projectEntry.ts` helpers
  - waits for project inventory before resolving direct `ai_guided` setup entry
  - cancel from forced entry now returns to the originating route instead of dropping to `/`
- `studio-web/src/projectEntry.ts`
  - now carries a sanitized `pendingReturnTo` field and exposes `buildPendingProjectCancelDestination(...)`

### Silent-Create Repairs Finished

- fixed forced-create cancel handoff loss for project and Co-Director entry paths
- fixed root `ai_guided` entry timing so existing projects can be reused after Home finishes loading
- added focused tests for both repaired paths

## Silent-Create Matrix

| Entry surface | Current behavior | `POST /api/projects` before explicit create? | Coverage | Notes |
| --- | --- | --- | --- | --- |
| Home chrome `Project -> Create project` | Opens shared Home drawer | No | `home-project-entry-closure`, `home-project-creation-audit` | Confirmed on live Beta |
| Project chrome `Project -> Create project` | Routes through Home drawer with `pendingKind=project` and `pendingReturnTo` | No | `home-project-entry-closure` | Cancel now returns to source project |
| Co-Director `createProject` action | Routes through Home drawer with `pendingKind=co-director` and `pendingReturnTo` | No | `execute.project-entry.test.ts`, `home-project-entry-closure` | Cancel now returns to Co-Director |
| Root `/?setupMode=ai_guided&setupSource=workspace_launch` with zero projects | Opens shared drawer | No | `home-project-creation-audit` | Confirmed on live Beta |
| Root `/?setupMode=ai_guided&setupSource=workspace_launch` with an existing project | Reuses existing project setup route | No | `home-project-creation-audit` | Confirmed on live Beta after fix |
| Explore cards with no project | Open shared drawer with pending destination | No | existing Home audit coverage plus shared drawer flow | Explicit create required |
| Template cards | Create immediately on template click | User-initiated explicit create | `home-project-creation-audit` | Not treated as silent create; deliberate one-click template action |
| Legacy `ProjectMenu` create | Routed through shared Home flow | No | inventory only | Surface appears unmounted in current tree |

## Handoff Snapshot

### Protected handoff snapshots captured during successful contract run

Artifact files:

- `docs/release-gate/home/artifacts/entry-contract/handoff-before.json`
- `docs/release-gate/home/artifacts/entry-contract/handoff-mid.json`
- `docs/release-gate/home/artifacts/entry-contract/handoff-after.json`

Observed snapshot values in all three files:

- `id`: `a7f665ce-c2d1-4e77-8aa0-b217cc977b56`
- `name`: `Manual Beta Handoff`
- `apiStatus`: `200`
- `sceneCount`: `1`
- `assetCount`: `0`
- `chatCount`: `0`
- `wikiCount`: `0`
- `planCount`: `0`
- `proposalCount`: `0`
- `approvalCount`: `0`
- `jobCount`: `0`
- `exportCount`: `0`

### Final live Beta handoff status

Direct investigation at the start of this follow-up:

- `GET /api/projects/a7f665ce-c2d1-4e77-8aa0-b217cc977b56` -> `404`
- response body: `{"detail":"Project not found"}`
- visible project count from `GET /api/projects`: `0`

This confirmed that the original protected handoff UUID was gone and that the live Beta project inventory had been fully emptied before restoration.

## Root Cause Analysis

### Root cause: later full beta-local reset deleted the handoff

The single best-supported root cause is a later execution of the full beta-local reset path, not the scoped Home entry cleanup.

Evidence:

- `tests/e2e/home/home-project-entry-closure.spec.ts` only deletes projects whose names start with that run's `ENTRY-CLOSURE-*` prefix, and it snapshots the protected handoff before, during, and after cleanup. In its `finally` block it explicitly skips any project name that does not start with the run id, then re-reads the handoff and expects it to remain unchanged.
- `scripts/reset_project_data.py` is materially different: with `--confirm-delete-all-projects`, it loads the live beta-local database path, enumerates **all** project ids, and deletes all project-owned rows plus the `projects` rows themselves. There is no protected-id allowlist or handoff exclusion in that deletion path.
- prior live-Beta Co-Director repair evidence explicitly records this destructive command against the same `8758` Beta target:
  - `studio-api\.venv\Scripts\python.exe scripts/reset_project_data.py --environment beta-local --confirm-delete-all-projects`
  - see `docs/release-gate/codirector-final/CODIRECTOR_RUNTIME_REPAIR_AND_UX_SUMMARY.md`
  - see `docs/release-gate/codirector-final/M214_CODIRECTOR_RUNTIME_REPAIR.md`
- the observed failure shape matched a full reset, not scoped entry cleanup: at investigation start the old handoff returned `404` and `GET /api/projects` returned `[]`.

Conclusion: the evidence supports a later full beta-local destructive reset as the handoff-deleting operation. No comparable evidence was found that the Home entry cleanup itself deleted the protected handoff.

## Replacement Handoff Restoration

The missing handoff was not recreated under the old UUID. Instead, one fresh replacement was created through the normal Home create flow on live Beta and then re-verified through the API.

Replacement handoff:

- `id`: `77a4b96c-8e3f-4501-897c-51bab99bedb7`
- `name`: `Manual Beta Handoff`
- create path: Home empty-state `Create Project` flow on live Beta

Final live Beta verification:

- final visible project count from `GET /api/projects`: `1`
- final visible projects:
  - `77a4b96c-8e3f-4501-897c-51bab99bedb7` / `Manual Beta Handoff`
- `GET /api/projects/77a4b96c-8e3f-4501-897c-51bab99bedb7` -> `200`
- `sceneCount`: `1`
- `assetCount`: `0`
- `chatCount`: `0`
- `wikiCount`: `0`
- `planCount`: `0`
- `proposalCount`: `0`
- `approvalCount`: `0`
- `jobCount`: `0`
- `exportCount`: `0`

## Cleanup Evidence

Earlier successful contract cleanup artifact:

- `docs/release-gate/home/artifacts/entry-contract/cleanup-summary.json`

Key evidence from that artifact:

- `runId`: `ENTRY-CLOSURE-2026-08-03T01-27-19-283Z`
- deleted `ENTRY-CLOSURE-*` project ids: `9`
- `remainingRunProjects`: `[]`

Current direct verification after restoration:

- visible `ENTRY-CLOSURE-*` projects: `[]`
- transient restore-side accidental projects were removed, leaving only the replacement handoff
- no unrelated project cleanup was performed

## Reviewer Synthesis

Seven independent GPT-5.4 reviewers were run and synthesized here:

- [Entry review 1](953c9e8c-ba8e-4a0b-b256-4e0139d1faf3)
- [Entry review 2](a04dc3e6-7086-4014-9e87-ece74493ae46)
- [Entry review 3](940fa7aa-3552-4e34-bf06-372bdf94b796)
- [Entry review 4](df02896b-b577-4d8d-a432-105cf314f9df)
- [Entry review 5](18a00231-3d8a-4c30-9df5-61b58b444808)
- [Entry review 6](8939951e-e904-4173-951a-0c3f62ee138f)
- [Entry review 7](acb8a045-bc34-4f47-b0c7-4d8c58f7c592)

Repeated reviewer findings:

- forced-create cancel returned to `/` instead of the originating context
- direct root `ai_guided` setup could decide before the project list finished loading
- `ProjectMenu` looks like a legacy/unmounted surface and needs to be called out honestly

Those repeated findings were repaired or documented in this closure pass.

Reviewer observations not treated as closure blockers here:

- template cards still perform explicit one-click creation by design
- backend `ProjectUpdate` rename validation is not aligned with `ProjectCreate` validation, but that is a project rename contract issue rather than the scoped project-entry silent-create contract
- stale-recents behavior outside the Home helper path merits future cleanup, especially for legacy surfaces

## Files Changed In This Closure Pass

- `studio-web/src/projectEntry.ts`
- `studio-web/src/pages/Home.tsx`
- `studio-web/src/components/dashboard/AppChrome.tsx`
- `studio-web/src/components/ProjectMenu.tsx`
- `studio-web/src/codirector/execute.ts`
- `studio-web/src/projectEntry.test.ts`
- `studio-web/src/codirector/execute.project-entry.test.ts`
- `tests/e2e/home/home-project-entry-closure.spec.ts`
- `tests/e2e/home/home-project-creation-audit.spec.ts`

## Beta Verification

- Restarted Beta after code changes with:
  - `powershell -ExecutionPolicy Bypass -File "C:\AdeptFilmWorks\AIVideoStudio\Restart-AdeptUI-Beta.ps1" -NoBrowser`
- Verified health with:
  - `powershell -ExecutionPolicy Bypass -File "C:\AdeptFilmWorks\AIVideoStudio\AdeptUI-Beta-Health.ps1"`
- Healthy ports confirmed:
  - UI `8760`
  - API `8758`
  - Comfy `8188`

## Test Commands And Results

| Command | Result |
| --- | --- |
| `npx playwright install chromium` | Passed; installed missing Playwright Chromium/browser runtime |
| `npx tsx --test "C:\AdeptFilmWorks\AIVideoStudio\studio-web\src\projectEntry.test.ts" "C:\AdeptFilmWorks\AIVideoStudio\studio-web\src\codirector\execute.project-entry.test.ts"` | Passed: `6 passed` |
| `python -m pytest tests/test_codirector_runtime_repair.py` | Passed: `9 passed` |
| `npx playwright test tests/e2e/home/home-project-entry-closure.spec.ts --project=chromium --reporter=line` | Passed after code fix + Beta rebuild: `1 passed (35.9s)` |
| `npx playwright test tests/e2e/home/home-project-creation-audit.spec.ts --project=chromium --reporter=line` | Passed after code fix + Beta rebuild: `1 passed (20.1s)` |
| `npx playwright test tests/e2e/home/home-project-entry-closure.spec.ts --project=chromium --reporter=line` | Final rerun failed immediately because protected handoff project returned `404` |
| `GET http://127.0.0.1:8758/api/projects` | Investigation start: returned `[]`; after restoration: returned exactly one project, `Manual Beta Handoff` (`77a4b96c-8e3f-4501-897c-51bab99bedb7`) |
| Home UI restore flow + direct API probes | Passed: replacement handoff created and verified at `GET 200` with `sceneCount=1`, `assetCount=0`, `chatCount=0`, `wikiCount=0`, `planCount=0`, `proposalCount=0`, `approvalCount=0`, `jobCount=0`, `exportCount=0` |

Quick note on re-running the handoff-protection assertion:

- Home e2e protected-handoff constants were updated to the restored ID `77a4b96c-8e3f-4501-897c-51bab99bedb7` after this restoration pass
- instead, the live replacement handoff was revalidated directly on Beta through the same API surfaces the spec checks for emptiness

## Final Gate

WHOLE-APPLICATION PROJECT ENTRY CONTRACT: **GO**

The repaired application flow is green, the live Beta Home audit is green, and the only previously failing gate condition, protected handoff integrity, is now restored on the authoritative Beta target. Live Beta currently contains exactly one protected handoff project, `Manual Beta Handoff` (`77a4b96c-8e3f-4501-897c-51bab99bedb7`), and that project returns `GET 200` with the expected blank scaffold state.
