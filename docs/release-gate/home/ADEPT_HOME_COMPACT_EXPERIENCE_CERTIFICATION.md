# Adept Home Page Compact Experience Certification

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` (working tree includes this Home compaction)  
**Review URL:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/  
**Active project used:** Korri Anadriya (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`)

## Verdict

**GO — ADEPT HOME PAGE COMPACT EXPERIENCE CERTIFIED**

## CO-DIRECTOR OLD HOME COMPOSER

**removed**

Home no longer hosts an inline chat surface. Removed from `CoDirectorLaunchCard`:

- composer textarea (`codirector-launch-composer`)
- send control
- prompt starters
- “Ask anything about your project…” treatment

Home is not a second Co-Director chat surface.

## CO-DIRECTOR FEATURE CARD

**image:** `/images/hero/CoDirector_Feature_16-9.png`  
Registered in `dashboardImages.codirector`. Responsive `object-fit: cover`, alt text, and motif fallback if the asset fails to load. Not hardcoded as base64.

**summary:** “Your intelligent production partner across Adept UI.”

**benefits:**

- Understands your project, scenes, and production context
- Helps plan, write, direct, and finish your work
- Works across Timeline, MAGI, creators, and Library
- Analyzes, proposes, and carries out supported production tasks

**CTA:** Enter Co-Director (`data-testid="enter-codirector"`)

**fullscreen:** Reuses existing `openCoDirector(..., { fullscreen: true })` → `/co-director?projectId=` → `CoDirectorFullScreen` / `data-mode="fullscreen"`. No second fullscreen architecture.

**project context:** Home bind via `useBindCoDirectorWorkspace`. With Korri Anadriya active the card showed `Active project: Korri Anadriya`. CTA opened `http://127.0.0.1:5173/co-director?projectId=beffd3d8-791d-4adf-9c4d-681ec9d4efb0` with header project Korri Anadriya. Close returned to `/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0`. One fullscreen shell. No Home composer left behind.

## PROJECT LIBRARY

**grid:** `repeat(auto-fill, minmax(280px, 1fr))` unchanged. At 1920, 2560, and 1440 owner-like width: **4 columns**.

**list:** Same bounded results scroller. Max-height fits complete list rows into the measured 3-row grid footprint.

**visible rows:** **3 complete rows.** Max-height = `rowHeight * 3 + gap * 2` from the first live card (`useHomeLibraryBounds`). Not a hardcoded 12-project cap.

**internal scroll:** Only `.gs-library__results` scrolls. Heading, Search, All / Active / Rendering / Complete, and Grid / List stay above the scroller. Adept thin teal scrollbar. Measured at 1920: `clientHeight 1416` / `scrollHeight 16476` / fourth row not visible.

**filters:** Still run on the full `projects` array.

**search:** Search for below-fold `autosave-repro` returned that project and reset scroller `scrollTop` to `0`.

**responsive behavior:** Column count follows the existing auto-fill grid. 1920 / 2560 / 1440 all showed 4 columns and three complete rows with no fourth-row sliver.

## HOME PAGE

| Surface | Height |
| --- | --- |
| before height | **20508 px** reconstructed at 1920 (same page, library `scrollHeight` substituted for the 3-row `clientHeight`) |
| after height | **5712 px** at 1920 after the visual card settled |
| 1920×1080 | page **5712**; library 4×3 rows; card **524 px**; CTA visible; no composer |
| 2560×1440 | page **5967**; library 4×3 rows; card **524 px**; CTA visible |
| 1440×900 (owner-like) | page **5455**; library 4×3 rows; card **504 px**; `Active project: Korri Anadriya` |

Home is substantially shorter because 143 projects no longer expand the page.

## CONSOLE

Live Home → fullscreen Co-Director → Close:

- no Home composer
- no provider alert on the Home card
- no duplicate Co-Director session
- fullscreen shell `data-mode="fullscreen"`
- project id retained

Playwright CLI could not launch Chromium in this agent environment (missing headless shell). Certification evidence is the live Vite browser walk plus unit/source-contract tests.

## REGRESSIONS

Verified live:

- Home hierarchy: Hero → Co-Director card → Timeline + MAGI → Projects/templates → compact Library → Explore
- Timeline Generator and MAGI Editor cards unchanged
- Project cards keep Active, resolution, scene/asset counts, generator, progress, Updated, Continue, menu
- Search / filters / Grid / List
- Project routing (`/project/{id}`)
- Active project context on the card and in fullscreen Co-Director

## TESTS

- `libraryRowBounds.test.ts` — **2 files / math helpers**
- `CoDirectorLaunchCard.test.ts` — composer absent, fullscreen path, asset registry
- `Home.compact.test.ts` — scroller + scroll reset wiring
- **6 passed** via Vitest
- `tests/e2e/home/home-compact-experience.spec.ts` added
- `tests/e2e/m32/generation-studio-aurora.spec.ts` updated off the removed composer

## RUNTIME

```text
COMFY BEFORE: healthy HTTP 200  GET http://127.0.0.1:8188/system_stats
COMFY AFTER:  healthy HTTP 200
COMFY RESTARTED?: NO
WHY?: Home UI/CSS only. Protected :8188 left untouched.
```

Vite HMR served the changes at http://127.0.0.1:5173/. Studio API http://127.0.0.1:8758/api/healthz **200**.

## ARTIFACTS

`docs/release-gate/home/artifacts/compact-2026-09-15/`

- `home-codirector-card-1920.png`
- `home-library-3rows-1920.png`
- `home-codirector-2560.png`
- `home-enter-codirector-fullscreen.png`

## LIMITATIONS

- Pre-change page height was reconstructed from the live 143-project library, not a screenshot taken before the first edit.
- Project cover cards remain ~461 px tall, so a correct 3-row library is ~1416 px — taller than a 1080 viewport. The page scrolls to the third row; the fourth row stays inside the library scroller, not on the page.
- Explore Adept UI and System Status remain below the library and still contribute to page length.
- Playwright headless did not run here because Chromium was not installed in the agent cache.

## STRICT THREE-ROW VIEWPORT (owner correction 2026-09-15)

Root cause: viewport used the first-card height while later rows were shorter, leaving leftover space that showed Row 4.

Repair: measure the first grid row, lock `grid-auto-rows` to that height, and set the results viewport to exactly `3 × row + 2 × gap`. Active badge overlays the cover so it no longer inflates Row 1. List and filter reuse the same locked height.

| Field | Measured (1440×900 and 1920×1080) |
| --- | --- |
| GRID CARD HEIGHT | **429.75 px** (uniform across rows) |
| ROW GAP | **16 px** |
| RESULTS VIEWPORT HEIGHT | **1321.25 px** (`429.75 × 3 + 16 × 2`) |
| VISIBLE GRID ROWS | **3** |
| ROW 4 HIDDEN AT TOP | **YES** (Row 4 starts 16 px below the viewport) |
| INTERNAL SCROLL | **YES** — Row 4 appears after scrolling the results scroller; hidden again at `scrollTop = 0` |
| HEADER FIXED | **YES** — `Your library` is outside the scroller |
| FILTERS FIXED | **YES** — Search / All / Active / Rendering / Complete / Grid / List stay put |
| LIST MODE | **1321.25 px** — same viewport; Grid → List → Grid unchanged |
| RESPONSIVE | 4 columns at 1440/1920; 3 columns at 1100; still 3 rows |
| HOME PAGE HEIGHT | **5361 px** at 1440×900 (143 projects; footprint no longer grows with count) |

## FINAL VERDICT

**GO — HOME PROJECT LIBRARY STRICT THREE-ROW VIEWPORT CERTIFIED**
