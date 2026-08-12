# Setup Download Progress + Source Manager Repair — Completion Report

## Verdict

**NO-GO**

Automated unit/API and Playwright evidence passed for progress, repair, required components, add-source, ComfyUI restart guidance, and clone≠ready. Full GO is blocked until live multi-GB install/repair certification and complete manual UX evidence are recorded against the certification boundary below.

## Identity

| Field | Value |
| --- | --- |
| Feature | Setup / Source Manager install progress, stall detection, ComfyUI repair |
| Working branch | `feature/m4-12-long-form-avatar-studio` |
| Starting tip SHA observed | `fa09c99d6395c29461cdec4555055faad116c435` |
| Install job package | `studio-api/app/source_manager/install_jobs/` |
| Commit status | uncommitted unless explicitly committed later |

---

## Root causes (original + remaining)

1. **Progress not visible** — Setup operations, download-queue ops, and IndexTTS2 used different job models; UI watched only one.
2. **Install state not persistent** — No shared InstallJob store surviving Setup ↔ Source Manager navigation/reload for custom installers.
3. **View required components dead** — Self-link / no focused panel for missing ComfyUI nodes.
4. **Add Source URL incomplete** — Validate → save → continue missing on Source Manager.
5. **Install component dead-end** — No state-aware path from missing source → install → repair.
6. **ComfyUI missing nodes lacked repair route** — Clone/install without restart + live node re-probe readiness rule.
7. **Stalled downloads looked “still installing”** — No heartbeat / Possible Stall / Interrupted / Waiting for Source classification.

---

## Architecture delivered

### Install job model
Canonical facade: `source_manager.install_jobs`.

- Adapts DownloadQueueManager + Setup operations + custom jobs (IndexTTS2, ComfyUI extensions).
- Persists custom jobs under `data/source_manager/install_jobs/`.
- Shared states including `repair_required`, `configuring` (restart required), `ready` only after health/node checks.
- Public `INSTALL_*` error codes with title / userMessage / technicalMessage / recovery actions.
- Multi-phase contract via `phases.py` (`phaseSteps`); overall percent capped below 100 until ready.

### Stall detector
`heartbeat.py` tracks `InstallHeartbeat` and classifies:

| Condition | Status |
| --- | --- |
| Quiet past component-specific threshold | Possible Stall |
| Worker not alive | Interrupted |
| Network active, bytes/phase frozen | Waiting for Source |
| Slow but advancing | Remains Downloading/Installing |

Never auto-fails merely because a large download is slow. Recovery actions: Retry Connection, Resume, Restart Worker, Open Diagnostics, Cancel Safely.

### Progress transport
- Primary: `GET /api/setup/install-jobs/events` (SSE snapshot + patches)
- Fallback: bounded polling in `useInstallJobs` when SSE drops
- Shared client store `installJobsStore` for Setup / Source Manager / Production Dock / Model Library chips

### ComfyUI extension pipeline
`comfy_extension_installer.py` + catalog component `comfyui_hunyuan_nodes`:

1. Resolve source → clone into `custom_nodes`
2. Install deps when `requirements.txt` present
3. Enter `restart_required` (**not ready**)
4. Restart ComfyUI (best effort) + re-probe live nodes
5. Ready only when required nodes register; otherwise typed `INSTALL_EXTENSION_MISSING` repair path

### Source validation / required components
Existing validate/save endpoints retained; Required Components panel lists missing Hunyuan nodes and maps to `comfyui_hunyuan_nodes`. IndexTTS2 still requires explicit `confirm` + `confirmDownloadModels` (never silent true).

---

## Files changed (primary)

### Backend
- `studio-api/app/source_manager/install_jobs/errors.py`
- `studio-api/app/source_manager/install_jobs/phases.py` (new)
- `studio-api/app/source_manager/install_jobs/heartbeat.py` (new)
- `studio-api/app/source_manager/install_jobs/events.py` (new)
- `studio-api/app/source_manager/install_jobs/comfy_extension_installer.py` (new)
- `studio-api/app/source_manager/install_jobs/schema.py`
- `studio-api/app/source_manager/install_jobs/service.py`
- `studio-api/app/source_manager/install_jobs/router.py`
- `studio-api/app/source_manager/install_jobs/requirements.py`
- `studio-api/app/setup/catalog.py`
- `studio-api/app/setup/diagnostics.py`
- `studio-api/tests/test_install_jobs_m412.py`

### Frontend
- `studio-web/src/contracts/installJobs.ts`
- `studio-web/src/hooks/useInstallJobs.ts` (+ poll re-export)
- `studio-web/src/state/installJobsStore.ts`
- `studio-web/src/components/install/*` (ProgressCard, ErrorPanel, StatusChip, RequiredComponents, CSS)
- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/components/ActiveDownloadsPanel.tsx`
- `studio-web/src/components/CapabilityPanel.tsx`
- `studio-web/src/pages/SourceManager.tsx`
- `studio-web/src/components/production-dock/ModelMenuDrawer.tsx`
- `studio-web/src/components/VideoModelLibrary.tsx`

### Tests / docs
- `tests/e2e/setup/setup-install-progress.spec.ts`
- `docs/release-gate/setup/SETUP_SOURCE_MANAGER_INSTALL_PROGRESS_REPORT.md` (this file)

---

## Test results

| Suite | Command | Outcome |
| --- | --- | --- |
| Unit / API | `cd studio-api; python -m pytest tests/test_install_jobs_m412.py -q` | **10 passed** |
| FE build | `cd studio-web; npm run build` | **passed** |
| Playwright | `npx playwright test tests/e2e/setup/setup-install-progress.spec.ts --project=chromium --retries=0` | **6 passed** |
| Live multi-GB install / repair | not executed this pass | **pending** |
| Manual UX stamp | not signed | **pending** |

Playwright coverage:
- progress after reload
- typed failure + repair
- required components panel
- multi-phase stepper + details collapsed by default
- ComfyUI restart guidance → ready after repair
- add source validate + save

Unit coverage additions:
- `INSTALL_*` error normalization
- multi-phase percent &lt; 100 until ready
- stall matrix (slow / stall / interrupted / waiting for source)
- ComfyUI clone ≠ ready; restart + re-probe ready path
- heartbeat / phaseSteps serialization

---

## Certification boundary

| # | Requirement | Evidence this pass |
| --- | --- | --- |
| 1 | Real progress visible | Playwright + unit serialize — **partial** (fixture/live IndexTTS2 not re-run) |
| 2 | Progress survives reload | Playwright passed |
| 3 | Typed failure appears | Playwright + unit `INSTALL_*` |
| 4 | Specific repair succeeds | Playwright repair + Comfy reverify unit |
| 5 | View Required Components works | Playwright passed |
| 6 | Add Source URL validates and saves | Playwright passed |
| 7 | ComfyUI extension installs | Unit fixture clone path — **no live git/custom_nodes cert** |
| 8 | ComfyUI restarts | Fixture/best-effort API — **no live Comfy restart cert** |
| 9 | Required nodes re-detected | Unit + Playwright fixture |
| 10 | Capability Blocked → Ready | Unit capability invalidate after probe — **no live capability flip** |
| 11 | Setup and Source Manager agree | Shared jobs/store — **manual dual-surface stamp pending** |
| 12 | Manual UX evidence complete | **pending** |

Any incomplete row forces **NO-GO**.

---

## Known limitations

- Live multi-GB IndexTTS2 / Hunyuan download not re-certified in this pass.
- ComfyUI restart is best-effort (docker runtime / HTTP interrupt); many desktop installs still need user Restart Later + verify.
- Legacy guided Setup installers without queue/custom jobs still return honest unsupported/guided placeholders.
- Manual UX screenshots under `docs/release-gate/setup/evidence/` not collected this pass.

---

## Beta

| Surface | URL |
| --- | --- |
| UI | http://127.0.0.1:8760/ |
| API health | http://127.0.0.1:8758/api/health |

Beta was restarted after this implementation and reported **READY**.

## Manual review path

1. Open Setup at http://127.0.0.1:8760/ (API http://127.0.0.1:8758/).
2. Start or observe an install; confirm phase stepper, bytes/speed, details collapsed.
3. Reload; confirm job restores.
4. Open Source Manager → View required components → Add Source URL.
5. For Hunyuan nodes: Install `Hunyuan ComfyUI Extension` → Restart ComfyUI → verify nodes before Ready.
6. Confirm Production Dock / Model Library chips match Setup status.
7. Stamp manual UX checklist; only then reconsider GO.

---

## Final verdict

**NO-GO** — implementation of progress, stall detection, SSE, ComfyUI install/restart/re-probe readiness rule, and Source Manager workflows is in place with strong automated coverage, but the mandatory live install + manual UX certification boundary is not fully proven.
