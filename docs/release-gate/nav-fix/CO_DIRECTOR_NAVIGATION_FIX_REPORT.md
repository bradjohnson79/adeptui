# ADEPT UI CO-DIRECTOR NAVIGATION FIX REPORT

**Date:** 2026-08-12
**Branch:** `beta`
**Commit:** `fc44ef5` — `fix(codirector): activate Spatial Map + Scene Creator navigation tabs`
**Previous HEAD:** `16e41b3c`
**Deployed URL:** `https://adeptui-6xdplrb5e-anoint.vercel.app`

---

## Root cause

The `normalizeContentTab` function in `studio-web/src/components/CoDirector/CoDirectorShell.tsx` (lines 31–56) was a runtime whitelist of valid `ContentTab` values. It was missing `spatial_map`, `scene_creator`, `development`, and `production` — even though all four are members of the `ContentTab` TypeScript type union in `navEntries.ts`.

When a user clicked the Spatial Map or Scene Creator tab:
1. The tab button's `onClick` handler fired correctly (no `disabled` prop, no `comingSoon`, no feature flag).
2. `handleTabChange(item.id)` called `onTabChange(id)` → `setContentTab(id)` in `CoDirectorShell`.
3. `setContentTab` called `normalizeContentTab("spatial_map")` which fell through the whitelist to `return "wiki"`.
4. State silently reverted to `"wiki"`. `SpatialMapPanel` / `SceneCreatorPanel` never mounted. The tab appeared inert.

The same bug also affected the `CoDirectorStageStrip` "Open Production" action (`setContentTab("production")` → reverted to `"wiki"`).

TypeScript did not catch this because the `ContentTab` type union was permissive, but `normalizeContentTab` was a restrictive runtime whitelist that diverged from the type.

## Files changed

| File | Change |
|------|--------|
| `studio-web/src/components/CoDirector/CoDirectorShell.tsx` | Added `spatial_map`, `scene_creator`, `development`, `production` to `normalizeContentTab` whitelist (now matches `ContentTab` union exactly) |
| `tests/e2e/codirector/codirector-navigation-fix.spec.ts` | NEW — 4 Playwright tests: Spatial Map nav, Scene Creator nav, tab availability, 6-tab regression |

## Verification matrix

### Spatial Map
- **Clickable:** PASS — tab button is a native `<button>` with `role="tab"`, no `disabled`, no `aria-disabled`
- **Correct route:** PASS — `tab === "spatial_map"` renders `<SpatialMapPanel projectId={projectId} onGoTab={onGoTab} />`
- **Project context preserved:** PASS — `projectId` sourced from `uiContext.projectId`, passed through `CoDirectorProjectContent` → `SpatialMapPanel`; project name visible in `codirector-header-project`
- **Loads successfully:** PASS — panel renders empty-state with "Create Atlas Shot with Co-Director", "Choose from Library", "Upload Image" buttons when no Atlas Shot exists

### Scene Creator
- **Clickable:** PASS — same as Spatial Map
- **Correct route:** PASS — `tab === "scene_creator"` renders `<SceneCreatorPanel projectId={projectId} onGoTab={onGoTab} />`
- **Project context preserved:** PASS — same chain
- **Loads successfully:** PASS — panel renders contextual prerequisite guidance ("Create an Environment Reference Sheet in Spatial Map first") with "Open Spatial Map" cross-tab button

### Accessibility
- **PASS** — Tab buttons use `role="tab"`, `aria-selected={tab === item.id}`, inside `role="tablist"`. Native `<button>` elements (keyboard-focusable, Enter/Space-activatable). No `aria-disabled="true"` on either tab. Focus indicators preserved. Test C explicitly verifies `not.toHaveAttribute("disabled")` and `not.toHaveAttribute("aria-disabled", "true")`.

### Regression tests
- **PASS** — Test D walks all 6 tabs (Wiki → Script Writer → Character Creator → Spatial Map → Scene Creator → Library), clicking each and asserting `aria-selected="true"`. All pass.

### Playwright
- **Spatial Map navigation:** PASS (6.9s)
- **Scene Creator navigation:** PASS (7.9s)
- **Tab availability:** PASS (11.0s)
- **Regression (6 tabs):** PASS (17.7s)
- **Total:** 4 passed (44.0s) — exit code 0

### Console/runtime errors
- **NONE** — Browser CDP `Runtime.evaluate` confirmed `window.__adeptErrors` is empty. No uncaught exceptions, no route errors, no React runtime errors, no 404s, no 5xx from the navigation.

## Subagent verification

| Subagent | Role | Verdict |
|----------|------|---------|
| Navigation audit | Trace root cause, check for additional defects | ROOT CAUSE CONFIRMED; found `production`/`development` also missing (fixed) |
| Routing audit | Verify routes, project context, API, backend, stale gates | ROUTING: PASS (both); PROJECT CONTEXT: PASS; STALE GATES: NONE; DEFECTS: NONE |
| Independent verification | Read-only review of fix + tests + accessibility | FIX VERIFIED: PASS; TESTS VERIFIED: PASS; REGRESSIONS: NONE; ACCESSIBILITY: PASS; READY FOR PRIMARY REVIEW |

## Deployment

- **Commit:** `fc44ef5` pushed to `origin/beta` (`16e41b3..fc44ef5`)
- **Vercel deploy:** `npx vercel --prod --yes` — exit code 0, build succeeded
- **Deployed URL:** `https://adeptui-6xdplrb5e-anoint.vercel.app`
- **Deployed verification:** Deployment is behind Vercel Authentication (SSO/Deployment Protection). This is a Vercel project configuration setting, not a defect in the navigation fix. The deployed build contains the exact same commit (`fc44ef5`) that passed all 4 Playwright tests locally. The SSO wall prevents autonomous browser verification of the deployed URL without user credentials.

## Workflow awareness

Both tabs follow the correct model per Section 7 of the task:
```
Navigation remains available → Tool opens → Tool displays contextual prerequisite/readiness guidance
```
- Spatial Map: opens with Atlas Shot empty-state guidance (not disabled)
- Scene Creator: opens with ERS prerequisite guidance + "Open Spatial Map" button (not disabled)

## Limitations

1. **Vercel SSO:** The deployed beta is behind Vercel Authentication. Autonomous browser verification of the deployed URL was not possible without user credentials. Local Playwright certification against `http://127.0.0.1:5173` (Vite dev server, same code) passed all 4 tests. The user should verify the deployed beta manually after authenticating.
2. **Nav Drawer parity:** `buildNavEntries` (used by the hamburger Nav Drawer) does not include `spatial_map`/`scene_creator` — they are only reachable via the inline tab strip in `CoDirectorProjectContent`. This is consistent with the current design (inline sub-tabs), not a defect. If Nav Drawer parity is desired, a follow-up can add them.

## FINAL VERDICT

```
GO — CO-DIRECTOR SPATIAL MAP AND SCENE CREATOR NAVIGATION CERTIFIED
```

Both tools are genuinely clickable, load their real production experiences using the correct current project, preserve project context, pass all 4 Playwright tests, pass accessibility checks, and introduce no regressions. The fix is deployed to Vercel beta (behind SSO; user should verify manually after authenticating).
