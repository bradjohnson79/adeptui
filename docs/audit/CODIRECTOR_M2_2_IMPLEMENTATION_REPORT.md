# Co-Director Milestone 2.2 — Implementation Report

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-2-tool-registry` (created from `a5b7106`, the M2.1 tip)
**Checkpoint:** tag `checkpoint/codirector-m2-2-start` on `a5b7106`
("docs: Co-Director M2.1 final summary report")
**Status:** Implemented, tested, documented.

---

## 1. Summary

Implemented the full M2.2 scope: a **bounded** tool registry with 15 read tools that run inline
inside a chat turn and 4 mutating tools that can only reach a write through the M2.1 approval
system, carried by a new `tool_call` proposal type with a server-owned payload. Also delivered: a
thin `CapabilityAdapter` over existing health probes, argument/result sanitization on both trust
boundaries, generalized staleness detection (`baseResourceVersions` instead of a single Bible
version id), a durable invocation ledger (`m003_codirector_tools`), six new REST endpoints, seven
additive SSE events, eight mock scenarios, frontend read-tool status plus generalized proposal
cards, and unit + Playwright coverage.

The invariant holds structurally, not by convention: read handlers have no write path, mutating
handlers are split into `preview()` / `apply()`, and `apply()` has exactly one caller —
`ToolExecutionService.execute_approved_proposal`, reachable only after a human approval row exists.
There is no execute-a-tool endpoint.

M1 and M2.1 architecture were not reopened. `ProposalService.approve()` gained **one** branch
(`proposal_type == "tool_call"`); every guard around it — terminal-state checks,
`APPROVAL_ALREADY_RECORDED`, staleness, the decision row, the `executing` transition, the receipt,
and the idempotency check — is shared with the Bible path. Reject / request-revision / cancel were
not touched.

## 2. Preconditions — status

| # | Precondition | Status |
|---|---|---|
| 1 | Main checkout on/near `phase2/codirector-m2-1-production-bible` (tip `a5b7106`); pack-authoring worktree left alone | Met |
| 2 | Branch `phase2/codirector-m2-2-tool-registry` from the M2.1 tip, unrelated WIP preserved | Met (see §7) |
| 3 | Checkpoint tag `checkpoint/codirector-m2-2-start` | Met, on `a5b7106` |
| 4 | `docs/audit/CODIRECTOR_M2_2_PREFLIGHT.md` | Met |
| — | Model may propose, never auto-mutate | Met, enforced structurally (§1 and `CODIRECTOR_TOOL_SECURITY.md` §1) |
| — | Reuse ONE approval system | Met, one branch in `approve()`, no second lifecycle |

## 3. The critical unblocker, resolved

The preflight identified the blocking gap: `ProposalService` only understood `BibleMutationSet`, and
`CoDirectorProposalCard` hardcoded Bible diffs. All four required pieces landed:

1. **`tool_call` proposal type with a server-owned payload** — `ToolCallPayload` carries `toolId`,
   `toolSchemaVersion`, `arguments` (the *sanitized* ones), `capabilitySnapshot`, `preview`,
   `inputHash`, and `baseResourceVersions`. The model contributes only a tool id and raw arguments.
2. **Branched `approve()`** — Bible path unchanged (`ops.apply_mutation_set`); tool path delegates to
   `ToolExecutionService.execute_approved_proposal`.
3. **`structured_output` `responseType`** — `message` | `read_tool_call` | `mutation_proposal`, with
   a new ```` ```tool ```` fence alongside the untouched ```` ```proposal ```` Bible fence. The
   response type is derived from the registry's declared `kind`, **not** from the model's claim, so a
   mutating tool labelled `read_tool_call` still becomes a proposal.
4. **Generalized proposal card** — one shell renders Bible diffs from `payload` or the
   server-computed `toolCall.preview` for tools.

## 4. Files created

**Backend — tools package**

- `studio-api/app/codirector/tools/__init__.py`
- `studio-api/app/codirector/tools/definitions.py` — `ToolDefinition`, `ToolParameter`,
  `ToolPreview`, `ToolCallPayload`, `ToolInvocationOut`, `ToolAvailability`, and the declared
  `READ_TOOLS` / `MUTATING_TOOLS`.
- `studio-api/app/codirector/tools/registry.py` — id-to-handler binding, with import-time validation
  that every declared tool has a handler and no handler exists for an undeclared tool.
- `studio-api/app/codirector/tools/capabilities.py` — `CapabilityAdapter` over existing probes.
- `studio-api/app/codirector/tools/sanitize.py` — argument validation, result scrubbing/truncation,
  input hashing.
- `studio-api/app/codirector/tools/execution.py` — `ToolExecutionService`: `execute_read`, `propose`,
  `execute_approved_proposal`, ledger writes, staleness tokens.
- `studio-api/app/codirector/tools/handlers/__init__.py`
- `studio-api/app/codirector/tools/handlers/project.py`
- `studio-api/app/codirector/tools/handlers/scenes.py`
- `studio-api/app/codirector/tools/handlers/bible_read.py`
- `studio-api/app/codirector/tools/handlers/system.py`

**Backend — services and migration**

- `studio-api/app/scene_service.py` — scene CRUD/summary/fingerprint helpers extracted from
  `routers/api.py` so handlers call services, not HTTP.
- `studio-api/app/project_service.py` — project profile/status/status-label/version-token helpers.
- `studio-api/app/migrations/m003_codirector_tools.py` — `codirector_tool_invocations`.

**Frontend**

- `studio-web/src/components/CoDirector/CoDirectorToolStatus.tsx`

**Tests**

- `studio-api/tests/test_codirector_tools.py` (75 tests)
- `tests/e2e/codirector/tools.spec.ts` (8 tests, `@critical @isolated`)

**Docs**

- `docs/audit/CODIRECTOR_M2_2_PREFLIGHT.md`
- `docs/architecture/CODIRECTOR_TOOL_REGISTRY.md`
- `docs/architecture/CODIRECTOR_TOOL_SECURITY.md`
- `docs/audit/CODIRECTOR_M2_2_IMPLEMENTATION_REPORT.md` (this file)
- `docs/audit/CODIRECTOR_M2_2_FINAL_SUMMARY.md`

## 5. Files changed

**Backend**

- `studio-api/app/codirector/bible/schemas.py` — `"tool_call"` added to `ProposalType`;
  `BIBLE_PROPOSAL_TYPES` / `TOOL_CALL_PROPOSAL_TYPE` constants; `ProposalOut.toolCall`;
  `ExecutionReceiptOut.toolId` / `toolInvocationId` / `toolResult` / `toolResultTruncated`.
- `studio-api/app/codirector/bible/proposals.py` — `is_tool_proposal` / `_raw_payload` helpers;
  `_is_tool_proposal_stale`; `_stale_for_row` / `_row_to_out` / `preview` now flavour-aware;
  `approve()` branched; `create_tool_proposal`; `_approve_tool_proposal`; `_attach_tool_details`.
- `studio-api/app/codirector/structured_output.py` — `ResponseType`, `_TOOL_FENCE_RE`,
  `ToolCallRequest`, `StructuredReply`, `has_tool_fence`, `strip_tool_blocks`, `extract_tool_block`,
  `parse_structured_reply` (a tool fence takes precedence over a proposal fence).
- `studio-api/app/codirector/service.py` — tool instructions in the system message; the read loop
  (`_interpret_reply`, `_run_read_tool`, `_propose_tool_call`, `_follow_up_request`,
  `TOOL_LOOP_LIMIT`) shared by `chat_for_project` and `stream_for_project`; new SSE emissions;
  removed the now-dead `_create_proposal_from_reply`.
- `studio-api/app/codirector/errors.py` — 10 `TOOL_*` and 3 `CAPABILITY_*` codes plus HTTP mappings.
- `studio-api/app/codirector/providers/mock.py` — `_tool_fence`, conversation-aware
  `_is_follow_up_turn`, `_TOOL_SCENARIOS`, and `_tool_scenario_reply` for the eight new scenarios.
- `studio-api/app/routers/codirector.py` — six tool endpoints; `/chat` now returns `toolInvocations`.
- `studio-api/app/routers/api.py` — now calls `scene_service` / `project_service` instead of inline
  scene-creation and status-label logic; `assistant_chat` unpacks the new return shape.
- `studio-api/app/db.py` — `CoDirectorToolInvocation` model.
- `studio-api/app/migrations/__init__.py` — registered `M003`.
- `studio-api/tests/test_migrations.py` — idempotency test now expects `M003`.

**Frontend**

- `studio-web/src/api.ts` — `toolCall` on `CoDirectorProposal`; four tool fields on
  `CoDirectorExecutionReceipt`; new `CoDirectorToolPreview` / `CoDirectorToolCall` /
  `CoDirectorToolDefinition` / `CoDirectorToolAvailability` / `CoDirectorToolInvocation`; seven new
  SSE event members; six new client functions.
- `studio-web/src/components/CoDirector/types.ts` — `CoDirectorToolActivity`.
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — `toolActivity` state, handling for
  all seven tool events (including clearing the partially-streamed request text on
  `tool_requested`), and flavour-aware approve confirmation and stale handling.
- `studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx` — renders Bible **or** tool
  proposals from one shell, including server-computed preview lines and warnings.
- `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` — renders `CoDirectorToolStatus`.
- `studio-web/src/styles.css` — tool-card accent, warning rows, and status-line styles.

**Docs**

- `docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md` — general tool calling marked implemented in
  M2.2, with what remains open restated (orchestrator, autonomous chains).
- `docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` — the "Tool calling + approvals" section now
  carries an as-built status note, including the two places M2.2 deliberately built *narrower* than
  the vision (closed registry, one-tool-per-turn cap) and why `queue_render` and reference
  attach/remove were excluded.

## 6. Service extraction (why `routers/api.py` changed)

Tool handlers must not call the app's own HTTP endpoints — that would duplicate validation, lose the
transaction, and let a tool's behavior drift from the UI's. Scene creation, scene field updates,
scene summarization, and project status-label computation were inline in `routers/api.py`, so they
were extracted to `scene_service.py` / `project_service.py` and the router now calls the same
functions the handlers do. This is a pure refactor: no behavior change, and the pre-existing
scene/project API tests cover it.

`scene_service.scene_fingerprint` is new, and exists for staleness: it hashes only the fields a tool
can target, deliberately **excluding** `output_path` so a render finishing doesn't invalidate a
pending title or prompt change.

## 7. Out of scope: other worktrees and pre-existing failures

The unrelated "Essential Pack Authoring" work now lives in its own worktree
(`AIVideoStudio-pack-authoring` on `phase1c/essential-pack-authoring`), alongside a
`production-systems-readiness` worktree. Both were left alone, and this branch's working tree
contains only M2.2 changes.

The full backend suite reports **8 failures**, in `test_pack_install.py`,
`test_pack_providers_github.py`, `test_phase0_baseline.py`, and `test_setup_refactor.py`. These are
pre-existing and unrelated — proven rather than assumed: a throwaway worktree was checked out at
`checkpoint/codirector-m2-2-start` and the full suite run there produced **the same 8 failures**
(186 passed at the checkpoint vs. 261 here; the 75-test delta is exactly `test_codirector_tools.py`).
Two of them are also order-dependent — running those four files in isolation swaps
`test_phase0_baseline::test_sqlite_initialization_is_isolated` for
`test_pack_install::test_refresh_source_does_not_create_folders`, identically on both revisions.

## 8. Test results

### Backend (pytest)

```
cd studio-api; .\.venv\Scripts\python.exe -m pytest tests\test_codirector_tools.py tests\test_production_bible.py tests\test_codirector_provider.py -q
```

**Result: 148 passed** in 8.8s (5 pre-existing Pydantic v2 deprecation warnings). Adding
`tests\test_migrations.py` gives **151 passed** in 9.1s. Full suite: **261 passed, 8 failed**, all 8
pre-existing per §7.

`test_codirector_tools.py` (75 tests) covers: registry closure and binding integrity; every read tool
over HTTP; kind-mismatch and unknown-tool guards; the schema-version guard; argument sanitization
(required, unknown-key drop, length, range, choices, non-object); input-hash determinism; result
scrubbing (secrets, absolute paths) and budget truncation; capability fail-closed behavior (probe
exception and unknown key); blocked reads still writing a `blocked` ledger row;
propose-changes-nothing; approve-applies-once for all four mutating tools; reject /
request-revision / cancel; approve-twice; all three staleness flavours (Bible, project, scene) plus
an unreadable payload; execution failure producing a `failed` receipt and ledger row while changing
nothing; `responseType` classification including a mutating tool mislabelled as a read; the chat read
loop and `TOOL_LOOP_LIMIT_REACHED`; the SSE lifecycle; and `M003` vs `create_all` schema parity plus
migration idempotency.

### Playwright — Co-Director suite

```
npx playwright test tests/e2e/codirector --retries=0
```

**Result: 23 passed (3.2m)** — `tools.spec.ts` (8) plus the unchanged M1 `chat-reliability.spec.ts`
(4) and `streaming-cancel.spec.ts` (4), M2.1 `production-bible.spec.ts` (6), and
`provider-states.spec.ts` (1), confirming M1 and M2.1 behavior is intact.

### Playwright — full `@critical` suite

```
npx playwright test --grep "@critical" --retries=0
```

**Result: 34 passed (5.5m)** — the full cross-suite `@critical` run (Co-Director, setup wizard, smoke
startup, and the rest): 31 in M2.1 plus the 3 new `@critical` tool tests, with no regressions outside
the Co-Director suite.

## 9. Notable fixes made along the way

1. **`CapabilityAdapter` private-cache access** — `ToolExecutionService` was reaching into
   `adapter._cache`; added a public `cached_states()` instead.
2. **`chat_for_project` return shape** — now includes `list[ToolInvocationOut]`, propagated to
   `routers/api.py::assistant_chat`.
3. **`responseType` authority** — `extract_tool_block` originally trusted the model's `responseType`.
   A reply could therefore label `create_scene` as a `read_tool_call` and have it executed without
   approval. Fixed by deriving the response type from the registry's declared `kind`; a test asserts
   the mislabelled case becomes a proposal.
4. **Duplicate `error` SSE event** — the streaming path emitted a generic `error` after
   `capability_blocked` / `tool_failed`, which the frontend reads as a dead turn even though the turn
   still completes with an answer. Removed; the specific events already carry the detail.
5. **Mock `mutation_tool_execution_failure` scenario** — originally proposed an operation that was
   invalid at *proposal* time, so it never reached execution. Changed to propose a valid
   `create_scene` and inject the fault at execution time via an E2E-only hook, so the test actually
   exercises the failure-after-approval path.
6. **Pre-existing TypeScript error in `CoDirectorSession.tsx`** — a misplaced `as const` on a ternary
   (`TS1355`) that predates this milestone; fixed by asserting each branch.
7. **Over-broad E2E catalog assertion** — the "no escape hatch" check used
   `/shell|exec|sql|file|path|command/i`, which matched `get_project_profile`. Replaced with an exact
   closed-set assertion over all 19 tool ids, which is both stricter and self-documenting: a newly
   added tool must be listed there deliberately.

## 10. Environment note on the first E2E run

The first full Co-Director E2E run reported 13 failures in 25 minutes, including M1
`streaming-cancel` tests, all with `ECONNREFUSED 127.0.0.1:8742`. This was **not** a code regression:
`artifacts/functional-audit/logs/api.log` showed several `e2e-start.mjs` supervisors from earlier
runs competing for port 8742 (`reuseExistingServer` is on locally), so the API was flapping
mid-suite. After tearing the stale stacks down, the same suite passed in 3.2 minutes with one genuine
test-only failure (§9.7). Worth remembering: an `ECONNREFUSED` cluster spanning unrelated specs is a
stack-health symptom, not a feature failure.

## 11. Remaining gaps vs. plan

None against the stated scope. Everything listed — the tools package, the four unblocker items, all
15 read tools and 4 mutating tools, the capability adapter over exactly the five named probe sources,
the migration and ledger, the six endpoints, the seven SSE events, the `TOOL_*` and `CAPABILITY_*`
taxonomy, all eight mock scenarios, the frontend status line and generalized cards, both test suites,
and all four new docs plus the two doc updates — is implemented and passing.

Deliberately not built, and documented as such in `CODIRECTOR_TOOL_SECURITY.md` §6: shell,
filesystem, SQL, and arbitrary handlers; auto-approval; task graphs; `queue_render`; reference
attach/remove; and a full Production Systems Readiness matrix.

One inherited simplification carries forward from M2.1: the proposal-lifecycle SSE events
(`proposal_updated`, `approval_recorded`, `execution_*`) remain reserved-but-unemitted, since
approve/reject are synchronous REST calls for a single reviewing user. The new tool events are
emitted.
