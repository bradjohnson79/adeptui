# M5.0 — Final Certification

| Field | Value |
| --- | --- |
| Milestone | `M5.0 Final E2E` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Final certification timestamp (UTC) | `2026-08-02T17:24:04Z` |
| Verdict | **NO-GO** |

## Binary Decision

**NO-GO**

M5 final certification cannot be promoted to `GO` in this pass.

## Hard Gates

| Gate | Result | Why |
| --- | --- | --- |
| AI-Guided Setup final closure | `PASS` | `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md` now records **GO**. |
| Addendum 9 live Beta stability | `PASS` | Repaired cold stop stayed down for `60s`, cold start returned to `READY`, and the final post-cold-start Beta smoke passed `13/13` with `--retries=0`. |
| Harness vs live Beta parity | `PASS` | The authoritative four-file setup subset is now green on live Beta for warm repeatability, post-restart, and repaired cold-start smoke. |
| Production Dock gate | `PASS` | Cold-start probe still returned `GET /api/production-control/gate` `200` with `verdict=GO`. |
| Runtime/status honesty | `PASS` | Cold-start probe returned `GET /api/health` `200`, `comfyReachable=true`, `GET /api/setup/status` `overall_status=ready`, and no active install/download work. |
| Co-Director live status quality | `FAIL` | Fresh live-project status check returned `statusIndicator=Degraded`, `score=82`, `band=Fair`, with timeout warnings in capability registry, provider/runtime, tool registry, ComfyUI runtime, and image runtime readiness. |

## What Was Verified Live

- The authoritative four-file Beta subset passed three consecutive identical warm-runtime executions with `--retries=0`
- The same four-file subset passed once more after `npm run beta:restart`
- Repaired cold stop succeeded:
  - `Stop-AdeptUI-Beta.ps1` returned success only after both `8758` and `8760` were down
  - explicit `0s / 15s / 30s / 45s / 60s` polling showed no API listener, no web listener, and no tagged Beta processes
- Repaired cold-start probe succeeded:
  - `GET /api/health` → `200`
  - `GET /api/setup/status` → `overall_status=ready`, `ready=35`, `not_installed=4`, `needs_attention=0`
  - `GET /api/production-control/gate` → `verdict=GO`
  - `GET /api/setup/install-jobs` → `33 total`, `0 active`, `0 queued-or-active`
  - `GET /api/downloads` → `6 total`, `0 active`, `0 non-terminal`
  - `/api/setup/status` did not expose any `fixture` provider IDs in the cert surface
- Repaired final post-cold-start Beta smoke passed `13/13`
- Fresh Co-Director status results:
  - stale deleted-project run escalated to `Blocked` because `library.preflight` hit `PROJECT_NOT_FOUND`
  - fresh run on a current live project completed but remained `Degraded`, `82`, `Fair`

## Why This Is Still NO-GO

### 1. Addendum 9 is repaired, but M5.0 still has a separate live-quality blocker

The stability blocker that previously kept this milestone red is repaired:

- cold stop now holds for the required verification window
- cold start returns to `READY`
- the repaired final post-cold-start Beta smoke passed `13/13`

That means the remaining `NO-GO` is **not** the Addendum 9 lifecycle issue anymore.

### 2. Current Co-Director status is still below final-release quality

The freshest valid live-project status check completed on Beta and still returned:

- `statusIndicator=Degraded`
- `score=82`
- `band=Fair`

Its dominant warnings remain in the exact areas that matter for a creator-facing final gate:

- capability registry
- Co-Director model runtime
- tool registry
- ComfyUI runtime
- image runtime readiness

That is honest, live Beta evidence on a valid project, and it is not strong enough for a final release `GO`.

### 3. A deleted-project status run must not be misread as the final blocker

One fresh status check returned `Blocked`, but that specific run was bound to a project ID that no longer existed and failed `library.preflight` with `PROJECT_NOT_FOUND`.

That stale-project result is not the release verdict driver. The release verdict driver is the subsequent valid-project run, which still landed at `Degraded / 82 / Fair`.

## Supporting Deliverables

- `M5_FULL_APPLICATION_AUDIT.md`
- `M5_END_TO_END_WIRING_REPORT.md`
- `M5_HARNESS_VS_LIVE_BETA.md`
- `M5_LIVE_BETA_STABILITY_CERTIFICATION.md`
- `M5_DOCK_STATUS_RUNTIME_HONESTY.md`
- `M5_PLAYWRIGHT_SMOKE_REPORT.md`
- `M5_REGRESSION_REPORT.md`
- `M5_UX_CERTIFICATION.md`

## Final Verdict

**NO-GO**

M5 final release should not be certified yet. AI-Guided Setup is now `GO`, Addendum 9 live Beta stability is now `PASS`, and the authoritative Beta subset is green across warm, restart, and repaired cold-start conditions. The remaining blocker is current live Co-Director status quality on a valid project, which still reports `Degraded / 82 / Fair`, so M5.0 stays **NO-GO**.
