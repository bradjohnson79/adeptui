# Co-Director "Production Brain" — M2/M3 Vision

**Date:** 2026-07-24
**Related:** `docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md` (M1, implemented),
`docs/audit/CODIRECTOR_PROVIDER_RELIABILITY_REPORT.md`
**Status:** Vision, partially superseded. Two sections have since been implemented and carry
status notes pointing at their as-built docs — Production Bible (M2.1) and Tool calling +
approvals (M2.1 + M2.2). Everything else remains future work and should **not** be read as a
description of current behavior.

---

## Why this document exists

Milestone 1 (reliability runtime — see the implementation plan) made Co-Director chat
trustworthy: structured errors, streaming, cancel, retry, and server-side persistence. It
deliberately stopped there. Co-Director is not yet a *co-director* — it's a reliable chat
box in front of a local model. This document sketches where the "Production Brain" work
picks up, so future milestones have a shared target without re-litigating M1's boundaries.

**None of this is scheduled. None of it should be started opportunistically inside an M1
bugfix.** It exists so M1's gateway/event/persistence seams (provider interface, SSE event
schema, conversation store) are designed with these future needs in mind, not so that they
get built now.

---

## M2 candidate: Production Bible (project knowledge grounding) — ✅ implemented in M2.1

**Status update (2026-07-24):** implemented as described below, plus the approvals mechanism
sketched in "Tool calling + approvals" further down (scoped to Bible mutations only, not a
general tool registry). See `CODIRECTOR_PRODUCTION_BIBLE.md` and
`CODIRECTOR_PROPOSALS_AND_APPROVALS.md` for the as-built design. The rest of this section is
left as originally written for historical context.

**Problem:** Co-Director currently only sees the literal chat transcript plus whatever
`project_id`/`scene_id` context is passed in. It doesn't know the project's established
characters, locations, visual style, prior scene outcomes, or continuity constraints unless
the user repeats them every time.

**Shape of the solution:**

- A per-project "Bible" document (structured, not free text) covering characters, locations,
  visual/style anchors, running continuity facts, and open narrative threads.
- Read path: injected into the `chat_for_project` / `stream_for_project` context block
  (the same place `mode` nudges and learning-preferences injection already live in
  `service.py`) as a bounded, summarized excerpt — not the whole document, to keep prompts
  small and providers cheap.
- Write path: **not automatic**. Bible updates should go through an explicit
  propose/approve step (see "Approvals" below), not be silently inferred from every chat
  message — silent inference is how continuity drifts.
- Storage: a new table, project-scoped, versioned (so "what did the Bible say when scene 4
  was generated" is answerable later for the continuity engine).

**Depends on M1:** the conversation persistence table's shape (project-scoped, JSON blob)
is a reasonable template; the Bible would likely be its own table for the same reasons
(need independent versioning/diffing, not just "another message").

---

## M2 candidate: Orchestrator / task graph

**Problem:** Today, "wants a plan" is a regex heuristic in `CoDirectorSession.send()` that
locally synthesizes an `ActionPlan` from `planFromIntention()` — there's no real task graph,
no dependency tracking between steps, and no way for Co-Director itself (vs. the FE
heuristic) to decide a request needs multiple coordinated actions.

**Shape of the solution:**

- A task graph: nodes are discrete actions (generate scene prompt, run storyboard panel,
  queue a render), edges are dependencies. Distinct from a chat turn — one chat turn might
  produce a task graph with several nodes.
- An orchestrator service that walks the graph, dispatching each node to the right existing
  subsystem (imagegen, director timeline, editor sequences, etc.) and reporting progress back
  over the same SSE channel M1 built for chat streaming (new event types, e.g.
  `task_started` / `task_progress` / `task_completed`, additive to the existing union).
- Retry/cancel semantics at the *task* level, reusing the same cancellation registry pattern
  (`_active_tasks` in `service.py`) already built for chat requests in M1.

**Depends on M1:** the request-cancellation registry and SSE event-streaming plumbing are
directly reusable — this is the main reason M1's event schema was designed as an open union
rather than a fixed enum.

---

## M2/M3 candidate: Tool calling + approvals — ✅ implemented in M2.1 + M2.2

**Status update (2026-07-24):** both halves now exist. M2.1 delivered the *approvals* half, scoped
narrowly to Bible mutations (`CODIRECTOR_PROPOSALS_AND_APPROVALS.md`). M2.2 delivered the *tools*
half as a **bounded registry** (`CODIRECTOR_TOOL_REGISTRY.md`,
`CODIRECTOR_TOOL_SECURITY.md`): 15 read tools that run inline within a turn, and 4 mutating tools
(`create_scene`, `update_scene_title`, `set_scene_prompt`, `record_director_decision`) that can only
reach a write through a `tool_call` proposal the user approves.

Two things were deliberately built more narrowly than sketched below, and should be read as
decisions rather than omissions:

- **The registry is closed, not open.** Tools are declared as data and bound to handlers in code;
  there is no plugin surface, no config-defined tool, and no shell/filesystem/SQL escape hatch. The
  "MCP-ish" framing below is not the direction taken.
- **A turn is capped at one read tool plus one follow-up completion.** The autonomous multi-step
  chaining implied below is still future work and needs the orchestrator/task-graph section, plus a
  cancellation and progress story, before it would be safe.

`queue_render` and reference attach/remove — both named below — were considered for M2.2 and
excluded: they start long-running or externally-visible work, which needs its own progress and
cancellation semantics before it can sit behind a one-click approval.

The rest of this section is left as originally written for historical context.

**The capability API is the truth source for M2.2 (added 2026-07-24, Production Systems
Readiness branch).** A tool registry needs to know which actions are actually safe to offer, and
that question now has exactly one server-side answer: `GET /api/capabilities`. Do not re-derive it
in the tool layer, and do not maintain a parallel list of "tools we think work."

Read `docs/audit/ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md` before building the registry. Its
§10 states the six binding rules; the short version:

- Only expose a tool whose capability appears in `callable`. A capability that is `blocked` must
  not be offered — the model should never propose an action that is guaranteed to fail.
- Use `requiresApproval` to decide whether a human must confirm, not the HTTP verb.
- Use `readOnly` to decide what may run without a proposal.
- When refusing, surface `reasonCode` and `recommendedAction` verbatim. "I can't queue a render
  because ComfyUI isn't running — start ComfyUI and refresh" is useful; "an error occurred" is not.
- Re-read the snapshot every turn. ComfyUI can stop mid-session; cached readiness lies.
- `serviceRef` names the existing application service or router function to call. The tool
  registry must call paths that already exist rather than adding new write paths.

As of that branch, 35 capabilities are callable, including the scene write set
(`project.scenes.create` / `update` / `delete`, all `requiresApproval: true`) backed by
`app/services/scene_service.py`. `codirector.tools` itself is registered as `not_implemented`, and
implementing it is exactly the M2.2 scope. Full inventory and honest blockers:
`docs/audit/ADEPT_PRODUCTION_SYSTEMS_READINESS_REPORT.md`.

**Problem:** Co-Director can talk about scenes but can't *act* on the project (create a
scene, attach a reference, queue a render) without the user manually doing it after reading
the reply.

**Shape of the solution:**

- A small, explicit tool registry (not open-ended code execution) — e.g. `create_scene`,
  `set_scene_prompt`, `attach_reference`, `queue_render` — each with a JSON schema and a
  server-side handler that calls the existing project/scene APIs directly (no new write
  paths, just a model-driven caller of paths that already exist).
- **Approvals are mandatory, not optional**, for any mutating tool call: the model proposes
  a call, the FE renders a diff/preview, the user approves or rejects, only then does the
  handler run. This mirrors the existing `ActionPlan` / `selectedSteps` approve-then-run
  pattern in `CoDirectorSession.tsx` (see `runSteps`), which was intentionally kept as
  local FE logic in M1 rather than promoted to a real tool-calling loop.
- Reuses M1's structured-error contract: a failed tool call should classify exactly like a
  failed chat turn (never a bare error string), and should be cancellable/retryable using
  the same primitives.

---

## M3 candidate: Prompt compilers

**Problem:** `mode` (`chat` / `prompt` / `guide` / `setup`) is a blunt instrument — a single
string that nudges the system prompt. There's no structured compilation from "what the user
wants" to "the exact prompt string a specific video/image model needs," despite the
knowledgebase (`studio-api/knowledgebase/generation/**`) already containing per-model prompt
language guidance.

**Shape of the solution:**

- A compiler step between "user intent" and "final generation prompt" that consults the
  relevant `knowledgebase/generation/video_models/{model}/*.md` guidance (already present in
  the repo) and the project's spatial/continuity context to produce a model-specific prompt,
  rather than relying on the base model to have absorbed that guidance implicitly.
- This is downstream of the Bible (needs character/location/style anchors) and likely
  downstream of the task graph (a "generate this shot" task node would invoke the compiler
  as one of its steps).

---

## M3 candidate: Asset lineage

**Problem:** Once an asset (image, video clip, audio) is generated, there's no structured
record of *what produced it* — which prompt, which model, which scene/task, which Bible
version was active. Continuity checking and "regenerate with a small change" workflows both
need this.

**Shape of the solution:**

- A lineage record per asset: source task/tool-call id, compiled prompt, model/provider,
  Bible version (if Bible exists by then), timestamp.
- Purely additive metadata — does not require changing how assets are generated, just how
  their provenance is recorded.

---

## M3 candidate: Continuity engine

**Problem:** Nothing currently checks a new scene/asset against established facts (a
character's established appearance, a location's established layout, a prop introduced two
scenes ago). This is the highest-value and highest-risk piece — false positives would be
extremely annoying — so it's explicitly last.

**Shape of the solution:**

- Reads the Bible + asset lineage to check new generation requests for contradictions before
  they're sent to a provider, surfacing a *warning* (not a hard block) with a Bible citation.
- Should be optional/dismissible per the same "recoverable" error-taxonomy pattern M1
  established — a continuity warning is not a failure, it's advisory.

---

## What M1 deliberately left as extension points for this work

- **SSE event union is open**, not a closed enum — new `type` values (task/tool events) can
  be added without touching the parsing logic in `api.codirectorChatStream`.
- **`chat_for_project` / `stream_for_project` context-building is centralized** in
  `service.py` — Bible injection has one place to plug in, not N call sites.
- **The cancellation registry is generic** (`request_id` → `asyncio.Task`), not chat-specific
  — task-graph node cancellation can reuse it directly.
- **The error taxonomy (`CoDirectorError` / `classifyCoDirectorError`) is provider- and
  domain-agnostic** — tool-call failures, Bible-write failures, and continuity warnings can
  all flow through the same `{code, message, recoverable, recommendedAction}` shape the FE
  already knows how to render.
