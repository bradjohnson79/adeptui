# Co-Director Operational Integrity Audit — Approval & Persistence

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c6/c7
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Audit scope:** Co-Director proposal/approval architecture, the four audited no-approval tools, preview fidelity, reject-path integrity, staleness handling, and persistence verification patterns.
**Audit mode:** READ-ONLY. No files modified; no non-readonly commands run during source investigation. The approve/reject code paths were verified directly against `studio-api/app/codirector/tools/execution.py`, `studio-api/app/codirector/bible/proposals.py`, and handler apply paths (see Section 8).
**Governing instrument:** Governing audit for the approval/persistence surface under Build Law 30. Complements `CODIRECTOR_ROUTING_AUDIT.md` (phases c2/c3) and `CODIRECTOR_ERROR_RECOVERY_AUDIT.md` (phase c6). Supersedes prior informal approval/persistence notes for this milestone.
**Sources of truth:** `data/tmp/codirector-audit-sources/routing-report.md`, `tool-registry-report.md`, `state-isolation-report.md`, `native-systems-report.md`, plus direct verification against the current tree (see Section 8).

---

## 1. Executive Summary

Co-Director's write path is a single proposal/approval system. The model can only ever *create* a proposal; approving, rejecting, or executing is a separate, explicit, user-triggered action. `ToolExecutionService.propose` (`execution.py:566`) validates arguments, computes a server-side preview, pins the resource versions it was built against, and hands a durable `tool_call` proposal to `ProposalService`. `ProposalService.approve` (`bible/proposals.py:358`) branches on flavour exactly once: Bible proposals apply through `operations.apply_mutation_set`; tool proposals apply through `ToolExecutionService.execute_approved_proposal` (`execution.py:697`), which replays the sanitized `payload.arguments` stored at proposal time — the model gets no second say at approval. The schema version is guarded (`execution.py:711`), and execution is idempotent per `(proposal, base state, payload)` via `inputHash` (`bible/proposals.py:496, 540`).

The reject path is clean: `ProposalService.reject` (`bible/proposals.py:304-319`) only records a decision row and flips status to `rejected`; no handler `apply` runs, no receipt is created, and the original authoritative state is untouched. The cancel and request-revision paths share this property. Staleness is enforced at approval and preview time via `is_stale` (`execution.py:685`), which compares pinned `baseResourceVersions` against the current world; a stale proposal is moved to `stale` status and raises `PROPOSAL_STALE` before any apply.

The audit identified **six findings** in the approval/persistence surface:

1. **Chat-stream audited-write routing drift**: three of four `requires_approval=False` tools are declared no-approval in the registry but routed as approval-gated proposals via the chat stream (hardcoded special-case at `service.py:753`).
2. **`production_plan.create_draft` proposal-gate bypass**: the one tool that does execute immediately via chat persists an unapproved draft with no preview-then-approve step; the model can truthfully claim "I created a plan" with no gate forcing it to disclose the draft is unapproved.
3. **ToolPreview field violations silently dropped**: posecraft passes `affectedResources` (13 handlers) and library passes `title`/`diff` (2 handlers) — fields not on the `ToolPreview` model, silently ignored by Pydantic v2, so the human reviewer loses structured change detail.
4. **Staleness checked at approval only, not at proposal creation**: a proposal built against already-stale resources is not surfaced to the model or creator at proposal-creation time on the chat stream.
5. **Persistence verification is handler-by-handler**: the gold-standard pattern (`director_timeline_tools` `_reload_master` + `save_master(bump_revision=True)`) is not framework-enforced; weak handlers (e.g. `wave4_plans.apply_create_draft`) rely on service internals with no handler-level re-read.
6. **Bible domain schema/handler mismatch persists empty entities**: `propose_character_update` silently persists empty `CharacterData` (declared schema lacks `data`), reporting success with a new Bible version number — a persistence-without-meanful-state defect.

Repairs for findings 1-6 are mapped to milestone phase c7 in Section 7.

## 2. Proposal/Approval Architecture

### 2.1 `propose` -> `ProposalService` -> `approve` -> `execute_approved_proposal`

The full chain, verified against source:

**Step 1 — `ToolExecutionService.propose`** (`studio-api/app/codirector/tools/execution.py:566-644`). Validates arguments, builds a server-side preview, pins base resource versions, and persists a `tool_call` proposal. Nothing is applied:

```566:644:studio-api/app/codirector/tools/execution.py
    @staticmethod
    async def propose(db, *, project_id, tool_id, arguments, scene_id=None, request_id=None,
                      created_by="assistant", adapter=None):
        """Build and persist a `tool_call` proposal. Nothing is applied here."""
        from ..bible.proposals import ProposalService
        _require_project(db, project_id)
        definition = tool_registry.require_kind(tool_id, "mutating")
        adapter = adapter or CapabilityAdapter(db, project_id)
        state = await adapter.state_for(definition.capability)
        readiness = await adapter.readiness_for_tool(definition.tool_id)
        if not state.available and not readiness.get("proposalReady"):
            error = state.as_error(definition.tool_id)
            _log_invocation(db, project_id=project_id, definition=definition, status="blocked",
                            arguments={}, capability_snapshot={definition.capability: state.to_dict()},
                            error=error, request_id=request_id, created_by=created_by)
            raise error
        clean_args = sanitize.sanitize_arguments(definition, arguments)
        ctx = ToolContext(db=db, project_id=project_id, scene_id=scene_id,
                          request_id=request_id, capabilities=adapter.cached_states())
        preview = ToolExecutionService._build_preview(ctx, definition, clean_args)
        base_versions = ToolExecutionService.base_resource_versions(
            db, project_id=project_id, definition=definition, arguments=clean_args)
        capability_snapshot = {definition.capability: {**state.to_dict(), "toolReadiness": readiness}}
        payload = ToolCallPayload(toolId=definition.tool_id, toolSchemaVersion=definition.schema_version,
                                  arguments=clean_args, capabilitySnapshot=capability_snapshot,
                                  preview=preview, inputHash=sanitize.compute_input_hash(...),
                                  baseResourceVersions=base_versions)
        return ProposalService.create_tool_proposal(db, project_id=project_id, payload=payload,
                                                     title=definition.title, summary=preview.summary,
                                                     request_id=request_id, created_by=created_by)
```

Key properties: `require_kind` (`registry.py:1226-1240`) enforces the tool is mutating; `sanitize_arguments` drops unknown keys; `base_resource_versions` (`execution.py:391-435`) pins only the resources in `definition.pinned_resources` (`bible`, `project`, `scene`, `plan`); `compute_input_hash` (`sanitize.py:113-132`) is the idempotency key over `toolId + schemaVersion + arguments + baseResourceVersions`.

**Step 2 — `ProposalService.create_tool_proposal`** (`bible/proposals.py:164-201`). Persists the row with `status="pending"`. Note: staleness is NOT computed here — `_row_to_out` is called with `is_stale=False` (`:201`).

**Step 3 — `ProposalService.approve`** (`bible/proposals.py:358-481`). The single approval entry. It:
1. Loads the row via `_get_row` (`:204-222`), which enforces `row.project_id == project_id` (raises `PROJECT_SCOPE_VIOLATION` otherwise — `:214-221`).
2. If already `completed`, returns the existing success receipt (idempotent re-approve — `:361-375`).
3. Rejects non-reviewable statuses with `PROPOSAL_INVALID_STATE` (`:383-390`).
4. Computes staleness: `_is_tool_proposal_stale` for tool proposals, `_is_stale` for Bible proposals (`:392-409`). If stale, sets `row.status="stale"` and raises `PROPOSAL_STALE` (recoverable, `preview_again`) *before any apply*.
5. Branches to `_approve_tool_proposal` (`:411-412`) for tool proposals.

**Step 4 — `_approve_tool_proposal`** (`bible/proposals.py:483-556`). Records the decision, sets `executing`, then calls `ToolExecutionService.execute_approved_proposal`:

```483:518:studio-api/app/codirector/bible/proposals.py
    @staticmethod
    def _approve_tool_proposal(db, row, *, note, decided_by):
        from ..tools.execution import ToolExecutionService
        payload = ToolExecutionService.parse_payload(row.payload_json)
        input_hash = payload.inputHash or ""
        existing_receipt = (db.query(CoDirectorExecutionReceipt).filter(...).first())
        if existing_receipt:
            return _receipt_to_out(db, existing_receipt)
        _record_decision(db, row, decision="approved", note=note, decided_by=decided_by)
        row.status = "executing"; row.updated_at = datetime.utcnow(); db.commit()
        try:
            outcome = ToolExecutionService.execute_approved_proposal(
                db, proposal=row, payload=payload, decided_by=decided_by)
        except CoDirectorError as err:
            receipt = CoDirectorExecutionReceipt(..., status="failed", ...)
            db.add(receipt); row.status = "failed"; db.commit(); raise
        # ... build success receipt, set row.status="completed" ...
```

**Step 5 — `execute_approved_proposal`** (`execution.py:697-789`). The argument-pinned replay with schema-version guard:

```697:723:studio-api/app/codirector/tools/execution.py
    @staticmethod
    def execute_approved_proposal(db, *, proposal, payload, decided_by="user"):
        """Apply an approved tool proposal. Called only from `ProposalService.approve`.

        The arguments replayed here are the sanitized ones recorded at proposal time — the model
        gets no second say at approval, which is what makes the approval meaningful."""
        definition = tool_registry.require_kind(payload.toolId, "mutating")
        tool_registry.check_schema_version(definition, payload.toolSchemaVersion)
        ctx = ToolContext(db=db, project_id=proposal.project_id,
                          scene_id=str(payload.arguments.get("sceneId") or "") or None,
                          request_id=proposal.request_id)
        started = time.monotonic()
        try:
            if _e2e_execution_fault():
                raise RuntimeError("Simulated tool execution failure (E2E).")
            raw = tool_registry.mutation_handler(definition.tool_id).apply(ctx, dict(payload.arguments))
```

`check_schema_version` (`registry.py:1243-1257`) raises `TOOL_SCHEMA_VERSION_MISMATCH` (non-recoverable) if the stored `toolSchemaVersion` differs from the current `definition.schema_version`. `ctx.project_id` is derived from `proposal.project_id` (DB row), not from model args — the model cannot redirect an approved proposal to another project.

## 3. The 4 Audited No-Approval Tools

Four tools are declared `requires_approval=False` in `studio-api/app/codirector/tools/definitions.py`. Each is assessed for whether the exception is justified.

| Tool | Definition | Handler apply | Justified? | Assessment |
|---|---|---|---|---|
| `production_plan.create_draft` | `definitions.py:1969-1986` (`requires_approval=False`, `:1975`) | `wave4_plans.apply_create_draft` (`wave4_plans.py:251-265`) -> `PlanService.create_draft` | **Conditionally justified, with a caveat.** The draft is non-authoritative (state=draft/unapproved) and cannot authorize production; the description (`:1973`) states "Persist an audited unapproved draft without plan-acceptance approval. Cannot authorize production." This keeps conversational drafting fluid. **Caveat (Finding 2):** the model can truthfully claim "I created a plan" with no gate forcing it to disclose the draft is unapproved. The `tool_completed` receipt carries `unapprovedDraft: True` (`service.py:791-797`), but nothing in the pipeline forces the model's prose to mention it. |
| `audio.cancel_batch` | `definitions.py:4133-4142` (`requires_approval=False`, `:4139`) | `audio_studio_tools.apply_cancel_batch` (`audio_studio_tools.py:537-545`) -> `audio_service.cancel_batch` | **Justified as an emergency escape, BUT ineffective via chat (Finding 1).** The description (`:4137`) says "Emergency cancel for an Audio Studio batch — terminates GPU workers at source. No second approval delay." This is a safety escape: a runaway GPU batch should not wait for a second approval. However, via the chat stream this tool is NOT routed through `execute_audited` (the audited branch at `service.py:749-753` is hardcoded to `production_plan.create_draft` only), so it falls through to `_propose_tool_call` (`service.py:800`) and becomes an approval-gated proposal — defeating the "no second approval delay" intent. It only executes immediately via the direct `/projects/{project_id}/tools/audited` endpoint (`routers/codirector.py:1884`). |
| `minimax_h3.offer_ltx_fallback` | `definitions.py:5967-5978` (`requires_approval=False`, `:5977`) | `minimax_h3_tools.apply_offer_ltx_fallback` (`minimax_h3_tools.py:242-250`) -> `preflight` | **Justified.** This *prepares* an explicit LTX fallback offer while preserving the MiniMax H3 prompt/frames/references; it does not switch runtimes. The actual switch (`minimax_h3.accept_ltx_fallback`, `:5980-5990`) IS approval-gated. Preparing an offer without a second gate is honest: it records intent without authorizing the fallback. **Same chat-routing drift as above (Finding 1):** via chat this becomes a proposal, not an immediate apply. |
| `minimax_h3.cancel` | `definitions.py:5991-6003` (`requires_approval=False`, `:6002`) | `minimax_h3_tools.apply_cancel` (`minimax_h3_tools.py:291-298`) -> `cancel` | **Justified as an emergency escape, BUT ineffective via chat (Finding 1).** Description (`:5995`): "Cancel the active MiniMax H3 request state while keeping the stored plan for review." Cancelling an in-flight chargeable request should not wait for a second approval. Same chat-routing drift: via chat it becomes a proposal. |

### 3.1 Finding 1 — Chat-stream audited-write routing drift

**Root cause:** `_interpret_reply` (`service.py:749-753`) special-cases the audited-write branch with a hardcoded set:

```749:753:studio-api/app/codirector/service.py
    if (
        definition is not None
        and definition.kind == "mutating"
        and not definition.requires_approval
        and structured.tool_call.tool_id in {"production_plan.create_draft"}
    ):
```

The fourth condition (`structured.tool_call.tool_id in {"production_plan.create_draft"}`) is a literal set, not a registry query. The three other `requires_approval=False` tools (`audio.cancel_batch`, `minimax_h3.offer_ltx_fallback`, `minimax_h3.cancel`) fail this condition, so they fall through to `if structured.response_type == "mutation_proposal"` (`service.py:800`) and are routed to `_propose_tool_call`, creating an approval-gated proposal. The `response_type` is derived from `definition.kind` (`structured_output.py:169`), so all four mutating tools get `response_type="mutation_proposal"` regardless of `requires_approval`.

**Impact:** The registry declares three emergency/no-delay tools, but the chat stream silently re-gates them behind a proposal. The direct REST endpoint (`routers/codirector.py:1884` -> `execute_audited`) honors `requires_approval` generically (`execution.py:458-465` raises if `requires_approval` is true), so the registry declaration is *effective via direct API* but *ineffective via chat*. This is a contract drift between the registry and the chat router, and it contradicts the "No second approval delay" intent in two tool descriptions.

**Severity:** Medium. It does not break correctness (a proposal is safer than an immediate apply), but it breaks the documented emergency semantics and creates a discrepancy between the two invocation paths.

### 3.2 Finding 2 — `production_plan.create_draft` proposal-gate bypass concern

**Root cause:** `apply_create_draft` (`wave4_plans.py:251-265`) calls `PlanService.create_draft` directly with no preview-then-approve step. The handler only checks `_project(ctx)` (`wave4_plans.py:35-43`) — it does not load the project or check for an existing draft with the same title/objective before persisting. Idempotency relies entirely on `PlanService` internals and the `requestId`-based prior-success check in `execute_audited` (`execution.py:467-481`).

The model can truthfully say "I created a plan" because a real `PlanService.create_draft` row is persisted (the `bibleVersionNumber`/plan id is real). The `tool_completed` receipt carries `unapprovedDraft: True` (`service.py:791-797`), but nothing in the pipeline forces the model's prose to disclose that the draft is unapproved. A creator hearing "I created a plan" may reasonably infer the plan is actionable, when in fact it is a draft that cannot authorize production.

**Severity:** Low-Medium. The draft is genuinely non-authoritative, so no production harm occurs. The risk is a creator misinterpreting the model's claim. The fix is a prose constraint, not a structural change.

## 4. Preview Fidelity

### 4.1 The `ToolPreview` contract

`ToolPreview` (`studio-api/app/codirector/tools/definitions.py:107-114`) declares exactly five fields:

```107:114:studio-api/app/codirector/tools/definitions.py
class ToolPreview(BaseModel):
    """Human-reviewable description of what a mutating tool would do, computed server-side."""
    summary: str = ""
    lines: list[str] = Field(default_factory=list)
    resourceKind: Optional[str] = None
    resourceId: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
```

Under Pydantic v2 default behavior, extra fields passed to a `BaseModel` are **silently ignored** (not stored, not rejected). The preview still constructs, but the extra data is lost. There is no `model_config = ConfigDict(extra="forbid")` and no validation warning, so a handler passing an undeclared field gets no signal that its intent was dropped.

### 4.2 Finding 3 — Posecraft `affectedResources` silently dropped (13 handlers)

**Root cause:** Thirteen posecraft preview handlers pass `affectedResources=("project",)`, which is not a `ToolPreview` field. Verified at `studio-api/app/codirector/tools/handlers/posecraft.py` lines 201, 217, 246, 276, 298, 317, 336, 352, 377, 394, 418, 433, 454:

```201:201:studio-api/app/codirector/tools/handlers/posecraft.py
    return ToolPreview(summary=summary, affectedResources=("project",))
```

Pydantic v2 silently ignores `affectedResources`, so the project-level impact annotation is lost. The preview still renders (the `summary` is preserved), but the structured "this affects the project" signal the handler intended to surface is dead. A human reviewer sees the summary line without the affected-resource annotation.

### 4.3 Finding 3 (cont.) — Library `title`/`diff` silently dropped (2 handlers)

**Root cause:** `preview_propose_asset_library_assignment` (`studio-api/app/codirector/tools/handlers/library.py:110-135`) passes `title=` and `diff={...}` to `ToolPreview`:

```119:135:studio-api/app/codirector/tools/handlers/library.py
    if loc.get("ambiguous"):
        return ToolPreview(
            title="Assign asset to library folder",
            summary=f"Ambiguous folder for '{args.get('path') or args.get('query')}' — choose a candidate.",
            diff={"candidates": loc.get("candidates") or []},
        )
    match = loc.get("match") or {}
    return ToolPreview(
        title="Assign asset to library folder",
        summary=f"Move '{asset.tag or asset.filename}' → {match.get('libraryPath') or match.get('displayPath') or 'target folder'}",
        diff={
            "assetId": asset.id,
            "targetPath": match.get("libraryPath") or match.get("displayPath"),
            "systemKey": args.get("systemKey") or match.get("systemKey"),
            "override": bool(args.get("override", True)),
        },
    )
```

Both `title` and `diff` are undeclared on `ToolPreview` and silently dropped. The library preview degrades to `summary`-only: the `diff` block containing the target folder path, asset id, and override flag is discarded, so the human reviewer sees only a summary line without the structured change details the handler intended to show. This is more serious than the posecraft case because the diff is the substantive content of the proposal.

**Severity:** Medium. The proposal still creates and applies correctly (the `apply` handler at `library.py:138-151` does not depend on the preview fields), but the human reviewer's ability to make an informed approve/reject decision is degraded for library assignment proposals.

## 5. Reject-Path Assessment

### 5.1 `ProposalService.reject` — no mutation, original state authoritative

`ProposalService.reject` (`studio-api/app/codirector/bible/proposals.py:304-319`) is verified to perform **no apply** and **no receipt creation**:

```304:319:studio-api/app/codirector/bible/proposals.py
    @staticmethod
    def reject(db, project_id, proposal_id, *, note, decided_by) -> ProposalOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        if row.status not in _REVIEWABLE_STATUSES:
            raise CoDirectorError(PROPOSAL_INVALID_STATE,
                f"Proposal cannot be rejected from status '{row.status}'.",
                details={"proposalId": proposal_id, "status": row.status},
                recoverable=False, recommended_action="none")
        _record_decision(db, row, decision="rejected", note=note, decided_by=decided_by)
        row.status = "rejected"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _row_to_out(row, is_stale=False)
```

The only writes are: (1) a `CoDirectorApproval` decision row via `_record_decision` (`:604-614`), and (2) `row.status = "rejected"`. No handler `apply` is invoked, no `CoDirectorExecutionReceipt` is created, no `apply_mutation_set` or `execute_approved_proposal` runs. The original authoritative state (Bible current version, scene, plan, etc.) is untouched. The same property holds for `request_revision` (`:322-337`) and `cancel` (`:340-355`): they only record a decision and flip status.

### 5.2 Terminal-state guard prevents double-action

`_REVIEWABLE_STATUSES = {"pending", "revision_requested", "stale"}` (`bible/proposals.py:53`) and `_TERMINAL_STATUSES = {"rejected", "completed", "failed", "cancelled"}` (`:52`). `reject` rejects any status not in `_REVIEWABLE_STATUSES` with `PROPOSAL_INVALID_STATE` (non-recoverable). So a proposal already `rejected` cannot be rejected again, and a `completed` proposal cannot be rejected (it can only be re-approved idempotently — `:361-375`). This prevents a reject from undoing a prior approve.

### 5.3 Project-scope guard on every decision

`_get_row` (`bible/proposals.py:204-222`) enforces `row.project_id == project_id` on every decision path (reject, approve, cancel, request_revision, get, preview). A proposal from Project B cannot be rejected/approved from Project A — it raises `PROJECT_SCOPE_VIOLATION` (non-recoverable). This closes the cross-project approval leak class identified in `state-isolation-report.md` for the tool-registry path.

**Verdict:** The reject path is clean. On reject, no mutation occurs and the original state remains authoritative. The terminal-state and project-scope guards are correct.

## 6. Staleness Handling

### 6.1 `is_stale` checked at approval and preview, NOT at proposal creation

`ToolExecutionService.is_stale` (`execution.py:685-694`) compares the pinned `baseResourceVersions` against the current world:

```685:694:studio-api/app/codirector/tools/execution.py
    @staticmethod
    def is_stale(db, *, project_id, payload):
        """Compare the pinned resource versions against the world as it is now."""
        definition = tool_registry.find(payload.toolId)
        if definition is None:
            return True
        current = ToolExecutionService.base_resource_versions(
            db, project_id=project_id, definition=definition, arguments=payload.arguments)
        return current != dict(payload.baseResourceVersions)
```

It is invoked by:
- `ProposalService.approve` (`bible/proposals.py:394`) — via `_is_tool_proposal_stale` (`:83-94`). If stale, sets `row.status="stale"` and raises `PROPOSAL_STALE` *before any apply* (`:395-409`).
- `ProposalService.preview` (`:248`) — reports staleness to the reviewer.
- `ProposalService.get` / `list` (`:228`, `:237`) — via `_stale_for_row` (`:97-102`), so the UI can badge stale proposals.

It is **NOT** invoked by `create_tool_proposal` (`bible/proposals.py:164-201`), which calls `_row_to_out(row, is_stale=False)` (`:201`). The docstring at `execution.py:704` confirms: "Called only from `ProposalService.approve`."

### 6.2 Finding 4 — Staleness not surfaced at proposal creation

**Root cause:** A proposal built against already-stale resources (e.g. the Bible was bumped between the model's read and the `propose` call) is created with `is_stale=False` (`bible/proposals.py:201`). The model and creator are not told at proposal-creation time that the proposal was built against stale state; the staleness is only detected when the creator later opens the preview or hits Approve. By then, the model may have moved on, and the creator must re-ask Co-Director.

**Severity:** Low. The staleness is still caught before any apply (so no bad write occurs), but the creator experience is degraded: a proposal that was born stale is presented as fresh until preview/approve. The fix is to compute `is_stale` at creation and emit a `proposal_stale_at_creation` warning event.

## 7. Persistence Verification Patterns

### 7.1 Gold-standard: `director_timeline_tools` revision-bump + reload

The `director_timeline_tools` handler is the gold-standard persistence pattern. Every mutating `apply_*` reads authoritative state via `_reload_master` (`director_timeline_tools.py:80`) before mutating, then persists via `store.save_master(..., bump_revision=True)`. Verified across all mutating apply handlers (e.g. `apply_set_playhead` `:835-853`, `apply_update_settings` `:880-901`, `apply_propose_add_batch` `:1196-1219`, `apply_propose_add_image_clip` `:1255-1289`, `apply_propose_layout_preset` `:1700-1714`, `apply_propose_zoom` `:1853-1874`, `apply_propose_add_camera` `:1910-1927`, `apply_propose_add_lipsync_track` `:2030-2048`, `apply_propose_bind_lipsync_clip` `:2223-2263`, `apply_propose_open_inpaint` `:2301-2332`, `apply_attach_optional_reference` `:1562-1590`):

```835:853:studio-api/app/codirector/tools/handlers/director_timeline_tools.py
def apply_set_playhead(ctx, args):
    ...
    store.save_master(
        ctx.db,
        project_id=ctx.project_id,
        scene_id=scene_id,
        master=master,
        bump_revision=True,
    )
```

The pattern is: read authoritative state -> mutate in memory -> persist with `bump_revision=True` so the timeline revision advances. The revision is what `base_resource_versions` pins (via `scene`/`project` pinned resources), so a subsequent proposal built against the old revision is detected as stale at approval. This closes the read-before-write -> persist -> staleness-detection loop.

### 7.2 Finding 5 — Persistence verification is handler-by-handler, not framework-enforced

**Root cause:** There is no framework-level invariant like "every mutating `apply` must call a `_require_*` re-read first." The `routing-report.md` §(c) and `tool-registry-report.md` §(c) confirm read-before-write is handler-by-handler. Weak handlers:

- `wave4_plans.apply_create_draft` (`wave4_plans.py:251-265`): only `_project(ctx)` checks the project id is present. It does NOT load the project or check for an existing draft with the same title/objective before calling `PlanService.create_draft`. Idempotency relies entirely on `PlanService` internals and the `requestId` prior-success check (`execution.py:467-481`).
- `wave4_plans.apply_propose`/`apply_approve`/`apply_reject` (`wave4_plans.py:285-328`): pass `planId` straight to `PlanService`; no handler-level read of the plan's current state. Staleness is enforced by `expected_version` inside `PlanService`, not by the handler calling `ToolExecutionService.is_stale` (that check lives in the approval flow, not the apply handler).
- `bible_domain.apply_propose_canon_supersession` (`bible_domain.py:157-165`): calls `BibleDomainService.create_canon_record` with `supersedes_stable_id` but the handler does NOT verify the superseded record exists or is the current version.
- `bible_domain.apply_propose_continuity_update` (`bible_domain.py:178-196`): generates a new `entity_key` (`f"cont-{uuid.uuid4().hex[:8]}"`) without reading existing continuity entities — could create duplicates.
- `bible_domain.apply_propose_reference_link` (`bible_domain.py:209-214`): does not check whether the asset or target already exists or whether a link already exists.

**Severity:** Medium. The services beneath these handlers generally enforce ownership and versioning (per `state-isolation-report.md` §b: scenes, characters, plans, minimax h3, director timeline all enforce `entity.project_id == ctx.project_id`), so the framework is defense-in-depth-fragile rather than broken. Any new handler that forgets the re-read inherits a leak.

### 7.3 Finding 6 — Bible domain schema/handler mismatch persists empty entities

**Root cause (verified):** `apply_propose_character_update` (`bible_domain.py:90-122`) reads `args.get("data")` at line 97, but the `production_plan`-style schema for `propose_character_update` declares only `stableId`, `entityKey`, `displayName` (per `tool-registry-report.md` §5.1). `sanitize_arguments` (`sanitize.py:90-110`) drops `data` as an unknown key, so `args.get("data")` is always `None`:

```96:103:studio-api/app/codirector/tools/handlers/bible_domain.py
    if not existing:
        data = CharacterData.model_validate(args.get("data") or {}).model_dump(mode="json")
        mutation = EntityMutation(
            entityType="character",
            entityKey=entity_key or f"char-{stable_id[:8] if stable_id else 'new'}",
            displayName=args.get("displayName", "Character"),
            data=data,
        )
```

`CharacterData.model_validate({})` produces an empty `CharacterData` object. The handler then calls `ops.apply_mutation_set` (`:115`) and returns `{"bibleVersionNumber": new_version.version_number}` (`:122`) — a real new Bible version is persisted, but it encodes empty/malformed character data. The tool reports success with a new version number while persisting meaningless state. This violates Build Law 8 (no silent behavior) and Law 11 (failure recovery): success is reported without verifying meaningful authoritative state.

The same class of defect affects `propose_canon_record` (`bible_domain.py:141-142` reads undeclared `entityStableId`/`sceneId`), `propose_canon_supersession` (`:162` reads undeclared `entityStableId`), `propose_continuity_update` (`:189-193` reads undeclared `entityStableId`/`sceneId`/`expectedValue`/`actualValue`/`resolved`), `propose_production_decision` (`:242-244` reads undeclared `rationale`/`entityStableId`/`sceneId`), and `propose_reference_link` (`:215-216` reads undeclared `purpose`/`primary`). Per `tool-registry-report.md` §5.1, `character_creator.propose_traits` (`character_creator.py:307`) and `propose_relationships` (`:350`) always raise `ValueError` because `traits`/`relationships` are stripped.

**Severity:** High for the silently-persisting-bad-data cases (`propose_character_update`); the always-failing cases (`propose_traits`/`propose_relationships`) are High but fail loudly. This is the single most important class of defect for the milestone per `tool-registry-report.md` §5.1 root-cause note.

## 8. Repair Recommendations (mapped to milestone phase c7)

Phase c7 owns approval/persistence repairs. Each repair references the finding it closes.

| ID | Finding | Repair | Files touched | Acceptance |
|---|---|---|---|---|
| c7.1 | 1 Chat-stream audited-write routing drift | Replace the hardcoded set at `service.py:753` with a registry query: route to `execute_audited` whenever `definition.kind == "mutating" and not definition.requires_approval`. Keep an explicit allowlist of which no-approval tools may be invoked via chat (document the safety case per tool). | `studio-api/app/codirector/service.py:749-753` | A Playwright scenario where the model requests `audio.cancel_batch` via chat executes immediately (not a proposal); a scenario for an approval-gated mutating tool still creates a proposal. |
| c7.2 | 2 `create_draft` proposal-gate bypass | Add a prose constraint in the `tool_completed` event handler and the `follow_up_prompt` for audited drafts: the model must state the draft is unapproved. Surface `unapprovedDraft: True` as a visible badge in the chat transcript, not just the receipt. | `service.py:791-797`, frontend `CoDirectorSession.tsx` | A Playwright scenario where the model creates a draft shows a visible "Draft — not approved" badge; the model's prose includes the unapproved qualifier. |
| c7.3 | 3 ToolPreview field violations | Set `model_config = ConfigDict(extra="forbid")` on `ToolPreview` (`definitions.py:107-114`) so undeclared fields raise at construction. Either add `affectedResources` to the model (and update the 13 posecraft handlers to use it) or remove the dead `affectedResources`/`title`/`diff` args from the posecraft and library handlers. For library, add a `diff` field to `ToolPreview` so the structured change detail reaches the reviewer. | `definitions.py:107-114`, `posecraft.py` (13 lines), `library.py:119-135` | A unit test passing `affectedResources`/`diff` to a preview either stores the field or raises; no silent drop. The library preview shows the diff in the approval UI. |
| c7.4 | 4 Staleness not surfaced at proposal creation | Compute `is_stale` in `create_tool_proposal` (`bible/proposals.py:164-201`) and emit a `proposal_stale_at_creation` warning event when the proposal was built against stale resources. Do not block creation (the creator may still want to see the proposal), but surface the warning so the model can re-ask immediately. | `bible/proposals.py:164-201`, `service.py` (propose event emission) | A test where the Bible is bumped between read and propose emits the `proposal_stale_at_creation` warning; the creator sees the badge. |
| c7.5 | 5 Persistence verification handler-by-handler | Introduce a shared helper (e.g. `require_scene_owned(ctx, scene_id)`, `require_plan_owned(ctx, plan_id)`, `require_bible_current(ctx)`) and require every mutating `apply` to call the relevant `_require_*` first. Add a registry-level invariant check (in `_validate_bindings`) that every mutating handler calls a re-read helper, or document the per-handler re-read contract. | `tools/handlers/*.py`, `tools/registry.py:1180-1192` | A test that mutates a resource after a proposal is created but before apply detects the change at the handler level (not only at approval). |
| c7.6 | 6 Bible domain schema/handler mismatch | Update the `ToolDefinition.parameters` for the affected Bible/character tools to declare the keys the handlers actually read (`data`, `entityStableId`, `sceneId`, `traits`, `relationships`, `rationale`, `purpose`, `primary`, `expectedValue`, `actualValue`, `resolved`). For `propose_character_update`, require `data` and reject empty `CharacterData` at the handler (`bible_domain.py:97`) instead of silently persisting it. For `propose_traits`/`propose_relationships`, declare `traits`/`relationships` so the tools stop always failing. | `tools/definitions.py` (schema tuples), `bible_domain.py:90-122, 136-244`, `character_creator.py:305-350` | A test calling `propose_character_update` with `data` persists the data (not empty); `propose_traits` with `traits` succeeds; `propose_character_update` with empty `data` raises `TOOL_ARGUMENTS_INVALID`. |

### 8.1 Cross-phase dependency

c7.1 (chat-stream audited routing) depends on c6.4 (generic-error collapse) being closed first, because routing more tools through `execute_audited` via chat increases the surface where a structured upstream error could be collapsed into `TOOL_EXECUTION_FAILED`. Sequence: c6.4 -> c7.1.

## 9. Verification log

Every citation was spot-verified against the current tree on 2026-08-07. The approve/reject code paths were verified directly against source (not solely from the source reports).

| # | Citation (as used in this doc) | Verified at | Source report claim | Correction |
|---|---|---|---|---|
| 1 | `execution.py:566-644` `propose` | execution.py:566-644 | routing-report §(a) step 5 | None. |
| 2 | `execution.py:391-435` `base_resource_versions` | execution.py:391-435 | routing-report §(c) | None. |
| 3 | `execution.py:697-723` `execute_approved_proposal` (argument-pinned replay) | execution.py:697-723 | routing-report §(d) point 4 | None. |
| 4 | `execution.py:711` schema-version check | execution.py:711 (`check_schema_version` call) | routing-report §(d) point 4 | None. |
| 5 | `execution.py:685-694` `is_stale` | execution.py:685-694 | routing-report §(d) gap 4 | None. |
| 6 | `execution.py:704` docstring "Called only from ProposalService.approve" | execution.py:704-708 | routing-report §(d) gap 4 | None. |
| 7 | `registry.py:1226-1240` `require_kind` | registry.py:1226-1240 | routing-report §(b) | None. |
| 8 | `registry.py:1243-1257` `check_schema_version` | registry.py:1243-1257 | routing-report §(b) | None. |
| 9 | `registry.py:1180-1192` `_validate_bindings` | registry.py:1180-1192 | routing-report §(b) | None. |
| 10 | `bible/proposals.py:164-201` `create_tool_proposal` (is_stale=False at :201) | proposals.py:164-201 | routing-report §(d) gap 4 | None. |
| 11 | `bible/proposals.py:204-222` `_get_row` (project-scope guard) | proposals.py:204-222 | state-isolation-report §(d) | None. |
| 12 | `bible/proposals.py:304-319` `reject` (no apply, no receipt) | proposals.py:304-319 | Not in source reports | **Directly verified**: reject only records decision + flips status; no `apply`/receipt. |
| 13 | `bible/proposals.py:322-337` `request_revision` | proposals.py:322-337 | Not in source reports | **Directly verified**: same no-apply property as reject. |
| 14 | `bible/proposals.py:340-355` `cancel` | proposals.py:340-355 | Not in source reports | **Directly verified**: same no-apply property; terminal-state guard at :342. |
| 15 | `bible/proposals.py:358-481` `approve` (staleness before apply at :394-409) | proposals.py:358-481 | routing-report §(d) point 4 | None. |
| 16 | `bible/proposals.py:483-556` `_approve_tool_proposal` | proposals.py:483-556 | routing-report §(d) point 4 | None. |
| 17 | `bible/proposals.py:52-53` `_TERMINAL_STATUSES`/`_REVIEWABLE_STATUSES` | proposals.py:52-53 | Not in source reports | **Directly verified**: terminal-state guard set. |
| 18 | `definitions.py:107-114` `ToolPreview` (5 fields) | definitions.py:107-114 | tool-registry-report §5.3 | None. |
| 19 | `definitions.py:1969-1986` `production_plan.create_draft` (requires_approval=False at :1975) | definitions.py:1969-1986 | tool-registry-report §4.23 | None. |
| 20 | `definitions.py:4133-4142` `audio.cancel_batch` (requires_approval=False at :4139) | definitions.py:4133-4142 | tool-registry-report §4 (audited tools) | None. |
| 21 | `definitions.py:5967-5978` `minimax_h3.offer_ltx_fallback` (requires_approval=False at :5977) | definitions.py:5967-5978 | tool-registry-report §4 (audited tools) | None. |
| 22 | `definitions.py:5991-6003` `minimax_h3.cancel` (requires_approval=False at :6002) | definitions.py:5991-6003 | tool-registry-report §4 (audited tools) | None. |
| 23 | `service.py:749-753` hardcoded `{"production_plan.create_draft"}` | service.py:749-753 | Not in source reports | **New finding**: 3 of 4 no-approval tools not routed via chat audited branch. |
| 24 | `service.py:791-797` `tool_completed` with `unapprovedDraft: True` | service.py:791-797 | routing-report §(d) gap 3 | None. |
| 25 | `service.py:800` fallthrough to `_propose_tool_call` | service.py:800 | Not in source reports | **Directly verified**: confirms c7.1 drift. |
| 26 | `structured_output.py:169` response_type from definition.kind | structured_output.py:169 | routing-report §(b) | None. |
| 27 | `routers/codirector.py:1884` `/tools/audited` endpoint | routers/codirector.py:1884 | Not in source reports | **Directly verified**: honors requires_approval generically. |
| 28 | `posecraft.py:201,217,246,276,298,317,336,352,377,394,418,433,454` `affectedResources` | posecraft.py (13 lines) | tool-registry-report §5.3 | None. All 13 lines verified. |
| 29 | `library.py:110-135` `title`/`diff` dropped | library.py:110-135 | tool-registry-report §5.3 | None. |
| 30 | `library.py:138-151` `apply_propose_asset_library_assignment` (does not depend on preview fields) | library.py:138-151 | Not in source reports | **Directly verified**: apply is independent of dropped preview fields. |
| 31 | `wave4_plans.py:251-265` `apply_create_draft` (no re-read) | wave4_plans.py:251-265 | routing-report §(c) | None. |
| 32 | `wave4_plans.py:285-328` `apply_propose`/`apply_approve`/`apply_reject` (no handler-level read) | wave4_plans.py:285-328 | routing-report §(c) | None. |
| 33 | `bible_domain.py:90-122` `apply_propose_character_update` (empty CharacterData at :97) | bible_domain.py:90-122 | tool-registry-report §5.1/§5.2 | None. |
| 34 | `bible_domain.py:136-244` canon/continuity/decision/reference handlers reading undeclared keys | bible_domain.py:136-244 | tool-registry-report §5.1 | None. |
| 35 | `director_timeline_tools.py:80` `_reload_master` | director_timeline_tools.py:80 | native-systems-report Part A row 1 | None. |
| 36 | `director_timeline_tools.py` `bump_revision=True` across mutating apply handlers | director_timeline_tools.py (e.g. :853, :901, :953, :1077, :1168, :1219, :1289, :1359, :1590, :1714, :1765, :1814, :1874, :1927, :1992, :2048, :2109, :2184, :2263, :2332) | native-systems-report Part A row 1 | None. Pattern verified at 20+ apply sites. |
| 37 | `sanitize.py:90-110` `sanitize_arguments` (drops unknown keys) | sanitize.py:90-110 | tool-registry-report §5.1 root cause | None. |

### 9.1 Summary of corrections

- No path corrections were required for this document. The `conversation/wiki_verification.py:10` correction (made in the Error Recovery audit) does not recur here.
- Three new findings not present in the source reports: (a) chat-stream audited-write routing drift (citation 23), (b) the direct `/tools/audited` endpoint honors `requires_approval` generically (citation 27), and (c) the library `apply` handler is independent of the dropped preview fields (citation 30). All three were verified directly against source.
- The reject-path assessment (Section 5) and the terminal-state guard (citation 17) were verified directly against `bible/proposals.py` source, not solely from the source reports, per the task requirement.

---

## 10. Verdict

**AUDIT COMPLETE.** The proposal/approval architecture is structurally sound: the model cannot apply without a human-approved proposal, approved-proposal replay is argument-pinned and schema-version-guarded, the reject path performs no mutation, and staleness is caught before any apply. Six findings (Section 3-7) are preserved for phase c7 repair. Finding 6 (Bible domain schema/handler mismatch persisting empty entities) is the most urgent: it is a silent-success defect that violates Build Law 8 and should be closed before any Bible-domain Co-Director capability is certified GO under Law 31. Findings 1 and 3 are Medium and should be closed in the same phase. Findings 2, 4, and 5 are Low-Medium and may be sequenced after the High-severity repairs.

