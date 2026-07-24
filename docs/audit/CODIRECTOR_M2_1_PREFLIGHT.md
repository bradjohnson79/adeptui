# Co-Director M2.1 — Preflight Notes (Production Bible & Durable Proposals)

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-1-production-bible`
**Checkpoint:** tag `checkpoint/codirector-m2-1-start` (also `checkpoint/codirector-m1-start` from M1)
**Scope:** see user request. This document captures the current-state investigation used to
plan the change without rewriting M1 architecture.

---

## 1. Current request path (M1, unchanged by M2.1)

```
Browser (CoDirectorSession.tsx)
  → api.codirectorChatStream() / api.codirectorChat()
    → POST /api/codirector/chat[/stream]  (routers/codirector.py)
      → codirector_service.chat_for_project / stream_for_project
        → codirector_service._prepare_chat_request(db, ...)
            - loads Project/Scene, builds context via assistant_module.build_context_block
            - appends learning_context_block
            - builds system + chat messages → ChatRequest
        → provider.generate() / provider.stream()   (ollama | mock)
      → SSE events: request_started, provider_connected, token*, completed | cancelled | error
  ← FE renders transcript; scene_setup / suggested_prompt surfaced as CTA cards (not proposals)
```

Provider selection: `active_provider_id()` — `ADEPT_CODIRECTOR_PROVIDER` wins; `mock` only
selectable when `STUDIO_E2E=1`. Cancellation: in-memory `_active_tasks` / `_cancelled`
keyed by `request_id` (not persisted — fine, M2.1 does not change this).

## 2. Current persistence

- `codirector_conversations` (`studio-api/app/db.py`): **one row per project**, entire
  transcript as a JSON blob in `messages_json`. No turns/sessions table, no request ledger.
- Tables are created via `Base.metadata.create_all(bind=engine)` inside `init_db()`
  (`app/db.py`), called from FastAPI's lifespan — **not** via the migration runner.
- The migration framework (`studio-api/app/migrations/`) exists but is **opt-in**: nothing
  in `main.py`/`init_db()` calls `MigrationRunner`. Only `M001` (metadata-only baseline) is
  registered. `studio-api/tests/test_migrations.py` exercises the runner directly against a
  throwaway SQLite file, not the app's `studio.db`.

**M2.1 implication:** to keep both "the app works" (via `create_all`) and "the migration
story is honest" (via an explicit, testable `m002`), Production Bible/proposal tables are
declared as SQLAlchemy models in `app/db.py` (picked up by `create_all`, so `init_db()` and
the pytest `client` fixture — which boots the full app — both provision them automatically)
**and** mirrored as raw-SQL DDL in a new `m002_production_bible.py` migration registered in
`app/migrations/__init__.py`, so `MigrationRunner.apply_pending()` against a *fresh* SQLite
file also produces the same schema. This matches the instruction "ensure `create_all` /
migration apply both work for tests" without wiring the runner into the live startup path
(that cutover is out of scope for M2.1 and would risk M1 regressions).

## 3. Context construction (today)

`codirector/service.py::_prepare_chat_request` builds `context` from:
1. `_build_project_payload()` (name, engine defaults, assets, scenes) → `assistant_module.build_context_block()`.
2. Optional scene director timeline (`_scene_director_dict`).
3. `learning_context_block(parse_learning(...))` appended.

There is **no bounded token budget** today — the whole project/scene payload is serialized
into the prompt. M2.1 adds `ProjectContextService.build()` as an **additional**, separately
bounded excerpt (Bible entities/facts only, with its own token budget and a
`context_manifest` describing what was included), appended after the existing context block.
It does not touch or reduce the existing project/scene/learning context, so M1 behavior for
projects without a Bible is byte-for-byte unchanged (`ProjectContextService.build()` returns
an empty excerpt + empty manifest when no Bible exists).

## 4. FE ActionPlan / structured-output surfaces (today)

- `codirector/types.ts` (`ActionPlan`, `PlannedStep`) is a **local, FE-only** heuristic
  (`planFromIntention()`) triggered by a regex over the user's message in
  `CoDirectorSession.send()`. It never round-trips through the backend and is unrelated to
  the model's actual reply.
- `assistant_module.extract_scene_setup()` / `extract_suggested_prompt()` parse fenced
  ```` ```scene_setup ```` / ```` ```prompt ```` blocks out of the model's raw text reply.
  This is the only existing "structured output from the model" pattern in the codebase.
- **M2.1 reuses this exact shape** for proposals: a new `extract_proposal_block()` parses a
  ```` ```proposal ```` fenced JSON block (schema: `{proposal_type, title, summary,
  entity_mutations, fact_mutations}`) out of the mock/ollama reply, the same way
  `scene_setup` is parsed today. A malformed block is caught and surfaced as a non-fatal
  `STRUCTURED_OUTPUT_INVALID` error event (chat still completes with the visible text) —
  it never crashes the stream.

## 5. Migration risk assessment

- **Additive only.** No existing table's schema changes; no existing column is renamed or
  dropped. `codirector_conversations` is untouched.
- **New tables:** `production_bibles`, `production_bible_versions`,
  `production_bible_entities`, `production_bible_facts`, `codirector_proposals`,
  `codirector_approvals`, `codirector_execution_receipts`. All FK to `projects.id` (directly
  or transitively) using the same `String(36)` id convention already used by
  `Scene`/`Asset`/`Job`.
- **Risk:** `MigrationRunner` and `create_all` must produce schema that agrees, or a
  fresh-migration test DB and the app's `create_all`-provisioned DB could silently diverge.
  Mitigated by keeping the `m002` DDL a direct, hand-checked mirror of the SQLAlchemy model
  columns, and covering both paths in `test_production_bible.py`.
- **Rollback:** all new tables are additive-only and unreferenced by any M1 code path, so
  the migration's `rollback_notes` documents a manual `DROP TABLE` sequence (children before
  parents) as informational only — `reversible=False`, consistent with `M001`'s pattern.

## 6. Expected files (plan)

**Backend**
- `studio-api/app/db.py` — add 7 new SQLAlchemy models (additive).
- `studio-api/app/migrations/m002_production_bible.py` (new) + `__init__.py` update.
- `studio-api/app/codirector/bible/__init__.py`, `schemas.py`, `service.py`, `operations.py`,
  `context.py`, `proposals.py` (new package).
- `studio-api/app/codirector/errors.py` — additive error codes.
- `studio-api/app/codirector/service.py` — wire `ProjectContextService` into
  `_prepare_chat_request`; parse/persist proposals from provider output in
  `chat_for_project`/`stream_for_project`.
- `studio-api/app/codirector/providers/mock.py` — `proposal_character_update`,
  `malformed_proposal` scenarios.
- `studio-api/app/routers/codirector.py` — new Bible + proposal endpoints under
  `/api/codirector/projects/{projectId}/...`.
- `studio-api/tests/test_production_bible.py` (new).

**Frontend**
- `studio-web/src/api.ts` — Bible/proposal client methods; extend `CoDirectorStreamEvent`.
- `studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx` (new).
- `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` — render proposal cards.
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — proposal state + SSE handling.
- `studio-web/src/components/ProductionBibleWorkspace.tsx` (new) + registration in
  `studio-web/src/core/workspaces.ts` and `studio-web/src/pages/ProjectEditor.tsx`.
- `tests/e2e/codirector/production-bible.spec.ts` (new).

**Docs**
- `docs/CODIRECTOR_PRODUCTION_BIBLE.md`, `docs/CODIRECTOR_PROPOSALS_AND_APPROVALS.md` (new).
- `docs/audit/CODIRECTOR_M2_1_IMPLEMENTATION_REPORT.md` (new, written after verification).
- Update `docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` (mark Bible section implemented)
  and whatever `IMPLEMENTATION_PLAN`-equivalent doc tracks milestones
  (`docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md`, referenced by the Brain doc).

## 7. Non-negotiables carried forward from M1

- No change to `PROVIDER_IDS`, `active_provider_id()` gating, or the mock-outside-E2E block.
- No change to existing SSE event *names* or fields — only additive new event types.
- Cancellation/retry/dedup semantics in `CoDirectorSession.tsx` are untouched.
- `codirector_conversations` persistence untouched.
- Model never mutates the Bible directly — every Bible write goes through a persisted
  proposal + explicit approval + execution receipt.
