# EXPLORE WORKSPACE ROSTER AUDIT: GO

## Summary

- Explore Adept UI now shows exactly **10** canonical workspace cards.
- **Storyboard** was removed from Explore.
- **Brand Studio**, **Voice Studio**, and **Audio Studio** were added.
- Brand Studio Production dropdown navigation was repaired end-to-end.
- Certified on live Beta at `http://127.0.0.1:8760/`.

## Branch And Runtime

- Branch: `feature/ai-guided-setup`
- Starting SHA for this pass: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta URL: `http://127.0.0.1:8760/`
- Beta API health: `http://127.0.0.1:8758/api/health`
- Final Beta health: READY (`web` 8760, `api` 8758, external ComfyUI 8188)

## Old vs New Explore Roster

| # | Before | After |
|---|--------|-------|
| 1 | Timeline | Timeline |
| 2 | MAGI Editor | MAGI Editor |
| 3 | Storyboard | Brand Studio |
| 4 | Spatial Map | Spatial Map |
| 5 | Image Generation | Image Generation |
| 6 | Text to Video | Text to Video |
| 7 | Avatar Studio | Avatar Studio |
| 8 | Library | Voice Studio |
| 9 | — | Audio Studio |
| 10 | — | Library |

Storyboard removal: absent from Explore DOM/config. No hidden Explore Storyboard card remains.

Storyboard distinction: Production menu **Create** category still exposes Storyboard (`workspace=script` / Storyboard Studio) as a deliberate production tool. It is retired only from the Home Explore creator roster.

## Brand Studio Root Cause

Two defects stacked:

1. **Home Production launch contract**
   - `AppChrome.goWorkspace()` on Home with no `projectId` fell back to a stale recent project or `goHome()` (dead click / wrong destination).
   - Repair: Home now passes `preferredProjectId` into chrome; with no eligible project, Production menu opens the centered Create Project modal via `buildHomeCreateProjectPath({ pendingEntry: { kind: "project", workspace } })`.

2. **Recent-project wipe during Home load**
   - `getEligibleProjectId([])` treated an empty loading list as “all recent ids are stale” and cleared `adept_ui_recent_projects`.
   - That broke preferred-project context after navigations and made Explore/Production launches inconsistent.
   - Repair: do not prune recent projects while the project list is still empty.

Additional regression fixed while wiring Home `projectId`:
- Project menu skipped the preferred project from Recent when `projectId` was set on Home, but only rendered the “current project” row inside a project shell.
- Repair: show the preferred project on Home as a selectable selected row.

## Canonical Routes

All Explore / Production launches use the WORKSPACES registry ids:

| Workspace | Canonical route |
|-----------|-----------------|
| Timeline | `/project/:id?workspace=timeline` |
| MAGI Editor | `/project/:id?workspace=magi` |
| Brand Studio | `/project/:id?workspace=brandstudio` |
| Spatial Map | `/project/:id?workspace=spatial` |
| Image Generation | `/project/:id?workspace=imagegen` |
| Text to Video | `/project/:id?workspace=txt2vid` |
| Avatar Studio | `/project/:id?workspace=avatar` |
| Voice Studio | `/project/:id?workspace=voicestudio` |
| Audio Studio | `/project/:id?workspace=audiostudio` |
| Library | `/project/:id?workspace=library` |

Source of truth:
- Workspace registry: `studio-web/src/core/workspaces.ts`
- Explore roster: `studio-web/src/core/exploreWorkspaces.ts`
- Production catalog: `studio-web/src/core/productionMenu.ts`
- Path helper: `buildProjectWorkspacePath()`

## Files Changed

- `studio-web/src/core/exploreWorkspaces.ts` (new)
- `studio-web/src/pages/Home.tsx`
- `studio-web/src/components/dashboard/AppChrome.tsx`
- `studio-web/src/components/dashboard/DashboardCards.tsx`
- `studio-web/src/components/ui/WorkspaceCard.tsx`
- `studio-web/src/core/workspaces.ts`
- `studio-web/src/core/productionMenu.ts`
- `studio-web/src/projectEntry.ts`
- `studio-web/src/projectEntry.test.ts`
- `studio-web/src/dashboardImages.ts`
- `studio-web/src/theme/auroraCardImagery.ts`
- `studio-web/src/styles.css`
- `studio-web/public/images/ui/workspaces/ws-brand.svg`
- `studio-web/public/images/ui/workspaces/ws-voice.svg`
- `tests/e2e/home/explore-workspaces-audit.spec.ts` (new)
- `tests/e2e/home/home-project-creation-audit.spec.ts`

## Status Badge

Removed the default `CONTINUE` badge from Explore cards. Cards keep the honest `Open →` action. CONTINUE is no longer shown for workspaces with no proven in-workspace state.

## Layout

- Large desktop (`≥1400px`): fixed **5 × 2** Explore grid
- Mid desktop: 4-column grid
- Narrow: `minmax(min(240px, 100%), 1fr)` to prevent horizontal overflow

## Playwright Results

Passed:

- `tests/e2e/home/explore-workspaces-audit.spec.ts`
  - A roster (exactly 10, Storyboard absent)
  - B Brand Studio Home card
  - C Brand Studio Production dropdown
  - D Voice Studio card + Production dropdown
  - E Audio Studio card + Production dropdown
  - F no-project modal → cancel / create → destination
  - G responsive layouts
  - H keyboard / alt text
  - I pageerror clean on Brand open
- `tests/e2e/home/project-creation-modal.spec.ts`
- `tests/e2e/home/home-project-creation-audit.spec.ts`
- `tests/e2e/m42/m42-production-menu.spec.ts` (earlier in pass)

Not re-certified in this pass:

- `tests/e2e/home/home-project-entry-closure.spec.ts` — blocked by missing protected handoff project `77a4b96c-8e3f-4501-897c-51bab99bedb7` (`404`). Not introduced by this roster change; handoff absent before/after explore audit.

## Project-Entry Behavior

| Path | Active project | No eligible project | Cancel |
|------|----------------|---------------------|--------|
| Explore Brand/Voice/Audio | Opens canonical workspace on current project | Centered Create Project modal; no POST until confirm; resumes workspace after create | No create; stay Home; no workspace open |
| Production Brand/Voice/Audio | Same canonical workspace + same project id | Same create-modal pending-destination contract | Same cancel contract |

## Accessibility Findings

- Explore cards are keyboard focusable buttons
- Enter opens Brand Studio from Explore
- Production menu Brand Studio is keyboard operable
- Brand / Voice / Audio card images have non-empty alt text
- Titles are unique across the Explore grid

## Console / Network Findings

- No pageerror on final Brand Studio open
- Disposable projects cleaned after explore audit
- Protected handoff id unchanged (`404` before/after)

## Artifacts

`docs/release-gate/home/artifacts/explore-workspaces/`

- `scenario-a-roster-1440.png`
- `scenario-b-brand-home-card.png`
- `scenario-d-voice-studio.png`
- `scenario-e-audio-studio.png`
- `scenario-g-layout-1920x1080.png`
- `scenario-g-layout-1440x900.png`
- `scenario-g-layout-1280x720.png`
- `scenario-g-layout-narrow-390x844.png`
- `handoff-state.json`

## Manual Review Path

1. Open `http://127.0.0.1:8760/`
2. Confirm Explore Adept UI shows the 10 titles above and no Storyboard card
3. With an active project: open Brand / Voice / Audio from Explore and from Production
4. With no project: each of those three opens Create Project; cancel creates nothing; create resumes into the chosen workspace

## Limitations

- Protected Manual Beta Handoff project was absent in this runtime; entry-closure suite was not re-certified here.
- Voice Studio may show its character chooser/empty shell when no character is selected; route and shell (`voice-studio-shell`) are correct.
- Explore card labels use short Home names (e.g. Timeline) while WORKSPACES/Production may still say Timeline Generator.

## Verdict

**GO**
