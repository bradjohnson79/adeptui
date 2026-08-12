# M3.2 — Co-Director UI Refinement Report (M3.2b + M3.2c)

**Date:** 2026-07-28  
**Slice:** Design-system buttons + Co-Director compact/fullscreen correction  
**Verdict:** **PASS**

## Scope delivered

| Area | Result |
|---|---|
| Shared `Button` / `IconButton` + tokens (`--space-*`, `--codirector-*`) | PASS |
| Accessible `Drawer` (Escape, backdrop, focus trap, restore focus) | PASS |
| Compact Cinematic Minimal Glass, chat-first | PASS |
| Hamburger nav (live entries only) | PASS |
| Fullscreen Chat \| Project Content (Overview / Library / Production / Bible / Approvals) | PASS |
| M2.14 three-pane **not** mounted in compact | PASS |
| Playwright CODIRECTOR-UI-01..18 | PASS (18/18) |

## Explicit exclusions (later slices)

- M3.2a generation-tools audit
- Guided/Standard/Advanced novice mode (M3.2d)
- Site-wide table/status IA (M3.2e)
- Heading cards (M3.2f)
- Production Canvas review actions beyond Approvals v1 (M3.2g–h)
- Project memory / canon / Bible promotion / ingestion (M3.2i–n)
- Final YES certification (M3.2o)

## Evidence

- Spec: `tests/e2e/m32/codirector-ui.spec.ts`
- Screenshots: `artifacts/m32/codirector-ui/` (written by the suite)
- Key UI: `studio-web/src/components/ui/{Button,Drawer}.tsx`, `CoDirectorShell.tsx`, `CoDirectorNavDrawer.tsx`, `CoDirectorProjectContent.tsx`, `codirector-cinematic.css`

## Playwright matrix

| ID | Check | Status |
|---|---|---|
| CODIRECTOR-UI-01 | Compact chat-first, no M2.14 grid | PASS |
| CODIRECTOR-UI-02 | Header controls no overlap | PASS |
| CODIRECTOR-UI-03 | Drawer opens from hamburger | PASS |
| CODIRECTOR-UI-04 | Escape closes + restores focus | PASS |
| CODIRECTOR-UI-05 | Backdrop closes drawer | PASS |
| CODIRECTOR-UI-06 | Fullscreen two-pane | PASS |
| CODIRECTOR-UI-07 | Composer always visible | PASS |
| CODIRECTOR-UI-08 | Long draft no layout break | PASS |
| CODIRECTOR-UI-09 | Production stages readable | PASS |
| CODIRECTOR-UI-10 | Approvals readable | PASS |
| CODIRECTOR-UI-11 | Icon a11y names | PASS |
| CODIRECTOR-UI-12 | Button text non-transparent | PASS |
| CODIRECTOR-UI-13 | 200% zoom usable | PASS |
| CODIRECTOR-UI-14 | Narrow viewport + drawer | PASS |
| CODIRECTOR-UI-15 | axe no serious/critical on popup | PASS |
| CODIRECTOR-UI-16 | No unexpected horizontal scroll | PASS |
| CODIRECTOR-UI-17 | No unexpected console errors | PASS |
| CODIRECTOR-UI-18 | Nav → Project Content expands | PASS |

**Run note:** Suite was executed against a dedicated E2E stack (`STUDIO_E2E=1` via `scripts/e2e-start.mjs`). Reusing a non-E2E API on `:8742` will fail `waitForAppReady` (`/api/e2e/status`).

## Known follow-ups (non-blocking)

- Global migration of remaining app `button` / `.primary` pills to shared `Button` (M3.2b polish).
- Stage strip / Approvals deepen when M2.14 plan APIs return rich stage data (404 plan is handled with empty-state copy).
- Composer Options and suggestion cards rely on cinematic overrides over legacy light-theme globals; further consolidation in M3.2e.

## Go / no-go

**GO** for first-slice acceptance: compact is chat-first without overlapping dense panels; drawer keyboard/Escape works; fullscreen preserves conversation with Project Content; shared Button used for Co-Director chrome; CODIRECTOR-UI matrix green; this report filed.
