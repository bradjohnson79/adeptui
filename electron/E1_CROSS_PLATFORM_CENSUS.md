# E1 — Cross-platform classification

Observed before any Electron source was added. This file is the classification map for the desktop shell. It does not change product behavior.

## Cross-platform ready

- `BrowserRouter` routes in `studio-web/src/App.tsx` (`/`, `/project/:id`, `/co-director`, `/setup/comfy`, and the rest). A `file://` load breaks reload and deep links. Production must serve `studio-web/dist` on a loopback HTTP origin that is not `:5173`.
- Vite `studio-web/vite.config.ts` proxies `/api` and `/media` to Studio API `:8758` and starts the runtime only from the dev server plugin.
- `studio-web/runtime/bootstrap.ts` is the one bootstrap contract. It probes `127.0.0.1:8759`, reuses a live control plane, and otherwise spawns `scripts/run_runtime_supervisor.py serve`. It does not itself kill a process on `8758`, `8759`, or `8188`.
- Boot treats Comfy as optional. `StartupSystemsGauge` remains the creator-facing readiness surface.
- Setup remains the owner of model roots, Comfy install, and component update plans.

## Platform adapter required

- Process spawn, ownership, and command-line inspection.
- User-data root. Electron `app.getPath("userData")` is the packaged `STUDIO_DATA_DIR`.
- Python executable location. Dev bootstrap looks for `studio-api/.venv/Scripts/python.exe` or `studio-api/.venv/bin/python`. A packaged app must pass an explicit interpreter and must not walk the developer tree.
- Icons and installer type (NSIS, dmg, AppImage, deb).

## Windows-specific, left in place

- `studio-api/app/config.py` defaults Comfy input, output, and models under `C:\Users\bradj\AppData\Local\Comfy-Desktop\...`. Packaged launch sets `STUDIO_DATA_DIR` and the Comfy directory env vars so a fresh profile does not use those defaults. The web app is not rewritten to remove them.
- Root `package.json` `dev:*.ps1` scripts stay the web workflow. The desktop path does not call them.
- `install:all` uses a Windows venv layout. That script is not the desktop installer.

## Electron blockers if ignored

- `file://` plus `BrowserRouter`.
- Google fonts in `studio-web/index.html` (Fraunces, Manrope) fail offline. Local font files are the only planned web edit.
- `window.open` is used for in-app asset previews (Character, Environment, Prop, Scene). External `http(s)` must go through `shell.openExternal`.

## Supervisor boundary

`studio-api/runtime_supervisor/serve.py` `serve_forever` starts the Studio API child and then calls Comfy `request_start(..., spawn=True)`. On this machine a healthy Comfy Desktop listener is reused and not killed. A second supervisor is still the wrong owner for a packaged window: it can adopt the developer control plane, and its API child defaults to `studio-api/.venv`.

Packaged Electron therefore does not call `serve`. It starts only `python -m uvicorn app.main:app` with the packaged interpreter when `:8758` is free or already that interpreter. A foreign listener is reported and left running. `:8188` is never started, stopped, or adopted.

Dev Electron still calls `startRuntimeBootstrap`, which reuses a healthy `:8759` and does not spawn a second supervisor.

## Not present

No macOS or Linux app code. CUDA and NVIDIA are not assumed. No Electron dependency existed at census time. Signing certificates are not in the tree.

## Version

`electron/version.json` is the only desktop version (`1.1.0`). Builder metadata, installer names, and the update bridge read it. Component recipe versions stay with Setup.
