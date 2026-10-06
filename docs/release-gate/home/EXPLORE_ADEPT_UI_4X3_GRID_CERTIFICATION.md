# GO — EXPLORE ADEPT UI 4×3 GRID CERTIFIED

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Local creator UI:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/ (`/api/healthz` 200)  
**Active project used for Open CTA proof:** Korri Anadriya (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`)

This is the current Explore Adept UI authority. Historical roster reports:

- `EXPLORE_WORKSPACE_ROSTER_AUDIT.md` — superseded
- `EXPLORE_CORE_CREATION_WORKSPACES_REPORT.md` — superseded

## Scope

Home **Explore Adept UI** only.

Removed from Explore (not from the product): Timeline, MAGI Editor.  
Added: Prop Creator, Environment Creator, Storyboard.  
Desktop layout locked to **4 columns × 3 rows = 12 cards**.

Unchanged by this mission:

- Co-Director feature card
- Timeline / MAGI Home feature cards (`studio-launch-cards`)
- Production menu (still lists Timeline Generator and MAGI Editor)
- compact Project Library
- top navigation
- active project state
- Timeline / MAGI / Storyboard / creator workspaces themselves

## Canonical roster (live-measured)

| Row | Col 1 | Col 2 | Col 3 | Col 4 |
| --- | --- | --- | --- | --- |
| 1 | Image Generation | Text to Video | 1 Frame | 3 Frame |
| 2 | Character Creator | Prop Creator | Environment Creator | Storyboard |
| 3 | Scriptwriter | Voice Studio | Audio Studio | Library |

Explore DOM ids: `imagegen`, `txt2vid`, `one`, `three`, `characters`, `propcreator`, `environmentcreator`, `script`, `scriptwriter`, `voicestudio`, `audiostudio`, `library`.

No `explore-workspace-timeline`. No `explore-workspace-magi`. No fourth Explore row at desktop.

## Layout (observed)

| Viewport | Columns | Result |
| --- | --- | --- |
| 1920×1080 | 4 | 3 equal rows, card 310×349 |
| 1440×1100 | 4 | 3 equal rows, card 297×341 |
| 800×1100 | 2 | 6 rows of pairs |
| 390×844 | 1 | 12 stacked cards; Explore grid itself did not overflow-x |

## Open CTA routes (Korri Anadriya)

Clicked from Home or opened via the same `/project/:id?workspace=` path the cards build:

| Card | Workspace | Shell |
| --- | --- | --- |
| Image Generation | `imagegen` | `cinematic-image-studio` |
| Text to Video | `txt2vid` | `txt2vid-panel` |
| 1 Frame | `one` | `one-frame-panel` |
| 3 Frame | `three` | `three-frame-panel` |
| Character Creator | `characters` | `character-profile-workspace` |
| Prop Creator | `propcreator` | `prop-creator-panel` |
| Environment Creator | `environmentcreator` | `environment-creator-surface` |
| Storyboard | `script` | `storyboard-studio` |
| Scriptwriter | `scriptwriter` | `scriptwriter-studio` |
| Voice Studio | `voicestudio` | `voice-studio-shell` |
| Audio Studio | `audiostudio` | `audio-studio-workspace` |
| Library | `library` | `library-filters` |

Storyboard reuses the existing Storyboard Studio (`workspace=script`). No new Storyboard implementation.

## Imagery

- Existing Explore JPGs reused for the eight unchanged cards.
- Storyboard reuses `ws-script.jpg`.
- New themed stills: `ws-prop-creator.jpg`, `ws-environment-creator.jpg`.
- All twelve images loaded (non-zero natural size) at 1440.

## Tests

`npx vitest run src/core/exploreWorkspaces.test.ts src/core/sceneCraftShelf.test.ts src/core/brandStudioRetirement.test.ts src/core/spatialMapShelf.test.ts`

**18 passed, 0 failed** (4 files).

E2E roster expectations updated to the 12-card set. Full Playwright `@critical` suites require `ADEPT_BETA_TARGET=1` and were not re-run in this pass; live browser proof above is the certification evidence.

## Files

- `studio-web/src/core/exploreWorkspaces.ts`
- `studio-web/src/core/exploreWorkspaces.test.ts`
- `studio-web/src/theme/auroraCardImagery.ts`
- `studio-web/src/dashboardImages.ts`
- `studio-web/src/styles.css` (Explore 1/2/4-col breakpoints; removed 5-col ≥1400)
- `studio-web/src/components/storyboard-studio/StoryboardStudio.tsx` (`data-testid="storyboard-studio"` on existing root)
- `studio-web/public/images/ui/workspaces/ws-prop-creator.jpg`
- `studio-web/public/images/ui/workspaces/ws-environment-creator.jpg`
- `studio-web/public/images/ui/LICENSE.md`
- `tests/e2e/home/explore-workspaces-audit.spec.ts`
- `tests/e2e/home/explore-core-creation-workspaces.spec.ts`
- `tests/e2e/home/home-production-discovery-expansion.spec.ts`
- `tests/e2e/home/home-project-creation-audit.spec.ts`

## Runtime

- Vite HMR / page refresh only. No Studio API recycle. No Comfy / MiniMax restart.
- `GET http://127.0.0.1:5173/` 200
- `GET http://127.0.0.1:8758/api/healthz` 200
- `GET http://127.0.0.1:8188/system_stats` 200

```text
COMFY BEFORE: healthy :8188 / system_stats 200
COMFY AFTER: healthy :8188 / system_stats 200
COMFY RESTARTED?: NO
WHY?: Explore Home CSS/roster only. Frontend-only. Protected runtime left untouched.
```

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Home Explore Open → |
| Frontend | PASS — 12 cards, 4×3 at desktop |
| API | N/A — roster is client registry |
| Backend | N/A |
| Persistence | N/A — no project mutation |
| Runtime | N/A — no generation |
| Result | PASS — each workspace shell mounted |
| Reload | PASS — Home still 12 cards after workspace returns |
| Downstream | PASS — existing workspaces, nav, feature cards intact |

## Limitations

- Hosted Vercel bundle was not rebuilt; this cert is local Vite `:5173`.
- Playwright `@critical` Explore suites were updated but not executed under `ADEPT_BETA_TARGET=1`.
- Narrow-viewport document overflow-x is pre-existing Home chrome, not the Explore grid.

## Verdict

**GO — EXPLORE ADEPT UI 4×3 GRID CERTIFIED**
