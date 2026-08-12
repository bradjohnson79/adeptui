# Co-Director Persistent Memory — Architecture (Wave A stub)

> **Status:** NO-GO — CO-DIRECTOR PERSISTENT MEMORY NOT YET DURABLY PROVEN
> Wave A implementer complete; independent Wave A verify still required before Wave B.
> Graduation remains **CONDITIONAL** until Wave D.

## 1. Purpose

This document is the architecture stub for Co-Director Persistent Memory. It
defines the durable conversation model introduced in Wave A and the waves
that follow. Wave A lands the server-owned event store and the race
certification harness. Subsequent waves (B–E) extend durability to
summarization, cross-device sync, retention, and the final graduation flip.

## 2. Governing law (non-negotiable)

The server owns BOTH creator and assistant/tool events. The client never
replaces the authoritative transcript; it only appends (creator turns) and
reconciles by id. Chat/stream completion MUST append assistant (+ tool)
events server-side. The client `sessionStorage` is a cache only — never an
authoritative overwrite source.

## 3. Storage model (Wave A)

### 3.1 `codirector_conversations` (thin header)

- `project_id` (PK)
- `model_id`, `provider_id` — current model/provider for the conversation
- `updated_at` — bumped on every append
- `revision` — monotonically increasing, bumped on every append; used for
  optimistic concurrency on the deprecated full-replace path
- `messages_json` — RETAINED ONLY for the reversible M028 backfill; no longer
  the source of truth. Reads ignore it once events exist.

### 3.2 `codirector_conversation_events` (append-only event log)

One row per appended message / tool event. This is the single source of truth.

- `id` (PK) — server-assigned event row id
- `project_id` (FK → projects.id, indexed)
- `sequence` (indexed) — server-assigned, strictly increasing per project
- `event_type` — `message` | `tool_call` | `tool_result` | `summary`
- `role` — `user` | `assistant` | `tool` | `system`
- `message_id` (indexed) — stable client/server message id; dedupe key
- `client_request_id` (indexed) — creator send idempotency key
- `content`, `message_type`, `status`, `attachments_json`
- `tool_id`, `tool_arguments_json`, `tool_result_json`, `request_id`
- `actor` — `user` | `assistant` | `system`
- `created_at`

### 3.3 Idempotency & concurrency

- Unique partial index on `(project_id, client_request_id)` — a retried
  creator append returns the original event instead of duplicating.
- Unique partial index on `(project_id, message_id)` — dedupes server-side
  assistant/tool events that share a stable message id.
- Optimistic concurrency: `expected_revision` on append. A mismatch yields
  HTTP 409 with the canonical folded conversation so the client can
  reconcile by id and retry.

## 4. API surface (Wave A)

- `POST /api/codirector/conversations/{project_id}/events` — append one or
  more events. Server assigns `sequence`. Idempotent on
  `client_request_id` / `message_id`. Optional `expected_revision` for
  optimistic concurrency (409 + canonical on conflict).
- `GET /api/codirector/conversations/{project_id}` — folds events into the
  legacy `{projectId, messages, model, providerId, updatedAt, revision}`
  shape. No client-visible shape change.
- `POST /api/codirector/conversations/{project_id}` — DEPRECATED as a blind
  full-replace. Now an idempotent append-merge by id; it can never truncate
  the event log. `allow_admin_replace=True` is the only repair path that
  fully replaces, and it requires a matching `expected_revision`.
- `chat_for_project` / `stream_for_project` — append the assistant reply
  (and tool call/result) as server-side events on completion.

## 5. Client model (Wave A)

- `studio-web/src/api.ts` adds `codirectorAppendConversationEvents` and
  exposes `revision` on `codirectorGetConversation`.
- `CoDirectorSession.tsx` appends a user turn as a single idempotent event
  (keyed on `client_request_id`), then after generation only RECONCILES by
  id via GET — it never POSTs the full transcript.
- `sessionStorage` remains a cache only.

## 6. Certification (Wave A)

- **Layer 1** — `studio-api/tests/test_codirector_persistent_memory_race.py`:
  12 forced-race scenarios × 100 iterations = 1,200 deterministic API
  executions with NO real LLM. Asserts zero truncation/loss/dup/cross-project
  /reorder and no pass-on-retry.
- **Layer 2** — `tests/e2e/codirector/codirector-memory-race-certification.spec.ts`:
  100 browser UI iterations cycling through the 12 scenarios with stubbed
  mock replies. `codirector-reload-persistence-race.spec.ts` stays green.

## 7. Waves B–E (out of scope for Wave A; do NOT start in this task)

- **Wave B** — Summarization / long-transcript compaction using `summary`
  events; provenance for compacted spans.
- **Wave C** — Cross-device sync + realtime revision broadcast.
- **Wave D** — Retention / export / import; graduation flip to GREEN.
- **Wave E** — Audit + repair tooling on top of the event log.

## 8. References

- Migration: `studio-api/app/migrations/m028_codirector_conversation_events.py`
- Event store: `studio-api/app/codirector/conversation_events.py`
- Service wiring: `studio-api/app/codirector/service.py`
- Router: `studio-api/app/routers/codirector.py`
- Client: `studio-web/src/api.ts`, `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- Layer 1: `studio-api/tests/test_codirector_persistent_memory_race.py`
- Layer 2: `tests/e2e/codirector/codirector-memory-race-certification.spec.ts`
- Race certification report: `docs/release-gate/codirector/CODIRECTOR_CONVERSATION_RACE_CERTIFICATION.md`
- Migration report: `docs/release-gate/codirector/CODIRECTOR_MEMORY_MIGRATION_REPORT.md`
