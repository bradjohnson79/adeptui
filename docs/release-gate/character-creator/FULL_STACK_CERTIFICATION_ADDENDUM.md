# FULL-STACK CERTIFICATION ADDENDUM

**Status:** BINDING (2026-08-14)  
**Applies to:** Character Creator Generate Hard-Block Repair and every Adept UI generation workflow certified after this date  
**Canonical with:** `memory/FULL_STACK_E2E_COMPLETION_LAW.md`

This task is not complete when source, tests, build, push, or Vercel deployment pass.

Before the final verdict, execute and document the complete live path on the actual product topology:

Hosted Vercel Character Creator Express → live Studio API → Character Sheet backend → selected model/runtime → generation job → generated image/view result → candidate state → Library/result hydration → reload persistence.

## Illustrious (mandatory live path)

For Illustrious, one real Profile Guided character-sheet candidate must execute through the actual local generation runtime. It is insufficient to prove only that the POST was issued.

Required E2E trace:

```
Generate click
→ Starting…
→ POST accepted
→ profile_guided persisted
→ Illustrious workflow selected
→ actual runtime job created
→ runtime executes
→ four required views generated
→ sheet/candidate completed
→ candidate appears in hosted UI
→ provenance = LOCAL — Illustrious XL — Profile Guided
→ result remains after refresh/reload
```

## Qwen and Z-Image

Qwen must receive the same E2E treatment if its runtime is available. If Qwen cannot actually execute, it must not be certified merely because its dropdown and request routing work.

Z-Image reference mode must likewise be verified through the real reference-conditioned runtime path when available.

## Automatic NO-GO

Any of the following is an automatic NO-GO:

- click sends request but runtime job never starts
- backend says success but no generated result returns
- model silently changes
- result appears only because of mocked fixture data
- candidate disappears after refresh
- Vercel frontend is new but backend/runtime remains stale
- local E2E passes but hosted product cannot execute the same workflow

## Independent verifier

The independent verifier must inspect the E2E evidence, not just source/tests.

## Final completion language

Final completion language may only be:

`CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`

when the actual live generation workflow has succeeded end to end.

Otherwise:

`NO-GO — FULL-STACK E2E NOT VERIFIED`

or:

`E2E BLOCKED — <exact runtime/provider blocker>`

Do not use READY FOR MANUAL BETA as a substitute for this binary gate when the required live generation path has not been proven.

## Candidate count (product vs E2E)

Express E2E certification may use `candidateCount=1` for the minimal live proof. Candidate count for normal production UX remains governed by the Character Creator product configuration (Amendment F5: **4** candidates × 4 views).

Do not turn the E2E debugging setting into the permanent Character Creator product contract.
