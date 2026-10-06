# Adept UI — Binding Full-Stack E2E Completion Law

**Status:** BINDING (2026-08-14)
**Applies to:** Cursor, Grok Bot, subagents, maintenance bots, implementation agents, verifier agents
**Applies to:** every Adept UI feature, repair, refinement, migration, integration, and production workflow

The browser/runtime behavior is authoritative. Not the source code, the plan, the build log, or the unit tests. If the creator cannot use the feature successfully end to end, the feature is not complete.

---

## 1. UI complete != feature complete

A task is NOT complete merely because:

- the page renders
- the button exists
- the dropdown opens
- the CSS looks correct
- TypeScript passes
- unit tests pass
- the backend route exists
- a component was wired in source
- a build succeeds

These prove implementation only. They do NOT prove product functionality.

## 2. Full-stack E2E is mandatory

Before a task may be certified COMPLETE, the actual creator workflow must be exercised through the full stack.

Required chain where applicable:

USER ACTION → FRONTEND CONTROL → FRONTEND STATE → REQUEST / COMMAND → API ROUTE → BACKEND SERVICE → PERSISTENCE → RUNTIME / PROVIDER / GENERATOR → RESULT → FRONTEND HYDRATION → RELOAD PERSISTENCE → DOWNSTREAM CONNECTED SYSTEMS

The entire applicable chain must be proven.

## 3. Button law

If a button is added or changed, do not certify it because it renders.

Prove: click → handler fires → request is sent → backend accepts it → intended operation executes → success/failure state returns → UI updates correctly.

A button that looks active but does nothing is an automatic NO-GO.

## 4. Dropdown law

If a dropdown selects Character, Prop, Camera, Generator, Provider, Scene, Shot, Voice, or Asset: prove the authoritative ID/value survives the complete workflow. Do not certify from display labels alone.

## 5. Generation law

For image/video/audio generation prove: selection → request → intended provider/model → job creation → runtime execution → polling/status → output asset → Library ingestion → provenance → candidate/result UI.

No silent fallback. No fake provenance. No endless spinner.

## 6. Persistence law

Any feature that saves state must be verified through reload: create/change state → save → refresh/reopen → same authoritative state returns. If reload loses the state: NO-GO.

## 7. Connected-system law

If a feature feeds another Adept UI system, E2E certification includes that handoff (e.g. Character Creator → Spatial Map → Scene Creator → Timeline). A feature is not complete if its own page works but its downstream contract is broken.

## 8. Local/API source law

Where Local/API routing exists:

- Local ON / API OFF → zero API jobs
- Local OFF / API ON → zero Local jobs
- Both ON → both intentionally eligible

A selected provider/model must actually be the one executed.

## 9. Failure path law

E2E certification must include at least one meaningful failure path where practical: visible error, no silent failure, no infinite loading, bounded retry, state remains recoverable.

## 10. Build success is not certification

Backend tests, frontend tests, TypeScript, and production build are necessary preconditions. They do not replace E2E certification.

## 11. Certification evidence

A completion report must include actual evidence: tested workflow, endpoint/request evidence, runtime/provider evidence, persisted IDs/state, output asset/result, reload verification, downstream verification, error-path verification, screenshots/logs where useful. Do not write PASS without evidence.

## 12. Independent verification

The implementing agent must not be the sole authority declaring completion. After implementation an independent verifier/subagent must inspect the actual evidence.

Verifier returns:

- `VERIFIED — FULL-STACK E2E PASSED`
- or `REJECTED — <specific blocker>`

## 13. Certification states

- **IMPLEMENTED** — Code exists but E2E not yet proven.
- **E2E BLOCKED** — Implementation exists but runtime/dependency prevents certification.
- **E2E FAILED** — Workflow was tested and failed.
- **READY FOR MANUAL BETA** — Automated/full-stack checks passed but creator approval is still required.
- **CERTIFIED COMPLETE** — Only allowed when the task's required full-stack E2E workflow and independent verification have passed.

Do not use COMPLETE before this point.

## 14. No mock-only certification

Mocks may support tests. Mocks cannot be the sole evidence for a live production workflow. Where a real runtime/provider/backend exists, exercise the real path at least once before certification.

## 15. Deployed surface law

If the reported defect occurred on hosted/Vercel: certification must include hosted verification. Local-only success does not close a hosted defect. If the target is local Beta: test the local Beta topology actually used by the creator.

## 16. Full-stack trace required in final report

Every completion report must include:

```
E2E TRACE
User action:
Frontend:
API:
Backend:
Persistence:
Runtime/provider:
Result:
Reload:
Downstream:
```

Each: `PASS | FAIL | NOT APPLICABLE`

## 17. Automatic NO-GO conditions

Automatic NO-GO if any applies:

- UI renders but action does nothing
- request never leaves frontend
- wrong API endpoint
- wrong provider/model executes
- state does not persist
- result does not hydrate
- downstream system cannot consume it
- silent fallback occurs
- failure is swallowed
- infinite spinner
- fake success state
- stale hosted bundle still serves old behavior

## 18. Final verdict law

A task may only end with `CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED` when all required layers pass.

Otherwise use `NO-GO — FULL-STACK E2E NOT VERIFIED` or `READY FOR MANUAL BETA` when creator review is intentionally still outstanding.

## 19. Subagent requirement

Use subagents for implementation, E2E trace validation, and independent verification. Do not allow one agent to implement, test superficially, and self-certify without challenge.

## 20. Adept UI product principle

The browser/runtime behavior is authoritative. Not the source code. Not the plan. Not the build log. Not the unit tests. If the creator cannot use the feature successfully end to end, the feature is not complete.

## 21. FULL-STACK CERTIFICATION ADDENDUM (binding 2026-08-14)

Canonical: `docs/release-gate/character-creator/FULL_STACK_CERTIFICATION_ADDENDUM.md`

This task is not complete when source, tests, build, push, or Vercel deployment pass.

Required live topology:

Hosted Vercel Character Creator Express → live Studio API → Character Sheet backend → selected model/runtime → generation job → generated image/view result → candidate state → Library/result hydration → reload persistence.

Illustrious requires one real Profile Guided character-sheet candidate through the actual local runtime. POST-only is insufficient.

Required trace: Generate click → Starting… → POST accepted → profile_guided persisted → Illustrious workflow selected → actual runtime job created → runtime executes → four required views generated → sheet/candidate completed → candidate appears in hosted UI → provenance = `LOCAL — Illustrious XL — Profile Guided` → result remains after refresh/reload.

Qwen must receive the same E2E treatment if its runtime is available. Dropdown/routing alone does not certify Qwen. Z-Image reference mode must run the real reference-conditioned runtime path when available.

Automatic NO-GO: click sends request but runtime job never starts; backend success with no generated result; silent model change; mocked fixture result; candidate disappears after refresh; new Vercel frontend with stale backend/runtime; local E2E while hosted cannot execute the same workflow.

Independent verifier inspects E2E evidence, not just source/tests.

Final language only:

- `CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`
- `NO-GO — FULL-STACK E2E NOT VERIFIED`
- `E2E BLOCKED — <exact runtime/provider blocker>`

Express E2E certification may use `candidateCount=1` for the minimal live proof. Candidate count for normal production UX remains governed by the Character Creator product configuration (Amendment F5: 4). Do not turn the E2E debugging setting into the permanent product contract.
