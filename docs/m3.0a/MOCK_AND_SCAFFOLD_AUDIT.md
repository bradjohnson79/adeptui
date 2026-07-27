# M3.0a Phase 0 — Mock and Scaffold Audit

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Date | 2026-07-26 |
| Scope | Production-reachable mock / fixture / scaffold / detect-only / fake-success patterns in `studio-api/`, `studio-web/`, `scripts/e2e-start.mjs` |
| Policy | Fixtures are OK **only** in isolated test infra (`tests/`, `e2e-start.mjs` + fixture server, env-gated CI adapters) |

Routers for `m28` / `m29` / `m213` / `m214` mount under `/api/codirector/*` (`studio-api/app/routers/codirector.py`); feature modules typically 404 unless their `STUDIO_FEATURE_*` flag is ON (defaults OFF). `/api/e2e/*` mounts only when `STUDIO_E2E=1` (`main.py`).

---

## 1. Environment flags

| Flag | Production default | Read location | Set / overridden by |
|------|-------------------|---------------|---------------------|
| `ADEPT_M28_FIXTURE_MODE` | unset → OFF | `studio-api/app/codirector/m28/__init__.py:fixture_mode_enabled` | `scripts/e2e-start.mjs` default `"1"`; tests |
| `ADEPT_M29_FIXTURE_MODE` | unset → OFF | `studio-api/app/codirector/m29/__init__.py:fixture_mode_enabled` | `e2e-start.mjs` default `"1"`; also accepted by M2.10b `fixture_mode_enabled` |
| `ADEPT_M210B_FIXTURE_MODE` | unset → OFF | `studio-api/app/codirector/m210b/flags.py:fixture_mode_enabled` | Not set in e2e-start (falls through to M29 flag) |
| `ADEPT_MOCK_IMAGEGEN` | unset → OFF | `studio-api/app/codirector/executive/imagegen_adapter.py` | Docs/tests; **does not enable silent completion** |
| `ADEPT_CODIRECTOR_PROVIDER` | unset → `ollama` (mock ignored unless E2E) | `studio-api/app/codirector/service.py:active_provider_id` | e2e-start default `"mock"` |
| `STUDIO_E2E` | unset → OFF | many modules | e2e-start forces `"1"` |
| `ADEPT_PACK_PROVIDER` | `github_releases` (`pack_settings.py`) | pack manifests / download queue | e2e-start default `"fixture_http"` |
| `ADEPT_PACK_FIXTURE_BASE_URL` | unset | `fixture_http` provider | e2e-start → `http://{host}:8765` |
| `ADEPT_CODIRECTOR_MOCK_SCENARIO` | `healthy` | mock provider / tools execution | E2E scenario control |

### `scripts/e2e-start.mjs` fixture-related defaults

| Variable | Default |
|----------|---------|
| `STUDIO_E2E` | `"1"` |
| `ADEPT_PACK_PROVIDER` | `"fixture_http"` |
| `ADEPT_PACK_FIXTURE_BASE_URL` | `http://{STUDIO_API_HOST}:{E2E_FIXTURE_PORT}` (8765) |
| `ADEPT_CODIRECTOR_PROVIDER` | `"mock"` |
| `ADEPT_M28_FIXTURE_MODE` | `"1"` |
| `ADEPT_M29_FIXTURE_MODE` | `"1"` |
| M2.8 feature flags | default `"1"` (radar, sandbox, virtual stage, shot profiles, recipe, location spin) |
| M2.9 production flags | default `"0"` unless overridden |
| `ADEPT_M210B_FIXTURE_MODE` | **not set** |
| `ADEPT_MOCK_IMAGEGEN` | **not set** |
| Fixture HTTP server | spawned (`e2e-fixture-server.mjs`) |

---

## 2. Findings table

**Production-reachable YES** = can activate with `STUDIO_E2E` unset (may still need a feature flag ON).

Severity: CRITICAL / HIGH / MED / LOW. Remediation required for M3.0a noted per row.

### 2.1 Env gates and E2E / pack

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| ENV-01 | `m29/providers.py:wants_fixture` | fixture_mode | **YES** | **CRITICAL** | Require env (or E2E); reject client `fixtureComplete` alone | `fixture_mode_enabled() or payload.get("fixtureComplete")` |
| ENV-02 | `executive/handlers.py` M2.9 image path | force_mock / fixture | **YES** | **CRITICAL** | Sanitize ingress; env-gate fixtureComplete | Routes when `m29` / `fixtureComplete` set |
| ENV-03 | `m28/__init__.py:fixture_mode_enabled` | fixture_mode | YES* | MED | Keep env-only | *When M2.8 flags ON |
| ENV-04 | `m29/__init__.py:fixture_mode_enabled` | fixture_mode | YES* | MED | Keep env-only | *When M2.9 flags ON |
| ENV-05 | `m210b/flags.py:fixture_mode_enabled` | fixture_mode | YES* | MED | Prefer dedicated M210B CI gate | Accepts M29 or M210B env |
| ENV-06 | `executive/imagegen_adapter.py` | e2e_only_mock | NO | LOW | None — refuses fake success | Warns when mock env set; polls real jobs |
| ENV-07 | `codirector/service.py:active_provider_id` | e2e_only_mock | NO | LOW | None | mock→ollama outside E2E; `build_provider("mock")` raises |
| ENV-08 | `setup/pack_settings.py` | pack_fixture | YES | LOW | Warn if `fixture_http` outside E2E | Default `github_releases` |
| ENV-09 | `scripts/e2e-start.mjs` | e2e_only_mock | NO | LOW | Keep isolated | Full fixture stack for Playwright |
| E2E-01 | `main.py` + `routers/e2e.py` | e2e_only_mock | NO | LOW | None | `/api/e2e/*` only when STUDIO_E2E |
| E2E-02 | `setup/download_sources/security.py:_dev_fixture_mode` | e2e_only_mock | NO | LOW | None | Localhost HTTP only in E2E |
| E2E-03 | `tools/execution.py:_e2e_execution_fault` | e2e_only_mock | NO | LOW | None | Forced tool faults for Playwright |
| E2E-04 | `source_manager/providers/fixture.py` | pack_fixture | NO | LOW | None | Fixture provider for pack E2E |
| E2E-05 | `setup/pack_providers/fixture_http.py` | pack_fixture | NO | LOW | None | Selected via env |
| PACK-01 | pack manifests fixture_http branch | pack_fixture | YES | MED | Block fixture_http unless E2E | Operator can set env manually |
| PACK-02 | `source_manager/downloads/queue.py` fixture prefer | pack_fixture | YES | MED | Same as PACK-01 | |
| CODIR-01 | `providers/mock.py:MockCoDirectorProvider` | e2e_only_mock | NO | LOW | None | Deterministic chat/tools |
| CODIR-02 | `intelligence/specialist_runner.py` E2E skip | e2e_only_mock | NO | LOW | None | Skips real provider in E2E |
| IMG-01 | `imagegen_adapter.should_use_mock_imagegen` | fake_success | NO | LOW | None | Always False |
| IMG-02 | `imagegen_adapter.poll_imagegen_job` | fake_success | NO | LOW | None | Raises on Comfy/queue failure |
| IMG-03 | `executive/capability.py` | fake_success | NO | LOW | None | Does not fake comfyui.health |
| IMG-04 | `queue_worker.py` | — | NO | LOW | None | No mock/fixture success paths found |

### 2.2 Vision + web defaults

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| VIS-01 | `vision/providers/__init__.py:get_provider` | force_mock | **YES** | **HIGH** | Block `provider=mock` outside E2E | Unknown/mock → MockVisionProvider |
| VIS-02 | `vision/providers/mock.py` | honesty_mocked | **YES** | **HIGH** | E2E-only or explicit fixture label | Named fixture profiles |
| VIS-03 | vision validators (`provider_id == "mock"`) | honesty_mocked | **YES** | MED | Gate mock branch on E2E | Multiple validators |
| VIS-04 | `vision/api.py` `/validate` | honesty_mocked | **YES** | **HIGH** | Reject mock provider in production | Accepts `provider: mock` when flag ON |
| VIS-05 | `CoDirectorValidationWorkspace.tsx:runValidate` | honesty_mocked | **YES** | **HIGH** | Default UI to local provider | Sends `provider:"mock"`, `fixtureProfile:"warnings"` |
| WEB-01 | `CoDirectorSession.tsx` offline plan fallback | scaffold | **YES** | MED | Never present as executed | Scaffold plan when intelligence unavailable |
| WEB-02 | `EnvironmentStudioWorkspace.tsx` | fixture_mode | **YES** | MED | Default `fixture:false` in UI | Calls m213 with fixture true |
| WEB-03 | `EnvironmentViewport.tsx` | scaffold | **YES** | LOW | Label only | FIXTURE/PROXY badge |
| WEB-04 | `UnifiedExperienceWorkspace.tsx` | honesty_mocked | **YES** | LOW | Label only | Hitchhiker smoke copy |
| WEB-05 | `SetupWizard.tsx` `__ADEPT_E2E_FORCED_PATH__` | e2e_only_mock | NO | LOW | None | E2E forced browse path |

### 2.3 M2.8

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| M28-01 | `m28/radar/service.py:discover` | fixture_mode | **YES** | MED | Env for fixtures; refuse live silently | Without env: empty + message |
| M28-02 | `m28/fixtures.py` discoveries | fixture_mode | YES* | MED | Env-gate only | Deterministic registry |
| M28-03 | `m28/sandbox/service.py:execute_approved_install` | **fake_success** | **YES** | **CRITICAL** | Real install or refuse | Writes `installed.fixture`; status installed |
| M28-04 | `m28/sandbox/service.py:validate` | **fake_success** | **YES** | **CRITICAL** | Real validate or Blocked | `ok:true`, `runtime:fixture-sandbox` |
| M28-05 | `m28/sandbox/service.py:detect` | fixture_mode | **YES** | MED | Label fixtureMode | Uses simulate detect |
| M28-06 | `m28/location_spin/service.py:spin_camera` | **fake_success** | **YES** | **HIGH** | Real frames or refuse | Always emits `fixture-spin-*` assetIds |
| M28-07 | `m28/location_spin/service.py:plan` | fixture_mode | YES* | LOW | Metadata only | Sets fixtureMode from env |
| M28-08 | `m28/recipes/service.py:complete_stage` | **fake_success** | **YES** | **HIGH** | Real stage or Blocked | Always `mock_generation_result()` |
| M28-09 | `m28/fixtures.py:mock_generation_result` | fake_success | YES* | MED | Env-gate recipe completion | Used by recipe stages |
| M28-10 | `m28/compat/service.py:evaluate` | scaffold | YES* | LOW | OK — heuristic on metadata | No fake generation |
| M28-11 | `m28/virtual_stage/service.py` | scaffold | YES* | LOW | OK — CRUD | No generation mocks |
| M28-12 | `m28/api.py` SandboxCreateBody default name | scaffold | YES* | LOW | Rename default | `"Fixture Sandbox"` |

### 2.4 M2.9 `force_mock` / `fixtureComplete`

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| M29-01 | `m29/fixtures.py` | fixture_mode | YES* | MED | Env-only activation | Never claims production_ready |
| M29-02 | `m29/image/service.py` | fixture_mode | YES* | **CRITICAL** | Fix wants_fixture payload bypass | Env or pre-enqueued fixtureComplete |
| M29-03 | `m29/frames/service.py` | fixture_mode | YES* | HIGH | Same | |
| M29-04 | `m29/video/service.py` | fixture_mode | YES* | HIGH | Same | |
| M29-05 | `m29/audio/service.py` | fixture_mode | YES* | HIGH | Same; refuses generate outside fixture | |
| M29-06 | `m29/lipsync/service.py` | fixture_mode | YES* | HIGH | Same | |
| M29-07 | `m29/render/service.py` | fixture_mode | YES* | HIGH | Same | |
| M29-08 | `m29/editing/service.py:propose_edit` | **fake_success** | **YES** | **HIGH** | Real proposal or Blocked when env off | Always returns `fixture_edit_result` |
| M29-09 | `m29/editing/service.py:execute_job` / apply | fixture_mode | YES* | HIGH | Payload gate fix | status `applied` when fixture mode |
| M29-10 | `m29/control/service.py:decompose` | scaffold | **YES** | MED | Real planner or label scaffold | Always `fixture_control_plan()` |
| M29-11 | `m29/control/service.py` enqueue | fixture_mode | YES* | MED | Don't set fixtureComplete without env | Sets when env ON |
| M29-12 | `m29/providers.py` real bridges | fake_success | NO | LOW | None — refuses without Comfy | Real provider bridge |

### 2.5 M2.10b

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| M210B-01 | `m210b/adapters/fixture_ci.py` | fixture_mode | YES* | MED | CI-only OK if env-gated | Deterministic WAV |
| M210B-02 | `m210b/adapters/generic_sandbox.py` | scaffold | YES* | LOW | OK — raises unavailable | Honest stub |
| M210B-03 | `m210b/adapters/kokoro.py` | scaffold | YES* | LOW | OK — refuses without install | Real when installed |
| M210B-04 | `m210b/registry.py:get_adapter` | fixture_mode | YES* | MED | Fixture adapter CI-only | FixtureCi under env |

### 2.6 M2.13 force_mock / fixture request paths

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| M213-01 | `m213/api.py:ConceptBody.forceMock` | **force_mock** | **YES** | **CRITICAL** | Default `forceMock=False` | Default `True` |
| M213-02 | `m213/concepts.py:generate_concept` | **force_mock** | **YES** | **CRITICAL** | Same; require real-provider opt-in | Defaults mock unless `STUDIO_M213_REAL_CONCEPT_PROVIDER` |
| M213-03 | `m213/api.py:SpinBody.fixture` | fixture_mode | **YES** | **HIGH** | Default `fixture=False` | Default `True` |
| M213-04 | `m213/camera_spin.py` | force_mock | **YES** | **HIGH** | Refuse synthetic frames by default | Generates fixture frames when fixture true |
| M213-05 | `m213/api.py:ReconstructBody.adapter` | fixture_mode | **YES** | **HIGH** | Default `detect` / auto | Default `"fixture"` |
| M213-06 | `m213/reconstruction.py:FixtureReconstructionAdapter` | fixture_mode | **YES** | MED | OK if explicit | Honest labels |
| M213-07 | `m213/reconstruction.py:OptionalBinaryAdapter` | detect_only | **YES** | LOW | OK — refuses fake real recon | Detection-only scaffold |
| M213-08 | `m213/route_b.py` import fixture bypass | fixture_mode | **YES** | MED | Require explicit fixture flag | `fixture:true` bypasses validation |
| M213-09 | `m213/persistence.py:end_to_end_guided` | **force_mock** | **YES** | **HIGH** | Gate on STUDIO_E2E | Hardcodes `force_mock=True` |
| M213-10 | `m213/api.py` `/e2e/guided` | fixture_mode | **YES** | MED | Gate on STUDIO_E2E | Name implies E2E but only needs M2.13 flag |
| M213-11 | `m213/protocol.py` | scaffold | YES* | LOW | OK — honest status categories | Scaffold notes |

### 2.7 M2.14 honesty mocked | fixture | scaffolded

All handlers below are production-mounted at `/api/codirector/m214/*` when `STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1=1` (default OFF). Responses carry honesty labels.

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| M214-01 | `m214/api.py` routes | scaffold | YES* | MED | Keep flag OFF until real providers | Partial wiring |
| M214-02 | `m214/idea_first.py` | honesty_mocked | YES* | MED | Real Storyteller or keep labeled | `honesty:"mocked"` |
| M214-03 | `m214/attachments.py` | honesty_mocked | YES* | MED | Same | |
| M214-04 | `m214/storyteller.py` | honesty_mocked | YES* | MED | Same | |
| M214-05 | `m214/sound_producer.py` | honesty_mocked | YES* | MED | Same | |
| M214-06 | `m214/messaging.py` | honesty_mocked | YES* | LOW | Same | Required exchange scaffolds |
| M214-07 | `m214/meetings.py` | honesty_mocked | YES* | LOW | Same | |
| M214-08 | `m214/conflicts.py` | honesty_mocked | YES* | LOW | Same | |
| M214-09 | `m214/media.py` + hitchhiker | honesty_mocked / fixture | YES* | MED | Same | Creates mocked/fixture media cards |
| M214-10 | `m214/plan_view.py` | honesty_scaffolded | YES* | LOW | Same | `honesty:"scaffolded"` |
| M214-11 | `m214/approvals.py` | honesty_scaffolded | YES* | LOW | Same | Approval center scaffolded |
| M214-12 | `m214/contracts.py` + `db.py` | honesty_mocked | YES* | LOW | Schema defaults | DB default `'mocked'` |
| M214-13 | `m214/api.py:MediaBody.honesty` | honesty_mocked | YES* | MED | Disallow client `real` without proof | Default `mocked` |
| M214-14 | `m214/kinds.py` CAPABILITY_IDS | scaffold | YES* | MED | Register truthfully until wired | All `partially_wired` |

### 2.8 Setup detect_only + executive pass-through

| ID | Location | Pattern | Prod? | Sev | M3.0a remediation | Notes |
|----|----------|---------|-------|-----|-------------------|-------|
| SETUP-01 | `setup_wizard.py` catalog | detect_only | **YES** | LOW | OK by design | comfyui, ffmpeg, python, ollama, fal_key |
| SETUP-02 | `setup/catalog.py` | detect_only | **YES** | LOW | OK | python component |
| SETUP-03 | `setup/orchestrator.py` detect_only skip | detect_only | **YES** | LOW | OK | No auto-install |
| SETUP-04 | `setup/component_kinds.py` | detect_only | **YES** | LOW | OK | KIND_DETECT_ONLY |
| EXEC-01 | `executive/handlers.py:_handle_validate` | force_mock | NO | LOW | None | Rejects provider=mock |
| EXEC-02 | `executive/handlers.py` sandbox install | **fake_success** | YES* | **CRITICAL** | Real install worker | Delegates to M28 fixture marker |
| EXEC-03 | `executive/handlers.py` sandbox validate | **fake_success** | YES* | **CRITICAL** | Real validate | Delegates to M28 fixture validate |
| EXEC-04 | `executive/handlers.py` recipe stage | **fake_success** | YES* | HIGH | Real stage or Blocked | Via RecipeService mock result |
| EXEC-05 | executive M2.9 delegates | fixture_mode | YES* | HIGH | Central payload sanitization | All M2.9 job types |

---

## 3. Priority remediation for M3.0a

1. **CRITICAL:** `wants_fixture()` must not honor client `fixtureComplete` alone; strip at executive ingress.
2. **CRITICAL:** M2.13 API defaults — `forceMock=False`, `fixture=False`, `adapter=detect|auto`.
3. **CRITICAL:** M2.8 sandbox install/validate — refuse or Blocked without real execution (remove `installed.fixture` / `fixture-sandbox` success in production).
4. **HIGH:** M2.8 location spin + recipe `complete_stage` — env-gate or refuse synthetic assets/results.
5. **HIGH:** Vision — block `provider=mock` outside E2E; fix UI default in `CoDirectorValidationWorkspace.tsx`.
6. **HIGH:** Gate `/m213/e2e/guided` on `STUDIO_E2E`.
7. **HIGH:** M2.9 `propose_edit` — stop returning fixture results when env off.
8. **MED:** M2.14 — keep unified-experience flag OFF until real providers; preserve honesty labels.
9. **MED:** Pack `fixture_http` — refuse outside E2E.

---

## 4. Acceptable fixture surfaces (isolated test infra only)

| Surface | Why OK |
|---------|--------|
| `tests/**` monkeypatch of fixture env vars | Isolated unit/integration |
| `scripts/e2e-start.mjs` + fixture HTTP server | Playwright supervisor only |
| Co-Director `MockCoDirectorProvider` under `STUDIO_E2E` | Hard-gated in `service.py` |
| Pack `fixture_http` when E2E sets provider | Isolated pack install E2E |
| `FixtureCiAudioAdapter` under explicit fixture env | CI audio without claiming production |
| imagegen_adapter refusal of silent mock completion | Correct honesty |

**Not acceptable for production acceptance:** any path returning `generated` / `applied` / `installed` / `validated` without real provider execution, especially from API defaults or client payload rather than explicit CI env.

---

## 5. Finding counts

| Group | Count |
|-------|------:|
| ENV | 9 |
| E2E | 5 |
| PACK | 2 |
| CODIR | 2 |
| IMG | 4 |
| VIS | 5 |
| WEB | 5 |
| M28 | 12 |
| M29 | 12 |
| M210B | 4 |
| M213 | 11 |
| M214 | 14 |
| SETUP | 4 |
| EXEC | 5 |
| **Total findings** | **94** |
| Production-reachable YES (incl. flag-gated YES*) — approximate unique IDs with Prod?=YES or YES* | **~70** |
| CRITICAL severity | **9** |
| HIGH severity | **22** |

---

## 6. Remediation log

Appended after the Phase 1 and Phase 3 remediation passes. The findings table above is the
Phase 0 snapshot and is deliberately left as written; this section records what changed
afterwards. Tip SHA at time of writing: `e2f3ae8a9750d44ec37b64361cbede6a95351d3c`.

### 6.1 CRITICAL - closed in Phase 1

| ID | Finding | Resolution | Evidence |
|----|---------|------------|----------|
| M29-01 .. M29-03, EXEC-01 | `wants_fixture()` honored a client-supplied `fixtureComplete`, so any caller could ask for a fake success | `fixtureComplete`, `mockAdapter` and `forceMock` are stripped at executive ingress unless the environment enables fixtures | `executive/handlers.py::_sanitize_ingress_payload`, `m29/providers.py::sanitize_client_payload` |
| M213-01 .. M213-03 | M2.13 API defaults allowed mock success (`forceMock=True`) | Defaults are `forceMock=False`, `fixture=False` | `m213/api.py` request models |
| M28-03 | Sandbox install wrote an `installed.fixture` marker and reported the model installed | Refuses outside `ADEPT_M28_FIXTURE_MODE` / `STUDIO_E2E` | `m28/sandbox/service.py` |
| M28-04 | Sandbox validate reported `runtime: fixture-sandbox` as a validated run | Refuses outside fixture mode | `m28/sandbox/service.py` |
| VIS-01 | `provider=mock` reachable in production | `get_provider` raises `VisionProviderUnavailable` outside E2E; schema default is `local` | `vision/providers/__init__.py`, `vision/schemas.py` |

### 6.2 HIGH - closed in Phase 3

Each of these was a path that reported work as done without doing it. The fix is the same
shape in every case: refuse loudly outside an explicitly enabled fixture environment, rather
than succeed quietly inside a production one.

| ID | Finding | Resolution | Test |
|----|---------|------------|------|
| M213-04 | `camera_spin` synthesised `fixture-spin-*` frames and returned them as a camera-spin environment | `synthetic_frames_allowed()` gates both the frame synthesis and an explicit `fixture=True` request; `PermissionError` becomes HTTP 503 at the route | `test_camera_spin_refuses_synthetic_frames_outside_fixture`, `test_camera_spin_refuses_fixture_request_outside_fixture_env`, `test_camera_spin_accepts_real_frames_without_fixture_env` |
| M213-05 | `ReconstructBody.adapter` defaulted to `"fixture"`, so the default reconstruction was a mock success | Default is now `"detect"`; `resolve_adapter_name` picks a real adapter or fails, and only an explicit `"fixture"` reaches the fixture adapter | `test_reconstruct_adapter_defaults_to_detect` |
| M28-06 | `location_spin.spin_camera` emitted `fixture-spin-*` assets as location coverage | Refuses unless `fixture_execution_enabled()`; HTTP 503 at the route | `test_location_spin_refuses_synthetic_coverage_outside_fixture` |
| M28-08 / EXEC-04 | Recipe `complete_stage` returned `fake_success` with a `fixture-asset-*` id, and the executive recorded the stage as complete | Refuses outside fixture mode; the executive handler catches the refusal and reports **Blocked** rather than failing the job or claiming success | `test_recipe_stage_refuses_mock_completion_outside_fixture`, `test_recipe_stage_handler_reports_blocked_outside_fixture` |
| M29-08 | `propose_edit` returned an `m29_fixture` proposal regardless of environment | Outside fixture mode it validates and echoes the caller's own ops, and raises `ValueError` (HTTP 400) on an empty op list; the fixture proposal is reachable only under `ADEPT_M29_FIXTURE_MODE` | `test_propose_edit_outside_fixture_is_not_a_fixture_result` |
| M213-06 | `/m213/e2e/guided` runs fixture adapters and was reachable in production | Returns HTTP 403 unless `STUDIO_E2E` | `m213/api.py`, covered in the M2.13 suite |
| VIS-05 | `CoDirectorValidationWorkspace.tsx` requested `provider: "mock"` | Requests `provider: "local"` | `studio-web/src/components/CoDirector/CoDirectorValidationWorkspace.tsx` |

Two supporting helpers were added so the gate is expressed once rather than re-derived at
each call site: `m28/fixtures.py::fixture_execution_enabled()` and
`m213/flags.py::fixtures_enabled()`. Both accept either the module's own fixture flag or
`STUDIO_E2E`.

### 6.3 Still open

| ID | Finding | Severity | Why it is still open |
|----|---------|---------:|----------------------|
| M214-* | 14 findings across the unified-experience layer, honestly labelled `mocked` / `fixture` / `scaffolded` | MED | The flag defaults OFF and the labels are accurate. Closing these means building the providers, which is M3.0b work, not remediation. |
| M210B-* | Audio adapters other than Kokoro | MED | `generic_sandbox` raises unavailable and `fixture_ci` is env-gated. Correct behaviour for unwired providers. |
| PACK-* | `fixture_http` pack source | MED | Env-gated to E2E. Item 9 on the Phase 0 priority list; the gate holds, so this is hygiene rather than exposure. |
| IMG-01 / IMG-02 | `ADEPT_MOCK_IMAGEGEN` | - | Already correct at Phase 0: the adapter refuses to fabricate a completion even with the variable set. Recorded here so it is not mistaken for an open item. |

### 6.4 What the remediations do not do

They do not make any generative platform work. Every fix in this log converts a false success
into an honest refusal, which improves the truthfulness of the system and its test suite
without adding a single real artifact. `REAL_ARTIFACT_VERIFICATION.md` is the counterpart to
this section and should be read with it: after all nine CRITICAL and seven HIGH closures, the
number of generative artifacts produced by a real provider during M3.0a is still zero.

### 6.5 Closed in M3.0b - job queue restart recovery

Appended 2026-07-26 at tip `e2f3ae8a9750d44ec37b64361cbede6a95351d3c`.

M3.0a left `RST = FAIL` across every queue-backed platform in
`FULL_STACK_WIRING_MATRIX.md`: the studio queue is an in-process asyncio queue, so any job
row left in `queued` or `running` belonged to a process that was gone and would never be
touched again. Those jobs sat in a non-terminal state forever.

`JobQueue.recover_interrupted()` in `studio-api/app/queue_worker.py` now runs from the
FastAPI lifespan in `studio-api/app/main.py`, before the worker starts. On startup it:

- re-enqueues recent `queued` jobs, so the work resumes;
- marks `running` jobs `failed` with stage `interrupted`, with a message stating the work
  was interrupted by an API restart rather than that it failed on its own merits. A
  provider-side render held by a dead process cannot be resumed by a new one, and saying
  which of the two happened is the whole point;
- marks `queued` jobs older than `STUDIO_JOB_RECOVERY_MAX_AGE_HOURS` as interrupted rather
  than silently starting stale work;
- leaves `done`, `failed` and `cancelled` untouched;
- records each action in the job's `history_json` for audit.

Covered by `studio-api/tests/test_job_queue_recovery.py`, 7 tests, all passing. Verified not
to disturb the rest of the suite: the 20 pre-existing pytest failures are identical with and
without that file present.

Consistent with section 6.4, this adds no generative artifact. It converts a silently
abandoned job into an honest, auditable outcome. Full M3.0b context in
`docs/M3.0B_SITUATION_BETA_TASK_REPORT.md`.
