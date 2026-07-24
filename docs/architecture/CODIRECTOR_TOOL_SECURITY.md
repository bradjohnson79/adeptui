# Co-Director Tool Security Model

**Date:** 2026-07-24
**Scope:** the bounded tool registry delivered in Milestone 2.2.
**Companion to:** `docs/architecture/CODIRECTOR_TOOL_REGISTRY.md` (what the tools are),
`docs/architecture/CODIRECTOR_PROPOSALS_AND_APPROVALS.md` (the approval lifecycle).

This document states the threat model the registry is built against, and — more usefully — where
in the code each defence lives, so a reviewer can check that a change hasn't quietly removed one.

---

## 1. The one invariant

> **The model may propose. The model may never mutate.**

Everything below is in service of that sentence. It is worth being precise about *why* it holds
structurally rather than by convention:

1. **Read handlers have no write path.** They call read-only service functions and return dicts.
   There is no session commit in any read handler.
2. **Mutating handlers are split in two.** `preview()` computes a description and commits nothing;
   `apply()` writes. `preview` and `apply` are separate function references in the registry, so
   the proposal path physically cannot reach the write half.
3. **`apply()` has exactly one caller.** `ToolExecutionService.execute_approved_proposal`, which
   is called only from `ProposalService._approve_tool_proposal`, which runs only after a
   `CoDirectorApproval` decision row exists for a human `approve` action. There is no HTTP
   endpoint that executes a tool, and there is no auto-approval path or setting.

A reviewer checking a new tool should verify (1)–(3) hold for it. If a "read" tool needs to write
something, it is not a read tool.

---

## 2. Trust boundaries

```
   ┌── untrusted ──┐                ┌──────── trusted ────────┐
   │  model output │ → sanitize.py →│ registry → handlers → DB │
   └───────────────┘                └─────────────────────────┘
                                              │
   ┌── untrusted ──┐                          ↓
   │ handler result│ ← sanitize.py ← ─────────┘   → model transcript + browser
   └───────────────┘
```

Model output is treated as hostile input on the way in; handler results are treated as
potentially sensitive on the way out.

### 2.1 Inbound: what the model is allowed to say

The model contributes **two things only**: a tool id, and a bag of arguments. It does not
contribute a preview, a capability claim, a resource version, an idempotency key, a proposal
status, or a "this is safe to run now" flag — all of those are computed server-side and stored on
the proposal.

Specific attempts and what stops them:

| Attempt | Defence |
|---|---|
| Name a tool that doesn't exist | closed registry → `404 TOOL_NOT_FOUND` |
| Name a real tool with a hand-written handler path | there is no name→import resolution; only the bound table |
| Label a mutating tool as `read_tool_call` to force immediate execution | `extract_tool_block` derives the response type from the registry's declared `kind`, ignoring the model's claim |
| Pass an extra argument a handler might read | unknown keys are dropped in `sanitize_arguments`, never forwarded |
| Pass a 10 MB string, a negative index, an unlisted enum value | `maxLength` / `minimum` / `maximum` / `choices` enforced per parameter → `400 TOOL_ARGUMENTS_INVALID` |
| Pass a JSON array or string where an object belongs | non-object arguments rejected outright |
| Chain tools to do unbounded work from one message | `TOOL_LOOP_LIMIT = 1` → `409 TOOL_LOOP_LIMIT_REACHED` |
| Get a mutation applied by proposing it | proposing writes a pending row and nothing else |
| Have a stale proposal applied anyway | `baseResourceVersions` re-checked at approval → `409 PROPOSAL_STALE` |
| Replay a proposal for a second effect | `inputHash` + existing-successful-receipt check → the first receipt is returned again |

The stored `arguments` on a proposal are the **sanitized** ones. This matters at approval time: a
proposal approved a day later replays only values the registry would accept today, not whatever
the model originally typed.

### 2.2 Outbound: what leaves the server

`sanitize_result` runs on every tool result before it reaches the model's transcript, the SSE
stream, the invocation ledger, or the browser:

- **Secrets.** `redact_secrets` (shared with the rest of the Co-Director error path) removes
  API-key- and token-shaped substrings.
- **Absolute paths.** Windows (`C:\...`, `\\host\share`) and common POSIX roots are replaced with
  `<path>`. A model has no need for the operator's directory layout, and a leaked path is free
  reconnaissance in a screenshot or a pasted bug report.
- **Size.** Strings cap at 1200 chars, lists at 50 items, dicts at 60 keys, nesting at depth 6,
  and the whole payload at the tool's declared character budget. Over-budget payloads shed whole
  top-level keys largest-first and are flagged `_truncated` with `_omittedFields`, so the model is
  never handed a partial answer that looks complete.

Result truncation is a *disclosed* degradation: it emits `tool_result_truncated` and the model is
told in-band that the result was shortened.

---

## 3. Failing closed

Anything that could turn an unknown into an assumption fails closed:

| Situation | Behaviour |
|---|---|
| A capability probe raises | that capability is `unavailable` with a short reason; no exception escapes into the turn |
| A capability probe hangs | 6-second timeout, then `unavailable` |
| A required capability is unavailable | the tool does not run; `CAPABILITY_UNAVAILABLE` (503) or `CAPABILITY_NOT_CONFIGURED` (409); a `blocked` ledger row is still written |
| A stored proposal payload no longer parses | the proposal is treated as stale; cancel is the only remaining action |
| `toolSchemaVersion` on a stored payload doesn't match the running server | `409 TOOL_SCHEMA_VERSION_MISMATCH` rather than best-effort replay |
| A handler raises during `apply()` | `502 TOOL_EXECUTION_FAILED`, a `failed` receipt, a `failed` ledger row, proposal left non-terminal, nothing written |
| The registry is internally inconsistent | `RuntimeError` at **import** time, so the app doesn't start rather than failing mid-turn |

A blocked capability is deliberately *not* a failed turn: the user gets an answer that says what
couldn't be checked. Silently pretending the check passed would be the security-relevant failure
here; refusing to answer at all would just push users to work around Co-Director.

---

## 4. Error surface

`TOOL_*` and `CAPABILITY_*` codes live in `codirector/errors.py` with explicit HTTP mappings, so a
tool failure is machine-classifiable by the frontend instead of a generic 500:

| Code | HTTP | Meaning |
|---|---|---|
| `TOOL_NOT_FOUND` | 404 | not in the closed registry |
| `TOOL_DISABLED` | 403 | declared but switched off |
| `TOOL_KIND_MISMATCH` | 400 | read endpoint asked for a mutating tool, or vice versa |
| `TOOL_ARGUMENTS_INVALID` | 400 | failed schema validation (names the parameter) |
| `TOOL_TARGET_NOT_FOUND` | 404 | the scene/entity the tool targets is gone |
| `TOOL_EXECUTION_FAILED` | 502 | handler raised; nothing was written |
| `TOOL_RESULT_TOO_LARGE` | 502 | result unusable even after shedding |
| `TOOL_LOOP_LIMIT_REACHED` | 409 | more than one read tool in a turn |
| `TOOL_SCHEMA_VERSION_MISMATCH` | 409 | stored payload predates a schema change |
| `TOOL_PAYLOAD_INVALID` | 502 | stored payload is unreadable |
| `CAPABILITY_NOT_CONFIGURED` | 409 | never set up → `configure_capability` |
| `CAPABILITY_UNAVAILABLE` | 503 | set up but unhealthy → `retry_or_check_service` |
| `CAPABILITY_UNKNOWN` | 400 | unknown capability key requested |

502 rather than 500 for handler failures is intentional: the failure is in a downstream
dependency the tool called, and the distinction drives different frontend copy and retry
behaviour.

---

## 5. Auditability

Every attempt — succeeded, failed, **or blocked** — writes a `codirector_tool_invocations` row.
The blocked case is the one that makes the ledger genuinely useful for review: "what was
Co-Director prevented from doing, and why" is answerable from the database, without log
correlation.

Each row carries the tool and schema version, kind, status, sanitized arguments, sanitized result
and its hash, whether it was truncated, the capability snapshot at the time, error code and
message, the owning proposal id for mutations, request id, duration, and the actor. Mutating
tools additionally leave the M2.1 audit trail intact: a `CoDirectorApproval` decision row and an
execution receipt, and — for `record_director_decision` — an immutable Bible version.

The ledger is exposed read-only at `GET /api/codirector/projects/{id}/tool-invocations`.

---

## 6. Deliberate non-capabilities

These are absent by design, not yet-to-be-built. Adding any of them reopens this document:

- shell / process execution
- filesystem read or write
- raw SQL or arbitrary ORM access
- network fetch of arbitrary URLs
- dynamic or plugin tool registration; tools defined in config, packs, or prompts
- auto-approval, "trusted tool" allowlists, or remembered approvals
- multi-step task graphs or autonomous chains
- render queueing (`queue_render`) and reference attach/remove — both were considered and
  excluded for M2.2 because they start long-running or externally-visible work, which needs its
  own cancellation and progress story before it can sit behind a one-click approval
- a full Production Systems Readiness matrix (the `CapabilityAdapter` is a thin read over
  existing probes and nothing more)

---

## 7. Review checklist for a new tool

1. Is it declared in `definitions.py` **and** bound in `registry.py`? (If not, the app won't
   start — that's the intended feedback.)
2. Read tool: does the handler touch no write path, and commit nothing?
3. Mutating tool: is the write confined to `apply()`? Does `preview()` describe the change in
   terms the user can actually evaluate?
4. Does it pin the right resources in `baseResourceVersions`, and does the fingerprint exclude
   fields that change for unrelated reasons?
5. Does its capability key correspond to a real probe, and does a missing dependency block it
   rather than crash it?
6. Is its `char_budget` sane for the largest realistic result?
7. Are there tests for the blocked path and the failure path, not just the happy path?
