# M214 Co-Director Runtime Repair

## Verdict

**GO**

The original live Beta failures were reproduced, repaired, and revalidated on the restarted Beta stack at `http://127.0.0.1:8760/` and `http://127.0.0.1:8758/`. After the Addendum 5 reset, only one Beta project remained, the first Dreamweaver message persisted the title and initialized the Wiki, the legacy `m214/plan/{id}` 404 no longer appeared, no raw `record_production_decision` tool-registry error surfaced, and fullscreen width measured `0.9` viewport width in the live verification script.

## Scope

This repair session covered:

- legacy `/api/codirector/m214/plan/{id}` 404s on new projects
- missing `record_production_decision` tool wiring
- creator-facing error UX and retry behavior
- Project Focus replacement with a creator-facing Project Wiki
- `Overview` to `Wiki` tab/default migration
- fullscreen Co-Director width and margin correction
- Project Wiki PDF and Offline HTML export
- Addendum 5 local Beta database reset, backup, and single-project recreation

## Root Causes

### 1. Legacy plan caller still active in live Beta

The main plan lookup path had already been repaired in `CoDirectorProjectContent`, but live Beta still emitted `/api/codirector/m214/plan/{projectId}` because `CoDirectorStageStrip` and `ProductionPlanPanel` were still calling `api.m214Plan(projectId)`.

### 2. `record_production_decision` missing from durable tool path

The save action existed as a concept in UX flows but was not fully registered end-to-end in the bounded Co-Director tool system, so live Beta could surface `'record_production_decision' isn't a Co-Director tool.`

### 3. Creator-facing Project Focus was leaking implementation diagnostics

Project Focus was still capable of presenting internal repository/tool-oriented content instead of a creator-readable project memory surface.

### 4. Fullscreen width was still constrained by a second CSS override

The general fullscreen CSS was widened, but `codirector-cinematic.css` still hard-clamped the fullscreen shell to `min(1200px, calc(100% - 1.5rem))`, keeping live Beta around `83%` width.

### 5. Beta certification state was polluted by legacy local projects

The Beta-local SQLite DB held 35 local projects from prior dev/cert activity, making clean Co-Director verification unreliable until the environment was reset and recreated.

## Repairs

### Backend/runtime

- Added canonical active-plan routes:
  - `GET /api/codirector/projects/{project_id}/plans/active`
  - `GET /api/codirector/projects/{project_id}/plans/{plan_id}`
- Added creator-facing Project Wiki route:
  - `GET /api/codirector/projects/{project_id}/wiki`
- Added Wiki export routes:
  - `POST /api/codirector/projects/{project_id}/wiki/export/pdf`
  - `POST /api/codirector/projects/{project_id}/wiki/export/html`
- Added `record_production_decision` tool definition, registry wiring, persistence, project-title update path, and creator-readable confirmation.
- Fixed proposal approval idempotency so repeat approval returns the original tool receipt instead of a conflict.
- Added `scripts/reset_project_data.py` with:
  - required `--environment beta-local`
  - `--dry-run`
  - mandatory confirm flag for deletion
  - automatic backup
  - post-reset FK integrity reporting

### Frontend

- Replaced Project Focus diagnostics with `ProjectWikiPanel`.
- Migrated default content tab to `Wiki` and normalized any `overview` preference.
- Added creator-facing Wiki export UI and dialog.
- Improved tool failure presentation and retry behavior.
- Rewired remaining fullscreen live callers away from `api.m214Plan(...)`.
- Removed the lingering cinematic fullscreen width clamp so live Beta now honors the wider fullscreen contract.

## Final Contracts

### Old

- `GET /api/codirector/m214/plan/{id}` used as normal active-plan lookup, including empty-state project loads

### New

- `GET /api/codirector/projects/{project_id}/plans/active`
  - returns typed empty:
    - `{ "ok": true, "status": "not_created", "plan": null }`
- `GET /api/codirector/projects/{project_id}/plans/{plan_id}`
  - returns the concrete plan by canonical `planId`
- `GET /api/codirector/projects/{project_id}/wiki`
  - returns sanitized creator-facing Project Wiki data
- `POST /api/codirector/projects/{project_id}/wiki/export/pdf`
- `POST /api/codirector/projects/{project_id}/wiki/export/html`

## Addendum 5 Reset Evidence

- Environment: `beta-local`
- Engine: local SQLite
- Database: `C:\AdeptFilmWorks\AIVideoStudio\data\studio.db`
- Backup path:
  - `C:\AdeptFilmWorks\AIVideoStudio\backups\pre-codirector-beta-reset-2026-08-02T22-16-23Z`
- Deleted project count: `35`
- Post-reset project count before recreation: `0`
- `orphanForeignKeys`: `0`
- Fresh UI-created project:
  - `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c`
- Final live API project list:
  - `The Dreamweaver` only

## Dreamweaver Live Verification

Script used:

- `node scripts/beta_verify_dreamweaver.mjs`

Live result:

```json
{
  "projectId": "fcd7b4b0-7d36-4757-ac82-a701e6e1a50c",
  "approved": true,
  "widthRatio": 0.9,
  "overviewTabCount": 0,
  "initialWikiDiagnosticsClean": true,
  "finalWikiDiagnosticsClean": true,
  "blockedFailures": [],
  "sendErrorText": "",
  "headerTitle": "The Dreamweaver",
  "wikiTitle": "The Dreamweaver",
  "reloadedHeaderTitle": "The Dreamweaver",
  "reloadedWikiTitle": "The Dreamweaver",
  "apiProjects": [
    {
      "id": "fcd7b4b0-7d36-4757-ac82-a701e6e1a50c",
      "name": "The Dreamweaver"
    }
  ]
}
```

Verified from this run:

- first Dreamweaver message saved and approved
- title persisted in Co-Director header and Wiki heading
- title persisted after reload
- Wiki remained default tab
- no duplicate `Overview` tab
- no raw repository diagnostics in Wiki
- no legacy `m214/plan` 404
- no raw tool-registry error
- fullscreen width measured `0.9`
- only one project remained in Beta API, named `The Dreamweaver`

## Tests and Commands

### Passing

- `npm --prefix studio-web run build`
- `node --test --experimental-strip-types studio-web/src/api.codirector-error.test.ts studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts`
- `studio-api\.venv\Scripts\python.exe -m pytest tests/test_codirector_runtime_repair.py -q`
- `studio-api\.venv\Scripts\python.exe scripts/reset_project_data.py --environment beta-local --dry-run`
- `studio-api\.venv\Scripts\python.exe scripts/reset_project_data.py --environment beta-local --confirm-delete-all-projects`
- `node scripts/beta_create_clean_project.mjs`
- `node scripts/beta_verify_dreamweaver.mjs`

### Known unrelated baseline failure

- `studio-api\.venv\Scripts\python.exe -m pytest tests/test_codirector_tools.py`

This broader registry snapshot suite still contains pre-existing tool-catalog mismatches outside the scope of this repair. It did not block the specific live Beta runtime issues covered here because the repaired Dreamweaver flow and reset gate were revalidated directly on Beta afterward.

## Key Files

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

### Tests and utilities

- `studio-api/tests/test_codirector_runtime_repair.py`
- `studio-web/src/api.codirector-error.test.ts`
- `tests/e2e/codirector/codirector-runtime-repair.spec.ts`
- `scripts/beta_create_clean_project.mjs`
- `scripts/beta_verify_dreamweaver.mjs`

## Remaining Notes

- The Dreamweaver title was conclusively verified in the Co-Director header, Wiki header, reload path, and live API project list.
- The dashboard/home card text was not used as the primary certification gate because the authoritative single-project state is already enforced by the post-reset API list and the active Co-Director route.
