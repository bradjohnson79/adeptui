# Co-Director Runtime Repair And UX Summary

Detailed report: `docs/release-gate/codirector-final/M214_CODIRECTOR_RUNTIME_REPAIR.md`

## Executive Verdict

**GO**

The Co-Director Beta repair is now live-verified on the clean Beta-local database. After the controlled reset and single-project recreation, the Dreamweaver flow persisted the title, initialized the creator-facing Wiki, avoided the original `m214/plan` 404 and raw tool-registry error, and met the fullscreen width requirement at `0.9` viewport width. The repaired state is running on `http://127.0.0.1:8760/` with API health on `http://127.0.0.1:8758/api/health`.

## Scope

This session completed:

- plan lookup repair for new/active projects
- `record_production_decision` registration and persistence
- creator-facing Project Wiki replacement for repository diagnostics
- Wiki tab defaulting and Overview migration
- recoverable error/retry UX
- Wiki export entry points
- fullscreen width/margin correction
- Addendum 5 safe local Beta database reset, backup, and single fresh project recreation

## Root Causes And Fixes

### Legacy plan 404

- Root cause: old `api.m214Plan(projectId)` callers remained in live fullscreen surfaces.
- Fix: switched remaining callers to typed active-plan lookup plus plan-by-id resolution.

### Missing production decision tool

- Root cause: `record_production_decision` was not fully wired through definition, registry, apply path, and persistence.
- Fix: added canonical tool wiring, persisted to existing decision infrastructure, and updated project title on approved save.

### Project Focus diagnostics

- Root cause: Project Focus could still surface internal retrieval/diagnostic content.
- Fix: Project Focus now uses the normalized creator-facing Wiki model and avoids raw tool/provenance text.

### Fullscreen width still too narrow

- Root cause: `codirector-cinematic.css` still overrode fullscreen shell width with a `1200px` clamp.
- Fix: removed the clamp and aligned cinematic fullscreen with the intended `90vw` contract.

### Dirty Beta-local data

- Root cause: the local Beta DB contained 35 legacy projects from prior dev/cert activity.
- Fix: created and ran a guarded reset utility, backed up local data, deleted project-scoped records, verified `orphanForeignKeys == 0`, restarted Beta, and recreated exactly one fresh project through the normal UI flow.

## Contracts And Endpoints

Repaired/used contracts:

- `GET /api/codirector/projects/{project_id}/plans/active`
- `GET /api/codirector/projects/{project_id}/plans/{plan_id}`
- `GET /api/codirector/projects/{project_id}/wiki`
- `POST /api/codirector/projects/{project_id}/wiki/export/pdf`
- `POST /api/codirector/projects/{project_id}/wiki/export/html`

Retired as normal empty-state behavior:

- `/api/codirector/m214/plan/{id}` for project bootstrap/active-plan lookup

## Files Changed

### Backend

- `studio-api/app/routers/codirector.py`
- `studio-api/app/codirector/wiki.py`
- `studio-api/app/codirector/wiki_export.py`
- `studio-api/app/codirector/bible/proposals.py`
- `studio-api/app/codirector/tools/definitions.py`
- `studio-api/app/codirector/tools/registry.py`
- `studio-api/app/codirector/tools/handlers/project_decisions.py`
- `scripts/reset_project_data.py`

### Frontend

- `studio-web/src/api.ts`
- `studio-web/src/components/CoDirector/ProjectWikiPanel.tsx`
- `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx`
- `studio-web/src/components/CoDirector/CoDirectorShell.tsx`
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `studio-web/src/components/CoDirector/CoDirectorConversation.tsx`
- `studio-web/src/components/CoDirector/CoDirectorStageStrip.tsx`
- `studio-web/src/components/CoDirector/ProductionPlanPanel.tsx`
- `studio-web/src/components/CoDirector/codirector-cinematic.css`
- `studio-web/src/styles.css`

### Tests and verification utilities

- `studio-api/tests/test_codirector_runtime_repair.py`
- `studio-web/src/api.codirector-error.test.ts`
- `tests/e2e/codirector/codirector-runtime-repair.spec.ts`
- `scripts/beta_create_clean_project.mjs`
- `scripts/beta_verify_dreamweaver.mjs`

## Test Evidence

Passing checks:

- `npm --prefix studio-web run build`
- `node --test --experimental-strip-types studio-web/src/api.codirector-error.test.ts studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts`
- `studio-api\.venv\Scripts\python.exe -m pytest tests/test_codirector_runtime_repair.py -q`
- `studio-api\.venv\Scripts\python.exe scripts/reset_project_data.py --environment beta-local --dry-run`
- `studio-api\.venv\Scripts\python.exe scripts/reset_project_data.py --environment beta-local --confirm-delete-all-projects`
- `node scripts/beta_create_clean_project.mjs`
- `node scripts/beta_verify_dreamweaver.mjs`

Known unrelated baseline issue:

- `studio-api\.venv\Scripts\python.exe -m pytest tests/test_codirector_tools.py`

This registry snapshot suite still has broader pre-existing catalog mismatches outside the scope of the repaired Dreamweaver runtime path.

## Live Beta Verification

Runtime:

- UI: `http://127.0.0.1:8760/`
- API: `http://127.0.0.1:8758/api/health`

Reset evidence:

- backup path:
  - `C:\AdeptFilmWorks\AIVideoStudio\backups\pre-codirector-beta-reset-2026-08-02T22-16-23Z`
- deleted projects:
  - `35`
- post-reset empty count:
  - `0`
- final fresh project:
  - `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c`

Dreamweaver evidence:

- first live message approved and saved
- header title: `The Dreamweaver`
- Wiki title: `The Dreamweaver`
- reload preserved both
- `overviewTabCount: 0`
- `blockedFailures: []`
- `sendErrorText: ""`
- `widthRatio: 0.9`
- live API project list contains exactly one project, `The Dreamweaver`

## Screenshots / Traces

- Playwright failure traces from the earlier missing-browser run remain under:
  - `artifacts/functional-audit/test-output/.../trace.zip`
- Final authoritative live verification for this repair used:
  - `node scripts/beta_verify_dreamweaver.mjs`

## Remaining Notes

- The single-project clean Beta state is preserved.
- No additional project was created after reset.
- The dashboard/home card text was not used as the authoritative selector proof; instead, the live API project list and the active Dreamweaver Co-Director route were used to confirm that only one project remains and that it carries the persisted title.

## Manual Review Checklist

- Open `http://127.0.0.1:8760/co-director?projectId=fcd7b4b0-7d36-4757-ac82-a701e6e1a50c`
- Confirm header shows `The Dreamweaver`
- Confirm `Wiki` is the default tab and `Overview` is absent
- Confirm Project Wiki is creator-facing, not diagnostic
- Confirm `Active plan: None` loads without console 404s
- Confirm no raw `'record_production_decision' isn't a Co-Director tool` message
- Confirm fullscreen width visually matches the wider `90vw` shell
- Confirm `/api/projects` returns exactly one project named `The Dreamweaver`
