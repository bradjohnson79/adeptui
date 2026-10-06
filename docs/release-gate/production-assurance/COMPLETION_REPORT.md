# Production Assurance + Capability Registry Truth

**Governing document for this journey.** Policy authority: `V11_READINESS_POLICY.md` and `studio-api/app/readiness/v11_policy.py`.

**FINAL VERDICT:** `GO — ADEPT UI PRODUCTION ASSURANCE + CAPABILITY REGISTRY TRUTH E2E CERTIFIED`

Knowledge foundation is a **landed dependency**, not an open PA blocker. WAN disambiguation was smoke-checked only. No glossary or knowledge tree was added here.

---

## Identity

| Field | Value |
|---|---|
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` |
| Working tree | Includes this mission; not committed unless requested |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Policy version | `v1.1` |
| Score meaning | **Adept Platform Production Readiness** |

Success string: `GO — ADEPT UI PRODUCTION ASSURANCE + CAPABILITY REGISTRY TRUTH E2E CERTIFIED`

Failure string: `NO-GO — ADEPT UI PRODUCTION ASSURANCE TRUTH INCOMPLETE`

---

## Original 84 state

Production Assurance reported **84 / Degraded / Fair** when Capability Registry had any blocker (including Temporal Continuity / VideoChat3 `MODEL_MISSING`). Every registry blocker was treated as `high` and capped the studio at 84.

A later live 84 also came from two honest-but-wrong mappings:

- probe timeouts (`comfy.health`, `codirector.provider`, `tools.registry` slow) scored as Degraded 84
- usable `DEGRADED` rows (for example `project.timeline.propose`) inherited workflow-degraded scoring and recapped 84

Those are not VideoChat3-by-name bugs. They are the same severity-architecture defect (PA-02).

## False-green 100 reproduction (PA-05)

Grok reproduced:

- Status = **100 / Operational**
- `/api/capabilities` still reported VideoChat3 / Temporal Continuity blocked

Root cause: Re-check consumed `force=False` / 300s capability TTL / 30s Status TTL. An older shared snapshot could stay green while the canonical registry was blocked.

That path is closed for explicit Re-check (`forceRefresh=true`): caches are invalidated, `warm_shared_bundle(force=True)` runs, and the UI writes the POST result through the latest-status cache.

---

## Root causes

1. **One severity for every registry blocker** — production, continuity-review, and optional gaps all capped at 84.
2. **Two authorities, two clocks** — Status TTL and Capability Registry TTL could disagree after Re-check.
3. **Ambiguous score meaning** — the number looked like “platform finished” while creator-path truth was missing.
4. **VideoChat3 treated as a core outage** without reading the Temporal Continuity contract.
5. **WAN / knowledge mistakes classified as runtime failure** — that work belongs to the separate knowledge mission (now landed).

---

## Closure 1 — Frozen v1.1 readiness policy

Single authority: `studio-api/app/readiness/v11_policy.py`.

| Class | Meaning | Status effect |
|---|---|---|
| PLATFORM CRITICAL | Adept cannot function meaningfully | Blocked · ≤35 |
| PRODUCTION CRITICAL | A core v1.1 creator workflow cannot run | Blocked · ≤35 |
| WORKFLOW DEGRADED | Core platform works; a supported workflow loses capability | Degraded · ≤84 |
| ADVISORY / REVIEW DEGRADED | Production works; review assistance is reduced | Operational · 85–94 · never Excellent / never 100 |
| OPTIONAL | Does not affect v1.1 readiness | Visible note only — does not cap Excellent |

Usable `DEGRADED` rows still appear. Production-class `DEGRADED` scores as workflow-degraded. Workflow/advisory `DEGRADED` scores as advisory. A Capability Registry probe timeout uses the advisory fallback so lost class cannot recreate “any high blocker → 84.”

## Closure 2 — VideoChat3 v1.1 role

Product contract: **required for Co-Director Temporal Continuity review, not for Adept v1.1 core production.**

| Fact | Decision |
|---|---|
| Setup catalog `videochat3_4b.required` | Stays **True** |
| Capability | `codirector.video_intelligence.ready` |
| Display | Co-Director Temporal Continuity |
| Readiness class | `advisory_review_degraded` |
| v1.1 requirement | `continuity_review` |
| Scoring | By class, not by the string `videochat3` |
| Install in this journey | **No** — preserve the real missing/optional-weight state |

Live 2026-09-05: required VideoChat3 4B weights are present; optional `internvideo3_8b` is missing. Registry status is **degraded** / `MODEL_MISSING` / `advisory_review_degraded`. Effect: “Temporal Continuity review is degraded. Timeline generation still works.”

This is still PA-01 honesty (not a fake port failure). It is **not** a core production outage.

## Closure 3 — Status ↔ Capability Registry

Explicit Re-check and Deep Diagnostic:

1. set `forceRefresh=true`
2. invalidate Status TTL
3. invalidate Capability Registry cache
4. `warm_shared_bundle(force=True)`
5. UI writes the POST run into the latest-status cache

After the same Re-check:

- Registry Temporal Continuity degraded / advisory → Status warning / 85–94 Operational
- Registry production blockers present → Status Blocked ≤35
- Registry cleared and no advisory gaps → Status may reach Excellent

No period after that Re-check where Registry shows a classified gap and Status reports 100.

## Closure 4 — Semantic severity

Capability rows expose `readinessClass`, `v11Requirement`, `workflowScope`, `severity`, `productionEffect`. Production Assurance scores from that classification. The UI does not rewrite the score.

## Closure 5 — Score meaning

The gauge is **Adept Platform Production Readiness**, not infrastructure-only health.

| Band | When |
|---|---|
| Excellent | Operational and ≥95 with no open advisory/review/production gaps |
| Operational | Production works; advisory/review gaps may remain (85–94) |
| Fair | Workflow-degraded, 70–84 |
| Degraded | Workflow-degraded, <70 |
| Blocked | Platform or production-critical failure |

## Closure 6 — Creator-path coverage

Lightweight, no generation:

| Check | Live Korri result |
|---|---|
| `create.path` | Healthy — list/open only, `createdProject=false` |
| `timeline.generator_truth` | Healthy — 16 honest rows |
| `timeline.context_binding` | Healthy when a scene is bound; `not_applicable` without one |
| `posecraft.identity_nav` | Healthy — `load_scene` only |
| `codirector.grounded_routing` | Healthy — knowledge foundation landed and routed |

## Closure 7 — Co-Director knowledge dependency

**LANDED.** `codirector.grounded_routing` reports schema `adept-codirector-knowledge/v1`, 53 entries, routed.

Playwright + live chat smoke (not a knowledge rewrite):

- “What is WAN in this Adept project?” → First/Last Frame video, not Wide Area Network
- “What does WAN mean in computer networking?” → Wide Area Network

No new glossary files or knowledge tree were added in this journey.

## Closure 8 — Legacy runtime authority

| Fact | Live |
|---|---|
| Live session owner | Adept Runtime Supervisor |
| `taskRegistered` (AdeptRuntimeService) | false |
| `legacyOwners` | `["AdeptBetaBackendManager"]` |
| `legacyAffectsCurrentSession` | false |
| `leftoverMayAffectNextLogon` | true |
| Retired this run | **No** |

The leftover name is disclosed, not retired. Retiring it while `AdeptRuntimeService` is unregistered would be unsafe. One live authority remains. This journey did not call `retire_legacy_tasks` and did not touch Comfy lifecycle.

## Closure 9 — Deep Diagnostic

Read-only on `HealthRun`: `readOnly=true`, `mutatesRuntime=false`, `mutatesConfig=false`, `installsModels=false`. Deep mode force-refreshes. Not Self-Heal.

---

## Live Status acceptance

Project: Korri Anadriya. API after final recycle: PID **17200**. Comfy PID **69108** unchanged.

| Step | Result |
|---|---|
| Open Co-Director Status | Operational chip; panel shows Production Assurance |
| Fresh `/api/capabilities?refresh=true` | Video intel **degraded** / `advisory_review_degraded`; `blockers=[]`; `productionBlockers=[]` |
| Re-check `forceRefresh=true` | **94 / Operational / Operational** · 16 healthy · 2 warning · 0 blocked |
| Authorities agree | Registry: Temporal Continuity degraded/advisory. Status: same gap as Review notes. Neither claims 100. Neither claims Blocked. |
| Known degraded condition | Optional InternVideo3 missing (safe, already present). Severity: Review notes, not Blockers. |
| Restore | Not performed — would require Source Manager install. Out of scope. |
| Re-check again (browser 7:30:55 PM) | Still **94 / Operational**. No false-green. No false-blocked. |

Creator-path checks and Comfy/Ollama were healthy on the final run. Probe-timeout noise no longer caps 84.

## Playwright

`tests/e2e/codirector/codirector-production-assurance-truth.spec.ts`

| Run | Result |
|---|---|
| After scoring repair, API PID 26712 | **1 passed** (1.2m) |
| After final recycle, API PID 17200 | **1 passed** (54.8s) |

Coverage: fresh capability sync, Re-check freshness, advisory gap prevents 100/Excellent/Blocked, severity/Operational labels, creator-path ids, runtime-authority fields, WAN domain smoke. No Runtime Supervisor regression (leftover reported, not retired).

Unit tests: `test_v11_readiness_policy.py` + `test_production_assurance_truth.py` → **22 passed** (live snapshot test also passed separately, 49s).

## Subagent review

Independent challenge: [PA truth challenge](d253a534-d816-461a-97c1-28156f137837) — `READY FOR PRIMARY REVIEW` only.

Must-fix on the successful Re-check path: **none**.

Residuals they raised, resolved by primary before this verdict:

1. Registry timeout inferred `WORKFLOW_DEGRADED` from `criticality=high` → fallback class is now advisory.
2. OPTIONAL leftover was capping Excellent → leftover is visible and does not own the score.
3. UI 30s latest cache could overwrite a Re-check → POST now invalidates and writes through `rememberLatestStatus`.

Mount auto-check remains `force=False` (30s/300s TTL). Explicit Re-check is the freshness gate. Creator-path checks remain smoke, not generate.

## Primary double-check

| Item | Result |
|---|---|
| Capability Registry | Video intel degraded/advisory; no production blockers |
| Status | 94 Operational, not 100, not 84, not Blocked |
| Re-check | forceRefresh; both authorities agree |
| VideoChat3 state | Catalog required stays True; continuity-review only; optional InternVideo3 missing preserved |
| Severity | Review notes for advisory; leftover optional; production healthy |
| Runtime authority | Supervisor live; leftover disclosed; not retired |
| Creator-path checks | Present, healthy, no generation |
| Knowledge | Landed smoke only — no PA knowledge rewrite |

---

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | **PASS** — Status chip → panel → Re-check |
| Frontend | **PASS** — `forceRefresh: true`; score semantics; Review notes |
| API | **PASS** — `/api/codirector/status/check` + `/api/capabilities?refresh=true` |
| Backend | **PASS** — v1.1 policy + semantic weighting |
| Persistence | **PASS** — latest run persisted; Re-check write-through |
| Runtime | **PASS** — Comfy PID 69108 healthy; Supervisor unchanged |
| Result | **PASS** — 94 Operational with Temporal Continuity visible |
| Reload | **PASS** — second Re-check still 94 Operational |
| Downstream | **PASS** — creator-path checks healthy; knowledge smoke WAN-correct |

---

## Runtime / Comfy

| | |
|---|---|
| COMFY BEFORE | PID **69108** · HTTP 200 |
| COMFY AFTER | PID **69108** · HTTP 200 |
| COMFY RESTARTED? | **NO** |
| WHY? | Ordinary PA/API work. Studio API recycled only via control-plane `POST /restart-api`. |

API recycles this journey (Comfy unchanged each time): 18208 → 59604 → 71588 → 26712 → **17200**.

---

## Limitations

- Optional InternVideo3 8B remains missing. Temporal Continuity review stays degraded until installed through Source Manager / Setup. That is honest advisory state, not a PA defect.
- `AdeptBetaBackendManager` remains a next-logon leftover until `AdeptRuntimeService` is proven. Not retired here.
- Creator-path checks do not run generation.
- Auto-open Status may still use TTL until the creator clicks Re-check.

---

## Manual review

1. Open `http://127.0.0.1:5173/co-director?projectId=beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
2. Click the Operational chip → Status.
3. Confirm **Adept Platform Production Readiness · v1.1**, score **94**, Review notes for Temporal Continuity.
4. Click Re-check. Confirm the number does not jump to 100 while Temporal Continuity is still degraded, and does not drop to 84/Blocked from that review gap alone.

---

## FINAL VERDICT

`GO — ADEPT UI PRODUCTION ASSURANCE + CAPABILITY REGISTRY TRUTH E2E CERTIFIED`
