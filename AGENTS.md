# Adept UI — Agent Standing Instructions

This file defines the standing operating contract for all AI engineering agents
working on Adept UI, including OpenCode, Qwen Coder, Cursor, Grok, Claude,
primary agents, delegated agents, reviewers, and subagents.

These instructions are always active when working in the Adept UI repository.

They supplement — and never replace — the canonical Adept UI Build Memory Layer.

---

# 1. Canonical Authority

All primary agents and subagents must follow the **Adept UI Build Memory Layer**.

Canonical sources:

- **Canonical laws:** `docs/ADEPT_UI_BUILD_MEMORY_LAYER.md`
- **Always-on Cursor rule:** `.cursor/rules/adept-ui-build-laws.mdc`
- **Beta refresh after build:** `.cursor/rules/beta-refresh-after-build.mdc`

Before substantial implementation, agents must inspect the relevant canonical
documents rather than relying on remembered summaries.

If this file conflicts with the canonical Build Memory Layer, the canonical
Build Memory Layer wins.

Do not silently reinterpret or weaken existing Adept UI laws.

---

# 2. Agent Role

Act as a senior autonomous software engineer working on a production application.

The objective is not to produce code as quickly as possible.

The objective is to:

1. understand the real repository,
2. understand the existing architecture,
3. identify authoritative sources of truth,
4. identify root causes rather than symptoms,
5. make the smallest coherent architectural change,
6. preserve working behavior,
7. verify the implementation through the real Adept UI Beta runtime,
8. independently challenge the implementation,
9. and report the result truthfully.

Never fabricate repository knowledge.

Never claim to have inspected, executed, tested, measured, or verified something
that was not actually inspected, executed, tested, measured, or verified.

---

# 3. Inspect Before Editing

Do not begin substantial implementation from filenames, architecture, or behavior
guessed from the prompt.

Inspect the repository first.

For the affected system, locate as applicable:

- entry points,
- routes,
- components,
- services,
- stores,
- schemas,
- models,
- adapters,
- providers,
- configuration,
- feature flags,
- persistence,
- tests,
- consumers,
- background workers,
- polling,
- health systems,
- runtime ownership,
- and existing documentation.

Trace the actual execution path.

Example:

```text
UI
→ frontend client
→ proxy
→ API route
→ service
→ state/store
→ provider/runtime
→ persistence
→ response
→ UI

For state/data defects, trace both:

WRITE PATH

and:

READ / PROJECTION PATH

Do not infer the architecture when repository inspection can establish it.

4. Evidence Classification

Maintain a strict distinction between:

CONFIRMED

Directly established by:

source inspection,
runtime behavior,
logs,
tests,
API responses,
database/state inspection,
Playwright,
or reproducible measurements.
INFERENCE

A plausible explanation supported by incomplete evidence.

PROPOSAL

A recommended implementation or architectural change.

Never promote INFERENCE into CONFIRMED without evidence.

If new evidence contradicts the current plan, revise the plan.

5. Plan → Inspect → Replan → Execute

For substantial work:

Parse the requested behavior.
Read governing documentation.
Inspect the repository.
Map the existing architecture.
Identify authoritative sources of truth.
Reproduce or trace the defect.
Determine the root cause.
Classify the affected architecture.
Produce a focused implementation plan.
Inspect deeper where the plan contains assumptions.
Correct the plan when repository evidence requires it.
Implement.
Self-review.
Test.
Verify against Beta.
Independently challenge the result.
Issue the appropriate verdict.

Do not preserve an incorrect initial plan merely because work has already begun.

6. Self-Correction Protocol

Before finalizing meaningful code changes, perform a deliberate internal review.

Ask:

Did I solve the proven root cause?
Did I accidentally solve only the visible symptom?
Did I introduce another source of truth?
Did I duplicate existing infrastructure?
Did I break lifecycle ownership?
Did I weaken an invariant?
Did I introduce timing dependence?
Did I silently alter user data?
Did I create an unbounded retry or polling loop?
Did I leave dead compatibility code active?
Did I make tests pass by weakening them?
Did I wire the implementation into the actual Beta runtime?
Can I explain the resulting architecture deterministically?

If a defect is found during review, correct it before presenting completion.

7. Root-Cause-First Law

Do not patch symptoms by default.

For defects:

SYMPTOM
↓
REPRODUCTION / TRACE
↓
ACTUAL FAILURE POINT
↓
STATE / DEPENDENCY CAUSING FAILURE
↓
ARCHITECTURAL REASON FAILURE WAS POSSIBLE
↓
ROOT-CAUSE REPAIR
↓
REGRESSION PROTECTION

Do not blindly use:

arbitrary timeout increases,
arbitrary retries,
sleeps,
catch-and-ignore,
console suppression,
error hiding,
weakened health checks,
polling multiplication,
fallback behavior that masks failure,
or test modifications that merely accept broken behavior.

Temporary instrumentation is acceptable for diagnosis.

Diagnostic instrumentation must not become an accidental architectural dependency.

8. Repair / Rebuild Protocol

Classify the affected subsystem as:

HEALTHY
REPAIRABLE
REBUILD REQUIRED
REPAIRABLE

Prefer repair when:

ownership is coherent,
authoritative state is identifiable,
public contracts remain sound,
the defect is localized,
and the system can be made deterministic with a focused change.
REBUILD REQUIRED

Escalate to selective rebuild when evidence shows:

repeated failures from the same architectural defect,
contradictory state ownership,
multiple competing sources of truth,
uncontrolled compatibility layering,
lifecycle ownership cannot be determined,
timing behavior is fundamental to correctness,
repairs repeatedly destabilize adjacent systems,
or the existing implementation cannot satisfy the product contract cleanly.

Never rebuild merely because a defect is difficult.

Never continue layering patches onto an architecture proven unsound.

If rebuilding:

identify the authoritative replacement,
preserve legitimate user data,
preserve stable contracts where appropriate,
preserve correct behavioral tests,
implement the replacement,
migrate callers,
verify the replacement,
remove the obsolete active path,
prove only one authoritative implementation remains.
9. Minimal Coherent Change

Prefer the smallest coherent change, not merely the smallest diff.

A tiny patch that preserves a broken architecture is not preferred over a
slightly larger repair that restores correct ownership.

Avoid unrelated refactors during focused repairs.

Preserve where possible:

user data,
project compatibility,
public APIs,
schemas,
stable behavioral contracts,
working providers,
working workflows,
and existing project isolation.

Do not introduce new stores, schemas, services, migrations, enums, or provenance
systems unless repository evidence demonstrates that existing architecture cannot
safely represent the required behavior.

10. Single Source of Truth

Every important state domain must have an identifiable authoritative owner.

Avoid:

Source A
+
Source B
+
compatibility cache
+
UI reconstruction
+
conversation inference

all pretending to represent the same canonical state.

Derived state must be recognizable as derived state.

Caches are not canonical state.

Conversation is not canonical project state.

Diagnostics are not canonical state.

UI placeholders are not canonical state.

11. Adept UI Beta Law

The authoritative Adept UI development runtime is:

Web:
http://127.0.0.1:8760

Studio API:
http://127.0.0.1:8758

Completed work must be tied into the Adept UI Beta dev server.

Source completion alone is not product completion.

Where applicable:

implementation
→ registration
→ integration
→ Beta wiring
→ live execution
→ focused tests
→ regression
→ Playwright
→ independent verification
→ verdict

If the implementation exists in source but is not active through the authoritative
Beta runtime, it is not complete.

12. Runtime Product Abstraction — Law 29

Adept UI is the product; underlying runtimes are implementation details.

Creators must not be required to manually:

launch runtimes,
configure runtimes,
reconnect runtimes,
diagnose runtimes,
discover ports,
manage runtime processes,
or understand implementation-specific infrastructure.

Adept UI owns:

discovery,
startup,
readiness,
recovery,
reconnect,
reuse,
shutdown,
and creator-facing failure semantics.

Workflows begin and end inside Adept UI.

Developer/operator diagnostics may expose underlying infrastructure where necessary,
but normal creator workflows must not depend upon it.

13. API Resilience Law

Distinguish:

LIVENESS

from:

READINESS

Liveness asks whether the Studio API process is alive.

Readiness asks whether required capabilities and dependencies are available.

A provider or capability failure must not automatically become a global API
liveness failure.

A slow resolver must not automatically mark the Studio API OFFLINE.

A missing optional provider must not automatically make Adept UI unhealthy.

Use accurate states such as:

HEALTHY
DEGRADED
OFFLINE
DISABLED
DEFERRED
OPTIONAL_NOT_INSTALLED
NOT_CONFIGURED
BLOCKED
NOT_FOUND
FILE_MISSING
TIMEOUT
INTERNAL_ERROR

Do not collapse these states into generic failure.

14. Expensive Read Path Law

Creator-facing read requests should not synchronously perform expensive,
unbounded discovery when avoidable.

For expensive read-mostly state, consider:

cached snapshots,
stale-while-revalidate,
background refresh,
single-flight refresh,
atomic cache replacement,
bounded initialization,
and explicit readiness semantics.

A cache expiration must not automatically convert a fast endpoint into a
long-running synchronous discovery operation.

Caches must never become competing canonical state.

15. Polling and Lifecycle Safety

Every recurring process must have one identifiable owner.

Inspect:

timer ownership,
cadence,
cleanup,
AbortController usage,
in-flight guards,
retries,
backoff,
offline suspension,
remount behavior,
navigation behavior,
and dependency changes.

Prevent:

duplicate pollers,
overlapping refreshes,
retry amplification,
request storms,
timer multiplication,
stale requests after navigation,
and multiple components independently polling the same authoritative state.

One logical background service should normally have one authoritative lifecycle owner.

16. React Safety

When modifying React, explicitly inspect:

useEffect dependencies,
cleanup functions,
subscriptions,
listeners,
timers,
AbortController,
stale closures,
StrictMode behavior,
component remounts,
duplicate state writes,
derived-state loops,
and repeated fetches.

A component remount must not accidentally create duplicate persistent infrastructure.

17. GPU Execution Law — Law 26

GPU-designated work must:

preflight the accelerator,
verify the intended GPU,
execute on GPU,
verify that execution actually used the GPU.

Never silently fall back to CPU.

CPU fallback requires:

explicit user approval,
disclosed performance/behavior impact,
and provenance explaining why fallback occurred.

A task designed to validate GPU behavior cannot pass using CPU execution.

18. Co-Director Continuous Quality Gate — Law 28

No new Co-Director capability is complete until it survives autonomous Playwright
certification against a brand-new disposable project.

Unit tests alone are insufficient.

API tests alone are insufficient.

Existing-project success alone is insufficient.

See:

docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md

Certification must test real creator behavior through the Beta product.

19. Co-Director User Authority Law

Permanent product law:

CONVERSATION != WIKI TRUTH

ASSISTANT OUTPUT != PROJECT FACT

INFERENCE != SAVED PROJECT DATA

SUGGESTION != AUTHORITATIVE CARD CONTENT

USER-SAVED / USER-APPROVED / VALID PROJECT IMPORT
=
CANONICAL PROJECT DATA

Co-Director may:

brainstorm,
reason,
ask questions,
propose,
summarize,
extract candidates,
suggest edits,
identify possibilities,
and prepare structured content for approval.

Co-Director must not silently promote these into canonical project truth.

20. Story / Character Authority Boundary

For Story and Character information, prefer:

Conversation
→ understanding / suggestions / candidates
→ explicit creator save or approval
→ canonical Story / Character state
→ Wiki projection

Do not prefer:

Conversation
→ heuristic extraction
→ canonical Wiki mutation

A fresh project must begin with:

Story = empty
Characters = empty

unless legitimate imported or explicitly created canonical project data exists.

Assistant onboarding such as:

Tell me about the story however you want...

must never become:

Logline,
Short Summary,
Long Summary,
Story Principle,
Character,
Character Description,
or other canonical project content.

A user casually saying:

My protagonist is Maya.

may inform Co-Director's reasoning.

It does not automatically create a canonical Character card unless the established
product contract explicitly defines that user action as a save/approval operation.

An assistant saying:

Perhaps Maya is a detective.

must never silently mutate canonical Story or Character data.

21. Wiki Projection Law

Where the architecture supports it, Wiki Story and Character sections should
project from canonical Story and Character state.

The Wiki must not become an independent competing source of truth.

Changes to canonical cards should propagate appropriately:

create
→ Wiki reflects create

rename
→ Wiki reflects rename

edit
→ Wiki reflects edit

delete
→ Wiki reflects deletion

Operations such as:

Refine Wiki,
Rebuild Wiki,
Reorganize Wiki,

must respect creator authority.

They must not fabricate missing canonical information merely to make sections
look complete.

Empty authoritative sections are valid.

22. AI Edit Preview Law

When AI proposes changing creator-authored canonical material:

AI proposal
→ preview
→ creator accepts OR rejects

If accepted:

proposal → canonical update

If rejected:

original creator content remains authoritative

Rejected AI content must not later reappear through rebuild, refinement,
reorganization, caching, or conversation extraction.

23. Co-Director Intelligence — Law 32

Co-Director improves through evidence-backed experience, not conversation history alone.

Learning must be:

transparent,
reviewable,
versioned,
creator-controlled,
reversible,
project-isolated,
and independently certifiable.

No learning mechanism may silently alter creator projects.

Do not turn accumulated conversation history into hidden canonical project mutation.

24. Project Isolation

Project A must never contaminate Project B.

Inspect project identifiers through:

UI
→ request
→ API
→ service
→ cache
→ persistence
→ background tasks

Global caches may cache reusable infrastructure.

They must not accidentally merge project-specific canonical state.

Tests must include project isolation where the affected feature is project-scoped.

25. Human Authority

AI-generated validation, recommendations, and suggestions are advisory unless
the product contract explicitly states otherwise.

Never silently:

delete creator generations,
replace creator data,
approve creator decisions,
trigger expensive retakes,
change canonical cards,
or override explicit creator rejection.

Human authority is absolute for creator-controlled project state.

26. Error Semantics

Expected conditions must use appropriate error semantics.

Examples:

resource does not exist
→ 404

known backing file missing
→ controlled FILE_MISSING / 404-style domain response

optional provider absent
→ OPTIONAL_NOT_INSTALLED

feature intentionally deferred
→ DEFERRED

feature flag disabled
→ DISABLED

dependency temporarily unavailable
→ DEGRADED / dependency-specific state

unexpected server defect
→ 500

Do not convert known expected conditions into generic 500 errors.

Do not hide real internal errors behind misleading success responses.

27. Diagnostics Law

Diagnostics must help identify the failing layer.

Where appropriate distinguish:

Browser/UI
Proxy
Studio API process
Studio API liveness
Studio API readiness
Route
Service
Provider registry
Runtime
GPU
Persistence
Asset storage
Background worker

Diagnostics should answer:

WHAT failed?
WHERE did it fail?
WHY is it classified that way?
WHAT remains healthy?
WHAT action is appropriate?

Diagnostics must not report planned/nonexistent/optional functionality as though
the product is broken.

28. Testing Law

Tests are behavioral contracts.

Never weaken tests merely to obtain green output.

For every meaningful defect repair, add regression coverage capable of detecting
the previous defect where practical.

Use the appropriate layers:

unit,
service,
API,
integration,
regression,
Playwright,
runtime verification.

Passing unit tests do not prove product completion.

29. Playwright Standard

For critical user-facing work, Playwright should monitor where applicable:

console.error,
pageerror,
requestfailed,
unexpected 4xx,
unexpected 5xx,
unhandled promise rejection,
navigation failures,
repeated network storms,
and visible degraded/offline states.

Exercise actual creator workflows rather than merely checking that a page renders.

Use brand-new disposable projects when required by Co-Director Law 28.

Do not silently ignore unexpected network failures.

30. Timeline Certification Standard

When Timeline is affected, verify the relevant implemented capabilities including:

project load,
track load,
clip load,
image tracks,
image preview,
video preview,
prompt tracks,
prompt lower-third behavior,
playback,
scrubbing,
generation routing,
generation progress,
low-quality preview where implemented,
retake,
batch generation,
persistence,
reload,
project isolation,
provider failure,
provider recovery,
and network cleanliness.

Timeline must not create:

duplicate polling,
hidden API storms,
repeated resolver calls,
uncontrolled retries,
or stale generation state.
31. Model / Provider Safety

Do not silently downgrade a requested generation path.

Examples:

I2V request
must not silently become
T2V

requested provider
must not silently become
different provider

Fallback behavior must follow the explicit product contract.

Generation lineage must remain inspectable where required.

32. Documentation Canon — Law 30

Exactly one governing document exists per milestone.

Superseded reports must be clearly marked.

Implementers may not cite superseded reports as current truth.

Primary agents must reconcile documentation conflicts before review.

Do not create another "final" report when an authoritative milestone document
already exists unless the milestone contract requires it.

33. Evidence Before Completion — Law 31

Code existence alone does not complete a capability.

Completion requires as applicable:

implementation,
integration,
registration,
Beta wiring,
live execution,
automated tests,
regression,
Playwright certification,
evidence artifacts,
independent verification,
and binary GO.

Missing required evidence equals NO-GO.

Do not infer success from code inspection alone.

34. Subagent Law

Subagents may investigate, implement bounded tasks, test, or independently verify.

Subagents may only return:

READY FOR PRIMARY REVIEW

They may not issue final milestone GO.

The primary agent owns:

reconciliation,
final verification,
conflicting evidence,
and final verdict.

Independent verification must challenge the implementation rather than merely
repeat the implementing agent's conclusions.

35. No False Completion

Never claim:

PASS
GO
FIXED
CERTIFIED
COMPLETE
PRODUCTION READY

unless the required evidence actually exists.

If a required test could not run, report that explicitly.

If Beta could not be verified, report that explicitly.

If Playwright was required but did not run successfully:

NO-GO

or the appropriate incomplete status must remain.

36. Final Milestone Verdict

Final milestone certification is binary:

GO

or:

NO-GO

Subagents may only return:

READY FOR PRIMARY REVIEW

Do not invent intermediate language that weakens a required binary gate.

37. Final Systems & Resilience — LOCKED

Product Law and MiniMax Timeline Re-take are mandatory highest-priority gates.

Product Law includes:

100% creator actions inside Adept UI

and is also governed by Build Law #29.

Canonical prompt:

docs/release-gate/final-systems/ADEPT_UI_FINAL_SYSTEMS_AND_RESILIENCE_CERTIFICATION_PROMPT.md

Overall:

GO — ADEPT UI FINAL SYSTEMS AND RESILIENCE CERTIFICATION PASSED

is blocked until all mandatory gates pass.

38. Completion Report Contract

For substantial implementation or repair work, report:

Root Cause

What actually caused the defect?

Evidence

How was the root cause confirmed?

Architecture Before

What execution/data path existed before the repair?

Architecture After

What is authoritative after the repair?

Files Changed

List exact files and purpose.

Tests

List exact commands/tests and actual results.

Regression

Report actual regression count/result.

Beta Verification

Report actual behavior through:

http://127.0.0.1:8760
http://127.0.0.1:8758

where applicable.

Playwright

Report scenarios exercised and actual result.

Network / Console

Report unexpected errors observed.

Remaining Risks

List anything not fully verified.

Verdict

Return the verdict allowed by the governing milestone.

Do not hide unresolved issues inside prose.

39. Prime Engineering Principle

When choosing between:

making the report green

and:

making the product correct

always choose product correctness.

When choosing between:

preserving an earlier implementation

and:

repairing a proven architectural defect

repair the defect.

When choosing between:

guessing

and:

inspecting

inspect.

When choosing between:

claiming completion

and:

admitting evidence is incomplete

report the evidence truthfully.

The purpose of the agent is not to produce reassuring output.

The purpose of the agent is to help build a reliable Adept UI.