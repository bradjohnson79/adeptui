# Ollama Runtime Fabric — Completion Report

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651`  
**Date:** 2026-09-04  
**Mission:** Journey closure — Unified Runtime Fabric + Headless Ollama (no redesign)

## Verdict

**GO — ADEPT UNIFIED RUNTIME FABRIC INCLUDING HEADLESS OLLAMA E2E CERTIFIED**

The two remaining live gates are now proven: true full cold-start, and live watchdog self-heal with post-recovery Co-Director inference.

## What remains preserved (not rewritten)

- `runtime.local_llm`
- Headless `ollama serve` (`CREATE_NO_WINDOW` / detached)
- Owned vs external process distinction
- Watchdog / backoff; Ollama health-miss threshold **2 cycles**
- Startup gauge Local AI Runtime (no ports)
- Co-Director provider-unavailable honesty
- PoseCraft product questions stay deterministic (not Ollama)

## Closure results

| Gate | Result |
|---|---|
| 1 True full cold-start | **PASS** |
| 2 Live Ollama watchdog self-heal | **PASS** |
| 3 Co-Director inference after recovery | **PASS** |
| 4 Model-readiness policy | **PASS** |
| 5 Startup gauge truth | **PASS** |
| 6 External Ollama safety | **PASS** (existing unit + lifecycle tests; not re-run destructively) |
| 7 Regression | **PASS** |
| Required tests | **PASS** |
| Independent double-check | **PASS** 10/10 |

## CLOSURE 1 — True full cold-start

Before shutdown (all Adept-owned, queue empty):

| Service | PID | Ownership | Health |
|---|---|---|---|
| Runtime Supervisor | 36572 | owned | running |
| Studio API | 62552 | owned | healthy |
| Comfy :8188 | 74356 | owned (`owned.json` true, Adept YAML) | ready |
| Ollama | 28160 | owned | `/api/tags` 200, modelReady |

Stop path: identity-verified `POST :8759/stop` then SIGTERM of owned supervisor 36572.  
Result: all four PIDs dead. No leftover `ollama serve`. An orphaned `llama-server` from prior owned PID 66168 was cleared so VRAM/duplicates would not contaminate the boot.

Bootstrap (normal supervisor path, not per-service start):

```text
studio-api\.venv\Scripts\python.exe scripts\run_runtime_supervisor.py serve
```

`20:04:59` spawn → `20:05:41` API + Comfy + Ollama HTTP 200.

After restore:

| Service | PID | Ownership | Health |
|---|---|---|---|
| Runtime Supervisor | 35844 | owned | :8759 up |
| Studio API | 53360 | owned | healthy |
| Comfy | 69108 (parent 31556) | owned | ready — **one listener** |
| Ollama | 30300 | owned | daemonOnline, modelReady, `qwen3.6:35b-a3b` |

- Duplicate Ollama: **no** (1 serve)
- Duplicate Comfy: **no** (parent/child tree, one :8188 LISTEN)
- Terminal/console windows: **none**
- Startup gauge observed: **Initializing Creative Runtime** / “Adept is bringing its creative runtime online. No action needed.”
- Modal auto-closed; Korri Anadriya home usable

Artifacts: `artifacts/COLD_START_BEFORE.json`, `artifacts/COLD_START_AFTER.json`

## CLOSURE 2 — Live watchdog self-heal

Started from Local AI Runtime **ONLINE** (owned PID **30300**).

Terminated **only** that verified `ollama serve`. Did **not** call `POST /start-ollama`.

| | |
|---|---|
| Kill | 2026-09-03T20:06:55 |
| Detection | **526 ms** — daemonOnline=false, availability=**STARTING**, modelReady=false, ownership still owned |
| Restart | pid file `2026-09-04T03:07:30Z` |
| Recovered | **48195 ms** — new owned PID **9248**, `/api/tags` 200, availability=**ONLINE**, modelReady=true |
| Storm | **no** — one `ollama` event in `restart_history.json` |
| Comfy during heal | **69108 unchanged** |
| Studio API during heal | **53360 unchanged** |

Artifact: `artifacts/WATCHDOG_SELF_HEAL.json`

## CLOSURE 3 — Co-Director after recovery

`POST /api/codirector/chat` on project `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`:

> Name the current project in one short sentence.

| Field | Observed |
|---|---|
| reply | “Understood. I am holding space for *Korri Anadriya* and will wait for your direction…” |
| model | `qwen3.6:35b-a3b` |
| providerId | `ollama` |
| fallbackUsed | **false** |
| fallbackReason | empty |
| duration | 38072 ms |

Not a canned fallback. Not provider-unavailable. HTTP daemon health alone was not used as the proof.

## CLOSURE 4 — Model-readiness policy

Frozen separately:

| State | This machine |
|---|---|
| daemon online | true (PID 9248) |
| model installed | `qwen3.6:35b-a3b`, `qwen3.8:27b` |
| model selected | `qwen3.6:35b-a3b` (`data/codirector_config.json` + `/api/codirector/config`) |
| selected model ready | **true** |

`gemma4:31b-it-qat` is the code default when nothing is selected. It is **not** the active required model here.

**Classification: NOT INSTALLED / OPTIONAL CONFIGURATION** — not a Runtime Fabric failure. No large-model pull was performed.

## CLOSURE 5 — Startup gauge

- Cold-start: modal **Initializing Creative Runtime** then auto-close
- Watchdog: `runtime.local_llm` **STARTING** → **ONLINE**
- Ordinary gauge chrome: logical labels only (unit: `startupSnapshot.test.ts` — 8 passed). No `:11434` / `:8188` / `:8758` shown to ordinary users

## CLOSURE 6 — External Ollama safety

Not re-run live (already conclusive, destructive-unnecessary):

- `test_start_ollama_adopts_external_when_not_owned`
- `test_watch_leaves_external_ollama`
- `test_stop_leaves_external_ollama`

## CLOSURE 7 — Regression

| Surface | Result |
|---|---|
| Startup modal | Appeared and auto-closed after required state |
| Studio API | healthz 200, PID 53360 |
| Canonical Comfy | system_stats 200, PID 69108 after authorized cold-start |
| Co-Director | live inference after watchdog |
| PoseCraft “What is PoseCraft used for?” | Deterministic staging-workspace answer; `fallbackUsed=false`; not an Ollama model call |
| Runtime Manager status | logical services present |
| Supervisor / snapshot tests | green (below) |

## Tests

- `studio-api/tests/test_ollama_runtime_fabric.py` — **11 passed**
- Supervisor group (`test_runtime_supervisor_lifecycle.py`, `test_adept_runtime_service.py`, `test_headless_comfy.py`, `test_dual_background_services.py`) — **75 passed**
- `startupSnapshot.test.ts` — **8 passed**
- Independent live double-check — **10/10 PASS** ([Double-check](f23984a2-1bf5-458e-bbef-153616bcec50))

## Runtime (after closure)

- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` PID **53360**
- Supervisor: PID **35844**
- Local AI Runtime: owned PID **9248**, required `qwen3.6:35b-a3b`

**COMFY BEFORE:** PID **74356** / RTX 5090 / ready / owned  
**COMFY AFTER:** PID **69108** / ready / owned / HTTP 200  
**COMFY RESTARTED?:** **YES**  
**WHY?:** Owner-approved true full cold-start required stopping Adept-owned `:8188` and restoring it through `runtime_supervisor serve`. After restore, watchdog self-heal and Co-Director inference did **not** restart Comfy (69108 held).
