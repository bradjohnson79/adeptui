# Revision A — Unified Completion Report

> **HISTORICAL.** Law 30 live evidence for the polish closure is [05-FINAL-POLISH.md](./05-FINAL-POLISH.md). This file remains the prior program GO report. Do not cite it as current polish truth.

**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)  
**This file** recorded the program GO for Co-Director Temporal Video Intelligence & Continuity (Revision A).  
**Absorbed / historical:** [01-IMPLEMENTATION-AND-CERTIFICATION.md](./01-IMPLEMENTATION-AND-CERTIFICATION.md), [02-LIVE-CERTIFICATION.md](./02-LIVE-CERTIFICATION.md), [03-LIVE-CLOSURE.md](./03-LIVE-CLOSURE.md). Do not cite those as current truth.

**Branch:** `feat/codirector-temporal-continuity`  
**Committed HEAD:** `d376feef16c05573dc7cb6243847f8c8d7008e16` (`d376fee MAGI: Live verification scripts…` — unrelated tip)  
**Live Studio API:** `apiRevision=f51838a` · `apiStartedAt=2026-08-20T16:27:33Z`  
**Worker Python:** `C:\AdeptFilmWorks\AIVideoStudio\data\venvs\videochat3-worker\Scripts\python.exe`

**Named cert project:** `Revision A Temporal Continuity`  
**Project ID:** `42ff15c3-5c39-4a7c-a430-e58e3719b6da`  
**Scene ID:** `2e3a2cfc-0094-4f7c-887a-5befa08db347`  
**Batches:** `bb_176e3046b4b0` (B1) → `bb_6c4b9668c339` (B2)

**Beta (left running):** creator UI http://127.0.0.1:8760/ · Studio API http://127.0.0.1:8758/

---

## Verdict

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

Independent verifiers:

| Pass | Result |
|---|---|
| Install / first live infer / cut ([Review](8743b939-1879-4801-aba6-a02b5e227a41)) | `VERIFIED — FULL-STACK E2E PASSED` |
| Audit-driven closure ([Review](8637820e-d67e-46f1-90d2-2d7e674b0423)) | `VERIFIED — FULL-STACK E2E PASSED` |

Architecture stayed frozen. Revision B and MAGI were not started.

---

## Scope

Prove Co-Director governs Timeline multi-batch generation without chat:

```text
TIMELINE MULTI-BATCH
        ↓
    BATCH 1 RENDERS
        ↓
  VIDEOCHAT3 SEES IT
        ↓
 CO-DIRECTOR UNDERSTANDS
        ↓
  PRESERVE / CONTINUE
        ↓
TEMPORAL CONTINUITY PACKET
        ↓
    BATCH 2 WAITS
        ↓
 REAL ADAPTER CONDITIONING
        ↓
  ACTION CONTINUES ACROSS
      THE BATCH BOUNDARY
```

Frozen product law (DeepSeek audit + [00-GOVERNING.md](./00-GOVERNING.md)):

- VideoChat3 observes; Co-Director decides; perception never submits generation
- `TemporalContinuityPacket` (`temporal-continuity-v1`)
- Last-frame `ContinuityBridge` remains first-class
- `supportsTemporalConditioning=false` (prompt continuation, not native temporal APIs)
- VideoChat3 Essential / not boot-critical; InternVideo3 optional; TimeLens excluded
- Degraded perception may release N+1 honestly

---

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continuity ON / Automatic / Strong. No Co-Director chat. Named project reused |
| Frontend | PASS | Playwright UI persist + Setup Video Intelligence Essential / Ready |
| API | PASS | Recycled `:8758` GPU worker. Lifecycle `videochat3Certified=true`, `timelineVisualReview=true` |
| Backend | PASS | Isolated worker, poll-safe SHA, `/free` + VRAM, stub guard, clip cleanup, submit gate |
| Persistence | PASS | Weights + `.adept-certify.json`. Packet `tcp_35a42252fdd1` survives GET reload |
| Runtime | PASS | RTX 5090 certify infer + in-API VideoChat3 review + Adept Comfy `:8188` `WORKFLOW_READY` |
| Result | PASS | Ready packet, structured observation, corridor clips in the named Library |
| Reload | PASS | Playwright policy reload; packet ID still on master |
| Downstream | PASS | `temporalContinuation.applied=true`, last-frame I2V, `supportsTemporalConditioning=false` |

---

## Automatic NO-GO checklist

| Condition | Result |
|---|---|
| License pin broken | **PASS** — `PASS — VIDEOCHAT3 LICENSE CLEARED` |
| Setup install skipped / hand-copied | **PASS** — `install_component('videochat3_4b')`; second call reused dest |
| Filename-only ready | **PASS** — small-file SHA + shard sizes + remote-code SHA + certify receipt |
| CPU-only infer | **PASS** — RTX 5090, CUDA torch, no silent CPU |
| Gemini / stills substitute | **PASS** — local MP4 only |
| Production stub leak | **PASS** — stub forbidden outside pytest / `ADEPT_ALLOW_PERCEPTION_STUB` |
| N+1 queued before packet | **PASS** — packet `16:57:12` before job `16:58:48` |
| Last-frame bridge dropped | **PASS** — `last_frame_i2v` + `cbr_8471441e8250` |
| Visual reset at the cut | **PASS** — corridor continue, not hut-sit reset |
| Automatic review only out-of-process | **PASS** — listening API wrote `tcp_35a42252fdd1` |
| Playwright hang unexplained | **PASS** — classified as test harness (`/api/setup/status` poll); probe fixed; **5 passed** |

---

## 1. License

Live Hugging Face reconfirm `2026-08-20` (do not trust the DeepSeek CC-BY-NC note).

### VideoChat3-4B — `PASS — VIDEOCHAT3 LICENSE CLEARED`

| Item | Pin |
|---|---|
| Repo | `MCG-NJU/VideoChat3-4B` |
| Revision | `37fa901ec5913f84bc31108ebc1e60ad1903634c` |
| Card | `apache-2.0`, `gated=false`, `private=false` |
| Standalone LICENSE file | Absent (404) — card is authority |
| Commercial + redistribution | Permitted under Apache 2.0 |
| Base LLM | Qwen3-4B, Apache-2.0 |
| `trust_remote_code` | Required; revision + SHA pinned |

Memos: [docs/models/videochat3-4b/LICENSE_CLEARANCE.md](../../models/videochat3-4b/LICENSE_CLEARANCE.md)

Remote-code SHA-256 (executed files):

| File | SHA-256 |
|---|---|
| `modeling_videochat3.py` | `853a76844c94612f350f222247983e734d70ebe37fc6778a4b3ea0e22bdc36f8` |
| `configuration_videochat3.py` | `b2c6fe79f9fc9ac75466dc9be6cf2b95a530f6c1a06638bf87ae75289444d02e` |
| `processing_videochat3.py` | `2cf662dca1391ad133ef80dad5cbb6505a0e30e3564881f6174dc6633e2c3696` |
| `video_processing_videochat3.py` | `bf33cff1b70465ed3cb1e9dc748504ab2a612f54037324068aab1b487189f6d1` |
| `videochat3_utils.py` | `fd528475338cce9969f43b65df88faf0a72455ab0eeb59cad740733060cef5ab` |

### InternVideo3-8B — optional, not a VideoChat3 blocker

| Item | Pin |
|---|---|
| Repo | `yanziang/InternVideo3-8B-Instruct` |
| Revision | `c4602918b65225650d152db2850fe34e01d21fcd` |
| Card | `apache-2.0` |
| Catalog | `internvideo3_8b` `required=False` |
| Installed on this machine | No (`deepSequenceReasoning=false`) |

---

## 2. Setup install and readiness

Dest: `data/models/video_understanding/videochat3-4b` (8.35 GB)

Route: Setup catalog `videochat3_4b` `required=True` → `huggingface_snapshot` → sequential `hf_hub_download` at the pinned revision (`resume_download=True`). Second install reused dest. Prepare plan no longer lists VideoChat3.

Two-tier readiness:

1. **Poll-safe verify** — markers + pinned small-file SHA + shard sizes + remote-code SHA. No 8.5 GB load on `/api/setup/status`. Worker `--health` not spawned on status polls.
2. **One-shot certify receipt** — `.adept-certify.json`. `codirector.video_intelligence.ready` and `timelineVisualReview=true` require `ok` + `liveInfer` + matching revision.

Playwright ready probe: `/api/health` + `/api/setup/lifecycle/video-intelligence` (not full catalog status).

---

## 3. Live GPU inference (direct worker)

| Field | Measured |
|---|---|
| Source clip | Local `Annie-Korri_00002_.mp4` |
| Review window | 3 s / 512 px / 2 fps (`extract_review_clip`) |
| Device | NVIDIA GeForce RTX 5090 |
| Attention | SDPA (flash-attn absent; `config.json` SHA not rewritten) |
| VRAM before / during / after | 29.33 GB free / **10.211 GB used** / 29.68 GB free |
| Load + infer | 24.202 s |
| `parseOk` | true |
| Mode | `live` — not stub, not Gemini, not stills |

Receipt: `data/models/video_understanding/videochat3-4b/.adept-certify.json`

---

## 4. Audit findings closed

| # | Severity | Finding | Closure |
|---|---|---|---|
| 1 | HIGH | Comfy `/free` not awaited | Sync `httpx.post(..., timeout=30.0)`. Evidence records `comfyFreeStatus`, `vramBeforeFreeGb`, `vramAfterFreeGb`. `/free` 200 is not treated as idle GPU |
| 2 | HIGH | `trust_remote_code=True` | Kept. Revision + remote-code SHA + frozen `VIDEOCHAT3_REPO_FILES`. No floating `main` |
| 3 | MEDIUM | Stub produces realistic observations | Production: `STUB_FORBIDDEN`. Missing model: `MODEL_NOT_INSTALLED`. No stub-derived preserve/continue |
| 4 | LOW | ffmpeg extract cleanup | `cleanup_extracted_clip`. Cadence window `bb_176e3046b4b0_interval_3.mp4` deleted after review |
| — | — | `:8188` listen ≠ ready | `probe_comfy_generation_ready`: `SOCKET_PRESENT` / `HTTP_RESPONSIVE` / `WORKFLOW_READY` (1933 `/object_info` keys) |

Low-VRAM honesty: first in-API review at **0.66 GB** free → `availability=unavailable` `INSUFFICIENT_VRAM` → N+1 still submitted. Later review at **7.1 GB** free → ready packet.

---

## 5. Automatic Timeline governance (in-API)

After recycling Adept-owned `:8758` so `worker_python()` is the GPU venv:

```text
Continuity ON · Review Automatic · Protection Strong
B1 Approved (no chat)
Packets for B1→B2 cleared
POST .../batches/bb_6c4b9668c339/generate
  → ensure_temporal_packet_before_submit (listening API)
  → POST /free + VRAM preflight
  → VideoChat3 live
  → compare_intent_vs_actual
  → packet tcp_35a42252fdd1 ready, cadence interval_3
  → job 0eb25e3b-1976-4628-ac2d-5205a027755d
```

| Proof | Value |
|---|---|
| Packet | `tcp_35a42252fdd1` `availability=ready` |
| Perception | `videochat3-4b` |
| Cadence | Automatic → `interval_3` (corridor walk + two characters). Dialogue fixture → `interval_5` |
| Packet created | `2026-08-20T16:57:12.185200+00:00` |
| Job created | `2026-08-20T16:58:48.533303` |
| `packetBeforeJob` | true |
| Review duration | 96972 ms |
| Continuation | `applied=true` |
| `supportsTemporalConditioning` | false |
| Last-frame | `lastFrameAssetId=d23cd9cbfb5440f28062daf11224de97` |
| Bridge | `cbr_8471441e8250` |
| Strategy | `last_frame_i2v` |
| Reload | packet ID still on master |

Observation (judge temporal state, not names): two blonde women in grey walk a dim corridor; the woman on the right turns to look at the left; the interaction is unfinished.

Compiled meaning: preserve motion / geography / lighting / wardrobe; do not restart the walk or turn; finish the unfinished action.

**Parser defect (disclosed):** VideoChat3 returned `unfinishedActions` as a string. The live packet’s Continue lines were split into characters (`Finish: T`, `Finish: h`, …). Preserve / Avoid / Next stayed coherent. `_as_str_list` now treats a string as one item. The on-disk packet was not rewritten.

---

## 6. Degraded path

| Case | Packet | N+1 |
|---|---|---|
| Stale API Python (`No module named 'torch'`) — first session | `tcp_4f65e6e5dab5` unavailable | Submitted |
| In-API `INSUFFICIENT_VRAM` (0.66 GB) | `tcp_0a236c58d82b` unavailable | Submitted |
| Controlled `ADEPT_TEMPORAL_PERCEPTION_MODE=fail` | `PERCEPTION_FORCED_FAILURE`, empty directives | Does not block |

No deadlock. No stub body. No fake `ready`.

---

## 7. Visual boundary

Inspected `artifacts/batch1-last-frame.png` vs `artifacts/batch2-first-frame.png` (same last-frame asset the automatic job conditions on).

| Axis | Observation |
|---|---|
| Character | Two near-copies of the Annie-Korri blonde braid / grey crop / detached sleeves / brown belt. Not distinct Anadriya vs Korri (start-still limit) |
| Blocking | Rear two-shot in a bamboo corridor; sides hold |
| Performance | Walk continues; unfinished look-back still unfinished at B2 open |
| Camera | Same corridor angle; not a snap back to the fire-hut sit |
| Scene | Bamboo rails, mosaic wall tiles, far door, dim overhead light |

**Did Batch 2 continue Batch 1 or reset?** Continue. It did not reset to the hut sit.

B1 itself morphs hut sit → corridor (I2V from an Annie-Korri still). The cert question is the B1→B2 cut.

The automatic-packet B2 job `0eb25e3b-…` remained **queued** (Adept Comfy `/queue` empty). New pixels from that job were not inspected. Cut inspect uses the project’s existing last-frame pair.

A/B Continuity OFF was not run.

Comfy graph on the inspected B2 file: `ltx-2.3-22b-distilled-fp8.safetensors` (Timeline id was `ltx-2.5-distilled`).

---

## 8. Tests (measured)

| Suite | Result |
|---|---|
| `studio-api/tests/test_temporal_continuity.py` | **25 passed** |
| Playwright `tests/e2e/codirector/codirector-temporal-continuity.spec.ts` | **5 passed, 0 failed** (Beta, chromium, retries=0) |

Playwright cases: ON/OFF persist, Automatic / 3 / 5 / Every batch, Strong / Standard, Advanced, next-shot note, reject hook, Setup Essential, `timelineVisualReview=true`. At least one case is UI → API.

Hang root cause: `waitForAppReady` used to poll full `/api/setup/status` (30s+ catalog wall). **Layer: test harness.** Fixed to `/api/health` + lifecycle. Classified; not left unexplained.

Regression (bounded): Continuity OFF does not block submit (unit). VideoChat3 Essential does not make every video path depend on a successful review.

---

## 9. Performance (measured)

| Metric | Value |
|---|---|
| VideoChat3 dest | 8.35 GB |
| Certify load + 3 s infer | 24.202 s |
| Peak VRAM during certify | 10.211 GB |
| Automatic in-API review | ~97 s (`/free` + load + infer) |
| Automatic cadence (active corridor) | `interval_3` |
| Automatic cadence (quiet dialogue) | `interval_5` |
| `/free` | HTTP 200; VRAM may be unchanged (Desktop Comfy resident) |

Automatic review is practical when roughly 7 GB or more is free after `/free`.

---

## 10. Files

### Product / API

- `studio-api/app/codirector/video_intelligence/paths.py` — pins, `worker_python()`, remote-code SHA
- `studio-api/app/codirector/video_intelligence/install.py` — sequential snapshot
- `studio-api/app/codirector/video_intelligence/health.py` — poll-safe verify
- `studio-api/app/codirector/video_intelligence/certify.py` — one-shot GPU receipt
- `studio-api/app/codirector/video_intelligence/worker.py` — SDPA, stub guard
- `studio-api/app/codirector/video_intelligence/worker_client.py` — GPU python, stub guard, cleanup
- `studio-api/app/codirector/video_intelligence/gpu_lease.py` — `/free` + VRAM + Comfy tiers
- `studio-api/app/codirector/video_intelligence/clip_extract.py` — review window + cleanup
- `studio-api/app/codirector/video_intelligence/service.py` — degrade reasons, clip cleanup
- `studio-api/app/codirector/video_intelligence/hardware_profile.py` — `workerPython` on lifecycle
- `studio-api/app/setup/status.py`, `diagnostics.py` — stale-while-revalidate / poll-safe
- `studio-web/src/components/SetupWizard.tsx` — Video Intelligence on loading screen
- `tests/e2e/helpers/app.ts` — cheap ready probe
- `tests/e2e/codirector/codirector-temporal-continuity.spec.ts`
- `studio-api/tests/test_temporal_continuity.py`

### Scripts / docs / artifacts

- `scripts/videochat3_live_certify.py`
- `scripts/temporal_continuity_two_batch_visual.py`
- `scripts/temporal_continuity_automatic_closure.py`
- `docs/models/videochat3-4b/LICENSE_CLEARANCE.md`
- `docs/models/internvideo3-8b/LICENSE_CLEARANCE.md`
- `docs/release-gate/codirector-temporal-continuity/artifacts/automatic-closure-evidence.json`
- `docs/release-gate/codirector-temporal-continuity/artifacts/temporal-continuation-stamps.json`
- `docs/release-gate/codirector-temporal-continuity/artifacts/batch1-last-frame.png`
- `docs/release-gate/codirector-temporal-continuity/artifacts/batch2-first-frame.png`

Working-tree closure files are **not all committed**. Do not treat `d376fee` as the closure commit.

---

## 11. Limitations (honest)

- Listening API revision `f51838a` vs current git HEAD `d376fee` (unrelated later commit). Closure code is on the working tree and was loaded by the recycled API at `16:27:33Z`.
- Automatic B2 job `0eb25e3b-1976-4628-ac2d-5205a027755d` remained queued; new Batch 2 pixels were not rendered.
- Live packet Continue lines are character-split; parser fix is in source only.
- Comfy Desktop can hold ~20 GB VRAM. Adept `/free` is a request, not proof the GPU is idle.
- Flash-Attention 2 is not installed; SDPA is the documented fallback.
- Full-resolution VideoChat3 SDPA OOM’d (~111 GiB attn). Review uses 3 s / 512 px / 2 fps.
- Comfy ran LTX 2.3 distilled while Timeline asked for `ltx-2.5-distilled`.
- Start still was a hut plate; B1 morphs hut → corridor.
- Job provenance sometimes labels LTX local jobs `videoModel=minimax-h3`.
- A/B Continuity OFF and hosted Vercel were not re-run.
- InternVideo3 is not installed.

---

## 12. Manual review

1. Open http://127.0.0.1:8760/ → project **Revision A Temporal Continuity**.
2. Timeline inspector → Extend & Continuity: On, Automatic, Strong.
3. Setup → Co-Director Video Intelligence: VideoChat3 required / Ready.
4. Compare `artifacts/batch1-last-frame.png` vs `artifacts/batch2-first-frame.png`.
5. Read `artifacts/automatic-closure-evidence.json`.

Do not open Co-Director chat to operate this path.

---

## Mandatory completion checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved (temporal-continuity-v1, last-frame bridge, supportsTemporalConditioning=false)
[x] Full-stack implementation completed
[x] Every visible Continuity / Setup Essential control wired
[x] Real runtime; no mock completion
[x] Persistence after reload verified
[x] Error/cancel/retry/recovery: degraded unavailable proven
[x] Authz + project isolation: named project reused (Playwright uses disposable projects)
[x] Unit/API/regression: 25 passed
[x] Playwright creator workflow: 5 passed
[x] Failures repaired and documented (status hang, stub, /free VRAM, string-split parse)
[x] Independent verifier passed
[x] Production build: studio-web served from Beta dist (no web change this closure pass)
[x] Beta updated and running; URLs reported
[x] Manual review path documented
[x] Evidence saved
[x] Unified Markdown completion report created (this file)
[x] Limitations honest
[x] Verdict: GO
[x] GPU preflight / CUDA worker / device / VRAM / no silent CPU
[x] Creator workflows inside Adept UI (Law 29)
[x] One governing doc; superseded reports marked (Law 30)
[x] Co-Director learning not silently mutating projects (Law 32) — N/A this milestone
```

---

## Final language

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`
