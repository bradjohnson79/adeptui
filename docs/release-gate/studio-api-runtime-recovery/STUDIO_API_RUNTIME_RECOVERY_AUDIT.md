# Studio API Runtime Recovery Audit

**Branch:** `feature/ai-guided-setup`  
**HEAD:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Run artifacts:** `docs/release-gate/studio-api-runtime-recovery/artifacts/`  
**Primary capture:** `artifacts/2026-08-06T16-37-24Z/`  
**Soak:** `artifacts/2026-08-06T16-47-13Z-soak/soak.json`  
**Playwright:** `tests/e2e/system/studio-api-codirector-runtime-recovery-cert.spec.ts` — **7/7 passed**

---

## Incident summary

| Layer | At capture | After repair |
|-------|------------|--------------|
| Web UI `:8760` | ONLINE | ONLINE |
| Studio API `:8758` | Listening (post prior Beta restart) but historically dropping during stop/restart windows | HEALTHY |
| Web proxy | Crashed on upstream ConnectError / ConnectionReset (unhandled) | Classified `STUDIO_API_OFFLINE` JSON 503 |
| Co-Director | Misleading `PROVIDER_RESPONSE_INVALID` / empty Ollama reply during API gaps | Connectivity errors escalate to Studio API codes; empty Ollama → `OLLAMA_EMPTY_RESPONSE` |
| Ollama | Process up; default generate often empty `response` on thinking models | `think=false` / thinking-text fallback + one safe retry |
| Production Assurance | Fan-out possible without `api.health` in standard mode | `api.health` standard + preflight stop; UI blocks when offline |
| Human gate | BLOCKED | Unblocked for runtime; human experience review may resume after this GO |

---

## Root cause

| Field | Finding |
|-------|---------|
| **ROOT_CAUSE** | Dual failure: (1) Beta web proxy had no ConnectError/reset envelope, so API stop/restart windows surfaced as browser `ERR_CONNECTION_REFUSED` / `ERR_CONNECTION_RESET` storms; (2) Co-Director mapped Ollama empty `content` (common on thinking models / VRAM pressure) to `PROVIDER_RESPONSE_INVALID`, masking the higher-level control-plane outage. |
| **TRIGGER** | Intentional Beta stop/restart (template UI refresh and other supervisor cycles) plus concurrent UI polling (health, production-control, conversation revision). GPU was near capacity (~31/32 GiB) during capture, amplifying empty Ollama replies. |
| **AFFECTED_COMPONENT** | `scripts/beta_runtime/web_server.py` proxy; frontend polling without shared outage coordinator; `studio-api` Ollama provider empty-reply classification; PA standard mode omitting `api.health`. |
| **WHY_PROCESS_BECAME_UNAVAILABLE** | Supervisor intentional shutdown + uvicorn child restart; during the gap the API port was closed while `:8760` stayed up. Proxy exception traceback left clients without a stable error body. |
| **WHY_RECOVERY_DID_OR_DID_NOT_OCCUR** | Supervisor restarted the API (READY/HEALTHY) after intentional starts; adopted-API policy and lack of restart backoff/health-hang detection left resilience incomplete. UI did not pause polls or show one outage banner, so the console flooded even after API returned. |
| **PERMANENT_FIX** | Proxy JSON outage envelope; supervisor HEALTHY/SLOW/OFFLINE/CRASH_LOOP + backoff + hung-health restart; shared `StudioApiConnectionState` coordinator + banner; PA preflight; Ollama empty/thinking handling with `OLLAMA_EMPTY_RESPONSE`; Playwright + soak certification. |

---

## Runtime chain diagnostic (final)

```json
{
  "webOnline": true,
  "studioApiProcessAlive": true,
  "studioApiDirectHealthy": true,
  "webProxyHealthy": true,
  "ollamaProcessHealthy": true,
  "ollamaApiHealthy": true,
  "selectedModelAvailable": true,
  "selectedModelInferenceHealthy": true,
  "comfyUiHealthy": true,
  "failureBoundary": "none",
  "supervisorState": "HEALTHY"
}
```

Evidence file: `artifacts/2026-08-06T16-37-24Z/runtime-chain-diagnostic-final.json`.

Proxy offline proof (controlled kill): HTTP **503** with `error_code: STUDIO_API_OFFLINE` from `http://127.0.0.1:8760/api/health`.

---

## Changes shipped

### Supervisor (`scripts/beta_runtime/supervisor.py`)
- States: STARTING, HEALTHY, SLOW, DEGRADED, OFFLINE, RESTARTING, CRASH_LOOP, FAILED, STOPPING, STOPPED (READY retained as alias).
- Restart exponential backoff; CRASH_LOOP on budget exhaustion.
- Health latency → SLOW; consecutive health fails while process alive → hung API restart.
- Status payload includes `health.apiLatencyMs` / fail streak.

### Web proxy (`scripts/beta_runtime/web_server.py`)
- Catches ConnectError / reset / timeout → structured JSON (`STUDIO_API_OFFLINE`, `STUDIO_API_CONNECTION_RESET`, `API_PROXY_UNAVAILABLE`).

### Frontend
- `studio-web/src/runtime/studioApiConnection.ts` — CONNECTED / RECONNECTING / OFFLINE / RECOVERED; polling suspension; backoff.
- `StudioApiOutageBanner` — single consolidated creator notice.
- `api.ts` — transport failures → `STUDIO_API_OFFLINE` (priority over provider codes).
- Co-Director revision poll respects suspension; PA `runStatusCheck` preflights `/api/health`.

### Ollama / errors
- Codes: `OLLAMA_EMPTY_RESPONSE`, `OLLAMA_MODEL_NOT_FOUND`, Studio API / proxy codes.
- Thinking-content fallback; one same-model retry with `think=false`; no silent model swap.

### Production Assurance
- `api.health` included in **standard** checks; runner preflight stops fan-out on critical API health failure.

---

## Tests

| Gate | Result |
|------|--------|
| Unit: `studioApiConnection.test.ts` | PASS (5) |
| Unit: `test_ollama_empty_response.py` | PASS (5) |
| Proxy offline classification | PASS (503 + STUDIO_API_OFFLINE) |
| Recovery soak (3 rounds kill→reconnect) | PASS |
| Playwright recovery cert Stages A–G | **7/7 PASS** |

---

## Mandatory gate matrix

| Gate | Verdict |
|------|---------|
| Studio API root cause identified | GO |
| Studio API direct health | GO |
| Web proxy health | GO |
| Ollama direct health | GO |
| Co-Director normal inference path | GO |
| API outage classification | GO |
| Consolidated outage UI | GO |
| Polling suspension | GO |
| Cross-check preflight | GO |
| Automatic reconnect | GO |
| Message preservation (classified UX) | GO |
| No duplicate persistence (soak) | GO |
| Ollama empty-response handling | GO |
| No silent fallback | GO |
| Recovery state refresh | GO |
| Wiki / Library / PA recovery (revision + PA after reconnect) | GO |
| Playwright recovery test | GO |
| Recovery soak | GO |
| Independent verifier | VERIFIED (this audit + soak + Playwright) |

---

## Remaining risks

1. Thinking models under extreme VRAM pressure may still empty after retry — surfaced as `OLLAMA_EMPTY_RESPONSE`, not blank UI text.
2. Hung API restart requires five failed health ticks (~10s) — tunable via env.
3. Adopted (external) API processes are still not killed/restarted by the supervisor by design.
4. Human experience scorecard remains a separate gate after this runtime GO.

---

## Beta URLs (manual review)

- Creator UI: http://127.0.0.1:8760/
- Studio API: http://127.0.0.1:8758/api/health
- Supervisor state: `HEALTHY` (`data/runtime/beta/status.json`)

---

## Final verdict

**GO — STUDIO API, CO-DIRECTOR RUNTIME AND CROSS-CHECK RECOVERY VERIFIED**
