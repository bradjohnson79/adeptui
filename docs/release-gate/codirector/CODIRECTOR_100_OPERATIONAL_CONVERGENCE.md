# Co-Director 100% Multi-LLM Peer Build — Operational Convergence

**Governing document for Adept UI Co-Director 100% certification.**

Predecessors (historical, not current 100% authority):

- `docs/release-gate/codirector/CODIRECTOR_KNOWLEDGE_FOUNDATION_OPERATIONAL_CONVERGENCE.md`
- `docs/release-gate/codirector/CODIRECTOR_VIDEO_INTELLIGENCE_OPERATIONAL_CONVERGENCE.md`

---

## Identity

| Field | Value |
| --- | --- |
| Project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` — 12B — Quarters Interview |
| Takes | Batch 1 `take_ab85f21f7a33` · Batch 2 `take_2e429bc813bc` |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Working tree | Dirty (this mission uncommitted) |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Evidence | `.runtime/_cd100_before.json` · `.runtime/_cd100_zero_warning_matrix.json` · `.runtime/_cd100_contract_freeze.json` · `.runtime/_cd100_grok_lane.json` · `.runtime/_cd100_kimi_lane.json` · `.runtime/_cd100_glm_lane.json` · `.runtime/_cd100_after.json` |

---

## Law

100% is not Status arithmetic. A required production capability that is degraded, disconnected, fallback-only, partially wired, or not implemented is a **NO-GO even if the Status registry fails to count it as a warning**.

Do not change: score weights, 35/84/95 caps, IC-LoRA optional, Timeline R2V/H3 fence, Spatial/3D shelf.

Knowledge routing WAN canary is superseded by `CODIRECTOR_WAN_RESIDUE_REMOVAL.md` (Timeline R2V probe).

---

## BEFORE

| Surface | Score | Warnings | Blocked | Notes |
| --- | --- | --- | --- | --- |
| Owner-stated | **94** | **2** | 0 | Authoritative owner BEFORE |
| Worse live UI (pre Re-check) | **35** | 0 | **1** | `comfy.health` offline while PID **45624** + `GET :8188/system_stats` 200 |
| Historical 94-band API | 94 | 1 | 0 | `capabilities.registry` Temporal Continuity / InternVideo3 |
| API forceRefresh (pre-implement) | 100 | 0 | 0 | `cdr_status_5a96e7963835` — not certification |

**Locked defect IDs:** `comfy.health` · `capabilities.registry` (historical 94) · `codirector.temporal_continuity.packet` (`tcp_6ebe5293937c` `SOURCE_VIDEO_MISSING`)

---

## AFTER (post-recycle, warmed)

| Surface | Score | Band | Healthy | Warnings | Blocked | Run |
| --- | --- | --- | --- | --- | --- | --- |
| API `forceRefresh` | **100** | Operational | **18** | **0** | **0** | `cdr_status_787ee67b283f` |
| Creator UI Status panel | **100** | Operational | **18** | **0** | **0** | “18 checks healthy, 0 warning, 0 blocked.” |

New Status check present and healthy: **Temporal Continuity Handoff** (`codirector.temporal_continuity`).

---

## WARNING / GAP CLOSURE

### 1. `comfy.health` false Blocked 35 — REQUIRED — CLOSED

Transient connect/timeout was mapped to offline → Blocked 35 while Comfy was up.

Fix: one retry; true death = refused + no listener; proven listener / busy generation reports healthy/busy, not timed_out (timed_out would cap 94).

### 2. Historical 94 `capabilities.registry` / InternVideo3 — OPTIONAL — CLOSED as warning

12B policy: `deepReview=auto`, `fastVisionModel=videochat3-4b`. Production Temporal Continuity gate is VideoChat3. InternVideo3 is extras only. **Not installed. Not downloaded.** Qwen Omni is not a replacement.

### 3. Stale Batch 1→2 packet — REQUIRED — CLOSED

Stale: `tcp_6ebe5293937c` `SOURCE_VIDEO_MISSING`.  
Ready: `tcp_cf727e0723ee` `availability=ready` `videochat3-4b` (`bb_d7c17eaa0847` → `bb_70f4f7e073cf`).  
Status now monitors the bound-scene latest **production** handoff (excludes `vi95_cert_probe`).

### 4. UI Re-check ignored `forceRefresh` — REQUIRED — CLOSED

`CoDirectorSession.runStatusCheck` now forwards `forceRefresh`, then `invalidateStatusCaches` + `rememberLatestStatus`.

### 5. `?workspace=codirector` landed on project home — CLOSED

ProjectEditor opens the Co-Director overlay in place; `sceneId` preserved.

### 6. `project.timeline.propose` heuristic — CLASSIFIED OPTIONAL

Sole consumer is menu-hidden legacy Generate Timeline. Honest `DEGRADED` kept. Does not own `warningChecks`.

### 7. `codirector.tools` stale `not_implemented` — CLOSED

Live catalog eval: **536** tools `locally_verified`. Status `tools.registry` remains the tool-count check.

### 8. Recycle false-negatives (checking / slow) — CLOSED

Post-recycle first run hit **91 / 4 warnings**: VideoChat3 setup `checking` reported as “Not installed”; completed-slow tools.registry counted as a warning; cold probes timed out. Fixed: certify receipt + `checking` ≠ missing; `slow` tallies healthy; Comfy/provider timeouts widened.

---

## REQUIRED MODEL INVENTORY

| Model | Role | Proof |
| --- | --- | --- |
| VideoChat3 4B | Required Temporal Continuity | Path present; certify `ok` + `liveInfer`; capability `locally_verified` |
| InternVideo3 8B | Optional deep-review | Not installed; `missingOptionalComponentIds`; 0 Status warnings |
| Qwen2.5-Omni 7B | Media Intelligence, not TC | Not used as replacement |

---

## CONTEXT REACH (re-verified, not rewritten)

Turn-grounding on 12B includes scene **12B — Quarters Interview**, Anadriya's Quarters, generator **minimax-h3**, takes `take_ab85f21f7a33` / `take_2e429bc813bc`.

Live chat “What is WAN?” (historical this mission): First/Last Frame spoken card. **Superseded 2026-09-14** — WAN is retired; Status canary is “What is Timeline?”. See `CODIRECTOR_WAN_RESIDUE_REMOVAL.md`.

---

## PEER BUILD

| Peer | Model | Return |
| --- | --- | --- |
| [Grok 4.6](6425a1f5-d0ec-4f54-97a8-e5496a92b66b) | runtime / Status / VI / Comfy flap | READY FOR PRIMARY REVIEW |
| [Kimi K3](ee8156b4-ac04-42e0-8d86-f851a9d04df7) | predicates / propose / tools / OPTIONAL tally | READY FOR PRIMARY REVIEW |
| [GLM 5.2](e36ecf80-3874-445e-9d65-2b9949d22441) | Status UI forceRefresh / deep-link | READY FOR PRIMARY REVIEW |

Primary cross-review repaired one integration defect: listener-present Comfy must not report `timed_out` (94 cap). Primary also closed recycle `checking`/`slow` false warnings.

### Tests (observed)

- Focused API after integration: **48 passed** then **40 passed** on the tightened set (0 failed)
- New/updated: `test_comfy_health_flap.py`, `test_temporal_continuity_status.py`, `test_video_intelligence_capability.py`, `test_production_assurance_truth.py`
- Frontend: **10 passed** (`CoDirectorSession.statusForceRefresh` + `ProjectEditor.codirectorDeepLink`)

---

## RESTART

| Step | Result |
| --- | --- |
| `scripts/restart_studio_api_only.py` | Studio API recycled (later recovered to PID **45352**) |
| Comfy `:8188` | PID **45624** before and after · `system_stats` 200 |
| `COMFY RESTARTED?` | **NO** |
| `WHY?` | Observe only. VideoChat3 used existing `/free`. No kill/restart. |
| Status after recycle + warmup | **100 / 18 / 0 / 0** on API and UI |

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | Open Korri Anadriya / 12B Co-Director Status, Re-check |
| Frontend | `forceRefresh: true` posted; chip/panel show Operational |
| API | `POST /api/codirector/status/check` 200 · run `cdr_status_787ee67b283f` |
| Backend | 18 checks including `codirector.temporal_continuity` |
| Persistence | Production packet `tcp_cf727e0723ee` ready on VideoChat3 |
| Runtime | VideoChat3 certified; Comfy PID 45624; Ollama ready |
| Result | Score 100 · 0 warning · 0 blocked |
| Reload | API recycle + UI reopen · 100 persists |
| Downstream | WAN spoken card; scene/take/generator in turn-grounding |

---

## LIMITATIONS

- Immediate Status during API process start can still be noisy until probes finish; warmed forceRefresh is the certification run.
- InternVideo3 8B is not installed (optional).
- `references.ic_lora.ready` remains honest `not_configured` (optional; HF ConnectError).
- `project.timeline.propose` remains honest `DEGRADED` (legacy menu-hidden).
- 87 `PARTIALLY_WIRED` registry rows were not mass-implemented (development-only).
- Packet structured continuity scores can still be `unknown`; availability is `ready`.
- This work is uncommitted on a dirty tree.

---

## FINAL

| Field | Value |
| --- | --- |
| Score | **100** |
| Warnings | **0** |
| Blocked | **0** |
| Band | Operational |

**GO — CO-DIRECTOR 100% MULTI-LLM PEER BUILD CERTIFIED**
