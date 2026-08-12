# M5.3 — Co-Director Harmonization & Final Beta Readiness

| Field | Value |
| --- | --- |
| Milestone ID | `M5.3` |
| Date context | `2026-08-02` |
| Branch note | `feature/ai-guided-setup` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Document role | Authoritative kickoff and readiness brief |
| Current certification state | Implementation certification pending |

## Mission

M5.3 exists to **harmonize Co-Director into a trustworthy production partner**, not to expand scope with new studios, new pipelines, or side quests. The milestone focus is narrow and consequential: make the creator-facing status, recommendations, and workflow awareness match the real production state of the open project on live Beta.

The intended behavior is the same tone as an experienced assistant director:

- never reckless
- never overly conservative
- aware of what matters now
- honest about what is unknown
- helpful without becoming an ops console

This is a **creator-engineering** milestone. The system must preserve technical honesty and proposal safety while presenting a calmer, clearer, more actionable experience for filmmakers and other creators.

## Guiding Philosophy

1. **Harmonization over feature expansion.** M5.3 fixes classification, awareness, summaries, and UX coherence; it does not authorize broad new capability work.
2. **Creator summary first.** The primary surface should answer: Is my project healthy, is my current workflow ready, what matters next, and what is merely optional?
3. **Truth before comfort.** Unknown must stay unknown, optional must stay optional, and inactive workflow requirements must not be misrepresented as blockers.
4. **Proposal safety remains intact.** Co-Director can inspect, recommend, explain, preview, approve, execute, verify, and persist; it must not silently mutate creator projects.
5. **One open project is the source of truth.** Status, recommendations, and runtime readiness must bind to the active project and survive reloads without inventing parallel state.

## Baseline From Audits

### What M5.0 already proved

The current baseline is not a general product readiness failure. The authoritative M5.0 final certification records **NO-GO solely because Co-Director live status quality remained below release quality** in a valid live project run: `Degraded / 82 / Fair`. See `docs/release-gate/m5-final/M5_FINAL_CERTIFICATION.md`.

The same M5.0 certification already marked the surrounding release gates as passing:

- AI-Guided Setup final closure: `PASS`
- Addendum 9 live Beta stability: `PASS`
- Harness vs live Beta parity: `PASS`
- Production Dock gate: `PASS`
- Runtime/status honesty baseline: `PASS`

This means M5.3 is the specific release-gate effort to remove the remaining Co-Director blocker without reopening already-passed Setup, Dock, and stability work.

### Current Co-Director baseline

From the plan and audits:

- Co-Director already has **426 tools** registered: `233` read and `193` mutating.
- The proposal gate is already solid in `studio-api/app/codirector/tools/definitions.py` and `studio-api/app/codirector/tools/execution.py`.
- `studio-api/app/codirector/status/weighting.py` already supports an `optional` criticality weight, but the live status registry in `studio-api/app/codirector/status/registry.py` is still dominated by `critical`, `high`, and `standard`, with no first-class `workflow_required` tier.
- Strong coverage already exists in timeline, setup/runtime, voice, voice environment, script, spatial, avatar, audio, continuity, production plan, and adjacent creator workflows.
- Thin or missing awareness remains in MAGI, Marketplace, Brand, Storyboard, and Image.
- Status truth is still fragmented across multiple surfaces and contracts.

### Coverage strengths and gaps

Current strengths:

- Setup and runtime awareness
- Voice and voice-environment flows
- Timeline and production planning
- Spatial, avatar, audio, continuity, and library-adjacent flows
- Stable proposal-gated mutation model

Current gaps:

- MAGI has no first-class `magi.*` awareness layer
- Marketplace awareness is thin
- Brand awareness is minimal
- Storyboard awareness is minimal
- Image support is thin and still skewed toward legacy `propose_*` behavior

The intent of M5.3 is **awareness coverage**, not new studio expansion. Thin areas need inspect and recommend intelligence so Co-Director can guide the creator through the real workspace, even where deeper feature work remains outside scope.

### Fragmented status surfaces to harmonize

The audits identified multiple overlapping status surfaces that currently speak different dialects:

- creator chrome `Status`
- `studio-web/src/components/CoDirector/CoDirectorStatusPanel.tsx`
- setup catalog `required` semantics
- capability and generation requirement surfaces such as `REQUIRED_FOR_GENERATION`
- Docker/runtime categories such as `core_mandatory` and `official_optional`

M5.3 exists to align these into one classification contract and one creator-facing summary model.

## Hard Architectural Decisions

These decisions come directly from the approved plan and should be treated as milestone law unless the primary owner explicitly reopens them:

1. **Single classification contract.** The system classifies status checks and workflow dependencies as `essential`, `workflow_required`, `recommended`, or `optional`.
2. **Creator summary is primary.** The creator-facing summary and workflow readiness surface comes first; numeric scoring and raw diagnostics move behind advanced disclosure.
3. **Unknown does not equal Ready.** Runtime honesty fields such as installed, running, GPU, VRAM, provider, version, pinned, certified, ready, and last-verified must never collapse unknown into a healthy state.
4. **Awareness over expansion.** MAGI, Marketplace, Brand, Storyboard, and Image gaps are closed with lightweight inspect and recommend awareness, not full new studio delivery.
5. **Law 16 contract freeze.** Classification, summary DTOs, and workspace matrix are frozen before parallel implementation so every contributor works from the same contract.
6. **GPT-5.4 specialized subagents.** Any specialized subagent work for this milestone follows Law 27 and uses `gpt-5.4-medium`.
7. **Proposal safety is preserved.** M5.3 does not weaken inspect -> recommend -> explain -> preview -> approve -> execute -> verify -> persist.

## Classification Model

The classification model is the core release-gate repair because the M5.0 failure was driven by status interpretation, not missing foundational systems.

| Class | Meaning | Release effect | Example |
| --- | --- | --- | --- |
| `essential` | Core production prerequisites required for the open project to function safely and truthfully | Can block or degrade Production Health | project binding, DB/API reachability, core tool registry, Bible/Timeline/Library core |
| `workflow_required` | Required only for the creator's active workflow or workspace | Affects Production Health only when that workflow is active | `IndexTTS2` during Voice Performance, `InfiniteTalk` during Avatar work |
| `recommended` | Important quality or experience enhancement, but not an automatic production blocker on its own | Warns and informs; should not by itself force a false hard failure | higher-quality runtime path, non-critical acceleration, enriched guidance |
| `optional` | Additional models, extra providers, experimental or additive components | Must never alone drag a healthy production project into false `Degraded` or `Blocked` | extra avatar packs, non-active image models, optional creative add-ons |

### Required interpretation rules

- Production Health derives from `essential` plus the currently active `workflow_required` checks.
- Missing `optional` items must be reported as available or not needed, not as creator-alarming degradation.
- Inactive `workflow_required` items must be visible without poisoning current workflow readiness.
- `recommended` items can warn, but they do not replace genuine blocker semantics.

## Phase Plan

| Phase | Focus | Primary output |
| --- | --- | --- |
| Phase A / 0 | Repository audit and contract freeze | Freeze classification, summary DTOs, workspace matrix, runtime honesty contract |
| Phase B / 1 | Workspace integration and E2E wiring | Close MAGI, Marketplace, Brand, Storyboard, and Image awareness gaps; verify real workspace chains |
| Phase C / 2 | Status engine and runtime honesty | Reclassify checks, prevent optional false degradation, emit creator-ready summary |
| Phase D / 3 | Creative intelligence and production awareness | Next-step recommendations and production progress awareness grounded in live context |
| Phase E / 4 | UX harmonization | Make creator summary primary, collapse diagnostics, keep proposal controls coherent |
| Phase F / 5 | Playwright, regression, and live Beta certification prep | Live evidence, regression proof, manual review path, certification package |
| Independent verifier | Second-pass audit by non-implementing verifier | `READY FOR PRIMARY CERTIFICATION` or `BLOCKED` |
| Primary owner | Integration, Beta restart, final report, binary decision | Final `GO` or `NO-GO`, with no mocked or misleading completion state |

## Phase Details

### Phase A / 0 — Repository Audit & Frozen Contracts

Freeze the shared contract before implementation:

- `SystemImportance` values
- `ProductionHealthSummary` DTO
- `ProductionProgressSummary` DTO
- workspace-to-tool-family matrix
- runtime honesty field contract
- reclassification list for status checks moving into `workflow_required` or `optional`

No scoring or UI rewrite should proceed before this freeze lands.

### Phase B / 1 — Workspace Integration & E2E Wiring

Use `studio-api/app/codirector/session_context.py`, the active workspace context, and the production workspace/menu definitions to ensure every production workspace has at least inspect plus contextual recommend coverage. The work here is awareness and E2E repair, not scope expansion.

### Phase C / 2 — Status Engine, Classification & Runtime Honesty

This is the critical path for fixing the M5.0 blocker:

- classification tags on every relevant check
- `workflowIds` where workflow-specific requirements apply
- Production Health derived only from `essential` and active `workflow_required`
- optional and inactive workflow requirements shown honestly without poisoning the health band
- stale deleted-project binding fixed so status follows the open project
- creator-oriented `ProductionHealthSummary` emitted from the API and surfaced in the UI

### Phase D / 3 — Creative Intelligence & Production Awareness

Add creator-facing recommendation intelligence based on real session and project context:

- next-step recommendations for the actual production stage
- plain-language explanation copy instead of raw runtime jargon
- truthful progress rollups for characters, storyboard, timeline, voice, spatial, Bible, continuity, and overall progress
- live inspect before recommendation display

### Phase E / 4 — UX Harmonization

Refine existing Co-Director UI so the creator sees:

- current Production Health
- current workflow readiness
- the next best step
- optional extras as optional

Advanced scoring, raw check lists, provider jargon, and diagnostic noise move behind progressive disclosure.

### Phase F / 5 — Playwright, Regression & Live Beta Certification Prep

Produce the implementation evidence package on live Beta `8760/8758`, including:

- Playwright coverage for classification, awareness, gating, project switch, reload, and workspace paths
- manual UX checklist
- final certification package prepared for binary milestone decision

## Planned Deliverables

All M5.3 release-gate deliverables live under `docs/release-gate/codirector-final/`.

- `CODIRECTOR_HARMONIZATION_AND_FINAL_BETA_READINESS.md`
- `CODIRECTOR_REPOSITORY_AUDIT.md`
- `CODIRECTOR_WORKSPACE_MATRIX.md`
- `CODIRECTOR_STATUS_CLASSIFICATION.md`
- `CODIRECTOR_RUNTIME_HONESTY.md`
- `CODIRECTOR_INTELLIGENCE_REPORT.md`
- `CODIRECTOR_PLAYWRIGHT_REPORT.md`
- `CODIRECTOR_MANUAL_UX_CHECKLIST.md`
- `CODIRECTOR_FINAL_CERTIFICATION.md`
- `README.md`

## Acceptance Criterion That Repairs The M5.0 Fail

The specific M5.0 failure is repaired when a **healthy Beta project with only optional extras missing** reports creator-facing status consistent with real production readiness:

- Production Health is `Excellent` or `Strong`
- Core Studio is operational
- the current workflow is ready if its actual required systems are healthy
- optional extras are listed as optional, available, or not needed
- missing optional components do **not** falsely surface as `Degraded` or `Blocked`

This is the core readiness target for M5.3. Until live Beta evidence proves it, certification remains pending.

## Definition Of Done

M5.3 is complete only when the primary owner can issue a **binary** certification in `CODIRECTOR_FINAL_CERTIFICATION.md`:

- **GO** if live Beta demonstrates harmonized classification, honest runtime status, creator-first summaries, proposal-gated recommendations, working workspace awareness, persistence after reload, and evidence-backed excellent or strong readiness when only optional extras are missing
- **NO-GO** if optional items still falsely degrade health, creator status remains fragmented or misleading, recommendations are dead or unsafe, or live Beta evidence does not hold on the open project

There is no implied partial certification in this kickoff brief. This document is readiness and execution guidance only.

## Key File Paths Expected To Be Touched

The plan and audits point to the following implementation surfaces as likely touch points:

- `studio-api/app/codirector/status/weighting.py`
- `studio-api/app/codirector/status/registry.py`
- `studio-api/app/codirector/status/types.py`
- `studio-api/app/codirector/session_context.py`
- `studio-api/app/codirector/tools/definitions.py`
- `studio-api/app/codirector/tools/execution.py`
- `studio-web/src/components/CoDirector/CoDirectorStatusPanel.tsx`
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `studio-web/src/core/workspaces.ts`
- `studio-web/src/core/productionMenu.ts`
- `studio-api/app/docker_runtime/registry.py`
- `studio-api/app/docker_runtime/contracts.py`
- `studio-web/src/dockerRuntime/contracts.ts`
- `studio-api/app/production_control/model_registry.py`
- `studio-web/src/components/CapabilityPanel.tsx`

These paths are listed as readiness-relevant scope markers, not as a claim that every file has already been changed.

## Primary Ownership Note

Primary ownership remains responsible for:

- freezing and protecting the shared contract
- coordinating parallel work without violating Law 16
- restarting Beta and leaving manual review ready
- integrating evidence into the final certification package
- issuing the only valid milestone verdict: `GO` or `NO-GO`

## Status Of This Document

This file is the **single authoritative Markdown readiness brief for M5.3 kickoff**. It does **not** certify implementation completion, does **not** overrule the current M5.0 `NO-GO`, and does **not** declare M5.3 `GO`. Implementation certification remains pending live Beta evidence.
