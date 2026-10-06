# Co-Director Video Intelligence — Operational Convergence (94 → 95+)

**PREDECESSOR — not current 100% authority.** Current 100% certification lives in `docs/release-gate/codirector/CODIRECTOR_100_OPERATIONAL_CONVERGENCE.md`.

**Historical governing document for Co-Director Temporal Continuity / Video Intelligence.**

Knowledge foundation (`CODIRECTOR_KNOWLEDGE_FOUNDATION_OPERATIONAL_CONVERGENCE.md`) remains historical for the 84→94 knowledge work. This document owns the remaining `codirector.video_intelligence.ready` / InternVideo3 advisory.

---

## Identity

| Field | Value |
| --- | --- |
| Project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` — 12B — Quarters Interview |
| Take | `take_ab85f21f7a33` on Batch 1 — asset `3277533f-efc4-406b-aff7-6d08f0290efa` |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed) | `99665cf7` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Evidence | `.runtime/_vi95_live_review.json` · `.runtime/_vi95_after.json` |

---

## CURRENT SCORE

| When | Score | Band | Indicator |
| --- | --- | --- | --- |
| Before this mission | **94** | shown as Operational (incorrect label) | Operational |
| After honest VI + band audit | **100** | **Operational** | Operational |

`POST /api/codirector/status/check` with `projectId` + `sceneId` + `forceRefresh` after Studio API recycle: **17 healthy / 0 warning / 0 blocked**.

---

## CAPABILITY ROOT CAUSE

**OPTIONAL-BUT-MISCLASSIFIED**

`codirector.video_intelligence.ready` is Temporal Continuity review.

- Required model: **VideoChat3 4B** (`videochat3_4b`). Catalog `required=True`. Default `fastVisionModel`.
- Optional deep-review: **InternVideo3 8B** (`internvideo3_8b`). Catalog `required=False`. Recommended pack only. Invoked only when `deepReview` is `on`, confidence &lt; 0.45, or a prior packet exists. Failure is already non-fatal (`extras.deepReviewUnavailable`).
- `_eval_video_intelligence` previously passed InternVideo3 as `optional=`, and `_model_component_eval` marked the **whole capability DEGRADED** when any optional component was missing. That advisory capped the studio at 94.

InternVideo3 is **not** required for Temporal Continuity. It was not installed, not superseded, and was not marked `locally_verified`.

---

## INTERNVIDEO3 STATUS

**ABSENT — optional deep-review, not installed.**

Not downloaded. Not required. Not disconnected (no weights to reconnect). Not hidden.

---

## MODEL PATH

| Model | Path | State |
| --- | --- | --- |
| VideoChat3 4B | `data/models/video_understanding/videochat3-4b` | Installed (~8.96 GB), certify receipt `ok` + `liveInfer` |
| InternVideo3 8B | `data/models/video_understanding/internvideo3-8b` | Directory absent |
| Qwen2.5-Omni 7B | `data/models/video_understanding/qwen2-5-omni-7b` | Installed — **separate** Media Intelligence / `analyze.video` path |

HF (not downloaded): `yanziang/InternVideo3-8B-Instruct` @ `c4602918b65225650d152db2850fe34e01d21fcd`. VRAM catalog 16 GB.

---

## RUNTIME LOAD

Isolated VideoChat3 worker via `gpu_lease`:

- Comfy `POST /free` (unload models) — **not** kill/restart
- VRAM 2.36 GB → 29.33 GB in ~4 s
- Route A `:8192` selective-free reported “not healthy — nothing to free”; port still listening
- Preflight `ok`, `freeVramGb` 29.33

**COMFY BEFORE:** PID **45624**, `GET :8188/system_stats` 200, ~0.6 GB free  
**COMFY AFTER:** PID **45624**, `GET :8188/system_stats` 200  
**COMFY RESTARTED?:** **NO**  
**WHY?:** Ordinary VI work. `/free` only. Studio API recycled via `scripts/restart_studio_api_only.py` (newPid 56300; `comfyPidUnchanged=True`).

---

## REAL INFERENCE

Production `review_completed_batch` on Batch 1 take `take_ab85f21f7a33`.

- Packet `tcp_308fd283dc71`
- `availability`: **ready**
- `perceptionModelId`: **videochat3-4b**
- `deepReviewInvoked`: false (first-batch review; InternVideo3 not required)
- Observed: “The two anime characters are sitting on a couch. The camera zooms in on the two characters.”
- Persist: `master.temporalPackets` with probe target `vi95_cert_probe`
- Certify receipt updated from this live consumer run

No mocks. No testsrc-only claim for this packet.

---

## CO-DIRECTOR CONSUMER

| Path | Role |
| --- | --- |
| `review_completed_batch` | Temporal Continuity consumer (this capability) |
| Timeline orchestrator `ensure_temporal_packet_before_submit` | Production handoff gate |
| `compile_temporal_continuation` | Packet → next-batch prompt (H3 fence unchanged) |
| Co-Director `analyze.video` | **Qwen2.5-Omni** Media Intelligence — different capability |

Trace proven:

video asset `3277533f-…` → `review_completed_batch` → VideoChat3 worker → ready packet → Timeline master persist → capability eval (receipt + VideoChat3) → Status 100.

Take path resolution now uses **current take first**, `approvedClip` fallback (`_batch_video_path`).

---

## VIDEO INTELLIGENCE RESULT

Ready Temporal Continuity packet on the live 12B interview take. Characters visible as two seated figures; camera zoom observed. Continuity scores remain `unknown` (model returned a short visual description; packet still `ready`). InternVideo3 was not invoked and is still listed as optional-missing in capability details.

---

## REGISTRY RESULT

`codirector.video_intelligence.ready`:

- `status`: **locally_verified**
- `healthy`: **true**
- Message: VideoChat3 certified; InternVideo3 optional and not required
- Details still list `missingOptionalComponentIds: ["internvideo3_8b"]`
- `capabilities.registry` Status check: **healthy**, advisory/workflow/production blocker lists empty

Health required **certify receipt** (`ok` + `liveInfer` + revision), not file presence alone.

---

## FINAL SCORE

**100**

---

## FINAL BAND

**Operational** (≥95)

---

## BAND LABEL AUDIT

Owner policy (thresholds unchanged: 35 / 84 / 95):

| Score | Band (after) | Band (before) |
| --- | --- | --- |
| ≤35 | Blocked | Blocked |
| ≤84 (workflow) | Workflow Degraded | Fair / Degraded |
| 85–94 | **Advisory** | Operational |
| ≥95 | **Operational** | Excellent |

94 was incorrectly labeled Operational/Excellent. Indicator for advisory gaps remains Operational (studio can work); **band** is now Advisory. Header chip shows the band.

---

## REGRESSIONS

| Item | Result |
| --- | --- |
| Knowledge routing / WAN / landing | Not reopened. `codirector.grounded_routing` still healthy. |
| IC-LoRA optional policy | Not changed. |
| Timeline R2V / H3 fence | Not edited. Pre-existing `test_request_builder_consumes_ready_packet` still fails (H3 prompt fence). Not this mission. |
| Comfy `:8188` | PID 45624 throughout. `/free` only. |
| Studio API | Recycled only. |
| False Comfy offline | One UI recheck used `comfy_health_fast(3s)` and reported offline while PID 45624 + `/system_stats` 200. Fast timeout is now 8s; `TimeoutError` is `timed_out` (advisory), not `offline` (Blocked). Latest Status after recycle: **100 Operational**. |
| Tests | `test_video_intelligence_capability.py` + `test_production_assurance_truth.py` **22 passed**. Temporal continuity suite: 71 passed, 1 pre-existing R2V fail. |

---

## Limitations

- InternVideo3 8B is still **not installed**. Optional deep-review remains unavailable. That is honest and no longer caps readiness at 94.
- VideoChat3 observation on this take is a short visual summary; structured character IDs / continuity scores were not filled.
- Probe packet `vi95_cert_probe` is stored on the 12B master for evidence; it is not a Batch 2 generation handoff.
- Working tree is dirty with unrelated Timeline/MAGI/R2V work. This mission’s files are uncommitted.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — 12B Quarters Interview take |
| Frontend | PASS — Status chip/band Operational at 100 |
| API | PASS — `/status/check` forceRefresh + temporal-continuity GET |
| Backend | PASS — `review_completed_batch` + capability eval |
| Persistence | PASS — packet + certify receipt |
| Runtime | PASS — VideoChat3 isolated worker; Comfy `/free` only |
| Result | PASS — ready packet, `videochat3-4b` |
| Reload | PASS — packet still on GET temporal-continuity after API recycle |
| Downstream | PASS — registry healthy; score 100 Operational |

---

## FINAL VERDICT

**GO — CO-DIRECTOR VIDEO INTELLIGENCE OPERATIONAL >=95**
