# Phase 0 Foundation Acceptance Report

**Date:** 2026-07-23  
**Decision:** ACCEPTED WITH CONDITIONS  
**Phase 1 authorization:** GRANTED WITH CONDITIONS  
**Setup Wizard refactor acceptance:** ACCEPTED WITH CONDITIONS  

Historical note: earlier in this same day the report briefly stood at Setup Wizard
**PROVISIONAL** / Phase 1 **NOT GRANTED** pending the final runtime gate. That
status is superseded by the **Final Runtime Verification Addendum** below.

## Executive sign-off

The Phase 0 safety foundations and Setup Wizard refactor are accepted with
bounded non-blocking conditions documented in
`docs/audit/phase0-final-verification.md`. Automated backend/frontend gates
passed with captured exit codes; read-only Setup API probes succeeded; browser
Setup Wizard hierarchy, Ready-card actions, Advanced collapsed default, and
checkpoint Escape/Cancel were verified in-session. One honesty defect (stale
`path_not_configured` diagnostic) was fixed with a focused regression before
sign-off.

Phase 1 is **authorized with conditions**. Remaining conditions are bounded
(native Browse dialog not exercised, some failure-state UI live exercises and
200% zoom deferred). Do not treat this as a release-sign for live unattended
provisioning; live `POST /api/setup/prepare` was intentionally not run.

## Evidence basis

- Phase 0 completion record: `docs/PHASE0_COMPLETION.md`
- Executed baseline matrix: `docs/audit/BASELINE_SMOKE_TESTS.md`
- Machine-readable baseline log:
  `docs/audit/phase0-baseline-results.json`
- Recovery procedure and evidence: `docs/phase0/RECOVERY.md`
- Architecture boundary record:
  `docs/phase0/ARCHITECTURE_BOUNDARIES.md`
- Setup Wizard target and acceptance criteria:
  `docs/SETUP_WIZARD_REFACTOR.md`
- Setup Wizard focused tests:
  `studio-api/tests/test_setup_refactor.py`

The executed Phase 0 baseline identifies branch `feat/director-workspace` at
commit `2c5f61d574f27aed8c4f4adc70e9c993bb862aa1`. The working tree was
intentionally dirty. Therefore, this report signs off the recorded evidence and
the inspected implementation; it is not a clean-commit provenance statement.

## Foundation decisions

### Backup and restore

- **Status:** Complete.
- **Evidence:** Three backup safety tests passed. A temporary-fixture
  create/verify/restore drill matched manifests, passed SQLite integrity, and
  reproduced the expected row and project without using production data.
- **Remaining risks:** Recovery has not been exercised against every
  machine-specific project layout. Operator discipline is still required for
  restore destinations and secret handling.

### Migration safety

- **Status:** Complete for the Phase 0 boundary.
- **Evidence:** M001 idempotence, checksum, and foreign-key tests passed. The
  migration runner is transactional, forward-only, and not invoked at startup.
- **Remaining risks:** No production migration or reader/writer cutover has
  occurred. Rollback metadata is informational; recovery relies on verified
  backup and restore rather than destructive reverse DDL.

### Generation provider layer

- **Status:** Complete for contracts; implementation deferred.
- **Evidence:** Provider-neutral lifecycle, capability, authentication,
  execution, cancellation, result, and cost-ownership Protocols exist for
  Local, External API, and Adept Cloud provider kinds.
- **Remaining risks:** No external provider is implemented, selected,
  authenticated, or called. Production generation paths remain unchanged.

### Workflow registry

- **Status:** Complete for inventory and metadata validation.
- **Evidence:** The registry inventories current LTX, WAN, LatentSync, and image
  builders with template version, provider kinds, required inputs,
  capabilities, and ComfyUI compatibility metadata.
- **Remaining risks:** Registry entries are not the production dispatch path.
  Validation is metadata-only and does not invoke builders or probe ComfyUI.

### Desktop platform layer

- **Status:** Complete for host-neutral contracts.
- **Evidence:** Interfaces cover filesystem, settings, secrets, windows,
  notifications, dialogs, clipboard, temporary files, and constrained OS
  integration without Electron imports or arbitrary command execution.
- **Remaining risks:** Electron and other concrete host implementations are
  deferred and no production desktop behavior has been cut over.

### Repository layer

- **Status:** Complete for contracts and boundary markers.
- **Evidence:** Protocols exist for Project, Scene, Profile, Generation,
  Timeline, Asset, Job, and Memory repositories, with inert SQLite boundary
  markers and factory contracts.
- **Remaining risks:** Existing SQLAlchemy sessions and route access remain
  authoritative. No repository cutover or non-SQLite implementation exists.

### Infrastructure adapters

- **Status:** Complete for additive wrappers.
- **Evidence:** Unwired ComfyClient and validated FFmpeg boundaries preserve the
  existing behavior while excluding arbitrary shell/FFmpeg arguments.
- **Remaining risks:** Production call sites are unchanged, so adapter
  integration behavior remains unproven.

### Workspace registry and compatibility

- **Status:** Complete with legacy compatibility retained.
- **Evidence:** Centralized workspace metadata, query aliases,
  `CoDirectorContext`, and default-off frontend feature flags were delivered.
  The captured TypeScript diagnostics do not occur in the new Phase 0
  core/workspace files.
- **Remaining risks:** Legacy tab IDs and routes remain intentionally supported.
  Deep navigation and first-time-user click-through tests remain manual.

### Feature flags

- **Status:** Complete for Phase 0.
- **Evidence:** Backend and frontend flags default off for unified generation,
  story, scene sheets, jobs, resources, and future rollout. New architecture
  paths remain additive and unwired.
- **Remaining risks:** Rollout behavior and flag interaction are not production
  tested because no cutover is authorized.

### Smoke-test harness

- **Status:** Complete with captured baseline exceptions.
- **Evidence:** Python compilation passed; the recorded backend suite passed
  9/9; isolated API startup and three backend smoke tests passed with
  `production_data_used: false`; API and web returned HTTP 200 in the executed
  baseline.
- **Remaining risks:** TypeScript and the frontend build exited 2 on the same 15
  diagnostics in `AssistantPanel.tsx`, `AvatarStudioWorkspace.tsx`,
  `ProjectHome.tsx`, and `Home.tsx`. Lint and deep product journeys were not
  captured as passes.

## Setup Wizard refactor acceptance addendum

### Implemented and statically evidenced

- Status-first Required and Optional component cards.
- Summary counts and overall readiness.
- One primary card action, with maintenance controls under Advanced.
- Prepare-plan confirmation and operation polling.
- Checkpoint dialogs for paths, licenses, elevation, credentials, and manual
  steps, including shared close/cancel controls.
- Path checkpoints use Adept recommended path + Browse (no free-typing primary UX).
- Canonical backend states, diagnostics, verification, operation locking,
  atomic schema-v2 state, and legacy endpoint/state compatibility.
- Path persistence no longer races status refresh into empty `model_locations`.
- Focused backend tests in `studio-api/tests/test_setup_refactor.py` cover
  canonical states, model verification, diagnostics, planning, operation
  locking/checkpoints, cancel, suggested path, status-refresh race, license
  acceptance, active-operation status, legacy-link honesty, atomic state, and
  endpoint wiring.

### Runtime verified in this continuation (2026-07-23)

- Dev servers: API `http://127.0.0.1:8742` and Vite `http://127.0.0.1:5173`
  both HTTP 200.
- `GET /api/setup/components/pack_essential_photoreal/suggested-path` → 200 with
  Adept Comfy Shared models path and `path_selector=directory`.
- OpenAPI registers `POST /api/setup/browse-path` and the suggested-path route.
- Persisting the suggested path into setup state succeeded; `/api/setup/state`
  showed
  `model_locations.pack_essential_photoreal` set to the recommended directory.
- Project venv: `pytest tests/test_setup_refactor.py -q` → **13 passed**.
- Native `POST /api/setup/browse-path` was intentionally not invoked (opens an
  OS folder/file dialog).

### Not accepted as fully runtime-proven

- A complete browser acceptance pass could not be finished in this agent session
  (browser MCP tabs would not stay open). Earlier pre-restart UI checks had
  confirmed close/cancel and recommended-path selection behavior against a stale
  API; those UI checks need a clean post-restart retest.
- TypeScript, Vite production build, focused lint, and Python compile were not
  re-executed as part of this continuation.
- Expanded backend suite beyond `test_setup_refactor.py` was not run here.
- No clean-machine, interrupted/resumed, offline, insufficient-disk,
  permission-denied, invalid-path, or partial-model scenario was run.
- No live `POST /api/setup/prepare` was issued, avoiding an unverified
  installation against the current machine.

### Known acceptance gaps

- No frontend or end-to-end Setup Wizard test suite exists.
- Disk, permission, connectivity, cancellation, secret/log redaction, and
  update-now/later paths do not have complete focused automated coverage.
- Several automated install/repair paths remain staged or machine-dependent;
  interface presence is not evidence of successful provisioning.
- The design's first-time-user 10-second comprehension target has not been
  measured.

## Prior decision (superseded by Final Runtime Verification Addendum)

Earlier the same day, Phase 0 foundations were **ACCEPTED WITH CONDITIONS** with
Setup Wizard still **PROVISIONAL** and Phase 1 **NOT GRANTED**, citing incomplete
runtime evidence and a prior 15-diagnostic frontend baseline. Those remaining
gates were executed in the Final Runtime Verification Addendum below; the prior
15 TypeScript diagnostics are **resolved** (`tsc -b` exit 0). Native Browse and
a subset of failure/a11y live exercises remain documented conditions rather than
authorization blockers.

---

## Final Runtime Verification Addendum

**Evidence:** `docs/audit/phase0-final-verification.md`,  
`docs/audit/phase0-final-verification-results.json`  
**Gate date:** 2026-07-23  
**Identity:** branch `feat/director-workspace`, commit
`2c5f61d574f27aed8c4f4adc70e9c993bb862aa1`, working tree dirty (preserved).

### Gate results (captured exit codes)

| Gate | Exit | Detail |
|------|------|--------|
| `python -m compileall app tests` | 0 | OK |
| Focused `tests/test_setup_refactor.py` (final) | 0 | **20 passed** |
| Full `studio-api` pytest (final) | 0 | **29 passed** |
| `npx tsc -b` | 0 | **0** diagnostics (prior 15 baseline **resolved**) |
| Focused oxlint (eslint absent) | 0 | SetupWizard/App/ProjectEditor/api/setup |
| `npm run build` | 0 | OK |
| Read-only Setup API probes | HTTP 200 | health, status, detect, state, prepare/plan, suggested-path, OpenAPI browse-path |
| Live `POST /api/setup/prepare` | not run | hard constraint |
| Native Browse dialog | deferred | non-blocking |

### Defect corrected in this gate

Stale cached diagnostics in `build_status` could report `path_not_configured`
after a pack path was auto-bound / persisted. Fixed in
`studio-api/app/setup/status.py` with regression
`test_status_refreshes_stale_path_not_configured_diagnostic`.

### Outcome B

```text
Decision: ACCEPTED WITH CONDITIONS
Setup Wizard refactor acceptance: ACCEPTED WITH CONDITIONS
Phase 1 authorization: GRANTED WITH CONDITIONS
```

Remaining conditions are clearly non-blocking, bounded, documented, and do not
compromise safety, data integrity, compatibility, or Phase 1 architecture work:

1. Native OS Browse dialog not interactively confirmed.
2. 200% zoom accessibility not re-captured after the final server restart.
3. Needs Attention / Update Available live card states statically inspected only
   (host was overall Ready).
4. No live prepare / real installs (hard gate constraint).

Phase 1 may proceed under these conditions. Do not begin Phase 1 implementation
in the same task that produced this addendum; stop after report and
recommendation.
