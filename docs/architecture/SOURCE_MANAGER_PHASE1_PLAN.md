# Source Manager — Phase 1 Architecture Plan

**Date:** 2026-07-24  
**Branch:** `phase1/source-manager-foundation`  
**Baseline:** Phase 0.5 complete (17/17 critical E2E, 19 download-source unit tests)  
**Status:** Phase 1A complete; Phase 1B download engine in progress (`phase1b/download-queue-install-receipts`). See `PHASE1B_DOWNLOAD_ENGINE_PLAN.md`.

---

## 1. Goals

Evolve Setup Wizard + Download Sources into a **unified Source Manager** that can discover, verify, download, install, link, track, diagnose, and recover AI assets and dependencies through a provider-neutral architecture.

Immediate Phase 1 deliverables:

1. Unified Source Manager architecture  
2. Advanced download queue and progress  
3. Source inspection and Asset Intelligence  
4. Dependency graph and missing-component detection  
5. Health Dashboard  
6. Expanded Playwright coverage  
7. Full clean-room validation  

**Non-goal for Phase 1:** every external provider and every model ecosystem. Build a stable extensible foundation first.

---

## 2. Current architecture (as of Phase 0.5)

### 2.1 Runtime surfaces

| Surface | Location | Notes |
|---------|----------|-------|
| Setup Wizard UI | `studio-web/src/components/SetupWizard.tsx` | Editor tab `"setup"` — not a standalone route |
| Download Sources UI | `DownloadSourcesPanel.tsx`, `AddSourceUrlDialog.tsx` | Embedded in Setup Wizard |
| Setup APIs | `/api/setup/*` in `routers/extra.py` + legacy detect in `setup_wizard.py` | Global under `data_dir` |
| Pack providers | `setup/pack_providers/` | `github_releases`, `fixture_http`; HF stub |
| Download Sources | `setup/download_sources/` | CLI detect, URL parse, SSRF, overrides, verify |
| Operations | `setup/operations.py` | Queue/checkpoint/interrupt; persisted in `setup_state.json` |
| Pack install | `setup/pack_install.py` | Staging → download → verify → extract → finalize |
| Component catalog | `setup/catalog.py` | Canonical; parallel legacy catalog in `setup_wizard.py` |
| Status model | `setup/status.py` | Canonical component statuses |
| GPU / services | `/api/gpu/stats`, `/api/health`, Comfy/Ollama probes | Adjacent; not Source Manager yet |
| E2E | `scripts/e2e-*.mjs`, `tests/e2e/`, `/api/e2e/*` | Fixture-only; must remain green |

### 2.2 Persistence today

`{data_dir}/setup_state.json` — `schema_version: 2`

Keys: `components`, `model_locations`, `status`, `operations`, `update_dismissals`, `source_overrides`, `download_sources` (+ runtime pack meta).

**Source overrides** (per component) store provider, URL, revision, selected files, install method, verification fingerprint — **no secrets**. Dual path: persisted override + in-memory `pack_manifests._SOURCE_OVERRIDES`.

### 2.3 Classification of existing code

| Area | Classification | Migration risk |
|------|----------------|----------------|
| `setup/catalog.py` component IDs | component-specific | **High** — do not rename without dual-read |
| `setup_wizard.py` legacy catalog | duplicated | Keep until detect consumers migrate |
| `download_sources/*` | provider + reusable security | Medium — wrap, don’t delete |
| Pack provider host allowlists vs `download_sources/security.py` | duplicated | **High** — unify carefully |
| `operations.py` persisted shape | operation-specific | **High** |
| Pack manifest `schemaVersion: 1` | component-specific | **High** |
| Fixture / CLI mocks | test-only | Preserve contracts |
| GPU poll (`GpuVramPanel`, status strip) | reusable patterns | Low — reuse for Health Dashboard |

### 2.4 Known gaps (Phase 0.5)

- CLI download job pipeline (progress/cancel/resume) not fully wired  
- HF pack provider stubbed  
- No normalized first-class Source records (only per-component overrides)  
- No dependency graph / Asset Intelligence / install receipts / rollback  
- No dedicated Source Manager or Health Dashboard routes  
- Setup Wizard carries advanced source UX that will grow overloaded  

---

## 3. Proposed architecture

### 3.1 Package layout (backend)

```
studio-api/app/source_manager/
  __init__.py
  contracts.py          # SourceProvider protocol + DTOs
  models.py             # SourceRecord, ComponentSourceAssignment, InstallReceipt
  persistence.py        # sources / assignments / receipts / queue state
  migration.py          # setup_state v2 → v3 + override → SourceRecord
  registry.py           # provider capability + priority selection
  security.py           # re-export / thin facade over download_sources.security
  providers/
    github_cli.py
    github_api.py
    huggingface_cli.py
    direct_http.py
    local_folder.py
    existing_install.py
    fixture.py
  parsers/              # URL / path normalization (wrap url_parse)
  verification/         # verify + fingerprints
  downloads/            # queue, progress, phases (Phase 1B)
  dependencies/         # graph engine (Phase 1D)
  manifests/            # component artifact manifests (Phase 1C)
  intelligence/         # Asset Intelligence classifiers (Phase 1C)
  health/               # Health Dashboard aggregation (Phase 1E)
  api.py                # FastAPI router /api/source-manager/*
```

**Compatibility facade:** existing `/api/setup/download-sources*` and source-override routes remain and call into Source Manager services.

### 3.2 Provider interface

```python
class SourceProvider(Protocol):
    id: str
    display_name: str
    priority: int

    def detect(self) -> ProviderDetectionResult: ...
    def authenticate(self, request: AuthenticationRequest) -> AuthenticationResult: ...  # optional
    def parse_source(self, input: SourceInput) -> ParsedSource: ...
    def verify_source(self, source: ParsedSource, context: VerificationContext) -> VerifiedSource: ...
    def list_artifacts(self, source: VerifiedSource, context: ArtifactQueryContext) -> list[SourceArtifact]: ...
    def create_download_plan(...) -> DownloadPlan: ...
    def execute_download(...) -> DownloadResult: ...  # Phase 1B+
    def supports_resume(self) -> bool: ...
```

Provider selection uses **capability + priority**, not UI branching:

1. Explicit user provider preference (if set)  
2. Parsed source kind match (github → GitHub CLI if auth’d else GitHub API; hf → HF CLI; local path → LocalFolder; fixture → Fixture)  
3. Capability flags (`can_list_private`, `can_resume`, `can_stream_progress`)  
4. Availability (detected, authenticated when required)  
5. Static priority fallback  

### 3.3 Normalized data model

#### SourceRecord

```json
{
  "id": "source_uuid",
  "provider": "github",
  "sourceType": "release_asset",
  "sourceUrl": "https://github.com/owner/repo/releases/tag/v1.0",
  "displayName": "owner/repo@v1.0",
  "owner": "owner",
  "repository": "repo",
  "revision": "v1.0",
  "branch": null,
  "commit": null,
  "assetPath": "pack.zip",
  "repositoryType": null,
  "authenticationRequired": false,
  "verificationStatus": "verified",
  "verifiedAt": "ISO_DATE",
  "verificationFingerprint": "hash",
  "metadata": {},
  "userDefined": true,
  "createdAt": "ISO_DATE",
  "updatedAt": "ISO_DATE"
}
```

Never store tokens, cookies, Authorization headers, or passwords.

#### ComponentSourceAssignment

```json
{
  "componentId": "pack_essential_photoreal",
  "sourceId": "source_uuid",
  "selectedArtifacts": ["pack.json", "..."],
  "installPlanId": null,
  "isOverride": true,
  "createdAt": "ISO_DATE"
}
```

#### InstallReceipt (Phase 1B/1F)

Tracks managed files for rollback; absent for legacy installs → rollback unavailable.

#### Download operation phases (Phase 1B)

`queued` → `resolving` → `verifying` → `waiting_for_auth` → `downloading` → `paused` → `extracting` → `validating` → `finalizing` → `installed` | `failed` | `cancelled` | `interrupted` | `rolling_back` | `rolled_back`

Map existing setup operation statuses onto this vocabulary via adapters; do not orphan in-flight Phase 0.5 ops.

### 3.4 Frontend surfaces

| Route / entry | Role |
|---------------|------|
| `/source-manager` | Dedicated Source Manager page |
| `/health` | Health Dashboard (Phase 1E) |
| Setup Wizard → Download Sources | Thin client of Source Manager (Providers + Add Source) |
| Per-component → Add/Change Source | Assigns `ComponentSourceAssignment` |
| `StudioChrome` links | Navigate to Source Manager / Health without leaving product chrome |

Setup Wizard remains the **guided** path; Source Manager is the **power** path. Progressive disclosure on component cards.

### 3.5 Asset Intelligence (Phase 1C)

Classify artifacts via filename, extension, path, size, bounded metadata reads, registry patterns. Confidence scores; never fully load multi-GB files. Classifications include `diffusion_model`, `vae`, `lora`, `ic_lora`, `workflow`, `pack`, `unknown`, etc.

### 3.6 Dependency graph (Phase 1D)

Manifests declare required/optional/alternatives/conflicts. Graph states: installed / missing / incompatible / unknown / optional / blocked / available_to_install. “Install Missing” builds a combined plan requiring user confirmation.

### 3.7 Health Dashboard (Phase 1E)

Aggregate system, GPU, services (API, frontend, Comfy, Ollama, CLIs), downloads, model/dependency footprint. States: Healthy / Degraded / Unavailable / Misconfigured / Authentication Required / Update Available / Unknown — each with recommended action. Polling with backoff; stop on unmount.

---

## 4. Migration strategy

### 4.1 State schema

- Bump `setup_state.json` to **`schema_version: 3`** when Source Manager keys are present.  
- New keys: `sources`, `component_sources`, `install_receipts`, `download_queue` (populated as subphases land).  
- **Dual-read / dual-write during 1A:**  
  - Read: prefer `component_sources` + `sources`; fall back to `source_overrides`.  
  - Write: update both until Setup Wizard paths fully migrate.  
- On load: `migration.migrate_source_overrides_v2_to_v3()` creates SourceRecords + assignments from existing overrides without deleting `source_overrides`.  
- Defaults remain recoverable by removing assignment/override (existing DELETE behavior).

### 4.2 Compatibility plan

| Existing API | Phase 1 behavior |
|--------------|------------------|
| `/api/setup/download-sources*` | Facade → Source Manager provider detect/auth |
| `/api/setup/sources/verify` | Facade → provider parse+verify |
| `/api/setup/components/{id}/source-override` | Writes assignment + SourceRecord + legacy override |
| Pack install / link / ops | Unchanged in 1A; queue wraps in 1B |
| `fixture_http` + E2E routes | Preserved |
| Legacy `/api/setup/detect` | Untouched in Phase 1 |

### 4.3 Unsafe-to-break list

- 17 critical Playwright tests  
- `test_download_sources.py` (19)  
- Component IDs and pack manifest ids  
- SSRF / HTTPS / E2E localhost exception  
- Operation interrupt-on-restart semantics  
- Isolated `STUDIO_DATA_DIR`  

---

## 5. Data model changes (summary)

| Entity | Storage | Introduced |
|--------|---------|------------|
| SourceRecord | `setup_state.sources` | 1A |
| ComponentSourceAssignment | `setup_state.component_sources` | 1A |
| Download queue ops | `setup_state.download_queue` + ops registry | 1B |
| InstallReceipt | `setup_state.install_receipts` | 1B/1F |
| Component artifact manifests | `source_manager/manifests/*.json` + pack manifests | 1C |
| Dependency edges | derived + cached in status | 1D |
| Health snapshot | ephemeral + light cache | 1E |

---

## 6. Test strategy

### 6.1 Preserve baseline every subphase

```bash
npm run e2e:stop
npm run e2e:start
npx playwright test --grep "@critical" --retries=0
# studio-api
pytest tests/test_download_sources.py -q
```

### 6.2 New coverage (by subphase)

| Subphase | Unit / integration | Playwright |
|----------|-------------------|------------|
| 1A | source parse, migrate overrides, provider select | Source Manager route, provider cards, save/remove source |
| 1B | queue order, progress/ETA, recovery | queue, cancel, retry, reload restore |
| 1C | classifiers, manifests | artifact classification + selection |
| 1D | dependency graph, install plan | missing/installed/optional, cancel before exec |
| 1E | health aggregation, backoff | health states, polling stop |
| 1F | receipts, rollback safety | managed rollback / unmanaged unavailable |

Fixture-only; no production model downloads. `@external` / `@large-download` remain opt-in.

### 6.3 Clean-room gate (Phase 1 complete)

Match Part 17 of the Phase 1 prompt: typecheck, lint, unit suites, critical + expanded E2E, build, stop, ports free, fresh start, re-run suites, API health, no traceback, no secrets in artifacts.

---

## 7. Implementation order

| Subphase | Scope | Checkpoint |
|----------|-------|------------|
| **1A** | Architecture doc; SourceRecords; provider interface; migration; `/source-manager` route; facades; preserve Setup Wizard | critical E2E green |
| **1B** | Download queue; progress; persistence; install receipts (create) | critical + queue tests |
| **1C** | Asset Intelligence; component manifests; artifact selection UI | classifier + selection tests |
| **1D** | Dependency graph; install-missing plan; Setup Wizard integration | dependency tests |
| **1E** | Health Dashboard; diagnostics; polling/backoff | health tests |
| **1F** | Rollback; polish; expanded Playwright; clean-room; final report | completion gates |

After each subphase: focused tests → existing critical E2E → fix regressions → coherent Git checkpoint.

---

## 8. Out of scope (Phase 1)

- Full Hugging Face pack provider production downloads of multi-GB models in CI  
- Arbitrary third-party cloud marketplaces  
- Automatic silent installs without confirmation  
- Promising rollback for unmanaged legacy directories  
- Replacing ComfyUI / Ollama themselves  
- Merging or deleting `setup_wizard.py` legacy detect (defer)  
- Desktop-native OS credential vaults beyond CLI auth guides  
- Live `@external` provider suite as a merge gate  

---

## 9. Security principles (carry forward)

- HTTPS default; SSRF + private IP + redirect revalidation  
- Host allowlists; `STUDIO_E2E` localhost HTTP exception only  
- Archive traversal / symlink escape / size & file-count limits  
- Manifest schema validation; no executable commands in manifests  
- CLI via argument arrays; no shell interpolation  
- Credential redaction; no secret persistence in source records  
- Bounded metadata reads; destination-path validation  
- Canonicalize local folders; warn on executables  

---

## 10. Success criteria (Phase 1)

Adept UI has one coherent system for discovering, verifying, downloading, installing, linking, tracking, diagnosing, and recovering assets. The user should not need to manually determine provider, required files, destinations, missing dependencies, service health, or safe resume/rollback — with transparent diagnostics and confirmation before destructive or large operations.

Baseline must remain: **17/17 critical E2E**, download-source units, pack install/link/fail-retry/interrupt, overrides, backend survival, isolated E2E data, clean-room start/stop.

---

## 11. References

- `docs/audit/PLAYWRIGHT_SETUP_WIZARD_SUMMARY_REPORT.md`  
- `docs/audit/DOWNLOAD_SOURCES_IMPLEMENTATION_REPORT.md`  
- `docs/audit/PLAYWRIGHT_FUNCTIONAL_AUDIT_ARCHITECTURE.md`  
- Phase 0.5 harness: `scripts/e2e-start.mjs`, `tests/e2e/`  
