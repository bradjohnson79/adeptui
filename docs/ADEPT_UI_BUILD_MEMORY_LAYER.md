# Adept UI Build Memory Layer — Permanent Build Laws

**Status:** Standing instructions for Cursor, Grok, primary agents, and all subagents on every milestone.  
**Cursor rules:** `.cursor/rules/adept-ui-build-laws.mdc`, `.cursor/rules/beta-refresh-after-build.mdc` (`alwaysApply: true`)

These laws are the permanent foundation. A change that violates them is incomplete regardless of local code edits.

---

## Law 1 — Beta Server Must Reflect the Completed Work

Every UI, workflow, API, configuration, or integration change must be applied to the active Beta development environment before the task is considered complete.

The agent must:

* start or restart the correct Beta services
* verify the correct branch and build are running
* confirm the updated UI is visible at the expected localhost address
* clear stale build caches when necessary
* report the exact Beta URL
* leave the Beta environment ready for manual review

A change that exists only in source code, tests, or screenshots is not complete.

---

## Law 2 — Every Task Ends With One Unified Completion Report

Every completed task must produce one authoritative Markdown report including:

* task and milestone name
* branch and starting SHA
* final SHA
* objective
* scope completed
* architecture and implementation summary
* files created or changed
* database or schema changes
* API and UI wiring
* tests executed and results
* failures encountered
* repairs and corrections made
* Beta server verification
* screenshots and artifact locations
* known limitations
* deferred items
* final verdict

Supporting reports may exist; the unified report is the primary source of truth.

---

## Law 3 — Never Abandon a Failed State

A failed test, broken build, runtime exception, incomplete migration, disconnected control, missing asset, or invalid workflow must be investigated and repaired:

1. identify the root cause  
2. repair the failure  
3. rerun the affected validation  
4. run regression checks around the repaired area  
5. document the original failure and final correction  

A failed state may remain only when the primary user explicitly instructs the agent to stop, preserve it for investigation, or defer the repair.

Failure must never be hidden, renamed as a warning, or excluded from the final report to obtain a GO verdict.

---

## Law 4 — Subagents Must Double-Check Their Work

Every implementation subagent must complete an internal second-pass review before returning.

Verify: owned scope complete; file boundaries respected; contracts followed; code compiles; tests pass; no mocks/placeholders as production; real integrations; error/recovery paths; no unrelated damage; evidence produced.

A subagent may report only:

```text
READY FOR PRIMARY REVIEW
```

It may never issue the final milestone GO. The primary agent must independently inspect and integrate all subagent work.

---

## Law 5 — Every Task Must Be Full-Stack and End-to-End

Where applicable, completion must cover:

```text
UI
→ client state
→ API contract
→ authentication and authorization
→ service layer
→ provider or runtime
→ persistence
→ asset registration
→ project library
→ Timeline or consuming subsystem
→ reload and recovery
→ user-visible result
```

Frontend-only demonstrations do not count as completion.

---

## Law 6 — Preserve Working Systems

Never rewrite, remove, rename, or replace an existing working system merely to simplify implementation.

Before modifying shared infrastructure, determine dependents, contract compatibility, regressions, and migration needs. Existing functionality must remain operational unless removal was explicitly approved.

---

## Law 7 — No Mock Completion

Mocks, fixtures, static JSON, fake progress, sample assets, simulated API responses, and hardcoded success states may be used only in explicitly designated test environments. They may never be presented as production evidence.

The following do not prove completion: UI cards alone, fixtures resembling output, mocked providers, manually copied assets, hardcoded GO flags, screenshots without runtime evidence.

Production certification requires real execution.

---

## Law 8 — No Silent Behavior

The system must never silently: switch providers; downgrade quality; use a fallback model; approve an asset; mutate a project; replace a Timeline clip; discard a failed attempt; change user settings; retry a chargeable operation; expose another project's assets.

Material changes require transparent user-visible status and, where appropriate, approval.

---

## Law 9 — Every Control Must Be Wired

Every visible button, menu item, form control, accordion, command, keyboard shortcut, and Co-Director tool must have a verified purpose and real behavior. No dead controls in production-facing UI.

```text
interaction → handler → validation → backend → success → error → persisted result
```

Disabled or future controls must be clearly labelled and must not imply missing functionality.

---

## Law 10 — Persistence Must Survive Reloads

Anything described as saved, approved, generated, selected, configured, added to a library, or placed on a Timeline must survive browser refresh, workspace/project reopen, server restart where appropriate, and navigation away/return. In-memory state alone is insufficient.

---

## Law 11 — Every Feature Needs Failure Recovery

Production workflows must handle: timeouts; cancellation; partial output; unavailable providers; invalid credentials; malformed responses; failed persistence; failed asset registration; failed Timeline placement; expired sessions; network interruption; application restart.

Failures must preserve useful evidence and offer a safe retry, repair, rollback, or alternative path.

---

## Law 12 — Tests Must Prove the User Workflow

Include the appropriate combination of unit, contract, API, integration, persistence, security, regression, Playwright E2E, and manual UX verification. Tests must exercise the creator workflow. A passing suite does not replace manual UX review when the milestone includes a human usability gate.

---

## Law 13 — Repair Requires Regression Testing

When a defect is corrected: add/update a detecting test; rerun the failed test; rerun surrounding subsystem tests; verify Beta UI; document regression protection. Repair without regression coverage is incomplete unless testing is impossible and the limitation is reported.

---

## Law 14 — Security and Project Isolation Are Mandatory

Every project-aware operation must verify authenticated user, project membership, role/permission, ownership boundaries, locked-project state, asset access boundaries, and mutation authorization.

Cross-project leakage, unauthorized mutation, exposed provider keys, insecure file paths, or client-trusted authorization → automatic **NO-GO**.

---

## Law 15 — Credentials Never Enter Source Code

API keys, tokens, passwords, private URLs, signing secrets, and provider credentials must never be hardcoded, committed, written into reports, displayed in screenshots, logged without redaction, or passed to browser code unnecessarily. Use the established secrets/env system; document only variable names and setup requirements.

---

## Law 16 — Shared Contracts Are Frozen Before Parallel Work

Before multiple subagents implement connected systems, the primary agent must freeze and publish shared contracts.

Contract changes require:

```text
change request → impact analysis → primary-agent approval → contract update
→ dependent-agent notification → affected test updates
```

Subagents may not independently redefine shared models, event formats, API payloads, statuses, or persistence structures.

---

## Law 17 — Respect File and Scope Ownership

Every agent/subagent must have owned scope, allowed/forbidden files, required inputs/outputs, dependencies, tests owned, and escalation conditions. Out-of-scope edits must be rejected or escalated. Uncoordinated edits to shared files are prohibited.

---

## Law 18 — One Source of Truth

Every production concept has one authoritative source (examples: Timeline state → Preview; DB → persisted assets; production gate → certification; provider registry → capabilities; shared contracts → payloads; unified completion report → milestone history). The UI must not maintain a competing fictional state.

---

## Law 19 — No Hidden Debt at Completion

Before declaring completion, search for and report: TODO, FIXME, temporary, placeholder, stub, mock, hardcoded, bypass, deprecated, unfinished, later, disabled validation.

Relevant remaining instances must be repaired, justified, or explicitly listed as unresolved. Unreported technical debt invalidates certification.

---

## Law 20 — Honest Capability Labels

Label models/providers/runtimes/features only as:

```text
Certified | Testing | Available | Unavailable | Unsupported | Requires Setup
```

Do not advertise readiness that runtime evidence does not support.

---

## Law 21 — Build and Migration Safety

Verify: clean production build; frontend type checking; backend import/startup; migration integrity and upgrade path; rollback/recovery; compatibility with existing data; no destructive migration without approval.

A feature that only works on a fresh database is not production-ready unless that limitation is intentional and approved.

---

## Law 22 — Manual Review Must Be Possible

Leave the app ready for immediate manual review: correct services running; required models/providers identified; sample project/path available; no hidden setup; clear review instructions; exact pages/workflows; secrets referenced safely; known limitations disclosed.

---

## Law 23 — Evidence Before Verdict

A GO verdict must be derived from evidence (command outputs, tests, API responses, artifacts, persistence, provider/model metadata, screenshots, Playwright traces, Beta verification, independent reviews). Never write the verdict first and justify afterward.

---

## Law 24 — Binary Certification

Every milestone ends in **GO** or **NO-GO**.

“Conditional GO,” “mostly complete,” “implementation complete except,” or similar language must not be used for final production certification. A milestone with an outstanding required gate is **NO-GO** (implementation layers may still be recorded as passed separately).

---

## Law 25 — Primary Agent Owns Final Integration

The primary agent remains responsible for architecture, contract authority, subagent dispatch, conflict resolution, integration, defect repair, Beta deployment, end-to-end execution, artifact verification, final report, and final verdict.

Subagent success does not equal milestone success.

---

## Law 26 — GPU-First Execution, Accelerator Verification, and No Silent CPU Fallback

Any workload designed or expected to use GPU acceleration must verify GPU readiness before execution.

The agent must check:

* compatible GPU detected
* correct GPU selected
* CUDA or required accelerator available
* GPU-enabled framework installed
* runtime and worker use the intended environment
* model and tensors are placed on the GPU
* sufficient VRAM is available
* no incompatible `cpu_offload` or CPU-only configuration is active
* the running process produces observable GPU utilization

Required execution order:

```text
GPU readiness check
→ GPU execution attempt
→ runtime verification
→ only then consider CPU fallback
```

The system must never silently bypass the GPU and continue on CPU.

CPU fallback is allowed only when:

* GPU execution is unavailable or fails,
* the failure is clearly reported,
* the estimated CPU performance impact is disclosed,
* the user explicitly approves the fallback,
* the fallback is recorded in job provenance and the completion report.

For long-running or production workloads, CPU fallback should default to **blocked**, not automatic.

### Required runtime evidence

For GPU-designated jobs, completion evidence must include:

* selected device
* framework build
* CUDA/accelerator availability
* GPU model
* GPU process
* VRAM usage
* GPU utilization
* execution duration
* fallback status

Example:

```text
Execution device: cuda:0
GPU: NVIDIA GeForce RTX 5090
PyTorch: CUDA-enabled cu128
GPU utilization observed: true
CPU fallback used: false
```

### Failure behavior

If the environment contains CPU-only PyTorch, an incorrect virtual environment, unavailable CUDA, or a worker configured for CPU execution, the job must stop with a clear diagnostic such as:

```text
GPU acceleration was requested, but the active worker is using
CPU-only PyTorch. Generation has been stopped to prevent an
unexpected CPU execution path.
```

The agent must then repair the environment, restart the affected worker, rerun the job, and document the correction.

---

## Law 29 — Product Abstraction

Adept UI is the product. Underlying runtimes (ComfyUI, Ollama, MiniMax, Babylon, and similar) are implementation details.

During normal product operation, creators must never be required to directly launch, configure, debug, or operate underlying runtimes.

Adept UI is responsible for:

* runtime discovery
* startup
* readiness checks
* automatic recovery
* reconnect
* reuse
* controlled shutdown

Creator workflows begin and end inside Adept UI.

---

## Law 30 — Documentation Canon

At any time there must be exactly one governing document for each product milestone. Historical reports remain historical. Superseded reports must be clearly marked.

Implementers may not cite superseded reports as current truth. Primary agents must reconcile conflicting documentation before requesting review.

---

## Law 31 — Evidence Before Completion

No capability is complete because code exists.

Completion requires:

* implementation
* integration
* Playwright certification
* evidence artifacts
* independent verification
* binary GO

Missing evidence equals **NO-GO**.

---

## Law 32 — Co-Director Intelligence

Co-Director must improve through evidence-backed experience. Conversation history alone is not intelligence.

Learning must be:

* transparent
* reviewable
* versioned
* creator-controlled
* reversible
* project-isolated
* independently certifiable

No learning may silently alter creator projects.

---

## Permanent Completion Checklist

```text
[ ] Correct branch and starting SHA verified
[ ] Shared contracts preserved or intentionally updated
[ ] Full-stack implementation completed
[ ] Every visible control wired
[ ] Real runtime used; no mock completion
[ ] Persistence verified after reload
[ ] Error, cancellation, retry, and recovery paths verified
[ ] Authentication, authorization, and project isolation verified
[ ] Unit/API/integration/regression tests passed
[ ] Playwright creator workflow passed where applicable
[ ] All failures repaired and documented
[ ] Subagents completed second-pass reviews
[ ] Primary agent independently reviewed integration
[ ] Production build passed
[ ] Beta dev server updated and running
[ ] Manual review path documented
[ ] Screenshots and evidence artifacts saved
[ ] Unified Markdown completion report created
[ ] Remaining limitations honestly documented
[ ] Final verdict issued as GO or NO-GO
[ ] GPU-designated workload performed accelerator preflight
[ ] Active environment contains GPU-enabled dependencies
[ ] Worker selected the intended GPU device
[ ] Model and tensors were verified on GPU
[ ] Live GPU utilization and VRAM usage were observed
[ ] CPU fallback did not occur silently
[ ] Any fallback received explicit user approval
[ ] Execution device and fallback status were saved in provenance
[ ] Creator workflows remain inside Adept UI; runtimes not exposed to creators (Law 29)
[ ] One governing document per milestone; superseded reports marked (Law 30)
[ ] Capability completion evidenced: Playwright, artifacts, independent verification (Law 31)
[ ] Co-Director learning transparent, reviewable, creator-controlled, project-isolated (Law 32)
```
