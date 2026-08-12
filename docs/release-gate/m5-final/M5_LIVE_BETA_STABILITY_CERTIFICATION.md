# Live Beta Stability Certification

| Field | Value |
| --- | --- |
| Addendum | `M5.0 Addendum 9 — Live Beta Stability, Repeatability & Harness Parity` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Authoritative subset | `ai-guided-setup-lifecycle.spec.ts`, `setup-page.spec.ts`, `source-manager.spec.ts`, `setup-install-progress.spec.ts` |
| Final Stability Verdict | **PASS** |

## Prior Fail Preserved

The earlier authoritative failure was real and remains part of the audit trail:

- warm-runtime repeatability was already green (`13/13` three consecutive times)
- post-restart smoke was green
- the first post-cold-start final smoke failed `12/13`
- during that failure, `waitForAppReady()` timed out on `/api/setup/status`, reset then hit `ECONNREFUSED 127.0.0.1:8758`, and the supervisor log showed `intentional shutdown` → `STOPPED` → fresh `READY`

That failure was not treated as a flaky assertion. It was a real lifecycle blocker and drove the repair work below.

## Repair Summary

Files repaired in this pass:

- [`scripts/beta_runtime/supervisor.py`](../../../scripts/beta_runtime/supervisor.py)
- [`Stop-AdeptUI-Beta.ps1`](../../../Stop-AdeptUI-Beta.ps1)
- [`Start-AdeptUI-Beta.ps1`](../../../Start-AdeptUI-Beta.ps1)
- [`Restart-AdeptUI-Beta.ps1`](../../../Restart-AdeptUI-Beta.ps1)

What changed:

- shutdown now keeps the Beta shutdown flag in place until the next explicit start, so stray survivors do not restart into a false cold-start boundary
- the supervisor `stop` action now waits for graceful shutdown, then force-sweeps any remaining tagged Beta wrapper/listener processes before reporting `STOPPED`
- `Stop-AdeptUI-Beta.ps1` now polls `8758` and `8760` and fails if Beta does not stay down
- `Start-AdeptUI-Beta.ps1` is now idempotent when Beta is already healthy
- `Stop-AdeptUI-Beta.ps1` and `Restart-AdeptUI-Beta.ps1` now honor a certification lock so overlapping operator restarts cannot recycle Beta during the smoke window

## Shared State Audit

Historical records remain persisted, but active leakage was not observed after repair:

| Surface | Observed after repaired cold start | Interpretation |
| --- | --- | --- |
| Setup install jobs | `33` total, `0` active, `0` queued-or-active | Historical creator/install history remains; no live leakage |
| Download operations | `6` total, `0` active, `0` non-terminal | Historical records remain; no stale queue work |
| Setup status | `overall_status=ready` | Healthy cold-start surface |
| Source Manager provider IDs | no `fixture` provider surfaced in `/api/setup/status` | No cert-surface fixture leak observed in this pass |

Conclusion: the addendum Definition of Done should be interpreted as **no active / queued / orphan in-flight state**. That condition is now satisfied. Historical completed or failed records still exist and are disclosed above.

## Repeatability Results

Authoritative command:

```text
$env:ADEPT_BETA_TARGET='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8760'
$env:STUDIO_API_BASE='http://127.0.0.1:8758'
$env:STUDIO_API_PORT='8758'
npx playwright test `
  tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts `
  tests/e2e/setup/setup-page.spec.ts `
  tests/e2e/setup/source-manager.spec.ts `
  tests/e2e/setup/setup-install-progress.spec.ts `
  --project=chromium `
  --retries=0
```

| Run | Result |
| --- | --- |
| Repeatability #1 | **PASS** — `13 passed` |
| Repeatability #2 | **PASS** — `13 passed` |
| Repeatability #3 | **PASS** — `13 passed` |
| Post-restart smoke | **PASS** — `13 passed` |

Warm-runtime repeatability requirement: **met**.

## Cold Stop / Start Evidence

### Pre-stop listener ownership

Before the repaired certification stop:

- API `8758` listener PID: `37320`
- Web `8760` listener PID: `41312`

### Stop proof

Repaired stop command:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File Stop-AdeptUI-Beta.ps1
```

Observed result:

- script returned success only after both `8758` and `8760` were down
- explicit 60-second poll after stop showed no API listener, no web listener, and no tagged Beta supervisor/web/api processes at:
  - `0s`
  - `15s`
  - `30s`
  - `45s`
  - `60s`

### Cold start proof

Cold start command:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File Start-AdeptUI-Beta.ps1 -NoBrowser
```

Observed result:

- runtime reached `READY` in about `19s`
- post-start listener ownership:
  - API `8758` listener PID: `35816`
  - Web `8760` listener PID: `42640`
- `/api/runtime/beta` reported `state=READY`
- `/api/health` reported `ok=true`, `comfyReachable=true`
- `/api/setup/status` reported `overall_status=ready`, `ready=35`, `not_installed=4`
- `/api/production-control/gate` reported `verdict=GO`
- no active install jobs or active downloads remained

## Final Stability Smoke

The repaired cold-start smoke was re-run on the live Beta stack with the certification lock active to prevent overlapping `Stop/Restart-AdeptUI-Beta` script calls:

- result: **PASS** — `13 passed`
- retries: `0`
- duration: about `1.8m`
- previously failing spec `verify refresh propagates ready state for focused component` passed

## Recycle Root Cause Assessment

The strongest evidence for the prior mid-suite recycle is **operator overlap**, not an internal Beta watchdog:

- the earlier failure window still shows a real `intentional shutdown` in [`data/runtime/logs/beta/supervisor.log`](../../../data/runtime/logs/beta/supervisor.log)
- terminal metadata shows numerous explicit `Restart-AdeptUI-Beta.ps1` invocations in parallel with other setup test work
- separate harness terminals were also active on `5173/8742`, confirming multiple overlapping certification/test sessions in the repo at the same time

This pass did not prove that every historical restart was caused by an external operator, but it did eliminate the accidental recycle path most likely to affect certification:

- script-level stop/restart interference is now guardable with the certification lock
- repaired shutdown stays down for the full verification window
- the final cold-start smoke now passes cleanly on `8760/8758`

## Harness vs Live Beta Comparison

See [`M5_HARNESS_VS_LIVE_BETA.md`](./M5_HARNESS_VS_LIVE_BETA.md).

Current parity state for the authoritative setup subset:

- warm-runtime parity: **green**
- cold-start final-smoke parity: **green** after the lifecycle repair and certification lock

## Remaining Differences

- harness-only pack/download suites using `/api/e2e/*` remain validation-only and were not used as Beta certification evidence
- historical install/download records are intentionally still present and should not be confused with active leakage
- broader M5.0 release quality still depends on other gates outside this addendum

## Final Stability Verdict

**PASS**

Checklist against Addendum 9:

- [x] Shared-state leakage repaired for the Beta cert subset
- [x] Cleanup/teardown is deterministic on the warm runtime
- [x] The authoritative subset passed three consecutive identical Beta executions
- [x] Live Beta smoke passed after a full restart
- [x] Cold stop stayed down for the required verification window
- [x] Cold start returned to `READY`
- [x] No active install jobs or active downloads survived the cold start
- [x] Final post-cold-start smoke passed cleanly
- [x] Beta remained continuously available during the repaired cold-start smoke window

Addendum 9 is now honestly **PASS**.
