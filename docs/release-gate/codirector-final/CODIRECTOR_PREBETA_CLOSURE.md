# Co-Director Pre-Beta Closure

Date: 2026-08-03  
Repo: `C:\AdeptFilmWorks\AIVideoStudio`  
Branch: `feature/ai-guided-setup`  
HEAD: `fa09c99d6395c29461cdec4555055faad116c435`  
Live Beta: UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758/`

## Verdict

**READY FOR MANUAL BETA**

The closure gate is now ready because the previously blocked evidence gaps were closed on live Beta: direct composer file-input upload persisted as a real project asset and survived reload, the durable plan workspace rendered from a created draft, the offline HTML export rendered directly from disk without HTTP requests, the activity surface stayed creator-facing, and the required minimum suite re-passed after the final repairs. A late cleanup-path defect in project deletion was also repaired and revalidated, so the READY-only environment handoff was completed instead of being skipped.

## What Changed

Closure repairs completed in this pass:

- `tests/e2e/codirector/codirector-prebeta-closure.spec.ts`
  - Added the focused live closure suite for direct upload, export hygiene, offline HTML, PDF note capture, plans visibility, activity honesty, reload persistence, and console/network hygiene.
  - Switched the upload fixture to a run-unique filename so the persistence proof cannot accidentally match residue from an earlier cert run.
- `studio-api/app/codirector/wiki_export.py`
  - Embedded the export model directly into `index.html` so the offline package no longer depends on `fetch('data/wiki.json')` when opened from disk.
  - Replaced `innerHTML` list rendering with DOM text-node construction for safer creator-facing offline output.
- `studio-web/src/components/CoDirector/activity.ts`
  - Tightened summary-fact generation so the activity card only claims plan/wiki/tool checks when those stages actually completed.
- `studio-api/app/project_cleanup.py`
  - Added broad project-residue cleanup for project-scoped rows plus indirect child records that were blocking real project deletion.
- `studio-api/app/routers/api.py`
  - Wired `DELETE /api/projects/{project_id}` through the new cleanup helper before removing the project row.
- `studio-api/tests/test_codirector_runtime_repair.py`
  - Added a regression proving project deletion succeeds even when Co-Director plan/context residue exists.

## Live Evidence

Latest focused closure artifact set:

- summary: `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-summary.json`
- PDF: `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-dreamweaver-closure.pdf`
- HTML ZIP: `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-dreamweaver-closure.zip`
- screenshots:
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-01-plans.png`
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-02-attachment-tray.png`
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-03-post-send.png`
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-04-activity.png`
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-05-offline-html.png`
  - `docs/release-gate/codirector-final/artifacts/prebeta-closure/PB-CLOSURE-1785715987172-06-reload.png`

Key facts from the latest passing closure run:

- direct upload asset id: `bd024a4b-e89f-4211-b2ac-7f991d6f3420`
- persisted upload name after send/reload: `PB-CLOSURE-1785715987172-closure-upload.png`
- durable plan id rendered in workspace: `ccb543b1-c824-4c9f-bac2-c5587d3cc56c`
- HTML export packaged `65` media entries and included the run-scoped upload
- PDF note: no omission marker detected; binary inspection suggests the image was embedded or rasterized
- offline extract rendered from local files only; the closure spec rejected any `http` or `https` requests

## Required Minimum Pass

Revalidated on restarted Beta after the closure repairs:

```text
$env:ADEPT_BETA_TARGET='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8760'
$env:STUDIO_API_BASE='http://127.0.0.1:8758'
npx playwright test tests/e2e/codirector/codirector-prebeta-closure.spec.ts tests/e2e/codirector/codirector-runtime-repair.spec.ts tests/e2e/codirector/codirector-prebeta-certification.spec.ts

7 passed (2.5m)
```

```text
python -m pytest studio-api/tests/test_codirector_runtime_repair.py studio-api/tests/test_codirector_tools.py

82 passed, 5 warnings in 291.68s (0:04:51)
```

Cleanup-path regression after the delete repair:

```text
python -m pytest studio-api/tests/test_codirector_runtime_repair.py

7 passed, 5 warnings in 27.79s
```

## Cleanup And Handoff

READY-only cleanup completed:

- deleted prior certification project `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c` (`The Dreamweaver`) after repairing the delete path
- verified project count dropped to zero
- created exactly one fresh handoff project through the UI flow: `b53bf82b-1081-46b9-acf2-d7899fe204e3` (`Manual Beta Handoff`)
- verified final project count is one and the new handoff project has `asset_count = 0`

Residual limitation to note honestly:

- a brand-new UI-created project still starts with the default blank scene scaffold (`scene_count = 1`), but no Dreamweaver cert assets, plans, or conversation residue remain

## Final Handoff Lines

Verdict: `READY FOR MANUAL BETA`  
Report path: `docs/release-gate/codirector-final/CODIRECTOR_PREBETA_CLOSURE.md`  
Project left for human: `b53bf82b-1081-46b9-acf2-d7899fe204e3` (`Manual Beta Handoff`)  
Environment reset complete. Ready for manual beta testing.
