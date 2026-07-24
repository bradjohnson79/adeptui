# Phase 1B — Download Queue Implementation Report

**Date:** 2026-07-24  
**Branch:** `phase1b/download-queue-install-receipts`  
**Verdict:** Core engine delivered and gated — **20/20** `@critical` Playwright; **33** related unit tests passed

---

## Architecture implemented

Provider-neutral download engine under `studio-api/app/source_manager/downloads/`:

| Module | Role |
|--------|------|
| `phases.py` | Central phase transitions |
| `models.py` | InstallPlan + DownloadOperation |
| `progress.py` | Rolling-window speed/ETA (real bytes) |
| `disk.py` | Disk-space preflight |
| `persistence.py` | `download_queue` + `install_receipts` in setup_state |
| `queue.py` | DownloadQueueManager (enqueue, concurrency, cancel, retry, recovery) |
| `receipts.py` | Managed receipts + link records |
| `executors/` | Fixture, DirectHTTP (+ Range probe), LocalCopy |
| `api.py` | `/api/downloads*`, `/api/install-history*` |

Plan doc: `docs/architecture/PHASE1B_DOWNLOAD_ENGINE_PLAN.md`

---

## Operation state machine

Phases: `queued` → `preflighting` → `resolving` → `verifying_source` → `downloading` → `extracting` → `validating` → `finalizing` → `installed`, plus `paused`/`cancelling`/`failed`/`interrupted`/`waiting_for_disk_space`.

Invalid transitions raise `InvalidPhaseTransition`.

---

## Queue concurrency

- Default: 1 large + 2 small active downloads  
- Destination + component locks persisted in `download_queue.locks`  
- Duplicate active ops for the same component reused (no double enqueue)  
- Priority ordering among queued ops  

---

## Provider executors

| Executor | Pause | Resume | Notes |
|----------|-------|--------|-------|
| Fixture | No | No | Primary E2E path; wraps pack resolve/download/extract/promote |
| DirectHttp | If Range honored | If Range + partial | Probes Accept-Ranges + 206 |
| LocalCopy / Existing | No | No | Link or chunked copy |
| github_cli / hf_cli | No (mapped to DirectHttp for URL assets) | No | Explicit “pause not supported” until CLI semantics proven |

---

## Progress / speed / ETA

- Byte counters from stream / staging  
- Rolling ~8s window; ETA null until samples + known total  
- Persist ~750ms while downloading; always on phase change  

---

## Cancellation / retry / recovery

- Cancel sets event; executor checks during progress; phase → `cancelling` → `cancelled`  
- Retry increments attempt history; clears checksum staging when needed  
- Startup `recover_interrupted()` converts orphaned active ops to `interrupted` (auto-resume off unless `ADEPT_DOWNLOAD_AUTO_RESUME=1`)  

---

## Receipts

- Managed installs write immutable receipts to `install_receipts`  
- Linked existing → `managed: false`, rollback unavailable  
- Install History UI + View Receipt dialog (Rollback placeholder disabled)  

---

## UI / API

- Source Manager: Active Downloads + Install History  
- Shared poll hook `useDownloadsPoll` with backoff  
- Setup Wizard cards show queue stage labels via `status.py` enrichment  
- Endpoints: GET/POST `/api/downloads`, cancel/pause/resume/retry/priority/cleanup, install-history  

---

## Tests

| Suite | Result |
|-------|--------|
| `test_download_queue_phase1b.py` + SM + download-sources | **33 passed** |
| Playwright `@critical` (incl. download-queue + source-manager) | **20 passed / 0 failed** |

Commands:

```bash
pytest tests/test_download_queue_phase1b.py tests/test_source_manager_phase1a.py tests/test_download_sources.py -q
npm run e2e:stop
npm run e2e:start
npx playwright test --grep "@critical" --retries=0
npm run e2e:stop
```

---

## Remaining limitations

- Full CLI pause/resume not claimed  
- Orchestrator pack install path still exists in parallel (queue is additive; fixture packs can enqueue via `/api/downloads`)  
- Range resume UI path lightly covered (capability messaging tested; deep Range e2e deferred)  
- Rollback action intentionally disabled until Phase 1F  
- Asset Intelligence / dependencies / Health Dashboard still deferred  

## Recommended Phase 1C

Asset Intelligence classifiers, component artifact manifests, recommended artifact selection UI, and deeper wiring of Setup Wizard “Download and Install” to always enqueue through DownloadQueueManager.
