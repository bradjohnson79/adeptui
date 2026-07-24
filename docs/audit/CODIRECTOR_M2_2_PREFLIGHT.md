# Co-Director M2.2 — Preflight Notes (Bounded Tool Registry & Approved Project Actions)

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-2-tool-registry` (from M2.1 tip `a5b7106`)
**Checkpoint:** tag `checkpoint/codirector-m2-2-start`
**Scope:** a bounded, declarative tool registry — read tools that execute immediately, and
mutating tools that can only ever *propose*. No shell, no filesystem, no SQL, no arbitrary
handlers, no auto-approval, no task graph.

---

## 1. The critical unblocker (why this is step one)

Today the approval system is hard-wired to Production Bible mutations end to end:

| Layer | Current state | Blocks M2.2 because |
|---|---|---|
| `codirector_proposals.payload_json` | Always a `BibleMutationSet` | A tool call has a different payload shape |
| `ProposalOut.payload` | Typed `BibleMutationSet` | FE can't receive a tool payload |
| `ProposalService.approve()` | Unconditionally calls `ops.apply_mutation_set` | Approving a tool proposal would write the Bible instead of running the tool |
| `_is_stale()` | Compares `based_on_version_id` to the Bible's `current_version_id` | Scene/project mutations aren't versioned by the Bible |
| `structured_output.py` | Only recognizes a ```` ```proposal ```` fence | No way for the model to request a tool |
| `CoDirectorProposalCard.tsx` | `describeMutations()` reads `payload.entityMutations` | Renders nothing useful for a tool call |

**Resolution chosen (one approval system, additive):**

- `proposal_type = "tool_call"` is a new value in the existing `codirector_proposals` table.
  `payload_json` holds a server-owned `ToolCallPayload` instead of a `BibleMutationSet`.
- `ProposalOut` keeps `payload: BibleMutationSet` (empty for tool proposals) and gains
  `toolCall: ToolCallPayload | None`. Existing Bible consumers are byte-for-byte unaffected;
  the FE discriminates on `toolCall` being present.
- `ProposalService.approve()` branches exactly once: Bible path unchanged, tool path delegates
  to `ToolExecutionService.execute_approved_proposal`. Decision recording, receipt writing,
  idempotency-by-`input_hash`, and terminal-state guards stay in `ProposalService` — there is
  no second approval pipeline.
- Staleness generalizes from a single Bible version id to a server-owned
  `baseResourceVersions` map (`{"bible": <versionId>, "scene:<id>": <fingerprint>,
  "project:<id>": <updatedAt>}`) recomputed at approve time. Mismatch still raises the
  existing `PROPOSAL_STALE` (409) so the FE's stale handling is reused verbatim.

## 2. Current state of the pieces M2.2 builds on

- **Proposal lifecycle** (`codirector/bible/proposals.py`): `create_proposal` →
  `pending` → `reject` / `request_revision` / `cancel` / `approve`. `approve` is idempotent
  per `(proposal, base version, payload)` via `operations.compute_input_hash`, records a
  `codirector_approvals` row, and writes a `codirector_execution_receipts` row. All of this is
  reusable for tools as-is.
- **Errors** (`codirector/errors.py`): `CoDirectorError(code, message, details, recoverable,
  recommended_action)` + `_STATUS_BY_CODE`. M2.2 adds `TOOL_*` / `CAPABILITY_*` constants and
  their status mappings — additive only.
- **Structured output** (`codirector/structured_output.py`): regex fence → JSON → pydantic,
  with a malformed fence surfaced as a non-fatal `STRUCTURED_OUTPUT_INVALID`. M2.2 keeps
  `extract_proposal_block()` untouched and adds a ```` ```tool ```` fence carrying
  `responseType: read_tool_call | mutation_proposal`.
- **SSE** (`codirector/service.py` → `routers/codirector.py`): open union discriminated on
  `type`; FE already ignores unknown types. M2.2 adds seven event types, renames nothing.
- **Migrations** (`app/migrations/`): `DEFAULT_REGISTRY = MigrationRegistry((M001, M002))`;
  DDL is hand-written to mirror the SQLAlchemy models so `create_all` (live path) and
  `MigrationRunner.apply_pending()` (test path) agree. M2.2 follows the same dual-declaration
  pattern for one new table.

## 3. Capability adapter — thin, over existing probes only

Production Systems Readiness as a full matrix is explicitly out of scope. The adapter wraps
probes that already exist, and nothing else:

| Capability key | Existing probe | Module |
|---|---|---|
| `project` | `db.get(Project, id)` | `app/db.py` |
| `bible` | `bible.operations.get_bible` + current version | `codirector/bible/operations.py` |
| `provider` | `codirector.service.get_health()` | `codirector/service.py` |
| `comfyui` | `ComfyClient.health()` (`/system_stats`) | `app/comfy_client.py` |
| `references` | `reference_capabilities(...)` | `app/references/capabilities.py` |
| `source_manager` | `source_manager.service.get_overview()` | `app/source_manager/service.py` |
| `preview_engine` | `preview_bus.capabilities_for(engine)` | `app/preview_bus.py` |

Every probe is wrapped so it can only ever return "unavailable" — a probe raising must never
fail a chat turn. Probes are snapshotted once per turn/request and reused.

## 4. Tool surface

**Read tools (15, execute immediately, never mutate):** `get_project_profile`,
`get_project_status`, `list_scenes`, `get_scene`, `get_active_scene`,
`get_current_bible_version`, `get_bible_entity`, `list_bible_entities`,
`get_relevant_bible_context`, `get_provider_health`, `get_selected_model`,
`get_comfyui_health`, `get_source_manager_status`, `get_reference_capabilities`,
`get_engine_capabilities`.

**Mutating tools (4, proposal + explicit approval only):** `create_scene`,
`update_scene_title`, `set_scene_prompt`, `record_director_decision`.

`record_director_decision` persists into the Production Bible as a fact with
`factType="director_decision"` rather than introducing a parallel decision store — the Bible
already is the project's durable, versioned knowledge record.

**Read loop bound:** at most **one** read tool per provider turn, plus at most **one**
follow-up completion. A second tool request in the follow-up turn raises
`TOOL_LOOP_LIMIT_REACHED` as a non-fatal error event; the turn still completes.

## 5. Service extraction

Scene/project logic is inline in `routers/api.py` today. Tool handlers must call services, not
HTTP, so the minimum shared surface is extracted to `app/scene_service.py` and
`app/project_service.py`, and `routers/api.py` is refactored to call the same functions. No
endpoint contract changes; the router keeps owning HTTP concerns (404s, response models).

## 6. Risk assessment

- **Additive schema.** One new table (`codirector_tool_invocations`). No existing column
  changes. `codirector_proposals.proposal_type` already accepts arbitrary `VARCHAR(48)`.
- **Approve branch.** The one genuinely risky edit. Mitigated by: the Bible branch keeping its
  exact current code path, `test_production_bible.py` being preserved unchanged, and a unit
  test asserting a Bible proposal still produces a new Bible version after the branch exists.
- **Result leakage.** Tool results flow back into the model's prompt and into the UI. All
  results pass through `sanitize.sanitize_result` — secret redaction (reusing
  `errors.redact_secrets`), absolute-path scrubbing, list/string caps, and a hard character
  budget with explicit `tool_result_truncated` signalling.
- **Streaming artifact.** A first turn that turns out to be a tool call has already streamed
  prose tokens. Handled by emitting `tool_requested`, on which the FE resets the in-flight
  bubble — no change to `completed`/`cancelled`/`error` handling.
- **Rollback:** drop `codirector_tool_invocations`; delete rows where
  `codirector_proposals.proposal_type = 'tool_call'`. `reversible=False`, documented in the
  migration's `rollback_notes` like `M001`/`M002`.

## 7. Non-negotiables carried forward

- The model may propose; it never auto-mutates. Read tools are the only immediate execution,
  and read handlers have no write path.
- One approval system. `ProposalService` remains the single decision/receipt authority.
- No change to existing SSE event names or fields; no change to `PROVIDER_IDS` or the
  mock-outside-E2E block; `codirector_conversations` untouched.
- M1 chat-reliability / streaming-cancel and M2.1 production-bible specs stay green.
- Tool calls never route through the FE-local `runSteps` / `executeStep` heuristic path.
