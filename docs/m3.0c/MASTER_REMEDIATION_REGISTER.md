# M3.0c Master Remediation Register

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Starting tip | `958edbe` |
| Manifest | `cf99d7e5…` LOCKED |
| Source | M3.0b FINAL_BETA_BLOCKERS, M3.0 completion residuals, pytest list, Playwright skips, platform inventory |

Status values: `Open` | `In progress` | `Closed`. Commit filled when closed in M3.0c.

## Blockers B1–B21

| ID | Origin | System | Severity | Current state | Expected state | Root cause | Owner area | Fix | Test | Artifact proof | Status | Commit |
|----|--------|--------|----------|---------------|----------------|------------|------------|-----|------|----------------|--------|--------|
| B1 | m3.0b | Image/Video generate | Critical | Was minting phantom assetIds | Withhold assetId until real artifact | Draft version on empty generate | Backend | Honesty path in Image/VideoService | test_m30b_beta_blockers | prior | Closed | `87e1d47` |
| B2 | m3.0b | M2.14 UI | Critical | Flags omitted from health | Serialize unifiedExperienceEnabled etc. | ProviderHealth.to_dict gap | Backend/FE | Flags on ProviderHealth | test_m30b_beta_blockers | prior | Closed | `87e1d47` |
| B3 | m3.0b | Audio mix | Critical | Ops shape silent no-op | Dict/string ops apply loudnorm | Executor stringified dict | Backend | normalize_audio_ops | test_m30b_beta_blockers | prior | Closed | `87e1d47` |
| B4 | m3.0b | Audio timeline | High | Generated cues stranded | Import→place works; generate needs provider | assetId null on generate | Backend | Import path closed | B4 proof + situations | import 12/12 | Closed (import) | `87e1d47` |
| B5 | m3.0b | Providers | Critical | Audio gen missing; video broken; stills OK | Real stills + motion + honest audio | No audio provider; video path bugs | Provider | Local Z-Image + fal queue; audio import-only disclosure | live proofs | m3.0c | In progress | |
| B6 | m3.0b | fal catalog | High | I2V-only; no fal image | Motion via fal queue; image PRODUCT_APPROVAL_REQUIRED | Empty FAL_IMAGE_MODELS (locked) | Provider/Docs | Docs-only Phase 5; fal video queue Phase 4 | matrix docs | m3.0c | In progress | |
| B7 | m3.0b | Intelligence | High | Was use_provider=False | Provider when healthy | Superseded by B15 | Backend | use_provider fix prior | intelligence proof | prior | Closed→B15 | `87e1d47` |
| B8 | m3.0b | M2.11 DAG | High | storyteller/sound-producer/VPC never run | Run or remove from DAG | KeyError / not wired | Backend | Wire or delist | test_m211 | | Open | |
| B9 | m3.0b | Orchestration response | High | Contradictory fields | Truthful modelUsed/errors/missingAssets | Mapping bugs | Backend | Align response fields | m211 tests | | Open | |
| B10 | m3.0b | Bible browser | Critical | Was red | Approve→v2 reject→v1 | Mock field appearance | FE/E2E | Fixed | B10 proof | prior | Closed | `87e1d47` |
| B11 | m3.0b | Vision PW | High | Specs failed | Pass or honest skip | Strict mode / pending | E2E | Closure Phase 13 | PW | prior partial | Open | |
| B12 | m3.0b | Cancel race | Medium | Flaky cancel | Deterministic cancel | Race | Backend/E2E | Stabilize | PW | | Open | |
| B13 | m3.0b | Beat sync | Medium | syncEvent unused | Implement or remove promise | Schema-only | Backend | place-cue or drop claim | audio tests | | Open | |
| B14 | m3.0b | Restart PW | Low | Hard skip stub | Real assertion or delete | Stub | E2E | Replace skip | PW | | Open | |
| B15 | m3.0-completion | Specialist runner | Critical | Analysis discarded | Preserve model content; honesty honest | Wrapper validation | Backend | unwrap+aliases (in tree) | specialist tests | ollama-raw | In progress | |
| B16 | m3.0-completion | Enrichment | High | Wrong-film scaffold | Brief-derived or empty | Lab defaults | Backend | Limited empty path present | m211 | | In progress | |
| B17 | m3.0-completion | Video I2V | Critical | sceneId dropped | sceneId in payload+handler | Payload omit | Backend | payload+`_m29_run` restore | regression | | In progress | |
| B18 | m3.0-completion | Export | High | Pack omits director_json | Include timeline | _export scenes omit | Backend | queue_worker._export fix | export test | | In progress | |
| B19 | m3.0-completion | Vision approve | High | reject band approved w/o override | Require override | approval API | Backend | Enforce in approve path | vision tests | | Open | |
| B20 | m3.0-completion | LTX/WAN | High | Native video fail | Fix or fal I2V path | Comfy workflows | Provider | Prefer fal motion | live | | Open | |
| B21 | m3.0-completion | Specialist timeouts | Low | Silent roster shrink | Surface timeouts | 50s cap | Backend | honesty notes | | | Open | |

## Unified jobs / fal residuals

| ID | Origin | System | Severity | Current state | Expected | Root cause | Owner | Fix | Test | Status | Commit |
|----|--------|--------|----------|---------------|----------|------------|-------|-----|------|--------|--------|
| UJ-1 | m3.0-completion | Co-Director inspect | Critical | 404 Studio jobs | Unified inspect | Separate stores | Backend | Bridge inspect | test_m30c_unified_jobs | Open | |
| UJ-2 | m3.0-completion | fal queue | Critical | Asset without Job | Full Studio Job path | Register-only proof | Backend/Provider | Live queue job ≤$15 | FAL_UNIFIED_QUEUE_PROOF | Open | |
| UJ-3 | m3.0a | fal image | Medium | Not registered | PRODUCT_APPROVAL_REQUIRED docs | Manifest lock | Docs | Phase 5 docs only | cert doc | Open | |

## Pytest failures (20)

| ID | Origin | Severity | Status |
|----|--------|----------|--------|
| PY01–PY20 | m30b-pytest.txt | High (gate) | Open — see BACKEND_FAILURE_CLOSURE.md |

## Playwright skips (6)

| ID | Spec | Kind | Status |
|----|------|------|--------|
| PW-S1 | capability-intelligence-m28 flags off | Inverse/env | Open |
| PW-S2 | production-executive-m27 flags off | Inverse/env | Open |
| PW-S3 | restart recovery stub | Critical journey | Open (B14) |
| PW-S4/5 | local-live gated | Live | Execute in cert run |
| PW-S6 | fal live gated | Live | Execute in cert run |

## Platform rows (summary)

See NATIVE_PLATFORM_INVENTORY — 8 PRESENT / 8 PARTIAL / 2 ABSENT (color, subs). Full green matrix in Phase 6 doc.

## Situations

| ID | Status entering | Target |
|----|-----------------|--------|
| S01–S12 | PARTIAL | EXECUTED |

## Register rule

No unresolved item may disappear by omission from a newer report. Close only with Fix + Test (+ Artifact when applicable) + Commit SHA.
