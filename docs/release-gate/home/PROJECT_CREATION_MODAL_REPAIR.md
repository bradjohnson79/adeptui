PROJECT CREATION MODAL UX: GO

## Summary

- Replaced the Home create drawer with a centered modal that keeps the default create flow on Home, resets cleanly between opens, and preserves pending-destination routing for non-Home entry points.
- Verified the final build on Beta at `http://127.0.0.1:8760/` with the dedicated modal certification suite plus the updated Home creation audit smoke.

## Branch And Runtime

- Branch: `feature/ai-guided-setup`
- Starting / current SHA used for this repair pass: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta URL: `http://127.0.0.1:8760/`
- Beta API health: `http://127.0.0.1:8758/api/health`
- Final Beta health: READY (`web` 8760, `api` 8758, external ComfyUI 8188)

## Scope Delivered

- Added `studio-web/src/components/generationStudio/HomeCreateProjectModal.tsx`
- Added `studio-web/src/components/generationStudio/HomeCreateProjectModal.css`
- Simplified `studio-web/src/components/dashboard/NewProductionCard.tsx` for compact modal-first UX with collapsed optional settings
- Updated `studio-web/src/pages/Home.tsx` to:
  - use the modal instead of the drawer
  - remount/reset form state on each open
  - keep explicit Home creates on Home
  - continue honoring pending destination flows from Setup / Project / Co-Director entry points
  - refresh active project context across Home and Co-Director surfaces
- Updated visible active-project acknowledgment on Home:
  - `studio-web/src/components/generationStudio/CreateProjectCard.tsx`
  - `studio-web/src/components/generationStudio/CoDirectorLaunchCard.tsx`
  - `studio-web/src/components/dashboard/ProjectCoverCard.tsx`
  - `studio-web/src/components/generationStudio/aurora-landing.css`
  - `studio-web/src/styles.css`
- Retired the old drawer wrapper: deleted `studio-web/src/components/generationStudio/HomeCreateProjectDrawer.tsx`
- Updated selector consumers / smoke helpers:
  - `tests/e2e/home/project-creation-modal.spec.ts`
  - `tests/e2e/home/home-project-creation-audit.spec.ts`
  - `tests/e2e/home/home-project-entry-closure.spec.ts`
  - `tests/e2e/m32/generation-studio-aurora.spec.ts`
  - `scripts/beta_create_clean_project.mjs`

## Test Summary

- Passed: `npm --prefix studio-web run build`
- Passed: `npx playwright test tests/e2e/home/project-creation-modal.spec.ts --project=chromium --reporter=line`
- Passed: `npx playwright test tests/e2e/home/home-project-creation-audit.spec.ts --project=chromium --reporter=line`
- Beta restarted successfully after the final build and remained READY after the test pass

## Hard Requirement Status

- `#1` Passed: at `1440x900`, the collapsed modal keeps project name, type, refine type (when present), profile summary, Cancel, and Create Project visible without scrolling; only the optional settings panel scrolls when expanded.
- `#2` Passed: after Home create, the Home active-project banner, Co-Director context label, project menu recent list, and active library card all update together while staying on Home.
- `#3` Passed: cancel, failure-close, and pending-destination completion all reopen with cleared errors, cleared optional expansion, and a fresh default name instead of stale carry-over.

## Whole-Application Entry Contract

- Not fully re-certified in this repair pass.
- `tests/e2e/home/home-project-entry-closure.spec.ts` was updated for the modal selectors and Home-stays-Home semantics, but that broader whole-application closure suite was not re-run in this pass.

## Protected Handoff Status

- Protected handoff target: `Manual Beta Handoff` / `77a4b96c-8e3f-4501-897c-51bab99bedb7` (restored after prior UUID `a7f665ce-…` was lost to a beta-local full reset)
- Status observed during this pass: absent before and absent after (`404` both times)
- Result: unchanged during this repair pass; no create, mutate, or delete action targeted that protected handoff id

## Artifacts

- Modal repair artifacts: `docs/release-gate/home/artifacts/project-creation-modal/`
- Home audit artifacts: `docs/release-gate/home/artifacts/`

## Limitations

- The protected handoff project was not present in this Beta runtime, so integrity was verified only as "absent before / absent after unchanged" rather than against a live existing handoff record.
- The full entry-closure suite remains a recommended follow-up if you want whole-application re-certification beyond the modal UX scope.
