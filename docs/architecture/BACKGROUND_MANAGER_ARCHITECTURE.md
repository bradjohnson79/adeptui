# ComfyUI Background Manager & Localhost Background Manager

## Purpose

Adept UI's Background Manager integration allows creators to run local AI
services (ComfyUI, Studio API, Ollama) quietly in the background without
manually launching terminals or managing processes.

Two user-facing concepts:

- **ComfyUI Background Manager** — keeps ComfyUI headless running and ready
  for image/video generation.
- **Localhost Background Manager** — keeps the Adept Studio Runtime, local
  AI services, and runtime health available without manual terminal startup.

## Ownership Model

| Service   | Ownership when pre-existing | Ownership when launched by Adept UI |
|-----------|-----------------------------|-----------------------------------|
| ComfyUI   | REUSED                      | OWNED                             |
| Studio API| REUSED                      | OWNED                             |
| Ollama    | EXTERNAL (adopted)          | OWNED                             |
| Tunnel    | REUSED                      | OWNED                             |

**STOP never blindly terminates unrelated user processes.** The manager
tracks PID ownership and only stops processes it started or explicitly
adopted.

## Startup Behavior

1. Creator clicks "Enable Recommended Background Services" in Setup Wizard
   or toggles individual managers in Settings → Local Runtime.
2. Preferences are saved via `PUT /api/runtime-manager/preferences`.
3. `POST /api/runtime-manager/start` invokes `Start-AdeptRuntime.ps1`.
4. Already-running services are adopted/reused safely — no duplicate
   processes are created.
5. Status is re-probed after start and returned to the UI.

## Shutdown Behavior

1. Creator clicks "Stop" in Settings → Local Runtime.
2. `POST /api/runtime-manager/stop` invokes `Stop-AdeptRuntime.ps1 -Force`.
3. Only OWNED/adopted processes are terminated.
4. EXTERNAL processes (e.g., user-launched Ollama) are left running.

## Windows Auto-Start

- **OFF by default.**
- When enabled, uses Task Scheduler registration via
  `Register-AdeptRuntimeStartup.ps1`.
- When disabled, task is removed via `Unregister-AdeptRuntimeStartup.ps1`.
- Preference persists in `data/runtime_manager/preferences.json`.

## Hosted-Mode Behavior

A browser hosted at `https://adeptui.vercel.app` **cannot** directly launch
local Windows processes. The UI represents this truth correctly:

- Lifecycle controls (Start/Stop/Restart) are **disabled** in the UI.
- Preference toggles are **disabled/readonly**.
- A clear message explains: "Lifecycle controls are not available from
  browser-hosted Adept UI."
- Server-side enforcement: `_check_hosted()` in the router returns **403**
  for any lifecycle POST from a hosted origin. Security does not rely
  exclusively on frontend button disabling.

## Electron Boundary

The architecture maintains the intended boundary:

```
React UI
  → Studio API service contract
    → runtime_manager router
      → runtime_manager service
        → PowerShell lifecycle scripts
          → OS process management
```

**React never directly executes PowerShell.** All lifecycle actions flow
through the Studio API HTTP contract. The same `runtime-manager` API contract
is suitable for Electron — the Electron shell would simply replace the
PowerShell service layer with Node.js child_process, without changing the
API surface.

## Remote Access Boundary

- Remote Access is under **Advanced** in Settings → Local Runtime.
- It does not dominate beginner setup.
- When enabled, displays the Cloudflare Tunnel endpoint.
- Requires an approved remote Adept UI client.

## Status Architecture

`GET /api/runtime-manager/status` aggregates health from:

- ComfyUI: `http://127.0.0.1:8188/system_stats`
- Studio API: `http://127.0.0.1:8758/api/healthz`
- Ollama: `http://127.0.0.1:11434/api/tags`
- Tunnel: `https://api-beta.adeptui.org/api/healthz`
- GPU: `http://127.0.0.1:8758/api/production-control/status` (fallback:
  `/api/health`)

All probes are async with bounded timeouts. Failures are classified as
`ServiceStatus.ERROR` without crashing the status response.

## Request-Sharing Architecture

The Background Manager UI **does not introduce independent polling loops**.

- **Settings → Local Runtime** fetches status on mount and on user action
  (Start/Stop/Restart). No `setInterval` polling.
- **Setup Wizard BackgroundServicesSection** fetches on user action only.
- The existing **SystemStatusStrip** (Studio API, ComfyUI, Provider, GPU,
  Capabilities badges) is preserved and uses the shared request-stability
  architecture (single-flight dedup, TTL cache, suspension-aware polling).

10 simultaneous consumers requesting runtime status do **not** produce 10
identical network requests — the shared request cache layer deduplicates
GET requests within their TTL window.

## API Routes

| Method | Path                              | Purpose           | Hosted |
|--------|-----------------------------------|-------------------|--------|
| GET    | /api/runtime-manager/status      | Aggregate status  | Yes    |
| POST   | /api/runtime-manager/start       | Start services    | 403    |
| POST   | /api/runtime-manager/stop        | Stop services     | 403    |
| POST   | /api/runtime-manager/restart     | Restart services  | 403    |
| GET    | /api/runtime-manager/preferences| Load preferences  | Yes    |
| PUT    | /api/runtime-manager/preferences| Save preferences  | Yes    |
