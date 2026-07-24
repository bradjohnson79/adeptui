# Co-Director Milestone 2.1 — Implementation Report

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-1-production-bible` (created from `82ee3fa`)
**Checkpoint:** tag `checkpoint/codirector-m2-1-start` → commit `82ee3faa71d10901de2594d63af6949a76503d9f`
("checkpoint: WIP snapshot before Essential Pack Authoring and Publishing work"). This checkpoint
predates M2.1 and also predates unrelated in-flight WIP for a separate "Essential Pack Authoring"
task; that WIP was preserved untouched in the working tree per the preflight instructions and is
**not** part of this feature (see §5).
**Status:** Implemented, tested, documented.

---

## 1. Summary

Implemented the full M2.1 scope: a versioned Production Bible, bounded context injection into
Co-Director chat via `ProjectContextService`, durable model-authored proposals with an
approve/reject/request-revision/cancel/stale lifecycle, execution receipts, additive SSE events,
two new mock provider scenarios, a Production Bible frontend workspace, proposal cards in the
conversation UI, and unit + Playwright test coverage. M1's streaming/cancel/retry/persistence
architecture was not touched — the Bible/proposal machinery plugs into the existing single
`_prepare_chat_request` call site and the existing SSE/error taxonomy.

## 2. Preconditions — status

| # | Precondition | Status |
|---|---|---|
| 1 | Branch `phase2/codirector-m2-1-production-bible` from current HEAD, dirty WIP preserved | ✅ |
| 2 | Safety checkpoint (commit or tag) | ✅ tag `checkpoint/codirector-m2-1-start` on `82ee3fa` |
| 3 | `docs/audit/CODIRECTOR_M2_1_PREFLIGHT.md` | ✅ |
| 4 | M1 architecture (streaming/cancel/retry/persistence/mock-only-e2e) unchanged | ✅ — verified by full pass of `chat-reliability.spec.ts` and `streaming-cancel.spec.ts`, both `@critical` |

## 3. Files created

**Backend**

- `studio-api/app/migrations/m002_production_bible.py`
- `studio-api/app/codirector/bible/__init__.py`
- `studio-api/app/codirector/bible/schemas.py`
- `studio-api/app/codirector/bible/operations.py`
- `studio-api/app/codirector/bible/service.py`
- `studio-api/app/codirector/bible/context.py` (`ProjectContextService`)
- `studio-api/app/codirector/bible/proposals.py` (`ProposalService`)
- `studio-api/app/codirector/structured_output.py`
- `studio-api/tests/test_production_bible.py` (73 tests total in the two-file run, see §6)

**Frontend**

- `studio-web/src/components/ProductionBibleWorkspace.tsx`
- `studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx`

**Tests**

- `tests/e2e/codirector/production-bible.spec.ts`

**Docs**

- `docs/audit/CODIRECTOR_M2_1_PREFLIGHT.md`
- `docs/architecture/CODIRECTOR_PRODUCTION_BIBLE.md`
- `docs/architecture/CODIRECTOR_PROPOSALS_AND_APPROVALS.md`
- `docs/audit/CODIRECTOR_M2_1_IMPLEMENTATION_REPORT.md` (this file)

## 4. Files changed

**Backend**

- `studio-api/app/db.py` — 7 new SQLAlchemy models (`ProductionBible`, `ProductionBibleVersion`,
  `ProductionBibleEntity`, `ProductionBibleFact`, `CoDirectorProposal`, `CoDirectorApproval`,
  `CoDirectorExecutionReceipt`).
- `studio-api/app/migrations/__init__.py` — registered `M002` in `DEFAULT_REGISTRY`.
- `studio-api/app/codirector/errors.py` — new `BIBLE_*`, `PROPOSAL_*`, `APPROVAL_*`,
  `EXECUTION_*`, `PROJECT_SCOPE_VIOLATION`, `STRUCTURED_OUTPUT_INVALID`, `RECEIPT_NOT_FOUND`
  codes + HTTP status mapping.
- `studio-api/app/codirector/service.py` — `_prepare_chat_request` now calls
  `ProjectContextService.build()`; added `_create_proposal_from_reply`; `chat_for_project` /
  `stream_for_project` now return/emit proposal + context manifest data; new SSE events
  (`context_manifest`, `proposal_created`).
- `studio-api/app/codirector/providers/mock.py` — added `proposal_character_update` and
  `malformed_proposal` scenarios.
- `studio-api/app/routers/codirector.py` — new Bible endpoints (`/projects/{id}/bible...`) and
  proposal endpoints (`/projects/{id}/proposals...`); updated `/chat` for the new return shape.
- `studio-api/app/routers/api.py` — updated `assistant_chat` to unpack the new 5-tuple.
- `studio-api/tests/test_migrations.py` — updated/renamed idempotency test for `M001` + `M002`.

**Frontend**

- `studio-web/src/api.ts` — new interfaces (`CoDirectorContextManifest`, `CoDirectorBibleEntity`,
  `CoDirectorBibleFact`, `CoDirectorBibleMutationSet`, `CoDirectorProposal`,
  `CoDirectorExecutionReceipt`, `CoDirectorBibleVersion`, `CoDirectorBible`, etc.), extended
  `CoDirectorStreamEvent` union, new Bible/proposal API client methods.
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — proposal state + actions
  (approve/reject/request-revision/cancel), `proposal_created` SSE handling, and the
  post-completion-error fix (see `CODIRECTOR_PROPOSALS_AND_APPROVALS.md` §3.1).
- `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` — renders
  `CoDirectorProposalCard` for active proposals.
- `studio-web/src/core/workspaces.ts` — registered the `bible` workspace.
- `studio-web/src/pages/ProjectEditor.tsx` — "Production Bible" menu entry + tab wiring.
- `studio-web/src/styles.css` — proposal card styles.

**Tests**

- `tests/e2e/codirector/chat-reliability.spec.ts` — added `waitForAppReady()` to `beforeEach`
  (reliability fix, unrelated to feature logic; see §7).
- `tests/e2e/codirector/streaming-cancel.spec.ts` — same fix.

**Docs**

- `docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md` — marked Production Bible / scoped
  approvals as implemented in M2.1, linked to the new docs.
- `docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` — added status notes on the two sections
  M2.1 partially implements (Production Bible; tool calling + approvals).

## 5. Out of scope: pre-existing "Essential Pack Authoring" WIP

At the start of this task the working tree already contained substantial uncommitted work for an
unrelated "Essential Pack Authoring and Publishing" feature (`studio-api/app/setup/pack_builder.py`,
`pack_publisher.py`, `pack_activate.py`, `pack_schema.py`, `pack_validator.py`,
`studio-web/src/components/SetupWizard.tsx`, `studio-web/src/setup/types.ts`,
`studio-api/tests/test_pack_authoring.py`, `packs/`, `docs/packs/`, `scripts/pack-*.mjs`,
`package.json` script entries, and modifications to `studio-api/app/setup/status.py` and the
`pack_essential_*.json` manifests). Per precondition #1 ("preserve dirty WIP — do not discard"),
this was **not** committed, modified, or reverted as part of this task — it remains as
uncommitted working-tree changes, untouched, ready for whoever picks that feature back up.

## 6. Test results

### Backend (pytest)

```
cd studio-api; .\.venv\Scripts\python.exe -m pytest tests\test_production_bible.py tests\test_codirector_provider.py -q
```

**Result: 73 passed, 5 warnings (Pydantic v2 deprecation, pre-existing/unrelated), 3.17s.**

Coverage in `test_production_bible.py` includes: Bible not-found before creation, import preview
(pure read), import confirm → version 1, manual entity/fact mutations → version bump
(copy-on-write), version history + version detail fetch, proposal create/list/filter, proposal
preview diff, approve → new Bible version + execution receipt, approve-twice →
`APPROVAL_ALREADY_RECORDED` (409), reject, request-revision (still approvable afterward), cancel,
stale detection on approve attempt (409 + status flips to `stale`, only cancellable after),
404/403 project scoping, approve-before-any-Bible-exists, `ProjectContextService` token-budget
truncation (manifest `truncated`/`includedEntityKeys`/`estimatedTokens`), well-formed proposal
fence parsing + persistence via `/chat`, malformed proposal fence → `STRUCTURED_OUTPUT_INVALID`
(502) without persisting a broken proposal, and migration/`create_all` schema parity for all 7
new tables.

### Playwright — Co-Director suite

```
npx playwright test tests/e2e/codirector --retries=0
```

**Result: 15 passed (2.4m).** Covers all of `production-bible.spec.ts` (import → confirm,
approve creates a version, manual entity add, reject, malformed-fence error handling, stale
proposal), plus the pre-existing `chat-reliability.spec.ts` and `streaming-cancel.spec.ts` M1
suites — confirming M1 behavior is unchanged.

### Playwright — full `@critical` suite

```
npx playwright test --grep "@critical" --retries=0
```

**Result: 31 passed (5.2m).** Full cross-suite `@critical` run (Co-Director, setup wizard, smoke
startup, etc.) — no regressions introduced by M2.1 outside the Co-Director suite.

### Pre-existing unrelated failures

9 backend tests fail in `test_pack_providers_github.py` / setup-wizard-adjacent modules — these
are pre-existing failures tied to the in-flight, uncommitted "Essential Pack Authoring" work
described in §5, not regressions from this task. They were failing before M2.1 changes and are
outside this milestone's scope.

## 7. Notable fixes made along the way

1. **`assistant_chat` tuple unpacking** (`routers/api.py`) — updated for the new 5-tuple return
   from `chat_for_project`.
2. **`test_default_registry_migrations_are_idempotent`** — updated to expect `M001` + `M002`.
3. **`RECEIPT_NOT_FOUND` → 404** — was missing from `_STATUS_BY_CODE`, defaulted to 500.
4. **Playwright flakiness**: added `waitForAppReady(request)` to `beforeEach` in all three
   Co-Director spec files to eliminate `ECONNREFUSED` races against the API server on cold start
   — this affects test setup only, not app or feature code.
5. **Real bug in `CoDirectorSession.tsx`**: a non-fatal `STRUCTURED_OUTPUT_INVALID` error
   arriving after a `completed` SSE event was overwriting the completed outcome, which combined
   with un-cleaned streamed text meant a malformed proposal fence's raw JSON could leak into the
   visible transcript. Fixed by tracking `postCompletionError` separately from a fatal
   `classifiedError` — see `CODIRECTOR_PROPOSALS_AND_APPROVALS.md` §3.1.

## 8. Remaining gaps vs. plan

None identified against the stated Scope IN. Everything listed — versioned Bible, bounded
context injection with token budget + manifest, durable proposals/approvals/receipts, APIs,
additive SSE events, structured provider output with two mock scenarios, FE Bible workspace with
import preview/confirm, proposal cards with approve/reject/revision/stale handling, unit tests,
Playwright tests, and all four requested docs — is implemented and passing.

Two events in the FE's `CoDirectorStreamEvent` union (`proposal_updated`, `approval_required`,
`approval_recorded`, `execution_started/completed/failed`, `bible_version_created`) are defined
but not currently emitted by the backend — approve/reject/etc. are synchronous REST calls, not
pushed over SSE, since there is one reviewing user per session today. This is called out
explicitly as a deliberate simplification in `CODIRECTOR_PROPOSALS_AND_APPROVALS.md` §6, not an
oversight; wiring them up is straightforward future work if multi-client live sync is needed.
