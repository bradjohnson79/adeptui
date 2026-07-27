# M3.0a Phase 4 - Playwright Test Plan

| Field | Value |
|-------|-------|
| Tip SHA | e2f3ae8a9750d44ec37b64361cbede6a95351d3c |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Date | 2026-07-26 |
| Config | `playwright.config.ts` - serial (`workers: 1`, `fullyParallel: false`), 1 retry, Chromium |
| Projects | `chromium` (root `tests/e2e`) and `workspaces` (`studio-web/e2e`) |
| Total collected | 104 tests across 34 spec files |
| Results | `PLAYWRIGHT_RESULTS.md` |

---

## 1. Configuration change made in this phase

Before M3.0a, `testDir` was `tests/e2e` and there was a single project. `studio-web/e2e` sits
outside that directory, so the M2.13 Environment Studio and M2.14 Unified Experience smokes
**never ran in a default `npx playwright test`**. They existed, they were referenced in their
milestone reports, and nothing executed them.

Rather than copy or symlink the files - which would fork them from the workspace they belong
to - the config now declares a second project:

```
projects: [
  { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  { name: "workspaces", testDir: path.join("studio-web", "e2e"), use: { ...devices["Desktop Chrome"] } },
]
```

Both workspace suites self-skip when their `STUDIO_FEATURE_*` flag is off, so including them
is safe by default and converts into real coverage the moment the flags are enabled in the
E2E environment. One M2.13 test also carried an unconditional pass that would have reported
green against an absent workspace; it now skips explicitly with a reason instead.

This is a small change with a disproportionate effect on the honesty of the suite: three
tests moved from "not collected, assumed covered" to "collected, and one of them actually
runs".

---

## 2. Layers

Six layers, outermost first. Each layer is a different kind of claim, so a gap in one is not
compensated by coverage in another.

| Layer | Claim under test | Specs | Tests | Pass | Fail | Skip |
|-------|------------------|------:|------:|-----:|-----:|-----:|
| 1. Shell and navigation | The app boots, routes, survives resize and meets the a11y floor | 4 | 7 | 7 | 0 | 0 |
| 2. Project and data lifecycle | Projects, scenes, references and timeline bindings persist and round-trip | 3 | 6 | 6 | 0 | 0 |
| 3. Setup, sources and capability gating | Installs, packs, downloads and the capability contract behave and fail honestly | 11 | 18 | 18 | 0 | 0 |
| 4. Co-Director intelligence and approval loop | Chat, bounded tools, proposals, approval gates, Bible writes, vision validation | 9 | 31 | 25 | 6 | 0 |
| 5. Production platforms and workspaces | M2.8, M2.7 executive, M2.9 suite, M2.13, M2.14 | 5 | 36 | 28 | 0 | 8 |
| 6. Providers, credentials and cloud | Provider health, Comfy resilience, fal.ai BYOK | 2 | 6 | 5 | 0 | 1 |
| **Total** | | **34** | **104** | **89** | **6** | **9** |

### Layer 1 - Shell and navigation

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/smoke/startup.spec.ts` | 1 | 1 pass |
| `tests/e2e/resilience/navigation.spec.ts` | 1 | 1 pass |
| `tests/e2e/responsive/viewports.spec.ts` | 4 | 4 pass |
| `tests/e2e/a11y/critical.spec.ts` | 1 | 1 pass |

Solid. This layer is also the one that would catch a build break, so its green is a
precondition for trusting anything below it.

### Layer 2 - Project and data lifecycle

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/projects/project-crud.spec.ts` | 3 | 3 pass |
| `tests/e2e/projects/references.spec.ts` | 1 | 1 pass |
| `tests/e2e/director/timeline-references.spec.ts` | 2 | 2 pass |

These are the tests behind every VERIFIED row in `REAL_ARTIFACT_VERIFICATION.md` section 4.
They are non-generative, and they are the only part of the stack where a full chain is proven
end to end.

### Layer 3 - Setup, sources and capability gating

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/capabilities/capabilities.spec.ts` | 7 | 7 pass |
| `tests/e2e/setup/setup-page.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/source-manager.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/component-source-states.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/download-sources.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/download-queue.spec.ts` | 2 | 2 pass |
| `tests/e2e/setup/pack-install.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/pack-link.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/pack-interrupt.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/pack-fail-retry.spec.ts` | 1 | 1 pass |
| `tests/e2e/setup/pack-release-diagnostics.spec.ts` | 1 | 1 pass |

The pack specs run against `fixture_http`, which is env-gated and refuses outside E2E. They
prove the install state machine, not that a real model downloaded.

### Layer 4 - Co-Director intelligence and approval loop

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/codirector/tools.spec.ts` | 8 | 7 pass, 1 fail (**fixed in this phase**) |
| `tests/e2e/codirector/production-bible.spec.ts` | 6 | 5 pass, 1 fail |
| `tests/e2e/codirector/production-bible-m23.spec.ts` | 1 | 1 fail |
| `tests/e2e/codirector/streaming-cancel.spec.ts` | 4 | 3 pass, 1 fail |
| `tests/e2e/codirector/closed-loop-m2-6-1.spec.ts` | 5 | 5 pass |
| `tests/e2e/codirector/chat-reliability.spec.ts` | 4 | 4 pass |
| `tests/e2e/codirector/intelligence-storyboard.spec.ts` | 1 | 1 fail |
| `tests/e2e/codirector/vision-storyboard-validation.spec.ts` | 1 | 1 fail |
| `tests/e2e/codirector/provider-states.spec.ts` | 1 | 1 pass |

This is where all six failures live. Root causes are in `PLAYWRIGHT_RESULTS.md` section 4;
none of them is a broken approval gate, and the two tests that specifically prove the model
cannot write directly (`tools.spec.ts` mutating-tool-becomes-approval-card, and
`production-bible.spec.ts` rejecting-a-proposal) both pass.

### Layer 5 - Production platforms and workspaces

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/codirector/capability-intelligence-m28.spec.ts` | 18 | 17 pass, 1 skip |
| `tests/e2e/codirector/production-executive-m27.spec.ts` | 11 | 9 pass, 2 skip |
| `tests/e2e/codirector/production-suite-m29.spec.ts` | 4 | 1 pass, 3 skip |
| `studio-web/e2e/m213-environment-studio.spec.ts` | 1 | 1 pass |
| `studio-web/e2e/m214-unified-experience.spec.ts` | 2 | 2 skip |

The skips are the story of this layer: 8 of the 9 skips in the entire suite are here, all of
them because a feature flag is off by default. M2.9's production suite contributes 3, M2.14
contributes 2, M2.7 contributes 2 (one flag-off case and one restart-recovery case), M2.8
contributes 1.

### Layer 6 - Providers, credentials and cloud

| Spec | Tests | Result |
|------|------:|--------|
| `tests/e2e/m30a/m30a-fal-ai-provider.spec.ts` | 5 | 4 pass, 1 skip (live gate) |
| `tests/e2e/resilience/gpu-comfy.spec.ts` | 1 | 1 pass |

Detail in `FAL_AI_PLAYWRIGHT_RESULTS.md`.

---

## 3. Coverage gaps

Ordered by how much they would change the M3.0a verdict if closed.

| # | Gap | Layer | Why it matters | What would close it |
|---|-----|-------|----------------|---------------------|
| 1 | **No test produces a generative artifact.** No spec submits an imagegen, render, lipsync or txt2vid job and then asserts a file exists on disk. | 5/6 | This is the single largest hole in the M3.0a evidence base. Every generative platform in the wiring matrix is NOT_TESTED for exactly this reason. | A local Comfy artifact spec, gated like the fal live block, that runs one imagegen and asserts the `Asset` row and the file. |
| 2 | **No live fal job.** | 6 | Credential acceptance and real rendering are both unproven. | `ADEPT_M30A_FAL_LIVE=1` plus a key and credits. |
| 3 | **No restart-recovery test for the studio job queue.** M2.7's executive has one and it is skipped; the studio queue has none at all. | 5 | The queue does not recover, and no test says so. The defect was found by reading `main.py`, not by a failure. | A spec that enqueues, restarts the API, and asserts the job reaches a terminal state. It would fail today, which is the point. |
| 4 | **M2.9 production suite is 3/4 skipped.** | 5 | Nine sections of native production UI have one executing test. | Enable `codirector_production_suite_v1` in the E2E env. |
| 5 | **M2.14 is 2/2 skipped.** | 5 | Newly collected in this phase, but still not executing. | Enable `codirector_unified_experience_v1` in the E2E env. |
| 6 | **No spec exercises the M2.13 workspace beyond nav chrome.** | 5 | One test asserts the viewport renders. Reconstruction, camera spin and approvals are pytest-only. | Extend `m213-environment-studio.spec.ts` past the shell. |
| 7 | **No cross-platform handoff test for spatial to director timeline.** | 2/5 | `spatialSendDirector` is wired and untested at the browser level. | One spec. |
| 8 | **`get_cloud_render_status` has no browser-level test.** | 4/6 | Covered by pytest and by the tool-catalog assertion, but no spec calls it through the chat loop. | Add to `tools.spec.ts`. |

Gaps 1 and 2 are the two conditions in the M3.0a verdict. Gap 3 is the one defect in this
list that is a bug rather than an absence of coverage.

---

## 4. Standing convention

Two rules this phase established, worth keeping:

1. **A flag-gated suite belongs in the default run, skipping.** A skip with a reason is
   information; an uncollected file is not. This is why `studio-web/e2e` is now a project.
2. **An expensive or credit-spending test belongs in the default run, gated and skipping.**
   The fal live block is the model: one command, same everywhere, and the gate is the only
   difference between a skip and a real result.
