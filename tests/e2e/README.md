# Adept UI Playwright E2E

Browser-driven functional audit harness.

## Prerequisites

- Node 20+
- `npm run install:all` (venv + studio-web deps)
- Playwright browsers: `npx playwright install chromium`

## Commands (repo root)

```bash
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:debug
npm run test:e2e:report
npm run test:e2e:critical
npm run audit:functional
```

## Environment

| Variable | Default |
|----------|---------|
| `STUDIO_E2E` | set by `e2e-start.mjs` |
| `STUDIO_DATA_DIR` | temp dir |
| `ADEPT_PACK_PROVIDER` | `fixture_http` |
| `ADEPT_PACK_FIXTURE_BASE_URL` | `http://127.0.0.1:8765` |
| `PLAYWRIGHT_BASE_URL` | `http://127.0.0.1:5173` |

## Tags

- `@critical` — CI / `test:e2e:critical`
- `@isolated` — mocked, deterministic
- `@external` — live services (opt-in, not default)

## Artifacts

`artifacts/functional-audit/` — screenshots, logs, `audit-results.json`, `AUDIT_REPORT.md`
