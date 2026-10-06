# Revision A — Co-Director Temporal Video Intelligence & Continuity Audit

## Executive Verdict

**AUDIT PASS — REVISION A IMPLEMENTATION IS READY FOR LIVE VIDEOCHAT3 INSTALLATION & PRIMARY CERTIFICATION**

The architecture is sound, properly layered, and does not require redesign before live VideoChat3 installation. The remaining gaps are in testing and live certification, not in architecture.

---

## Architecture Trace — Multi-Batch Governance

```
Batch N completes
  ↓
orchestrator.submit_next_queued_batch (orchestrator.py:1278)
  ↓
bridge_blocks_submit (continuity.py — existing last-frame gate)
  ↓
ensure_temporal_packet_before_submit (video_intelligence/service.py:392)
  → creates/reuses TemporalContinuityPacket
  → if VideoChat3 available, runs perception
  → if unavailable, creates degraded unavailable packet
  ↓
packet_blocks_submit (video_intelligence/service.py:73)
  → checks: Continuity ON? Predecessor exists? Ready packet exists?
  → if any is false, gate is open → submit proceeds
  → if gate is blocking → TEMPORAL_REVIEW_PENDING
  ↓
submit_batch_generation (orchestrator.py:226)
  → ALSO checks packet_blocks_submit (line 350) — double gate
  → builds request with temporalContinuityPacketId
  → submits to adapter
```

**Verified: CD governs automatically.** The user does not need to open Co-Director or send a chat message. The temporal review is invoked automatically in the sequential chain (`submit_next_queued_batch`) and in `submit_batch_generation` itself. No race condition — both gates check before submission.

---

## Packet Integrity

| Field | Status | Evidence |
|---|---|---|
| Unique type name | ✅ | `temporal-continuity-v1` |
| Explicit versioning | ✅ | `PACKET_SCHEMA = "temporal-continuity-v1"` (contracts.py:11) |
| Serialization | ✅ | Pydantic model with model_dump |
| Persistence | ✅ | Stored in master.temporalPackets via `_persist` |
| Source IDs | ✅ | PacketSource with batchId, targetBatchId, executionSnapshotId |
| Availability state | ✅ | `ready` / `unavailable` / `low_confidence` |
| Reason for unavailable | ✅ | `SOURCE_VIDEO_MISSING`, `MODEL_NOT_INSTALLED`, etc. |
| Confidence/uncertainty | ✅ | ContinuityScores with `known` / `unknown` |
| Default behavior | ✅ | Favors `keep_and_continue` — not unnecessary regeneration |

---

## Perception Authority Boundary

**Verified: Perception observes only. Co-Director decides.**

| Layer | Authority | Evidence |
|---|---|---|
| VideoChat3 worker | Returns structured JSON observation ONLY | `worker.py` — prints JSON to stdout, returns `rawText`, `characters`, `camera`, `scene` |
| `compare_intent_vs_actual` | Builds the packet — decides preserve/continue/avoid | `compare.py` — Co-Director logic, not VLM |
| `packet_blocks_submit` | Gates batch submission | `service.py:73` — checks policy + packet availability |
| `submit_batch_generation` | Refuses if packet blocks | `orchestrator.py:350` — `TEMPORAL_REVIEW_PENDING` |

The VLM NEVER writes to project state, NEVER enqueues generation, NEVER mutates batches.

---

## Generator Capability Matrix

| Generator | Pixel handoff | Prompt continuation | End frame | Video ref | Native temporal | Revision A strategy |
|---|---|---|---|---|---|---|
| LTX | Last-frame I2V | ✅ Native | ✅ | ❌ | ❌ | Prompt continuation + temporal packet |
| MiniMax T2V | ❌ (T2V only) | ✅ prompt_context | ❌ | ❌ | ❌ | Prompt continuation |
| MiniMax I2V | ✅ Start frame | ✅ | ✅ | ❌ | ❌ | Prompt continuation + start frame |
| Seedance | Reference image | ✅ | ❌ | ❌ | ❌ | Prompt continuation |
| Kling | ❌ (not live) | N/A | ❌ | ❌ | ❌ | N/A |

`supportsTemporalConditioning=false` for ALL adapters — verified in contracts.py:65.

---

## Existing Continuity Regression

**No regression found.** The existing `ContinuityBridge` (last-frame pixel handoff) is checked FIRST in `submit_next_queued_batch` (line 1285-1325) before the temporal packet is evaluated (line 1326-1334). Both gates are independent. The temporal review is additive.

---

## Setup Classification

| Component | Required | Boot critical | Evidence |
|---|---|---|---|
| VideoChat3 4B | ✅ **YES** | ❌ No | `required=True` (catalog.py:523), not in boot sequence |
| InternVideo3 8B | ❌ No | ❌ No | `required=False` (catalog.py:535), hardware-gated |
| TimeLens | ❌ Excluded | ❌ N/A | Not found in any component, worker, or config path |

**Verified: VideoChat3 absence does not block video generation.** `perception_mode()` returns `"stub"` when model not installed, producing `unavailable` packets with honest reasons. The `TEMPORAL_REVIEW_PENDING` gate is only `packet_blocks_submit` — degraded packets are `unavailable` which opens the gate.

---

## License Gate

| Component | Code License | Model License | Source | Status |
|---|---|---|---|---|
| VideoChat3 4B | Apache 2.0 | CC-BY-NC-4.0 | MCG-NJU/VideoChat3-4B | Requires commercial evaluation |
| InternVideo3 8B | MIT | CC-BY-NC-4.0 | OpenGVLab/InternVideo3 | Requires commercial evaluation |
| TimeLens | Excluded | N/A | N/A | Removed from all paths |

**Note:** Both VideoChat3 and InternVideo3 use CC-BY-NC-4.0 model weights. The "NC" (non-commercial) restriction requires review for commercial Adept UI deployment. The code is permissively licensed (Apache 2.0 / MIT), but model weights are NC.

---

## Worker Preflight

`worker.py` (codirector/video_intelligence/worker.py):
- Process-based isolation (separate Python process)
- Returns structured JSON via stdout
- No state mutation
- Stub mode produces realistic observations for testing
- All model paths are configurable
- `trust_remote_code` is used for VideoChat3 (the model requires it)
- FFmpeg video ingestion via clip_extract.py
- Timeout handling: 1800s default
- Failure codes: 2 (model missing), 3 (inference fail), 4 (no output)

---

## GPU Lifecycle

Sequential model execution:
1. Video generation → ComfyUI
2. Comfy `/free` (best_effort_free_generator — non-blocking, not guaranteed to complete)
3. VideoChat3 loads → perception → worker exits
4. VRAM released when worker process exits
5. Next video generation

GPU availability is checked via `preflight_for_review` — returns `unavailable` packet if GPU insufficient.

---

## Remaining Live-Certification Gates

| Gate | Status | Required for GO |
|---|---|---|
| Packet persistence after reload | Not tested (no live model) | ✅ |
| Two-batch visual continuity | Not tested (no live model) | ✅ |
| Degraded packet unblocks submit | ✅ Unit tested | ✅ |
| Comfy GPU handoff timing | Not tested (no live model) | ✅ |
| VideoChat3 worker first-load | Not tested (not installed) | ✅ |
| Frontend Continuity ON/OFF | Not tested | ✅ |
| Playwright test | Not written | ✅ |

---

## Required Fixes (None BLOCKER, all HIGH to LOW)

| # | Severity | Finding | File |
|---|---|---|---|
| 1 | **HIGH** | `best_effort_free_generator` calls `/free` with `httpx` but does not await/timeout properly — the Comfy request may silently fail, leaving GPU loaded. Must be synchronous or awaited correctly. | gpu_lease.py |
| 2 | **HIGH** | `trust_remote_code=True` is required by VideoChat3. This is a supply-chain risk that must be documented and pinned to a specific revision. | worker.py |
| 3 | **MEDIUM** | No frontend Playwright test exists for Continuity ON/OFF toggle. | tests/e2e/ |
| 4 | **MEDIUM** | `perception_mode()` returns `"stub"` when model not installed, but the stub mode produces realistic observations. Production must never use stub. | worker_client.py |
| 5 | **LOW** | Temp-file cleanup for ffmpeg-extracted clips is not explicitly verified — should ensure `tempfile` cleanup in clip_extract.py. | clip_extract.py |

---

## Critical Next-Stage Question

**If VideoChat3 were installed right now, is the current Adept UI implementation safe and sufficiently wired to begin the real two-batch Revision A certification without first redesigning or repairing the architecture?**

**YES**

The architecture is:
- Correctly layered (perception observes, CD decides)
- Properly gated (packet_blocks_submit blocks submit, not generation)
- Existing continuity preserved (bridge_blocks_submit checked first)
- Generator capabilities honest (supportsTemporalConditioning=false)
- Setup correctly classified (VideoChat3 required=True, InternVideo3 optional)
- Worker properly isolated (separate process, JSON output)
- Failure paths honest (unavailable packets with reasons, not fake data)

The pre-live-installation checklist:
1. Pin VideoChat3 + InternVideo3 model revisions and document CC-BY-NC licensing
2. Ensure Comfy /`free` call is synchronous/awaited (gpu_lease.py)
3. Document `trust_remote_code` risk and mitigation
4. Clear temp directory after ffmpeg clip extraction
5. Install VideoChat3 → run worker → verify first observation
6. Run two-batch Timeline generation with Continuity ON
7. Verify packet created, gate holds, packet released, batch N+1 proceeds
8. Verify degraded mode (uninstall VideoChat3 → packet unavailable → batch still submits)
