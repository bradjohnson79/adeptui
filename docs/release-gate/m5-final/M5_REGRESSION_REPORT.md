# M5.0 — Regression Report

| Field | Value |
| --- | --- |
| Milestone | `M5.0 Final E2E` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Probe window (UTC) | `2026-08-02T16:21Z` to `2026-08-02T16:40Z` |

## Executive Summary

Live M5 regression evidence is mixed: the Production Dock gate still reports `GO`, and the managed local E2E harness passed its focused smoke slice, but the real Beta still failed the same smoke against `8760/8758`. The final M5 gate therefore remains `NO-GO`.

## Live Probe Timings

All timings below were gathered against the running Beta API at `http://127.0.0.1:8758`.

| Endpoint | Sample timings (ms) | Reading |
| --- | --- | --- |
| `GET /api/health` | `2085.1`, `2092.9`, `2103.3` | Reachable, but not especially fast. |
| `GET /api/setup/status` | `4815.4`, `100.7`, `93.5` and later `5347.2`, `9.2` | Cold path is slow; warm path is fast. |
| `GET /api/production-control/gate` | `26.6`, `29.5`, `29.6` and later `25.6`, `31.0` | Fast and stable. |
| `GET /api/production-control/status` | `3001.4`, `3090.8`, `3101.2` and later `2936.2`, `2983.8` | Consistently slow for a status surface. |
| `GET /api/codirector/status/registry` | `24.9`, `25.0`, `24.1` and later `20.2`, `15.8` | Fast. |
| `GET /api/codirector/status/latest?projectId=...` | `200.5`, `26.3` | Warm result is acceptable. |
| `POST /api/codirector/status/check` | `15410.8`, `15433.2`; later manual sample `7109.5` | Major latency concern; still degraded even on the faster follow-up sample. |
| `GET /api/gpu/stats` | `52.0`, `56.0`, `55.8` | Fast device probe only; not job-time GPU certification. |

## Current Live Status

### Latest steady-state reading

- `GET /api/health` -> `ok=true`, `comfy_reachable=true`, `comfy_status=ready`
- `GET /api/setup/status` -> `overall_status=ready`, `overall_label=Ready to Generate`
- Setup counts:
  - `ready=35`
  - `not_installed=4`
  - `needs_attention=0`
- Remaining `not_installed` components:
  - `longcat-video-avatar-1-5-local`
  - `infinitetalk-local`
  - `musetalk-1-5-local`
  - `echomimic-v2-local`

### Instability observed in the same probe window

Earlier in the same pass, before the later steady-state recovery, live Beta briefly reported:

- `GET /api/health` -> `ok=false`, `comfy_reachable=false`, `comfy_status=unreachable`
- `GET /api/setup/status` -> `overall_status=additional_setup_required`

That later recovered without any product code change in this pass. M5 should therefore treat Beta readiness as unstable over the observation window, not as a clean uninterrupted green state.

## Regression Findings

### 1. Live Beta still fails focused smoke

Direct Beta-targeted smoke at `8760/8758` finished:

- `7 passed`
- `4 failed`
- `1 flaky`
- total runtime `11.5m`

Failing Beta slices:

- `tests/e2e/codirector/codirector-status-cross-check.spec.ts`
- `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` render case
- `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` focused deep-link certify case
- `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` focused refresh case

Flaky Beta slice:

- `tests/e2e/setup/setup-install-progress.spec.ts` -> `restores install progress after reload`

### 2. Managed harness green does not translate to Beta green

The same focused slice on the Playwright-managed local stack finished:

- `12 passed`
- `0 failed`
- `0 flaky`
- total runtime `4.0m`

That proves the specs are valid and the app can still pass under its managed local harness, but M5 final release truth must follow Beta, not the harness.

### 3. Co-Director status remains degraded and slow

Live manual probe on the anchor project returned a persisted status run with:

- `statusIndicator=Degraded`
- `score=82`
- `band=Fair`
- `partial=true`
- dominant warnings:
  - `capabilities.registry`
  - `codirector.provider`
  - `comfy.health`
  - `image_runtime.readiness`
  - `tools.registry`

This is not a final-certification-quality result for a creator-visible status surface.

### 4. Production status remains expensive

`GET /api/production-control/status` stayed near `~3.0s` across repeated warm samples. For a creator-facing status view, that is still a noticeable wait and should be treated as a performance regression risk.

### 5. Beta intentionally omits `/api/e2e/status`

Live Beta returned `404` for `GET /api/e2e/status`. That is expected per the Playwright helper comments and is not itself a release blocker, but it reinforces that isolated harness green cannot be used as a substitute for Beta smoke evidence.

## Regression Verdict

**NO-GO**

The critical regression is not a single crashing endpoint. It is the mismatch between a locally passing harness and a Beta that still fails creator-facing setup and Co-Director smoke, combined with slow/degraded Co-Director status checks and a transient readiness wobble during the same observation window.
