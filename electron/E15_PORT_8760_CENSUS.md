# 8758 / 8760 census

Written before the desktop port split. No global replacement.

## DEV-ONLY — keep 8758

- Vite proxy in `studio-web/vite.config.ts`
- Dev supervisor `runtime_supervisor/constants.py` `API_PORT`
- Dev supervisor child launch, which still refuses a non-8758 port for the browser stack
- `studio-web/runtime/bootstrap.ts` default spawn of that supervisor
- Electron development mode, which loads Vite `:5173` and therefore the Vite proxy
- Playwright and e2e helpers that target the live dev API
- Boot facts when `ADEPT_RUNTIME_MODE` is unset

## ELECTRON-AWARE — read the endpoint owner

- `electron/runtime.cjs` packaged uvicorn spawn
- `electron/renderer-server.cjs` `/api` and `/media` proxy
- `electron/main.cjs` status and collision text
- `studio-api/app/boot/live.py` and the port line in `evaluate.py`
- `studio-api/app/main.py` CORS, only when the process is the packaged runtime
- `studio-api/app/codirector/routers/diagnostics.py` direct API probe
- `studio-web/src/pages/DiagnosticsPage.tsx` label, which prints the probed port
- `studio-web/src/components/StartupSystemsGauge.tsx`, which shows the boot endpoint

## TEST FIXTURE

- `electron/update/bridge.test.mjs` netstat sample
- `studio-api/tests/test_boot_certification.py`
- e2e specs under `tests/e2e/`

## DOCUMENTATION

- `electron/E1_CROSS_PLATFORM_CENSUS.md`
- `electron/E14_DESKTOP_CERTIFICATION.md`
- Historical docs that mention retired web `:8760`

## STALE / DEAD — do not treat as the desktop API

`RETIRED_WEB_PORT = 8760` is the old frontend server. The supervisor must not start that server, and the control plane must not move to 8760. Background Services stay on 8759. Comfy stays on 8188.

## AMBIGUOUS — left unchanged

Root probe scripts (`_*.py`), memory notes, and release-gate history. They describe the dev API or the retired web server.

## Mode decision

Electron development loads Vite, so its Studio API stays 8758. Electron packaged mode is the isolated API on 8760. The two can run together.
