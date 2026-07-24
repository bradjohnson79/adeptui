# Co-Director Provider Reliability — Completion Report

**Branch:** `phase1b/codirector-provider-reliability`
**Related:** `docs/audit/CODIRECTOR_PROVIDER_ROOT_CAUSE.md`

## Summary

The browser no longer calls Ollama (directly or via a thin passthrough that leaks raw
`TypeError` text). All Co-Director LLM traffic now routes through a provider-neutral
gateway (`app/codirector/`) exposed at `/api/codirector/*`. The gateway classifies every
failure into a structured `{code, message, details, recoverable, recommendedAction}`
payload, so the frontend can distinguish "Ollama is offline" from "model not installed"
from "Adept API itself is unreachable" and react accordingly — Retry, Open Settings, or
pick a different model — instead of ever rendering a bare `Failed to fetch`.

In `STUDIO_E2E=1` (or `ADEPT_CODIRECTOR_PROVIDER=mock`), a deterministic mock provider
answers chat/health/model requests so Playwright can exercise the full reliability matrix
(ready, connection refused, no models, model missing, timeout) without a real local Ollama
install.

## Request path — before vs. after

**Before**

```text
CoDirectorSession.send()
  → api.assistantChat() → fetch("/api/assistant/chat")
  → routers/api.py assistant_chat()  [inline Ollama plumbing, bare 502/503 string details]
  → assistant.py chat_ollama() / ollama_reachable()
  → httpx → http://127.0.0.1:11434

Any transport failure (Adept API down, Ollama down) surfaced as:
  "I couldn't reach the local model. Failed to fetch."
```

**After**

```text
CoDirectorSession.send()
  → preflight: api.codirectorHealth("active")  → GET /api/codirector/providers/active/health
  → api.codirectorChat()                       → POST /api/codirector/chat
  → routers/codirector.py chat()
  → app/codirector/service.py chat_for_project()   [project/scene context, mode nudges,
                                                      scene_setup + suggested_prompt extraction]
  → app/codirector/service.get_provider()          [mock in E2E, else ollama]
  → providers/mock.py | providers/ollama.py        [structured CoDirectorError on failure]

/api/assistant/chat and /api/assistant/health remain as thin aliases over the same
gateway (chat_for_project / get_health) so any FE code still calling the legacy path
keeps working during migration.
```

## Backend changes

- `app/codirector/errors.py` *(pre-existing, extended)* — added `PROJECT_NOT_FOUND`,
  `VALIDATION_ERROR`, and `status_code_for_error()` (code → HTTP status mapping used by
  every codirector/assistant endpoint).
- `app/codirector/service.py` *(new)* — the gateway:
  - `active_provider_id()` / `get_provider()` — `ADEPT_CODIRECTOR_PROVIDER=mock|ollama`
    wins; otherwise `STUDIO_E2E=1` defaults to `mock`, else `ollama`. Unknown/cloud
    provider ids raise `PROVIDER_NOT_CONFIGURED` instead of silently falling back.
  - `list_providers_info()`, `get_health()`, `list_models()`.
  - `chat_for_project()` / `stream_for_project()` — rebuilt the project/scene context
    block, learning-preferences injection, and mode nudges that used to live inline in
    `routers/api.py::assistant_chat`, plus `scene_setup` / `suggested_prompt` extraction
    shared by both the streaming and non-streaming paths.
  - `run_cancellable()` + `request_cancel()` / `is_cancelled()` — an in-memory
    `asyncio.Task` registry so `/api/codirector/cancel` can abort an in-flight
    non-streaming request, and the SSE stream loop checks a cancelled-set each tick.
  - `get_conversation()` / `save_conversation()` / `delete_conversation()` — project-scoped
    conversation persistence backed by the new `codirector_conversations` SQLite table.
- `app/routers/codirector.py` *(new)* — endpoints:
  - `GET  /api/codirector/providers`
  - `GET  /api/codirector/providers/{providerId}/health` (accepts `active` as an alias for
    "whichever provider is currently selected")
  - `GET  /api/codirector/providers/{providerId}/models`
  - `POST /api/codirector/chat`
  - `POST /api/codirector/chat/stream` (SSE; owns its own DB session rather than using
    `Depends(get_db)`, since FastAPI tears a yield-dependency's session down as soon as the
    endpoint returns the `StreamingResponse`, before the generator body is ever iterated)
  - `POST /api/codirector/cancel`
  - `GET/POST/DELETE /api/codirector/conversations/{projectId}`
  - All `CoDirectorError`s become `HTTPException(status_code=status_code_for_error(code),
    detail=error.to_dict())` — 503 for connection/provider-unavailable, 400 for
    model/validation problems, 404 for missing project, 504 for timeout, 499 for
    cancellation.
- `app/routers/api.py` — `assistant_health` / `assistant_chat` rewritten as thin aliases
  over `codirector_service.get_health()` / `chat_for_project()`. `propose_timeline` (a
  separate, unrelated Ollama call) was left untouched.
- `app/db.py` — added `CoDirectorConversation` table (`project_id` PK, `messages_json`,
  `model_id`, `provider_id`, `updated_at`); created automatically via the existing
  `Base.metadata.create_all()` in `init_db()`.
- `app/routers/e2e.py` — added `POST /api/e2e/codirector/scenario` (E2E-only) so
  Playwright can flip the mock provider between `connection_refused` / `no_models` /
  `model_missing` / `timeout` / `slow` mid-suite by setting
  `ADEPT_CODIRECTOR_MOCK_SCENARIO` for the running process (the mock provider already
  re-reads that env var on every call).
- `app/main.py` — registers the new `codirector_router` at `/api` alongside the existing
  routers.
- `scripts/e2e-start.mjs` — API process now launches with `ADEPT_CODIRECTOR_PROVIDER=mock`
  by default (overridable) so the whole Playwright suite never depends on a real local
  Ollama install.

## Frontend changes

- `studio-web/src/api.ts`
  - `ApiError` gained `code` / `details` / `recoverable` / `recommendedAction`, populated
    from a `{code,message,...}` JSON `detail` object when present.
  - `classifyCoDirectorError()` — maps any thrown value (structured `ApiError`, or a raw
    `TypeError: Failed to fetch` from the browser) to `{code, message, recommendedAction,
    recoverable}`. Network-level fetch failures become `BACKEND_UNAVAILABLE` with a plain,
    actionable message instead of the raw `TypeError` text.
  - New helpers: `codirectorProviders`, `codirectorHealth`, `codirectorModels`,
    `codirectorChat` (accepts an `AbortSignal`), `codirectorCancel`,
    `codirectorGetConversation` / `codirectorSaveConversation` / `codirectorDeleteConversation`.
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — `send()` rewritten:
  - **Preflight**: calls `codirectorHealth("active")` before every send; blocks the send
    (keeping the draft and attachments intact) with a classified, actionable error if the
    provider is unreachable, has no models, or the selected model is missing — the message
    never reaches the transcript in that case.
  - **Transport-time failures** (after the user's message is already in the transcript):
    the user's message is preserved, `sendError` is set instead of appending a raw error
    string, and `retryLastSend()` re-sends the same text/mode.
  - **Never renders `Failed to fetch`**: every catch path runs the error through
    `classifyCoDirectorError`.
  - **AbortController**: a ref-held controller is aborted on provider unmount (app close)
    and on `closeSession()` (panel close); `isAbortError` results are treated as silent,
    non-error cancellations.
  - **Model selection**: `selectedModelId` is sent as `model` on `codirectorChat`; the
    Options panel exposes a model `<select>` populated from the health response.
  - **Best-effort conversation sync**: after each successful turn, the transcript is
    persisted via `codirectorSaveConversation` (fire-and-forget); `clearConversation()`
    also calls `codirectorDeleteConversation`.
- `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` — renders a
  `.codirector-error-card` banner (role="alert") with **Dismiss**, **Open Settings**, and
  **Retry** actions whenever `sendError` is set.
- `studio-web/src/components/CoDirector/CoDirectorOverflowMenu.tsx` — the existing
  "Model & provider" options panel now shows the endpoint, live status, a model dropdown,
  and a **Refresh / Test** button that re-runs the health preflight on demand.
- `studio-web/src/styles.css` — `.codirector-error-card` styling.

## Tests

- `studio-api/tests/test_codirector_provider.py` (new) — covers:
  - Ollama endpoint normalization (`host:port`, missing scheme, trailing slash, bare host).
  - `classify_httpx_error` for connect/timeout, plus truncation of unknown-error text to
    200 chars (secret/log-size safety basic).
  - `status_code_for_error` mapping and `CoDirectorError.to_dict()` key shape.
  - Mock provider scenarios: healthy, connection refused, no models, model missing,
    timeout, unknown-model rejection, and SSE-style lifecycle event ordering.
  - Gateway provider selection: default `ollama`, E2E default `mock`, explicit env
    override, and that an unconfigured/cloud provider id errors rather than silently
    falling back.
  - HTTP endpoints via `TestClient` (provider forced to `mock` per test so nothing touches
    a real Ollama): `/providers`, `/providers/{id}/health` (including the `active` alias),
    `/providers/{id}/models`, `/chat` (ready / connection-refused-503 / model-missing-400 /
    timeout-504 / empty-messages-400 / unknown-provider-503 / unknown-project-404),
    `/assistant/chat` and `/assistant/health` alias parity, conversation
    GET/POST/DELETE round-trip, and a cancel call for an unknown request id.
- `tests/e2e/codirector/chat-reliability.spec.ts` (new, `@critical @isolated`) — using the
  new `POST /api/e2e/codirector/scenario` override:
  1. **Ready mock chat** — send a message, assert an assistant bubble containing the mock
     reply, and assert the page text never contains `Failed to fetch` / "I couldn't reach
     the local model".
  2. **Provider unavailable** (`connection_refused`) — asserts the `.codirector-error-card`
     appears with Retry/Open Settings, the user's message is preserved in the transcript,
     and no bare fetch-failure text is rendered.
  3. **No models installed** (`no_models`) — asserts the send is blocked with an
     actionable, model-related message.
  4. **Health endpoint classification** — direct API assertions that
     `/api/codirector/providers/mock/health` and `.../active/health` return the expected
     `code` / `reachable` / `modelAvailable` combination per scenario.
  - `tests/e2e/codirector/provider-states.spec.ts` (pre-existing) is unaffected and keeps
    passing against the same gateway via the `/api/assistant/health` alias.

## Verification status

**pytest and Playwright were not run for this change.** The sandboxed shell/execution
backend for this session was completely unavailable for the entire session (every command,
including a bare `echo`, returned "no exit status" / "Execution backend unavailable" both
directly and via an isolated shell subagent) — this is an infrastructure outage, not a
result of the code changes. All Python and TypeScript files were re-read end-to-end after
writing and checked for import/reference correctness (e.g. the `Depends(get_db)` +
`StreamingResponse` session-lifetime bug described above), and `ReadLints` reported no
issues on every touched/created file, but nothing here has been exercised at runtime.

**Before merging, run:**

```bash
# Backend unit/integration tests
cd studio-api
.venv\Scripts\python.exe -m pytest tests/test_codirector_provider.py -v
.venv\Scripts\python.exe -m pytest -v   # full regression, esp. setup/source-manager suites

# Playwright critical suite (new + existing Co-Director specs, plus a broader smoke pass)
npx playwright test tests/e2e/codirector --grep @critical
npx playwright test --grep @critical
```

## Known gaps vs. the full 28-part spec

- **True token streaming to the UI**: `POST /api/codirector/chat/stream` exists, is wired
  to both providers' `stream()` implementations, and chunks tokens over SSE, but
  `CoDirectorSession.tsx` still calls the non-streaming `/api/codirector/chat` endpoint.
  Wiring the composer to consume the SSE stream (progressive token rendering) is not done.
- **Real mid-request cancel button in the composer UI**: `retryLastSend` covers the failure
  path, and the backend cancel registry/endpoint work end-to-end, but there is no visible
  "Stop generating" button wired to `api.codirectorCancel()` while `busy` is true.
- **Server-side conversation as source of truth**: conversations are saved to
  `/api/codirector/conversations/{projectId}` after each turn (fire-and-forget) and cleared
  on "Clear conversation", but the panel still loads/persists its transcript from
  `sessionStorage` on mount rather than hydrating from the server — server persistence is
  exercised but not yet authoritative.
- **Cloud provider stubs**: the gateway's `PROVIDER_IDS` list and `PROVIDER_NOT_CONFIGURED`
  error path are ready for `fal_*`/cloud providers, but no cloud provider implementation
  was added (out of scope — mock/ollama only, per the constraints).
- **Full 28-part copy review**: error/status copy was written to match the root-cause doc's
  intent (never show "Failed to fetch"; classify connection/model/timeout distinctly), but
  it has not been checked line-by-line against a separate "PART 24" copy spec document,
  which was not present in the repo at the time of this change.
- **Execution verification**: as noted above, pytest/Playwright could not be run in this
  session due to an infrastructure outage; this report reflects static review only.
