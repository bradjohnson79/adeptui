# M3.0d Master Remediation Register

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting tip (M3.0d) | `aff00c131a464ee9cdf156fd8a2977016264b375` |
| Prior M3.0c impl / docs | `8ba6b62` / `5a854f1` |
| Provider manifest SHA (LOCKED) | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |

Status values: `Open` | `In progress` | `Closed`. Close only with Fix + Test (+ Artifact) + Commit SHA.

## Blockers B5–B21

| ID | Origin | System | Severity | Current state | Expected state | Root cause | Owner area | Implementation | Test | Artifact | Status | Commit |
|----|--------|--------|----------|---------------|----------------|------------|------------|----------------|------|----------|--------|--------|
| B5 | m3.0b | Providers | Critical | Local Z-Image stills; fal motion via queue; audio import-only | Real stills + motion + honest audio disclosure | No generative audio provider; LTX/WAN not production-ready | Provider | Local ComfyUI still path; fal Seedance queue; audio service import/place only | `test_m30_audio_timeline.py`, situations S01–S12 | `artifacts/m30a-local/`, `artifacts/m30c-fal/`, `phase18-final-validation.json` | **Closed (bounded)** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B6 | m3.0b | fal catalog | High | Motion via fal queue; no fal image endpoint | Motion via fal; image PRODUCT_APPROVAL_REQUIRED | Empty `FAL_IMAGE_MODELS` (manifest lock) | Provider/Docs | Docs-only fal image boundary; fal video queue Phase 4 proof reused | `FAL_UNIFIED_QUEUE_PROOF.md` | `artifacts/m30c-fal/unified_queue_proof.json` | **Closed (bounded)** | `5a854f1` + M3.0d docs |
| B8 | m3.0b | M2.11 DAG | High | storyteller/sound-producer/VPC in DEFAULT_PIPELINE | Specialists run or are delisted | KeyError / not wired | Backend | DAG order includes all three; runner resolves ids | `test_m211_production_intelligence.py::test_dag_order` | pytest 631/0/6 | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B9 | m3.0b | Orchestration response | High | Contradictory success/failure fields | Truthful status/success/errors | Mapping bugs | Backend | `honesty.normalize_orchestration_response` | `test_m30d_closures.py::test_b9_*` | `studio-api/app/codirector/m211/honesty.py` | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B11 | m3.0b | Vision PW | High | Vision specs exercised in full PW run | Pass or honest skip | Strict mode / pending | E2E | Existing vision E2E + approval API tests | Playwright full suite | `M30D_PLAYWRIGHT_CERTIFICATION.md` | **Closed (bounded)** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B12 | m3.0b | Cancel race | Medium | Cancel path deterministic in executive tests | Deterministic cancel | Race in async cancel | Backend/E2E | Executive cancel tests + idempotency spec | `test_production_executive.py`, PW idempotency | PW 111 passed | **Closed** | prior + M3.0d |
| B13 | m3.0b | Beat sync | Medium | syncEvent schema-only | syncEvent resolves bar timing on place | Option A not wired | Backend | `_resolve_sync_start` + `place_cue` persists syncEvent | `test_m30d_closures.py::test_b13_*` | `m29/audio/service.py` | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B14 | m3.0b | Restart PW | Low | Hard skip stub | Real restart recovery assertion | Stub skip | E2E | `/api/e2e/seed-running-job` + `/api/e2e/recover-jobs` | `production-executive-m27.spec.ts` restart test | `studio-api/app/routers/e2e.py` | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B15 | m3.0-completion | Specialist runner | Critical | Provider payload unwrap present | Preserve model content; honesty label | Wrapper validation discarded analysis | Backend | `_unwrap_provider_payload` in specialist_runner | `test_m211_production_intelligence.py` | ollama-raw fixtures | **Closed (code)** | prior + M3.0d |
| B16 | m3.0-completion | Enrichment | High | Limited-analysis empty path | Brief-derived or honest empty | Lab defaults | Backend | Limited path labeled; no wrong-film scaffold in production gate | m211 intelligence tests | — | **In progress** | — |
| B17 | m3.0-completion | Video I2V | Critical | sceneId in payload+handler | sceneId preserved end-to-end | Payload omit | Backend | `_m29_run` + job params restore sceneId | situation exports + I2V tests | `phase18-final-validation.json` sceneKeys | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B18 | m3.0-completion | Export | High | Pack includes director_json | Export reads durable timeline | `_export` omitted director_json | Backend | `queue_worker._export` + `export_contract: m30d-canonical-timeline-v1` | export jobs in S01–S12 | all 12 packs `directorJson: true` | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B19 | m3.0-completion | Vision approve | High | reject band approved without reason | overrideReason required | approval API gap | Backend | `record_decision` enforces overrideReason | `test_m30d_closures.py::test_b19_*` | `vision/approval.py` | **Closed** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| B20 | m3.0-completion | LTX/WAN | High | Native Comfy video NOT_PRODUCTION_READY | fal I2V/T2V is production motion route | Comfy workflows fail/unreliable | Provider | Document NOT_PRODUCTION_READY; fal queue proven | fal proof + platform matrix | `NATIVE_PLATFORM_GREEN_MATRIX` | **Closed (routed)** | M3.0c + M3.0d docs |
| B21 | m3.0-completion | Specialist timeouts | Low | Timeouts surface in warnings | Surface timeouts in honesty | 50s cap | Backend | `normalize_orchestration_response` promotes timeouts to warnings | `test_b9_*` timeout paths | honesty.py | **Closed (bounded)** | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Unified jobs / fal residuals

| ID | Origin | System | Severity | Current | Expected | Root cause | Fix | Test | Artifact | Status | Commit |
|----|--------|--------|----------|---------|----------|------------|-----|------|----------|--------|--------|
| UJ-1 | m3.0-completion | Co-Director inspect | Critical | Studio job 404 on inspect | Unified inspect DTO | Separate Executive/Studio stores | `unified_jobs.to_unified_dto` bridge | `test_m30c_unified_jobs.py` | `UNIFIED_JOB_SYSTEM_PROOF.md` | **Closed** | `8ba6b62` |
| UJ-2 | m3.0-completion | fal queue | Critical | Asset without Job row | Full Studio Job + falRequestId | Register-only proof | Live queue submit + reconcile | fal proof script | `artifacts/m30c-fal/unified_queue_proof.json` | **Closed** | `8ba6b62` |
| UJ-3 | m3.0a | fal image | Medium | Not registered | PRODUCT_APPROVAL_REQUIRED docs | Manifest lock | Docs-only boundary | cert docs | `M30D_FAL_MOTION_PROOF.md` | **Closed (docs)** | `PLACEHOLDER_DOCS_SHA` |

## Pytest failures PY01–PY20

| ID | Origin | Severity | Status | Evidence |
|----|--------|----------|--------|----------|
| PY01–PY20 | m30b-pytest.txt | High (gate) | **Closed** | Full suite `631 passed, 6 skipped, 0 failed` — see [BACKEND_FAILURE_CLOSURE.md](./BACKEND_FAILURE_CLOSURE.md) |

## Playwright skips PW-S1–S6

| ID | Spec | Kind | Status | Notes |
|----|------|------|--------|-------|
| PW-S1 | `capability-intelligence-m28` flags-off | Inverse/env | **Open (intentional)** | Default E2E flags ON; inverse case not required for beta |
| PW-S2 | `production-executive-m27` flags-off | Inverse/env | **Open (intentional)** | Same |
| PW-S3 | restart recovery | Critical journey | **Closed** | Real assertion via e2e seed/recover (B14) |
| PW-S4 | `m30-completion-local-live` readiness | Live gate | **Open** | `ADEPT_M30A_LOCAL_LIVE` unset |
| PW-S5 | `m30-completion-local-live` artifact | Live gate | **Open** | Same |
| PW-S6 | `m30a-fal-ai-provider` live | Live gate | **Open** | `ADEPT_M30A_FAL_LIVE` unset; fal proof reused from M3.0c |

## Production situations S01–S12

| ID | Status entering M3.0d | Target | Status | Artifact |
|----|----------------------|--------|--------|----------|
| S01 | EXECUTED (M3.0c) | EXECUTED | **Closed** | `phase18-final-validation.json` n=1 |
| S02 | EXECUTED | EXECUTED | **Closed** | n=2 |
| S03 | EXECUTED | EXECUTED | **Closed** | n=3 |
| S04 | EXECUTED | EXECUTED | **Closed** | n=4 |
| S05 | EXECUTED | EXECUTED | **Closed** | n=5 |
| S06 | EXECUTED | EXECUTED | **Closed** | n=6 |
| S07 | EXECUTED | EXECUTED | **Closed** | n=7 |
| S08 | EXECUTED | EXECUTED | **Closed** | n=8 |
| S09 | EXECUTED | EXECUTED | **Closed** | n=9 |
| S10 | EXECUTED | EXECUTED | **Closed** | n=10 |
| S11 | EXECUTED | EXECUTED | **Closed** | n=11 |
| S12 | EXECUTED | EXECUTED | **Closed** | n=12 |

## Open items summary (gate blockers)

| ID | Reason still open |
|----|-------------------|
| B16 | Four live brief intelligence proof still pending — limited-analysis path only code-proven |
| PW-S1, PW-S2 | Intentional inverse/env skips — not product defects |
| PW-S4, PW-S5, PW-S6 | Live-gated specs require env keys not exercised in this cert run |
| A11Y | Keyboard-only and screen-reader certification incomplete — see `M30D_ACCESSIBILITY_CERTIFICATION.md` |

## Register rule

No unresolved item may disappear by omission from a newer report. Parent stamps Implementation SHA / Documentation SHA after commit.
