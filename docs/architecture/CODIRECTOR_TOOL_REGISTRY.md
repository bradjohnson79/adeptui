# Co-Director Milestone 2.2 — Bounded Tool Registry and Approved Project Actions

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-2-tool-registry`
**Related:** `docs/architecture/CODIRECTOR_PROPOSALS_AND_APPROVALS.md` (the approval system this
reuses), `docs/architecture/CODIRECTOR_PRODUCTION_BIBLE.md` (the Bible read/write path several
tools sit on), `docs/architecture/CODIRECTOR_TOOL_SECURITY.md` (the trust boundaries in detail),
`docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` (§"Tool calling + approvals" — M2.1 delivered
the approvals half; this delivers the bounded tool half)
**Status:** Implemented.

---

## 1. What "bounded" means

The registry is a **closed set**. A tool exists only if it is declared as data in
`definitions.py` *and* bound to a handler function in `registry.py`. There is no dynamic lookup,
no name-to-import resolution, no runtime registration, and no generic "run this" handler. The
module refuses to import if a declared tool has no binding, or if a handler is bound for a tool
nobody declared:

```64:76:studio-api/app/codirector/tools/registry.py
def _validate_bindings() -> None:
    """Fail at import time rather than mid-turn if the registry is internally inconsistent."""

    for definition in TOOL_DEFINITIONS:
        bound = _READ_HANDLERS if definition.kind == "read" else _MUTATION_HANDLERS
        if definition.tool_id not in bound:
            raise RuntimeError(f"Tool '{definition.tool_id}' is declared but has no {definition.kind} handler.")
    unknown = (set(_READ_HANDLERS) | set(_MUTATION_HANDLERS)) - set(_BY_ID)
    if unknown:
        raise RuntimeError(f"Handlers bound for undeclared tools: {sorted(unknown)}")


_validate_bindings()
```

Consequently there is no shell, filesystem, SQL, HTTP-fetch, or arbitrary-code tool, and no way
to add one without editing both files. Adding a tool is a code change under review, never a
configuration or prompt change.

---

## 2. Two kinds of tool, and why the asymmetry is the design

| | **Read tools** | **Mutating tools** |
|---|---|---|
| Count | 15 | 4 |
| Runs when | immediately, inside the chat turn | only after an explicit human approval |
| Handler shape | `async (ctx, args) -> dict` | `preview(ctx, args) -> ToolPreview` + `apply(ctx, args) -> dict` |
| Approval artifact | none | a `tool_call` proposal |
| Write path | none exists | `apply()`, reachable only from `ProposalService.approve` |

A read tool runs on its own because its handler has no write path at all — the worst case is a
wasted query. A mutating tool cannot run on its own because the only caller of `apply()` is
`ToolExecutionService.execute_approved_proposal`, which is in turn only called by
`ProposalService.approve()` after a human decision row has been written.

### 2.1 Read tools

| Tool | Capability | Answers |
|---|---|---|
| `get_project_profile` | `project` | name, director, resolution, fps, default engine |
| `get_project_status` | `project` | scene/asset counts, render progress, active jobs, status label |
| `list_scenes` | `project` | ordered scenes with engine, duration, whether rendered |
| `get_scene` | `project` | one scene in full |
| `get_active_scene` | `project` | the scene the user has selected right now |
| `get_current_bible_version` | `bible` | version number, summary, entity/fact counts |
| `get_bible_entity` | `bible` | one entity by key, plus facts about it |
| `list_bible_entities` | `bible` | entities in the current version, optionally by type |
| `get_relevant_bible_context` | `bible` | the same bounded excerpt chat context injects, with its manifest |
| `get_provider_health` | `provider` | is the local model provider reachable and ready |
| `get_selected_model` | `provider` | which model is configured, and is it installed |
| `get_comfyui_health` | `comfyui` | is the render backend reachable, VRAM headroom |
| `get_source_manager_status` | `source_manager` | registered/verified sources, component assignments |
| `get_reference_capabilities` | `references` | are Director visual references usable, and what blocks them |
| `get_engine_capabilities` | `preview_engine` | preview/streaming capabilities for an engine |

### 2.2 Mutating tools

| Tool | Capability | Pins | Effect on approval |
|---|---|---|---|
| `create_scene` | `project` | `project` | appends a scene to the end of the timeline |
| `update_scene_title` | `project` | `scene` | renames one scene |
| `set_scene_prompt` | `project` | `scene` | replaces one scene's motion prompt |
| `record_director_decision` | `bible` | `bible` | writes a continuity fact as a new Bible version |

`record_director_decision` deliberately goes through `operations.apply_mutation_set`, so a
recorded decision is an ordinary immutable Bible version visible in the version history — not a
side-channel store that the Bible workspace knows nothing about.

---

## 3. Shape of a turn

```
User chats → provider reply
  ├─ no fence ......................... message. Nothing runs.
  ├─ ```tool fence, read tool ......... tool_requested → tool_started → run → tool_completed
  │                                     → result appended to the transcript
  │                                     → ONE follow-up completion → `completed` (the answer)
  ├─ ```tool fence, mutating tool ...... tool_requested → propose → tool_proposal_created
  │                                     → `completed` (the model's prose) → approval card
  └─ ```proposal fence (M2.1) ......... unchanged Bible proposal path
```

Two properties are worth stating explicitly:

- **The tool-request turn is not shown.** For a read tool the server withholds that turn's
  `completed`, runs the tool, feeds the result back, and only the follow-up answer reaches the
  transcript. The UI clears the partially-streamed request text on `tool_requested` and shows a
  status line in its place, so the user never reads the model talking to itself.
- **`responseType` is advisory.** The model may label its request, but the registry's declared
  `kind` decides whether it executes now or becomes a proposal. A reply claiming
  `read_tool_call` for `create_scene` is treated as a mutation proposal, not as permission.

### 3.1 The read loop bound

`TOOL_LOOP_LIMIT = 1`: at most one read tool per user message, plus at most one follow-up
completion. If the follow-up asks for another tool, the turn ends with
`409 TOOL_LOOP_LIMIT_REACHED` rather than continuing. The bound exists so one user message can
never expand into an unbounded chain of local work, and it is enforced in the shared
`_interpret_reply` path so streaming and non-streaming chat cannot disagree about it.

---

## 4. The `tool_call` proposal

A mutating tool's proposal carries a **server-owned** payload. The model contributes a tool id
and raw arguments and nothing else; everything stored is computed server-side:

```113:129:studio-api/app/codirector/tools/definitions.py
class ToolCallPayload(BaseModel):
    """The server-owned payload of a `tool_call` proposal.

    Every field is produced by the server at proposal time. The model contributes only the
    tool id and raw arguments, and even those are re-validated against the tool's declared
    schema before they are stored — the stored `arguments` are the sanitized ones, so approving
    a proposal can never replay something the registry would reject.
    """

    toolId: str
    toolSchemaVersion: int = TOOL_SCHEMA_VERSION
    arguments: dict[str, Any] = Field(default_factory=dict)
    capabilitySnapshot: dict[str, Any] = Field(default_factory=dict)
    preview: ToolPreview = Field(default_factory=ToolPreview)
    inputHash: str = ""
    baseResourceVersions: dict[str, Optional[str]] = Field(default_factory=dict)
```

- `arguments` are the **sanitized** ones (§5). Approval replays only what the registry would
  accept today.
- `preview` is what the user reads. It is computed once, at proposal time, and shown as-is
  afterwards — re-deriving it at approval time would let a since-changed world quietly rewrite
  what the user is agreeing to.
- `inputHash` is the idempotency key for execution.
- `baseResourceVersions` pins the state the proposal was built against (§6).

### 4.1 One approval system, not two

`ProposalService` gained a second flavour, not a second lifecycle. `approve()` branches exactly
once — on `proposal_type == "tool_call"` — and everything around that branch is shared: the
terminal-state guards, the `APPROVAL_ALREADY_RECORDED` fast path, the staleness gate, the
`CoDirectorApproval` decision row, the `executing` transition, the receipt, and the idempotency
check against an existing successful receipt. Reject / request-revision / cancel are untouched
and work identically for both flavours.

The receipt gains four optional fields for the tool case (`toolId`, `toolInvocationId`,
`toolResult`, `toolResultTruncated`); a Bible receipt still reports `resultingVersionNumber`, and
so does a tool receipt when the tool wrote the Bible.

---

## 5. Arguments and results

`sanitize.py` sits on both trust boundaries:

- **Arguments (model → server).** Validated against the tool's declared `ToolParameter` list.
  Unknown keys are dropped rather than rejected (a model inventing a field shouldn't fail an
  otherwise valid call, but that field must never reach a handler); types are coerced or
  rejected; `maxLength`, `minimum`, `maximum`, and `choices` are enforced. Failures raise
  `400 TOOL_ARGUMENTS_INVALID` naming the offending parameter.
- **Results (server → model and browser).** Scrubbed of secret-shaped strings and absolute
  Windows/POSIX paths, capped in string length, list breadth, dict width, and nesting depth, then
  fitted to the tool's character budget by shedding whole top-level keys largest-first — which
  keeps the remaining JSON valid and self-describing, unlike slicing a serialized string. A
  truncated result is flagged (`_truncated`, plus a `tool_result_truncated` event) rather than
  silently handed to the model as if it were complete.

---

## 6. Staleness, generalized

M2.1 asked one question: "is the Bible still on the version this proposal was built against?"
M2.2 generalizes that to a map of pinned resources, because a scene rename must not be
invalidated by an unrelated Bible edit (and vice versa):

| Pinned resource | Token |
|---|---|
| `bible` | the Bible's `current_version_id` |
| `project` | the project's `updated_at` |
| `scene` | a hash of the scene fields a tool can target (`index`, `name`, `engine`, `prompt`, `duration_sec`, `camera_note`, `continuity_json`, `seed`) |

The scene fingerprint deliberately excludes `output_path`, so a render finishing doesn't
invalidate a pending title or prompt change. A proposal whose stored payload no longer parses is
treated as stale too — an unreadable payload can never be applied safely, so cancel is the only
remaining action.

---

## 7. Capability adapter

`capabilities.py` is a thin wrapper over probes that already exist elsewhere in the app — it is
**not** a Production Systems Readiness matrix, and adding a readiness surface is explicitly out
of scope for M2.2. Each capability key answers one question: "can a tool that needs this run
right now?"

| Key | Probe source |
|---|---|
| `project` | the project row |
| `bible` | `bible.operations.get_bible` + a current version |
| `provider` | `codirector.service.get_health` |
| `comfyui` | `comfy_client.comfy.health` |
| `references` | `references.capabilities.reference_capabilities` |
| `source_manager` | `source_manager.service.get_overview` |
| `preview_engine` | `preview_bus.capabilities_for` |

Three outcomes, mapped to two error codes: available; never set up
(`CAPABILITY_NOT_CONFIGURED`, `409`, action `configure_capability`); set up but unhealthy
(`CAPABILITY_UNAVAILABLE`, `503`, action `retry_or_check_service`). Every probe is wrapped so it
can only fail closed — a probe that raises or times out (6s) degrades to "unavailable" with a
short reason, never an exception escaping into a chat turn. Probes run at most once per request.

---

## 8. Invocation ledger

Every attempt is written to `codirector_tool_invocations` — including one that was *blocked* by a
capability, which is what makes "what did Co-Director do, and what was it prevented from doing"
answerable from the database alone. Rows record the tool, schema version, kind, status
(`succeeded` / `failed` / `blocked`), sanitized arguments, sanitized result and its hash, whether
it was truncated, the capability snapshot at the time, error code/message, the owning proposal
(for mutations), request id, duration, and who triggered it.

Schema lives in `app/db.py::CoDirectorToolInvocation` and is mirrored by the hand-written
`M003` migration, so `create_all` and the migration runner produce identical tables (asserted by
a test).

---

## 9. APIs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/codirector/tools` | The catalog, project-independent. No probes run. |
| `GET` | `/api/codirector/projects/{id}/tools` | Catalog + availability + capability snapshot. |
| `GET` | `/api/codirector/projects/{id}/tools/availability` | Availability only. |
| `POST` | `/api/codirector/projects/{id}/tools/read` | Run a read tool now. `400 TOOL_KIND_MISMATCH` for a mutating tool. |
| `POST` | `/api/codirector/projects/{id}/tools/proposals` | Create a `tool_call` proposal. Applies nothing. |
| `GET` | `/api/codirector/projects/{id}/tool-invocations` | The ledger, newest first, optionally filtered by `tool_id`. |

**There is deliberately no "execute tool" endpoint.** Mutations are approved through the existing
`/proposals/{id}/approve|reject|request-revision|cancel` endpoints, which is what keeps one
approval system rather than two.

---

## 10. SSE events (additive)

| Event | When |
|---|---|
| `tool_requested` | The reply asked for a tool. `kind` distinguishes read from mutating. |
| `tool_started` | A read tool is about to run (carries its human-readable title). |
| `tool_completed` | A read tool succeeded (carries the sanitized invocation). |
| `tool_failed` | A tool errored for a non-capability reason. |
| `tool_result_truncated` | The result was shortened to fit its budget. |
| `tool_proposal_created` | A mutating tool became a pending proposal. |
| `capability_blocked` | A required capability wasn't available; carries `capability` and the error. |

A capability block is **not** a failed turn: it is reported through `capability_blocked`, the
model is told plainly what it couldn't check, and the turn still completes with an answer. The
generic `error` event is not also emitted for it — a client would read that as a dead turn.

---

## 11. Frontend

- `CoDirectorToolStatus` renders one compact line ("Checking: List scenes…", "Checked: List
  scenes", "Couldn't check: …"). It has no buttons by design: read tools are status, not a task
  list, and nothing here may become a way to run or approve anything.
- `CoDirectorProposalCard` now serves both flavours from one shell. Bible proposals derive their
  lines from `payload` as before; tool proposals render the **server-computed**
  `toolCall.preview` (summary, lines, warnings) — the browser never builds a tool preview itself,
  since showing anything other than what the server recorded would make the approval meaningless.
  Tool cards carry a distinct accent (`.codirector-proposal-tool`) and stale copy that talks
  about the project rather than the Bible.
- Nothing in this path touches the legacy frontend-local `runSteps` / `planFromIntention`
  execution: tool results come from the server, and tool mutations go through proposals.

---

## 12. Testing

- **Unit/integration** — `studio-api/tests/test_codirector_tools.py` (75 tests): registry
  closure and binding integrity, kind-mismatch guards, schema-version guard, argument
  sanitization (required/unknown/length/range/choices/non-object), input-hash determinism, result
  scrubbing and truncation, capability fail-closed behavior, every read tool over HTTP, blocked
  reads still logged, propose-changes-nothing, approve-applies-once, reject/revision/cancel,
  approve-twice, all three staleness flavours, unreadable payload, execution failure → failed
  receipt + ledger row, `responseType` classification (including a mutating tool mislabelled as a
  read), the chat read loop and its bound, the SSE lifecycle, and `M003` schema parity.
- **E2E** — `tests/e2e/codirector/tools.spec.ts` (8 tests, all tagged `@critical @isolated`):
  a read tool runs inline with a status line and no fence leakage, a mutating tool applies only
  after Approve, reject leaves the project untouched, blocked and unconfigured capabilities still
  finish the turn, a stale tool proposal can only be cancelled, an execution failure changes
  nothing and leaves durable evidence, and the catalog contains no shell/filesystem/SQL escape
  hatch. The M1 chat-reliability and streaming-cancel specs and the M2.1 production-bible spec are
  unchanged.
