# Co-Director Milestone 1 — Final Summary Report

**Date:** 2026-07-24  
**Branch:** `phase1b/codirector-provider-reliability`  
**Status:** Complete  
**Checkpoint:** `2409aee` / tag `checkpoint/codirector-m1-start`  
**Ship commit:** `f76de42` — *Co-Director M1: streaming, cancel, retry-dedup, server persistence*

**Related docs**

- [Root cause](CODIRECTOR_PROVIDER_ROOT_CAUSE.md)
- [Reliability report (detailed)](CODIRECTOR_PROVIDER_RELIABILITY_REPORT.md)
- [Implementation plan (as-built)](../architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md)
- [Production Brain vision (M2/M3)](../architecture/CODIRECTOR_PRODUCTION_BRAIN.md)

---

## Verdict

Co-Director is no longer a fragile Ollama chat panel that collapses every failure into  
`I couldn't reach the local model. Failed to fetch.`

It is an Adept-owned, provider-neutral reliability runtime:

- Browser talks only to Adept `/api/codirector/*`
- Adept talks to Ollama (or a deterministic mock in E2E)
- Failures are structured, recoverable, and actionable
- User messages are preserved; cancel is not an error; retry does not duplicate turns
- Conversations persist by project on the server

Milestone 1 is **closed**. Production Bible / orchestrator / tools / approvals remain Milestone 2+.

---

## Root cause (confirmed)

| Fact | Detail |
|------|--------|
| Browser → Ollama CORS? | **No.** Browser never called Ollama directly. |
| Actual path | `CoDirectorSession` → `/api/assistant/chat` → Adept → Ollama `:11434` |
| Bad UX string | Built in `CoDirectorSession` by interpolating `err.message` |
| When Adept/proxy down | `err.message` = `Failed to fetch` → generic bubble |
| When Adept up, Ollama down | Usually a clearer 503 string — still unstructured |

**Real weakness:** thin assistant endpoint, hardcoded model (`gemma4:12b`), no preflight, no structured codes, FE unable to distinguish backend loss from provider loss.

---

## Architecture — before vs after

### Before

```text
UI send()
  → /api/assistant/chat
  → inline Ollama plumbing + bare 502/503 strings
  → catch: "I couldn't reach the local model. ${err.message}"
```

### After

```text
UI send()
  → preflight GET /api/codirector/providers/active/health
  → prefer POST /api/codirector/chat/stream (SSE tokens)
  → fallback POST /api/codirector/chat
  → cancel POST /api/codirector/cancel
  → persist GET/POST/DELETE /api/codirector/conversations/{projectId}

Gateway (app/codirector/service.py)
  → MockCoDirectorProvider (STUDIO_E2E only) | OllamaProvider
  → CoDirectorError { code, message, details, recoverable, recommendedAction }
```

Legacy `/api/assistant/chat` and `/api/assistant/health` remain **thin aliases** over the same gateway (no second implementation).

---

## What shipped (Milestone 1 checklist)

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Structured errors; never bare `Failed to fetch` | Done |
| 2 | `/api/codirector/*` gateway; FE uses it for chat/health/models/config | Done |
| 3 | Provider interface + Ollama + Mock | Done |
| 4 | Health + model discovery + model selection | Done |
| 5 | SSE streaming + Stop Generating + cancel | Done |
| 6 | Retry without duplicating the user message | Done |
| 7 | Server conversation persistence by project | Done |
| 8 | Unit + Playwright + `@critical` green | Done |
| 9 | Implementation / reliability / Production Brain docs | Done |

---

## API surface

| Method | Path | Role |
|--------|------|------|
| GET | `/api/codirector/providers` | List providers |
| GET | `/api/codirector/providers/{id}/health` | Health (`active` alias) |
| GET | `/api/codirector/providers/{id}/models` | Model discovery |
| GET/PUT | `/api/codirector/config` | Endpoint / model / timeout |
| POST | `/api/codirector/chat` | Non-streaming chat |
| POST | `/api/codirector/chat/stream` | SSE stream |
| POST | `/api/codirector/cancel` | Cancel in-flight request |
| GET/POST/DELETE | `/api/codirector/conversations/{projectId}` | Persistence |
| POST | `/api/e2e/codirector/scenario` | E2E mock scenario flip (E2E only) |

**Error codes (selected):**  
`BACKEND_UNAVAILABLE`, `CONNECTION_REFUSED`, `PROVIDER_UNAVAILABLE`, `REQUEST_TIMEOUT`,  
`MODEL_NOT_SELECTED`, `MODEL_NOT_FOUND`, `NO_MODELS_INSTALLED`, `PROVIDER_RESPONSE_INVALID`,  
`REQUEST_CANCELLED`, `STREAM_INTERRUPTED`, `PROVIDER_NOT_CONFIGURED`, `UNKNOWN_PROVIDER_ERROR`

---

## Frontend behavior

- **Preflight** before generation; block with actionable card when not Ready / no models / model missing
- **Stream first**, non-stream fallback; incremental tokens in the bubble
- **Stop generating** → abort + `codirectorCancel`; partial text kept; status `cancelled` / `interrupted` (not an error card)
- **Retry** resends the existing transcript slice — no second user bubble
- **Hydrate** from server on project bind; persist every completed / failed / cancelled turn
- **Clear conversation** requires confirmation
- Options panel: provider status, endpoint, model dropdown, Refresh / Test

---

## Test results (exact)

| Suite | Result |
|-------|--------|
| `pytest tests/test_codirector_provider.py` | **42 passed** |
| Full backend pytest | 155 passed, **8 failed** (pre-existing, unrelated: pack-install / pack-providers-github / phase0-baseline / setup-refactor) |
| `playwright test tests/e2e/codirector` | **9 passed** |
| `playwright test --grep "@critical"` | **29 passed** |

### Playwright coverage (`tests/e2e/codirector/`)

- `chat-reliability.spec.ts` — ready chat; provider unavailable (no `Failed to fetch`, prompt preserved, Retry); no models; health classification
- `streaming-cancel.spec.ts` — incremental stream; Stop generating; retry-dedup; reload persistence
- `provider-states.spec.ts` — route / health smoke (legacy alias)

### Bugs found while going green

1. `get_health()` did not catch `build_provider()` failures → unknown/mock-outside-E2E raised instead of degraded health.
2. `mountedRef` cleanup-only pattern permanently “unmounted” the session under React StrictMode → streamed replies never painted.
3. Co-Director FAB locator was a substring match (`name: "Co-Director"`) and collided with “Ask Co-Director” launchers → fixed to `button.codirector-fab`.

---

## Key files

**Backend:** `studio-api/app/codirector/` (`errors`, `service`, `config_store`, `providers/*`), `routers/codirector.py`, `routers/e2e.py` (scenario), `db.py` (`CoDirectorConversation`), `scripts/e2e-start.mjs`

**Frontend:** `studio-web/src/api.ts`, `components/CoDirector/CoDirectorSession.tsx`, `CoDirectorComposer.tsx`, `CoDirectorConversation.tsx`, `CoDirectorOverflowMenu.tsx`, `CoDirectorMessage.tsx`, `types.ts`

**Tests:** `studio-api/tests/test_codirector_provider.py`, `tests/e2e/codirector/*.spec.ts`

---

## Deferred (intentionally not M1)

| Item | Milestone |
|------|-----------|
| Native Ollama NDJSON streaming (today: generate-then-rechunk) | M1.x / M2 polish |
| Cloud providers (OpenAI / Anthropic / Gemini / …) | M2+ |
| Production Bible, context assembly, modes, specialists | M2 |
| Orchestrator, tools, proposals, approvals, task graph | M2 |
| ComfyUI / Source Manager / Virtual Stage / prompt compilers / lineage / continuity | M3 |
| Full Settings → AI Providers / Health Dashboard / Setup Wizard cards polish | Early M2 |

---

## Completion gates

| Gate | Met? |
|------|------|
| No bare `Failed to fetch` in chat | Yes |
| Browser never calls Ollama | Yes |
| Mock unavailable outside E2E | Yes |
| Cancel ≠ application error | Yes |
| Retry does not duplicate user message | Yes |
| Conversations restore by project | Yes |
| Backend stays up when Ollama is down | Yes |
| `@critical` Playwright green | Yes (29/29) |
| Co-Director unit tests green | Yes (42/42) |

---

## Recommended next phase

Start **Milestone 2 — Production Brain foundation**:

1. Production Bible schemas (project profile, characters, locations, continuity rules)
2. Bounded `ProjectContextService` + context manifest
3. Configuration-driven Co-Director modes
4. Specialist registry + `CoDirectorOrchestrator` (propose, don’t mutate)
5. Read-only tools → proposal/write tools with approval records
6. Thin Health Dashboard + Setup Wizard Co-Director status cards (reuse M1 health API)

Until then, local production use should: run Ollama, select a discovered model in Co-Director Options, and treat Adept API availability as a first-class health signal.
