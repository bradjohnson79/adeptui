# M3.0c Release-Mode Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |

## Frontend production build

```text
cd studio-web
npm run build
→ exit 0 (vite production build succeeded; chunk size warning only)
npm run lint
→ exit 0 after fixing conditional useMemo in TimelineReferencesPanel.tsx
```

## API / migrations

- Backend full pytest: **624 passed, 6 skipped, 0 failed**
- Migrations covered by suite (clean-install / idempotent cases green)
- Fal env bridge works when `STUDIO_FAL_ENV_BRIDGE=1` (verified key state without exposing secret)

## Feature flags / workers

- Production Executive + M2.9 flags exercised in E2E and live proofs
- Job workers start with API lifespan; recovery runs before worker start

## Fixture dependency

- Situation Phase 18 run used fixtures OFF
- Production paths withhold phantom asset IDs when providers missing
