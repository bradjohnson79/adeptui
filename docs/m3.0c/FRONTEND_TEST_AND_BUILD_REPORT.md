# Frontend Test and Build Report

Date: 2026-07-27

## Lint

```text
cd studio-web
npm run lint
→ EXIT 0
```

Fixed conditional `useMemo` in `TimelineReferencesPanel.tsx` (rules-of-hooks). Remaining oxlint messages are warnings only.

## Build

```text
cd studio-web
npm run build
→ EXIT 0 (tsc -b && vite build)
```

Chunk size warning only (>500 kB). No TypeScript/build errors.

## Unit / component suite

No vitest/jest suite in `studio-web`. Browser coverage is Playwright (see `PLAYWRIGHT_FULL_GREEN_REPORT.md`).
