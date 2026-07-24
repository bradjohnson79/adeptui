# Co-Director Provider Reliability — Completion Report

**Branch:** `phase1b/codirector-provider-reliability`
**Related:** `docs/audit/CODIRECTOR_PROVIDER_ROOT_CAUSE.md`,
`docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md`,
`docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md`

> **Update (this session):** streaming + Stop Generating, retry-without-duplicate, and
> authoritative server-side conversation persistence — previously listed under "Known gaps"
> below — are now implemented and covered by Playwright. See "Session 2 additions" and the
> revised "Known gaps" section for what is genuinely still open for M2/M3.

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

## Session 2 additions — streaming, cancel, retry-dedup, persistence

- **Config endpoints** — `studio-api/app/codirector/config_store.py` (new) persists
  endpoint/model/timeout overrides to `codirector_config.json` under the data dir;
  `GET/PUT /api/codirector/config` in `routers/codirector.py` read/write it, with hostname
  validation on `PUT`. `service.build_provider("ollama")` now reads this store (falling back
  to `Settings` env defaults), and `list_provider_ids()`/`build_provider("mock")` reject the
  mock provider outside `STUDIO_E2E`/e2e-enabled runs so a stray env var can never mask a
  broken production setup. Secrets are redacted from Ollama HTTP error bodies
  (`errors.redact_secrets`) before they reach a `CoDirectorError` detail.
- **`api.ts: codirectorChatStream`** — a hand-rolled SSE client (`fetch` + `ReadableStream`
  reader, no library) that parses `data: {...}\n\n` frames into typed `CoDirectorStreamEvent`s
  (`request_started` / `provider_connected` / `token` / `completed` / `cancelled` / `error`),
  classifies a non-2xx/no-body response into an `ApiError` the same way `req()` does, and
  rethrows `AbortError` distinctly from transport failures.
- **`CoDirectorSession.tsx` rewritten `send()` / new `performSend()` / `cancelSend()`**:
  - The user's message is now appended to the transcript **before** the health preflight and
    persisted immediately — a provider-down or no-models block no longer silently drops it
    (previously the preflight ran first and returned before the message existed).
  - `performSend()` prefers `codirectorChatStream`, rendering tokens incrementally into a
    `status: "streaming"` message bubble; on `completed` it finalizes the bubble and persists
    the full turn via `codirectorSaveConversation`. If the stream transport itself throws
    (not a graceful `error` SSE event) it falls back once to non-streaming `codirectorChat`.
  - `cancelSend()` (wired to a new "Stop generating" button in `CoDirectorComposer`, shown in
    place of Send while `busy`) calls `api.codirectorCancel(requestId)` and aborts the local
    `AbortController`; the resulting `AbortError` is marked `status: "cancelled"` (vs.
    `"interrupted"` for a non-user-initiated abort, e.g. unmount) and any partial text is kept
    rather than discarded.
  - **Retry no longer duplicates the user's message.** `pendingRetryRef` now tracks the
    already-appended message's id; `retryLastSend()` resends the existing transcript slice up
    to and including that message via `performSend()` instead of calling `send(text)` again
    (which previously appended a second copy).
  - A `mountedRef` guards every post-await state update — note this **must** be reset to
    `true` at the top of its own mount effect (not just cleared `false` on cleanup), because
    `<StrictMode>` double-invokes effects in dev and a cleanup-only ref permanently "unmounts"
    the session after the first synthetic cycle. (This exact bug caused every streamed reply
    to silently vanish during manual verification — see "Verification status" below.)
- **Authoritative persistence** — a new effect hydrates `messages` from
  `codirectorGetConversation(projectId)` whenever the bound project changes, replacing the
  `sessionStorage`-only load. A session-scoped flag (`markStreamingStart/End` /
  `consumeAbandonedStreamingFlag` in `CoDirector/types.ts`, backed by `sessionStorage` so it
  survives a reload but not a new tab) detects a stream that was still in flight when the
  page was torn down and appends an `status: "interrupted"` assistant turn on the next load
  instead of silently showing nothing. `sessionStorage` remains a draft cache (used when no
  `projectId` is bound, or if the server is unreachable at load time).
- **"Clear conversation"** now asks for confirmation (`window.confirm`) before calling
  `clearConversation()` (which already called `codirectorDeleteConversation`).
- `CoDirectorMessage.tsx` — renders a small "Stopped" / "Interrupted — you can retry" status
  label under cancelled/interrupted bubbles.

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
- `tests/e2e/codirector/streaming-cancel.spec.ts` (new, `@critical @isolated`) using the
  `slow` mock scenario (0.35s pre-stream delay + 50ms/token) to get a reliable window for
  interacting mid-stream:
  1. **Incremental streaming** — a "Stop generating" control appears while busy, the
     assistant bubble is non-empty before the turn completes, and the final bubble contains
     the full `[mock]` reply.
  2. **Cancel** — clicking "Stop generating" returns the composer to idle with no error card,
     and the user's message stays in the transcript (a cancel is not a failure).
  3. **Retry without duplication** — provider down → error card → fix provider → click
     **Retry** on the error card (not the composer) → exactly one user bubble with the
     original text, followed by a successful assistant reply.
  4. **Reload persistence** — send a message, confirm it via a direct
     `GET /api/codirector/conversations/{projectId}` call, `page.reload()`, reopen
     Co-Director, and confirm both the user and assistant bubbles reappear from the server
     (not from `sessionStorage`, since a hard reload clears in-memory React state but the
     conversation is re-fetched by project id).

## Verification status

**pytest and Playwright were both run this session and are green.**

```text
studio-api/tests/test_codirector_provider.py -q   → 42 passed
studio-api (full suite)                            → 155 passed, 8 failed
  (all 8 failures are pre-existing, unrelated to Co-Director: pack-install / pack-providers-
   github / phase0-baseline / setup-refactor schema-version and status-label assertions —
   none of the touched Co-Director files are imported by those tests)

npx playwright test tests/e2e/codirector --retries=0        → 9 passed
  (chat-reliability.spec.ts ×4, provider-states.spec.ts ×1, streaming-cancel.spec.ts ×4)
npx playwright test --grep "@critical" --retries=0           → 29 passed (full critical suite)
```

Two real bugs were found and fixed while getting to green (not just test-harness issues):

1. **`service.get_health()` didn't catch `build_provider()` exceptions** — only
   `provider.health()` was wrapped in the `try/except CoDirectorError`, so requesting health
   for an unknown/unconfigured provider (or `mock` outside E2E, added this session) raised
   instead of returning a `Degraded` result. Fixed by moving `build_provider()` inside the
   `try`.
2. **`mountedRef` cleanup-only pattern silently broke all streaming** — `<StrictMode>`
   (enabled in `main.tsx`) double-invokes effects in dev, so a `useEffect(() => () => {
   mountedRef.current = false }, [])` with no corresponding "set true" on mount permanently
   flips the ref after the first synthetic mount→cleanup→mount cycle, causing every
   `performSend()` post-await state update to be silently skipped — replies streamed from the
   backend (confirmed via direct `curl`/CDP `fetch` against the same endpoint) but never
   reached the UI. Fixed by setting `mountedRef.current = true` at the top of the mount
   effect, not just `false` in its cleanup. This was caught via manual browser reproduction
   (CDP `Runtime.evaluate` replaying the exact fetch/SSE-parse logic) after the first
   Playwright run for "ready mock provider completes a chat turn" timed out waiting for the
   reply to appear.

Also fixed: `tests/e2e/codirector/chat-reliability.spec.ts`'s `openCoDirector()` used
`page.getByRole("button", { name: "Co-Director" })`, which is a substring match and now also
matches "Ask Co-Director" launcher buttons and a banner button — 3/4 tests failed on a
`strict mode violation` (4 matching elements) before ever exercising the gateway. Changed to
`page.locator("button.codirector-fab")`, which uniquely targets the global FAB.

## Known gaps vs. the full 28-part spec

Streaming, Stop Generating, retry-without-duplicate, and authoritative server-side
persistence (previously listed here) are now implemented — see "Session 2 additions" above.
Remaining, genuinely out-of-M1-scope items:

- **Cloud provider stubs**: the gateway's `PROVIDER_IDS` list and `PROVIDER_NOT_CONFIGURED`
  error path are ready for `fal_*`/cloud providers, but no cloud provider implementation
  was added (out of scope — mock/ollama only, per the constraints).
- **True incremental network streaming from Ollama itself**: `OllamaProvider.stream()` still
  calls `generate()` once and re-chunks the full reply into synthetic token events (same
  approach as the mock provider) rather than consuming Ollama's own NDJSON stream — the FE
  event schema (`request_started` / `provider_connected` / `token` / `completed`) already
  supports true incremental delivery whenever that's added, no FE changes required.
  Ollama-native NDJSON streaming was intentionally deferred; see the noted comment in
  `providers/ollama.py`.
- **Settings UI polish** (Detect / Test / Refresh / Change Endpoint / Diagnostics beyond the
  existing status + model dropdown + Refresh button in `CoDirectorOverflowMenu`) was not
  in scope for this session's M1 gap list and was left as-is.
- **Full 28-part copy review**: error/status copy was written to match the root-cause doc's
  intent (never show "Failed to fetch"; classify connection/model/timeout distinctly), but
  it has not been checked line-by-line against a separate "PART 24" copy spec document,
  which was not present in the repo at the time of this change.
- **Production Bible, orchestrator, tools/approvals, task graph, prompt compilers, asset
  lineage, continuity engine**: explicitly out of scope for Milestone 1 per the task
  constraints; see `docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` for the M2/M3 vision.
