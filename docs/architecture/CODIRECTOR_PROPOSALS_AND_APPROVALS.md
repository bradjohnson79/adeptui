# Co-Director Milestone 2.1 — Durable Proposals, Approvals, and Execution Receipts

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-1-production-bible`
**Related:** `docs/architecture/CODIRECTOR_PRODUCTION_BIBLE.md` (the read path / data model this
writes into), `docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md` (M1 reliability runtime this
builds on), `docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` (§"Tool calling + approvals" —
this milestone implements the approvals half of that vision, scoped to Bible mutations only)
**Status:** Implemented.

---

## 1. Why proposals exist

M2.1's one hard invariant: **the model never mutates the Production Bible directly.** There is
no tool, no API path, no code path by which a chat reply causes a Bible write on its own. The
only lever the model has is to emit a structured proposal that a human must explicitly approve.

This is deliberately narrower than the full "tool calling + approvals" vision in
`CODIRECTOR_PRODUCTION_BRAIN.md` — there is exactly one "tool" (propose a Bible mutation), not a
general registry, and no task-graph or multi-step execution is involved.

---

## 2. End-to-end flow

```
User chats → CoDirectorService streams a reply
           → reply contains a ```proposal fenced JSON block (model's choice, not automatic)
           → backend parses + validates the block, persists a CoDirectorProposal (status=pending)
           → SSE emits `proposal_created` (or a non-fatal `error` event if the block was malformed)
           → FE renders a CoDirectorProposalCard — never raw JSON
           → user clicks Approve / Reject / Request Revision / Cancel
           → Approve: staleness check → apply_mutation_set → new Bible version + execution receipt
           → FE shows "Proposal approved and applied — a new Production Bible version was created."
```

The model never sees or handles the approval step — that round-trip is entirely between the FE
and `ProposalService`.

---

## 3. Structured output extraction

`app/codirector/structured_output.py` mirrors the existing `assistant.extract_scene_setup` /
`strip_scene_setup_blocks` fence-then-parse pattern M1 already used for `scene_setup`, applied to
```` ```proposal ```` blocks:

- `extract_proposal_block(reply) -> ProposalExtractionResult | None` — `None` means no fence at
  all (nothing to report, most replies). A present-but-malformed fence (invalid JSON, wrong
  shape, failed Pydantic validation) returns a result with `.error` set rather than being
  silently dropped or silently accepted.
- `strip_proposal_blocks(reply) -> str` — removes the fence(s) from the text shown to the user.

`codirector/service.py::_create_proposal_from_reply` is the single call site (used by both
`chat_for_project` and `stream_for_project`):

- No fence → passthrough, no proposal.
- Fence present, valid → `ProposalService.create_proposal(...)` persists it; the cleaned
  (fence-stripped) text is what the user sees, plus a `proposal_created` event/field.
- Fence present, malformed → **non-fatal** `STRUCTURED_OUTPUT_INVALID` `CoDirectorError`. The
  chat turn still completes (the model's prose reply, minus the broken fence, is still shown) —
  this is a "the model tried to propose something and got the format wrong" signal, not a
  connection/provider failure, so it must not discard an otherwise-successful reply.

### 3.1 A real bug this caught (fixed during M2.1, not deferred)

Initially, the frontend's stream-event reducer (`CoDirectorSession.tsx::performSend`) treated any
`error` event — fatal or not — as the terminal outcome for the turn, which meant a
`STRUCTURED_OUTPUT_INVALID` event arriving *after* a `completed` event overwrote the "completed"
outcome. Combined with token-by-token streaming rendering the *raw, unstripped* fence text as it
arrived (the cleanup only happens once, on the `completed` event), the net effect was: the raw
```` ```proposal ```` JSON block leaked into the visible transcript instead of being replaced by
the cleaned text, and the assistant's finished reply was dropped in favor of an error card.

Fixed by tracking a `postCompletionError` separately from a fatal `classifiedError`: an `error`
event arriving after `completed` no longer changes the outcome — the reply is finalized normally
(with its cleaned, fence-stripped content) and the error is surfaced as an *additional* banner,
not a replacement. Covered by
`tests/e2e/codirector/production-bible.spec.ts::"a malformed proposal fence surfaces a structured
error, never raw JSON"`.

---

## 4. Proposal lifecycle (`app/codirector/bible/proposals.py::ProposalService`)

### 4.1 States

```
pending ──approve──> executing ──(success)──> completed
   │                              └─(failure)──> failed
   ├──reject──────────────────────────────────> rejected
   ├──request-revision─────────────────────────> revision_requested ──(same transitions again)
   ├──cancel────────────────────────────────────> cancelled
   └──(Bible version changes underneath it)────> stale ──cancel only──> cancelled
```

- **Reviewable** (`pending`, `revision_requested`, `stale`): can be rejected/cancelled;
  `pending`/`revision_requested` can also be approved.
- **Terminal** (`rejected`, `completed`, `failed`, `cancelled`): cannot be acted on again.
- `stale` is reachable only from an approve *attempt* (see §4.3) — it is not a state a proposal
  starts in.

### 4.2 Approve → execute → receipt

`ProposalService.approve()`:

1. `completed` → `409 APPROVAL_ALREADY_RECORDED` (already applied; not re-appliable).
2. Not reviewable → `409 PROPOSAL_INVALID_STATE`.
3. **Staleness check** (§4.3) — may short-circuit with `409 PROPOSAL_STALE`.
4. Compute `input_hash = sha256(proposalId, basedOnVersionId, payload)`. If a `success` receipt
   with this exact hash already exists, return it instead of re-applying — idempotency defense
   for concurrent double-submission, distinct from the `APPROVAL_ALREADY_RECORDED` fast path
   above (which handles the common sequential "clicked twice" case).
5. Record the `approved` decision, flip status to `executing`, call
   `operations.apply_mutation_set()` (creating the Bible if this project didn't have one yet —
   a proposal can exist and later be approved before any Bible import/confirm happened).
6. On success: `CoDirectorExecutionReceipt(status="success", resultingVersionId=...)`, proposal →
   `completed`.
7. On failure: rolls back, records a `status="failed"` receipt with the exception message,
   proposal → `failed`, raises `502 EXECUTION_FAILED` (recoverable, `recommended_action: retry`).

### 4.3 Staleness

A proposal records `based_on_version_id` (the Bible's `current_version_id` at proposal-creation
time, or `null` if no Bible existed yet). If the Bible's current version has moved on by the time
someone tries to approve it (another proposal was approved first, or the user made a manual
edit), `_is_stale()` returns true:

- The proposal's status flips to `stale` (persisted, not just reported).
- Approval raises `409 PROPOSAL_STALE` with `recommended_action: "preview_again"`.
- A `stale` proposal can only be cancelled — the FE hides Approve/Reject/Request-Revision and
  shows a dedicated warning (`.codirector-proposal-stale`) plus a "Cancel proposal" action.

This is the concrete mechanism preventing the "two proposals land on an out-of-date Bible and
double-apply/conflict" failure mode.

### 4.4 Preview

`GET /proposals/{id}/preview` computes an entity-level diff (`add`/`remove`/`update` per entity
key) against the Bible's current version without applying anything — `ops.diff_entities()`
compares before/after entity sets built the same way `apply_mutation_set` would build them. Used
for showing "what would change" before the user commits to approving.

---

## 5. APIs (`/api/codirector/projects/{projectId}/proposals...`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/proposals?status=` | List, optionally filtered by status, newest first. |
| `POST` | `/proposals` | Manual/testing entry point (`proposal_type`, `title`, `summary`, `payload`). The normal path is the model's ```` ```proposal ```` fence — this exists for direct API/test use. |
| `GET` | `/proposals/{id}` | One proposal, with live-recomputed `isStale`. |
| `GET` | `/proposals/{id}/preview` | Entity/fact diff + staleness, without applying. |
| `POST` | `/proposals/{id}/approve` | → execution receipt (§4.2). |
| `POST` | `/proposals/{id}/reject` | → `rejected`. |
| `POST` | `/proposals/{id}/request-revision` | → `revision_requested` (still reviewable/approvable). |
| `POST` | `/proposals/{id}/cancel` | → `cancelled`. |
| `GET` | `/proposals/{id}/receipt` | Latest execution receipt. `404 RECEIPT_NOT_FOUND` before any approval attempt. |

All decision endpoints accept `{note?, decidedBy?}` and record a `CoDirectorApproval` audit row
regardless of outcome. A proposal fetched/listed for a `projectId` it doesn't belong to returns
`403 PROJECT_SCOPE_VIOLATION`.

---

## 6. SSE events (additive to the M1 union)

| Event | When |
|---|---|
| `context_manifest` | Once per turn, only if the project has a Bible (`bibleVersionId` present) — see `CODIRECTOR_PRODUCTION_BIBLE.md` §3. |
| `proposal_created` | After `completed`, only if the reply contained a valid proposal fence. |

`proposal_updated`, `approval_required`, `approval_recorded`, `execution_started/completed/failed`,
and `bible_version_created` are reserved in the FE's `CoDirectorStreamEvent` union
(`studio-web/src/api.ts`) for future real-time multi-client sync (e.g. a second reviewer's
approval showing up live) — M2.1's actual approve/reject/etc. flows are synchronous
request/response against the REST endpoints above, not currently pushed over SSE, since there is
exactly one reviewing user per session today.

---

## 7. Frontend: `CoDirectorProposalCard`

`studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx`, rendered inline in
`CoDirectorConversation` for every non-terminal proposal (`CoDirectorSession.tsx` filters to
`pending`/`revision_requested`/`stale`/`executing` — terminal proposals disappear from the
conversation view once resolved). Renders:

- A human-readable summary of the mutation set (`"character: Ava"`, `"Remove prop: Lantern"`,
  `"Fact: ..."`) — **never raw JSON**.
- Approve / Reject / Request Revision buttons with an optional note textarea, when reviewable and
  not stale.
- A stale warning + Cancel-only action when the proposal has gone stale.
- Busy-state disabling (`proposalActingId`) so a double-click can't fire two decisions.

---

## 8. Testing

- **Unit** (`studio-api/tests/test_production_bible.py`): proposal creation, list/filter,
  approve → new version + receipt, approve-twice → `APPROVAL_ALREADY_RECORDED`, reject, request-
  revision → still-approvable, cancel, 404/403 scoping, staleness detection + stale→cancel-only,
  preview diff, approve-before-Bible-exists, structured-output fence parsing (well-formed +
  malformed), chat/stream integration with both mock scenarios.
- **E2E** (`tests/e2e/codirector/production-bible.spec.ts`): approve creates a new Bible version
  (`@critical`) and the raw fence never reaches the DOM; reject leaves the Bible untouched;
  malformed fence surfaces a structured error while still finalizing the assistant's cleaned
  reply; a proposal that goes stale can only be cancelled, never approved.
