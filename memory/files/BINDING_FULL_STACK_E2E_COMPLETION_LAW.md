# ADEPT UI — BINDING FULL-STACK E2E COMPLETION LAW

**Saved:** 2026-08-14 (PT)
**Status:** BINDING
**Applies to:** Cursor, Grok Bot, subagents, maintenance bots, implementation agents, verifier agents
**Applies to:** every Adept UI feature, repair, refinement, migration, integration, and production workflow

The browser/runtime behavior is authoritative. Not the source code. Not the plan. Not the build log. Not the unit tests.

If the creator cannot use the feature successfully end to end, the feature is not complete.

---

## 1. UI COMPLETE != FEATURE COMPLETE

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

---

## 2. FULL-STACK E2E IS MANDATORY

Before a task may be certified COMPLETE, the actual creator workflow must be exercised through the full stack.

Required chain where applicable:

USER ACTION
→ FRONTEND CONTROL
→ FRONTEND STATE
→ REQUEST / COMMAND
→ API ROUTE
→ BACKEND SERVICE
→ PERSISTENCE
→ RUNTIME / PROVIDER / GENERATOR
→ RESULT
→ FRONTEND HYDRATION
→ RELOAD PERSISTENCE
→ DOWNSTREAM CONNECTED SYSTEMS

The entire applicable chain must be proven.

---

## 3. BUTTON LAW

If a button is added or changed: do not certify it because it renders.

Prove:

click → handler fires → request is sent → backend accepts it → intended operation executes → success/failure state returns → UI updates correctly

A button that looks active but does nothing is an automatic NO-GO.

---

## 4. DROPDOWN LAW

If a dropdown selects Character, Prop, Camera, Generator, Provider, Scene, Shot, Voice, or Asset: prove the authoritative ID/value survives the complete workflow.

Do not certify from display labels alone.

---

## 5. GENERATION LAW

For image/video/audio generation, prove:

selection → request → intended provider/model → job creation → runtime execution → polling/status → output asset → Library ingestion → provenance → candidate/result UI

No silent fallback. No fake provenance. No endless spinner.

---

## 6. PERSISTENCE LAW

Any feature that saves state must be verified through reload.

Required: create/change state → save → refresh/reopen → same authoritative state returns

If reload loses the state: NO-GO.

---

## 7. CONNECTED-SYSTEM LAW

If a feature feeds another Adept UI system, E2E certification includes that handoff.

Examples:

- Character Creator → Spatial Map → Scene Creator → Timeline
- Prop Creator → Library → Spatial Map → Scene Creator
- Avatar Studio → Library → Timeline

A feature is not complete if its own page works but its downstream contract is broken.

---

## 8. LOCAL/API SOURCE LAW

Where Local/API routing exists:

- Local ON / API OFF → zero API jobs
- Local OFF / API ON → zero Local jobs
- Both ON → both intentionally eligible

A selected provider/model must actually be the one executed.

---

## 9. FAILURE PATH LAW

E2E certification must include at least one meaningful failure path where practical.

Verify: visible error, no silent failure, no infinite loading, bounded retry, state remains recoverable.

---

## 10. BUILD SUCCESS IS NOT CERTIFICATION

These are necessary but insufficient: backend tests, frontend tests, TypeScript, production build.

They are preconditions to E2E certification. They do not replace it.

---

## 11. CERTIFICATION EVIDENCE

A completion report must include actual evidence such as:

- tested workflow
- endpoint/request evidence
- runtime/provider evidence
- persisted IDs/state
- output asset/result
- reload verification
- downstream verification
- error-path verification
- screenshots/logs where useful

Do not write PASS without evidence.

---

## 12. INDEPENDENT VERIFICATION

The implementing agent must not be the sole authority declaring completion.

After implementation, an independent verifier/subagent must inspect the actual evidence.

Verifier returns:

- `VERIFIED — FULL-STACK E2E PASSED`
- or `REJECTED — <specific blocker>`

---

## 13. CERTIFICATION STATES

Use these states:

- **IMPLEMENTED** — Code exists but E2E not yet proven.
- **E2E BLOCKED** — Implementation exists but runtime/dependency prevents certification.
- **E2E FAILED** — Workflow was tested and failed.
- **READY FOR MANUAL BETA** — Automated/full-stack checks passed but creator approval is still required.
- **CERTIFIED COMPLETE** — Only allowed when the task's required full-stack E2E workflow and independent verification have passed.

Do not use COMPLETE before this point.

---

## 14. NO MOCK-ONLY CERTIFICATION

Mocks may support tests. Mocks cannot be the sole evidence for a live production workflow.

Where a real runtime/provider/backend exists: exercise the real path at least once before certification.

---

## 15. DEPLOYED SURFACE LAW

If the reported defect occurred on hosted/Vercel: certification must include hosted verification.

Local-only success does not close a hosted defect.

If the target is local Beta: test the local Beta topology actually used by the creator (`:8760` UI → `:8761` Studio API).

---

## 16. FULL-STACK TRACE REQUIRED IN FINAL REPORT

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

Each: PASS | FAIL | NOT APPLICABLE

---

## 17. AUTOMATIC NO-GO CONDITIONS

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

---

## 18. FINAL VERDICT LAW

A task may only end with:

`CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`

when all required layers pass.

Otherwise use:

`NO-GO — FULL-STACK E2E NOT VERIFIED`

or

`READY FOR MANUAL BETA`

when creator review is intentionally still outstanding.

---

## 19. SUBAGENT REQUIREMENT

Use subagents for implementation, E2E trace validation, and independent verification.

Do not allow one agent to implement, test superficially, and self-certify without challenge.

---

## 20. ADEPT UI PRODUCT PRINCIPLE

The browser/runtime behavior is authoritative.

Not the source code. Not the plan. Not the build log. Not the unit tests.

If the creator cannot use the feature successfully end to end, the feature is not complete.
