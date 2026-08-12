# Co-Director Persistent Memory — Migration Report (M028)

> **Status:** Migration implemented and exercised under Layer 1 certification.
> Independent verify still required.

## 1. Migration identity

- **File:** `studio-api/app/migrations/m028_codirector_conversation_events.py`
- **Revision:** `0028`
- **Checksum source:** `M028:codirector-conversation-events:v1`
- **Reversible:** Intent-reversible. The legacy `messages_json` column is
  preserved, so a rollback simply ignores the new table and column. The new
  table + `revision` column can be dropped without losing legacy data.

## 2. What the migration does

1. Creates `codirector_conversation_events` (append-only event log) with
   indexes on `project_id`, `sequence`, `message_id`, `client_request_id`,
   `tool_id`, `request_id`, plus two unique partial indexes for idempotency:
   - `ux_convo_events_client_request` on `(project_id, client_request_id)`
     WHERE `client_request_id IS NOT NULL`
   - `ux_convo_events_message_id` on `(project_id, message_id)` WHERE
     `message_id IS NOT NULL`
   - **No FK to `projects.id`** — intentionally. The legacy
     `codirector_conversations` header used a plain string `project_id` with
     no FK so conversations could be seeded for project ids not in the
     `projects` table (test seeding, historical data, repair tooling). The
     event log mirrors that contract to preserve backward compatibility. The
     SQLAlchemy model in `db.py` likewise uses a plain indexed `String(36)`.
2. Adds `revision INTEGER DEFAULT 0` to `codirector_conversations` (idempotent
   `ALTER TABLE` guarded by a column-existence check).
3. Backfills every existing `codirector_conversations.messages_json` row into
   the new event log. The backfill is **idempotent** and **defensive**: it
   returns early if the legacy header table does not exist (bare
   migration-runner path on a fresh engine), and a row whose `message_id`
   already has an event is skipped, so re-running after a partial failure
   never duplicates events. Each backfilled event gets a server-assigned
   `sequence` (continuing from any existing max sequence for the project),
   and the header `revision` is bumped past the backfill so optimistic
   concurrency sees the migration.

## 3. Verification

- **Schema:** `init_db()` in `studio-api/app/db.py` mirrors the migration
  (creates the table/column when absent and adds `revision` to existing
  rows), so a fresh DB and a migrated DB converge on the same schema.
- **Layer 1 cert:** `studio-api/tests/test_codirector_persistent_memory_race.py`
  runs 1,200 deterministic executions (12 scenarios × 100) plus a 409
  conflict test, a legacy-save append-merge test, and a chat-server-side
  append test. All 15 test functions passed (1,500 total assertions across
  iterations) in the implementer run. Result: `15 passed, 5 warnings in
  202.60s`.
- **Backfill idempotency:** exercised by the duplicate_retry scenario and
  the legacy-save append-merge test — re-appending the same `message_id` /
  `client_request_id` returns the original event with `appendedCount=0`,
  `duplicateCount=1`, and never inserts a second row.
- **No truncation:** the legacy-save append-merge test proves a stale
  1-message `POST /conversations/{id}` body does NOT drop existing events;
  the folded conversation retains all prior events.

## 4. Rollback plan

1. Stop the API.
2. Drop `codirector_conversation_events` and the `revision` column (or leave
   the column; it is harmless and ignored by legacy code).
3. Restart the API on the pre-M028 code path. `messages_json` is intact, so
   the legacy full-replace path continues to work.

## 5. GO gate evidence (migration)

- [x] Migration file present and registered in
  `studio-api/app/migrations/__init__.py` (`M028`).
- [x] `messages_json` migrated into events and verified via Layer 1
  (fold + idempotency + no-truncation assertions).
- [x] Reversible in intent; `messages_json` preserved.
- [ ] Independent verify re-run — PENDING (separate agent).
