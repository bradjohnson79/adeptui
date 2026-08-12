# M5.0 — UX Certification

| Field | Value |
| --- | --- |
| Milestone | `M5.0 Final E2E` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Target | Live Beta at `http://127.0.0.1:8760/` |
| Verdict | **NO-GO** |

## Evidence Basis

This certification is based on:

- live Beta API probes at `8758`
- focused Playwright smoke against the already-running Beta at `8760/8758`
- existing M5 reports already present in this folder
- `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md`

This pass did **not** complete an interactive manual browser walkthrough, so UX claims below stay limited to what the live Beta smoke and payloads can honestly prove.

## Creator-First Criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Creator can enter Setup reliably from the project surface | `FAIL` | Beta smoke could not reliably render `.setup-wizard-page` for the lifecycle entry case. |
| Focused AI-Guided deep links preserve creator context | `PARTIAL` | Root redirect preserving source/component passed, but focused Hunyuan and FLUX entry cases failed to show the expected AI-Guided state. |
| Primary remediation path stays inside Setup | `PASS` | Existing containment evidence still points all install/remediation affordances back into Setup rather than hidden side flows. |
| Runtime/status language stays honest | `PARTIAL` | Setup and Dock status can be truthful, but live Co-Director status remains `Degraded/Fair`, so the overall creator readiness story is still not clean. |
| Reload/recovery behavior is dependable | `PARTIAL` | `restores install progress after reload` was flaky on Beta. |
| Co-Director status visibility is creator-safe | `FAIL` | The Beta smoke for status panel/history visibility failed twice. |

## What Beta Still Does Well

- `GET /api/production-control/gate` remains fast and returns `verdict=GO`.
- Live steady-state setup status recovered to:
  - `overall_status=ready`
  - `ready=35`
  - `not_installed=4`
  - `needs_attention=0`
- The Beta-targeted smoke still passed several critical install-progress flows:
  - blocked-capability entry
  - collapsed details behavior
  - cancel path
  - restart guidance / repair path
  - add-source validation
- `root AI-guided redirect preserves source and component` passed on Beta.

## UX Breaks That Block Certification

### 1. Setup entry is not reliable enough

Creator setup is the front door for this release. On the real Beta, the focused smoke was unable to rely on:

- `.setup-wizard-page`
- `AI-Guided Setup` heading
- `Opened for FLUX.1 Dev.` confirmation copy

Those are first-screen creator cues. If they are not consistently visible, the Setup experience is not certifiable.

### 2. Co-Director status is still not trustworthy enough

The Beta smoke for `codirector-status-cross-check` failed twice, and the live manual status check still produced:

- `statusIndicator=Degraded`
- `score=82`
- `band=Fair`

That is not the experience standard for a creator-facing "tell me if I am ready" surface.

### 3. Reload confidence is still below release quality

The install-progress reload scenario recovered only on retry. For creator-facing setup/install work, flaky reload behavior is not good enough for a final UX pass.

### 4. Setup cannot pass while AI-Guided final certification stays NO-GO

`docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md` still says:

- **NO-GO**
- broader Setup certification is not honestly complete

M5 UX cannot overrule that upstream setup verdict.

## UX Certification Verdict

**NO-GO**

The Beta still shows valuable creator-facing progress, but the experience is not final-certification quality while Setup entry is inconsistent, Co-Director status visibility is failing in live smoke, reload behavior is flaky, and AI-Guided Setup itself remains upstream `NO-GO`.
