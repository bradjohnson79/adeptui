# Playwright Functional Audit — Architecture

Phase 0.5 browser-driven audit of Adept UI (Gen Studio).

## Stack

| Layer | Detail |
|-------|--------|
| Frontend | React 19 + Vite 8 on `127.0.0.1:5173` |
| Backend | FastAPI + uvicorn on `127.0.0.1:8742` |
| Proxy | Vite proxies `/api` and `/media` → API |
| Package managers | npm (root + studio-web); Python venv in `studio-api/.venv` |
| Data | Isolated via `STUDIO_DATA_DIR` (never the user `data/` tree) |

## Dev vs E2E launch

- Normal: `npm run dev` (API with `--reload` + Vite)
- E2E: `scripts/e2e-start.mjs` starts API **without** `--reload`, sets `STUDIO_E2E=1`, waits for `/api/health` and `/api/setup/status`, then Vite

## Setup UI entry

There is no `/setup` route. Open:

`/project/{id}?workspace=setup`

## Pack sources

Resolution order: explicit URL / override → GitHub Releases (`ADEPT_PACK_*`) → Hugging Face (stub) → not configured.

E2E uses `ADEPT_PACK_PROVIDER=fixture_http` plus a local fixture HTTP server, or `set_source_override` localhost ZIP URLs via the E2E control API.

## Folder picker

Production opens a native OS dialog via `POST /api/setup/browse-path`.

With `STUDIO_E2E=1`, the same endpoint accepts `forced_path` and returns it without a dialog. The UI only sends `forced_path` when `window.__ADEPT_E2E_FORCED_PATH__` is set by Playwright.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `STUDIO_E2E` | Enables forced browse path + E2E control routes |
| `STUDIO_DATA_DIR` | Isolated SQLite + setup state |
| `STUDIO_API_HOST` / `STUDIO_API_PORT` | API bind (default 127.0.0.1:8742) |
| `ADEPT_PACK_PROVIDER` | `fixture_http` for mock releases |
| `ADEPT_PACK_FIXTURE_BASE_URL` | Base URL of the fixture server |
| `ADEPT_PACK_GITHUB_OWNER` / `REPOSITORY` | Live GitHub (unused in mock mode) |
| `PLAYWRIGHT_BASE_URL` | Default `http://127.0.0.1:5173` |

## Artifacts

`artifacts/functional-audit/` (gitignored):

- `audit-results.json`
- `AUDIT_REPORT.md`
- screenshots, traces, videos, backend logs

## Test tags

- `@critical` — required CI / `test:e2e:critical`
- `@isolated` — fully mocked, deterministic
- `@local` — needs local services optionally
- `@external` — live GitHub/HF/Ollama/Comfy (opt-in)
- `@large-download` — disabled by default

## Commands

```bash
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:debug
npm run test:e2e:report
npm run test:e2e:critical
npm run audit:functional
```
