# Adept UI — Agent Standing Instructions

These instructions govern ALL primary agents, coding agents, reviewers,
subagents, and autonomous implementation work performed on Adept UI.

They apply regardless of model:

- DeepSeek
- Qwen
- GLM
- Kimi
- Grok
- OpenAI
- Claude
- or any other agent/model

Adept UI is a production software system.

Do not optimize for appearing complete.
Optimize for actually being complete.

---

# 1. Authority

All agents must follow the Adept UI Build Memory Layer.

Canonical laws:

`docs/ADEPT_UI_BUILD_MEMORY_LAYER.md`

Always-on Cursor rule:

`.cursor/rules/adept-ui-build-laws.mdc`

Beta/runtime refresh law:

`.cursor/rules/beta-refresh-after-build.mdc`

Architecture and milestone-specific governing documents take precedence over
older implementation reports.

If two documents conflict:

1. identify the conflict;
2. determine the current authoritative source;
3. do not silently choose whichever instruction is easier;
4. reconcile before certification.

---

# 2. Product Law

Adept UI is the product.

Underlying runtimes are implementation details.

Creators should not be required to manually operate:

- ComfyUI
- Python
- Uvicorn
- Ollama
- Cloudflare
- local ports
- runtime terminals
- node graphs
- lifecycle scripts

unless they explicitly enter an Advanced/Developer workflow.

Adept UI owns:

- discovery
- startup
- readiness
- reconnect
- recovery
- reuse
- shutdown
- dependency visibility
- creator-facing status

This is Build Law #29.

---

# 3. Investigate Before Modifying

Do not begin implementation from assumptions.

Before changing a subsystem:

1. inspect the current implementation;
2. identify the actual authoritative branch;
3. inspect related tests;
4. inspect existing abstractions;
5. inspect recent relevant implementation;
6. identify ownership boundaries;
7. identify whether the requested capability already partially exists.

Do not create duplicate systems simply because an existing system was not
immediately discovered.

Prefer:

`inspect → understand → reuse → extend → certify`

over:

`guess → rebuild → patch`

---

# 4. Repository Truth

Never assume the current working tree is equivalent to the deployed product.

Before milestone or deployment work, establish:

- current branch;
- HEAD SHA;
- git status;
- authoritative branch;
- remote SHA;
- deployed SHA where applicable;
- whether required files are tracked by Git.

Local filesystem existence is NOT proof that a file exists in Git.

A clean deployment must be reproducible from a clean checkout.

Untracked or ignored source required by the product is a release blocker.

---

# 5. Preserve Working Architecture

Do not broadly rewrite working systems when a localized repair is sufficient.

Before introducing a new:

- manager
- router
- store
- provider
- supervisor
- polling system
- cache
- runtime abstraction
- API layer

prove that an existing one cannot be safely extended.

Favor the smallest architecture that solves the verified problem while
remaining suitable for:

- Open Source / Electron
- Hosted Beta
- Adept UI Cloud

Avoid environment-specific hacks when a transport-independent solution is
practical.

---

# 6. Never Hide Failures

Do not make a failing system appear healthy by:

- suppressing an error;
- converting failure to warning;
- returning fake readiness;
- adding placeholder modules;
- using mock success in production paths;
- disabling checks;
- weakening TypeScript;
- adding arbitrary `any`;
- bypassing certification;
- silently falling back to another runtime/model.

Fix the underlying cause.

If the cause cannot be fixed within scope, return NO-GO with the exact blocker.

---

# 7. Completion Means End-to-End Completion

Code existence does not equal feature completion.

A capability is complete only when applicable stages have passed:

1. implementation;
2. integration;
3. persistence;
4. UI wiring;
5. runtime wiring;
6. error handling;
7. recovery behavior;
8. regression tests;
9. Playwright;
10. live environment verification;
11. evidence;
12. independent review;
13. binary verdict.

Missing evidence = incomplete.

This is Build Law #31.

---

# 8. Do Not Stop at "Implemented"

If the requested task includes implementation AND verification, continue through
verification.

Do not stop merely because:

- code compiles;
- unit tests pass;
- files exist;
- the endpoint exists;
- the UI renders;
- the agent believes the fix is logically correct.

If the task explicitly requires Playwright, live certification, a soak test,
runtime verification, or deployment verification, those are part of the task.

Do not report:

`GO`

while simultaneously saying:

`Playwright not run`
`live verification pending`
`deployment not tested`

That is:

`READY FOR PRIMARY REVIEW`

or:

`NO-GO`

depending on the governing gate.

---

# 9. Evidence Must Be Observed, Not Predicted

Never substitute predicted results for measured evidence.

Invalid:

`Expected request count: ~30`

when the required test has not run.

Valid:

`Measured request count over 10 minutes: 43`

If a value is predicted, label it clearly:

`PREDICTED`

Never use predicted values to satisfy a certification gate.

---

# 10. Binary Certification

Final milestone certification is binary:

`GO`

or:

`NO-GO`

Subagents may return only:

`READY FOR PRIMARY REVIEW`

unless explicitly authorized to issue the governing final verdict.

A GO requires every mandatory criterion to pass.

One mandatory blocker = NO-GO.

Never use:

- mostly GO
- near GO
- practical GO
- implementation GO

as a substitute for the governing binary gate.

Sub-gates may be reported individually, but the overall verdict remains binary.

---

# 11. Failure Handling

When a test fails:

1. capture the exact failure;
2. determine whether it is new or pre-existing;
3. reproduce it independently where possible;
4. identify root cause;
5. repair if within scope;
6. rerun the affected test;
7. rerun relevant regression;
8. update evidence.

Do not classify a failure as "pre-existing" merely because it appears unrelated.

Prove baseline reproduction before excluding it.

---

# 12. Root Cause Before Patch

Do not patch symptoms before identifying root cause.

For runtime/network/UI failures, trace the entire chain:

`UI → hook/store → API client → transport → API → runtime → dependency`

For deployment failures:

`working tree → Git → build → deployment → browser → backend`

For lifecycle failures:

`creator action → control layer → supervisor → process → health probe → UI state`

Repair the earliest incorrect layer practical.

---

# 13. Request Stability Law

Adept UI frontend components must not independently create uncontrolled backend
traffic.

Shared runtime information should use shared state wherever practical.

Required principles:

- single-flight requests;
- bounded concurrency;
- TTL caching for read-mostly state;
- centralized connection health;
- polling suspension during outages;
- exponential/bounded retry;
- cleanup on unmount;
- no recursive emit→fetch loops;
- no request creation during render;
- no accumulating timers;
- no duplicated recovery engines.

A successful health response must never recursively cause an uncontrolled new
health request.

Live soak testing is required for networking fixes that can degrade over time.

---

# 14. Runtime Ownership Law

Adept UI may stop or restart only processes it owns.

Processes must be distinguishable internally as appropriate:

- OWNED
- REUSED
- EXTERNAL

If Adept UI discovers an already-running healthy ComfyUI, Ollama, Studio API, or
other runtime:

reuse it when safe.

Do not kill unrelated:

- Python
- Node
- Ollama
- ComfyUI
- cloudflared
- user processes

based solely on executable name.

---

# 15. Local Runtime Architecture

Current hosted Beta runtime architecture is:

`Vercel frontend`
→ `Cloudflare secure endpoint`
→ `Studio API :8758`
→ `Localhost Background Manager`
→ `ComfyUI / Ollama / GPU`

The old local frontend Beta server on:

`:8760`

is retired from the normal hosted Beta path.

Do NOT resurrect the old :8760 stack unless a specific test explicitly requires
that legacy environment.

Use the current Localhost/Background Runtime Manager for backend lifecycle.

---

# 16. Background Manager Product Terminology

Creator-facing terminology:

- ComfyUI Background Manager
- Localhost Background Manager
- Local Runtime
- Background Services
- Remote Runtime Access

Do not expose normal creators to:

- Beta Backend Manager
- Uvicorn
- PID
- PowerShell
- internal ports
- cloudflared

except inside Advanced Diagnostics where technically appropriate.

---

# 17. GPU Law

GPU-designated work must:

1. preflight accelerator availability;
2. verify the expected GPU;
3. execute on GPU;
4. record accelerator provenance where required.

Never silently fall back to CPU.

CPU fallback requires:

- explicit user approval;
- disclosed performance impact;
- recorded provenance.

This is Build Law #26.

---

# 18. Model/Provider Law

Never silently substitute:

- generation model;
- provider;
- runtime;
- checkpoint;
- workflow;
- accelerator.

If certification requires a specific model, use that model.

Example:

MiniMax H3 certification means MiniMax H3.

Do not silently substitute LTX, WAN, or another generator because it is easier.

---

# 19. Co-Director Continuous Quality Gate

No new Co-Director capability is complete until it survives autonomous
Playwright certification against a brand-new disposable project.

Unit/API green alone is insufficient.

Reference:

`docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md`

This is Build Law #28.

---

# 20. Co-Director User Authority

Conversation understanding is not automatically canonical project data.

Do not silently convert:

- assistant onboarding;
- generic conversation;
- questions;
- scaffolding;
- inferred names;
- accidental capitalized words

into canonical Wiki Story or Character data.

Canonical project mutation requires an authorized save/approval path according
to current Co-Director contracts.

User-created project truth takes precedence over agent inference.

---

# 21. Co-Director Intelligence Law

Co-Director improves through evidence-backed experience, not conversation
history alone.

Learning must be:

- transparent;
- reviewable;
- versioned;
- creator-controlled;
- reversible;
- project-isolated;
- independently certifiable.

No learning may silently alter creator projects.

This is Build Law #32.

---

# 22. Documentation Canon

Exactly one governing document per milestone.

Superseded reports must be clearly marked.

Do not cite obsolete reports as current truth.

If implementation changes invalidate evidence:

update the evidence.

This is Build Law #30.

---

# 23. Playwright Law

When Playwright is required:

- run it;
- do not substitute unit tests;
- use the actual requested environment;
- create disposable projects where required;
- capture browser console;
- capture page errors;
- capture request failures;
- capture unexpected 4xx/5xx;
- verify persistence/reload;
- verify recovery where applicable.

For time-dependent defects, run an appropriate soak duration.

A 30-second test does not certify a defect known to appear after five minutes.

---

# 24. Hosted Beta Certification

For hosted Beta work, distinguish:

BUILD GO

from:

RUNTIME GO

from:

HOSTED PRODUCT GO

A successful Vercel build proves only deployment/build integrity.

Hosted product certification requires actual browser/runtime functionality.

---

# 25. Clean-Clone Law

Before declaring deployment readiness, ensure the product can be built from a
clean checkout of the authoritative branch.

Do not rely on:

- untracked source;
- ignored source;
- local-only generated files;
- machine-specific paths;
- caches;
- manually copied assets.

---

# 26. Security

Never commit:

- API keys;
- tokens;
- tunnel credentials;
- private keys;
- passwords;
- local secret files.

Never place secrets into browser-visible `VITE_*` values.

Do not expose raw local runtime ports to the public Internet when a secure
transport is required.

Use explicit CORS origins when credentials are enabled.

---

# 27. User Experience Law

Normal creators should receive creator language.

Prefer:

`Runtime Ready`

over:

`Uvicorn process PID 1234 listening on 8758`

Prefer:

`ComfyUI needs attention`

over raw Python exceptions.

Technical details belong in Diagnostics.

Do not require technical knowledge to use normal product workflows.

---

# 28. Branch Discipline

Do not:

- force push without explicit authorization;
- rewrite shared history;
- merge unrelated branches casually;
- modify unrelated features during focused repair;
- deploy from the wrong branch.

Before deployment, report:

BRANCH
HEAD SHA
REMOTE SHA
DEPLOYMENT SHA

They must be intentionally aligned.

---

# 29. Scope Discipline

Fix everything necessary to complete the requested capability.

Do not use "scope" as an excuse to stop before required integration or
certification.

But also do not expand into unrelated redesign.

Use:

`necessary for completion`

as the boundary.

---

# 30. Subagent Law

Subagents are specialists.

Give subagents narrow, verifiable tasks.

They may:

- investigate;
- audit;
- implement scoped work;
- test;
- review.

They may not independently redefine product law or issue the final milestone GO
unless explicitly authorized.

Primary agent must reconcile subagent findings.

---

# 31. Autonomous Continuation

Do not stop for user confirmation when:

- the next step is already authorized by the governing prompt;
- required information can be discovered from the repository/runtime;
- testing is part of the task;
- a safe repair is clearly within scope.

Ask the user only when:

- credentials/user interaction are genuinely required;
- destructive/risky action requires approval;
- product intent is genuinely ambiguous;
- an external manual action cannot be performed autonomously.

---

# 32. No Premature Handoff

Do not return:

`No further action needed`

while mandatory work remains.

If work remains, explicitly state:

`REMAINING`

and continue where authorized.

A task that requires implementation + Playwright + live verification is not
complete after implementation.

---

# 33. Final Report Standard

Certification reports must distinguish:

IMPLEMENTED
TESTED
LIVE VERIFIED
NOT VERIFIED
BLOCKED
DEFERRED
OPTIONAL

Reports must contain exact test counts where available.

Example:

`134 passed, 2 failed, 4 skipped`

not:

`tests mostly passed`

For live measurements, report observed numbers.

---

# 34. Final Systems & Resilience Gate

Product Law and MiniMax Timeline Re-take remain mandatory highest-priority gates
for Final Systems & Resilience.

Canonical prompt:

`docs/release-gate/final-systems/ADEPT_UI_FINAL_SYSTEMS_AND_RESILIENCE_CERTIFICATION_PROMPT.md`

Overall final certification remains blocked until its mandatory gates pass.

Required final verdict:

`GO — ADEPT UI FINAL SYSTEMS AND RESILIENCE CERTIFICATION PASSED`

Anything less is not final release certification.

---

# 35. Definition of Done

Before saying DONE, ask:

- Is it implemented?
- Is it wired?
- Can the creator reach it?
- Does it persist?
- Does it recover?
- Does it work in the intended environment?
- Did the required tests run?
- Did Playwright run where required?
- Did live certification run where required?
- Is evidence current?
- Are there zero unresolved mandatory blockers?

If any required answer is NO:

the task is not done.

Continue or return NO-GO with the exact blocker.