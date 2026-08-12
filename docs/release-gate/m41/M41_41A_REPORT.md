# M41 Phase 4.1A — Video Runtime & Generation Infrastructure Report

| Field | Value |
|---|---|
| **Phase** | 4.1A — Video Runtime & Generation Infrastructure |
| **Date** | 2026-07-29 |
| **Product** | Adept UI Studio / Adept FilmWorks |
| **Runs parallel with** | M41 Wave 5 (Specialists — no media execution) |
| **Hard gate for** | M41 Wave 6 (Media Generation Execution) |
| **Baseline** | [`M41_41A_VIDEO_RUNTIME_AUDIT.md`](./M41_41A_VIDEO_RUNTIME_AUDIT.md) · [`docs/audit/generate-workflow-audit.md`](../../audit/generate-workflow-audit.md) |
| **Verdict** | **CONDITIONAL GO — architecture and automated contracts complete; Wave 6 wiring may begin; production activation blocked pending live cert** |

---

## 1. Objective

Build and certify the **video runtime engine** — not merely “fix generation” — so Wave 6 can connect Co-Director and product tools to a trustworthy stack:

- ComfyUI as first-class local runtime
- Model Compatibility Registry
- VRAM safety
- Canonical job lifecycle
- Verified deep cancellation / recovery
- Output validation + playback readiness
- Provider-normalized cloud paths
- Operator diagnostics

**Maturity label:** Adept UI has a complete video runtime *architecture* with automated contracts. Live ComfyUI generation, cancellation confirmation, VRAM-release observation, and playback certification remain outstanding before production activation.

---

## 2. Sequencing

```text
Wave 4 (GO) Durable Planning Operator
        │
        ├────────────────┬────────────────┐
        ▼                ▼                │
   Wave 5           Phase 4.1A            │
 Specialists     Video Runtime & Gen Infra│
 (no media exec)   CONDITIONAL GO         │
        │                │                │
        └────────┬───────┘                │
                 ▼                        │
     Wave 6 wiring may begin              │
     Production activation ◄── live cert  │
```

| Unlock | Status |
|---|---|
| Wave 5 specialists (no media execution) | Allowed |
| Wave 6 **wiring / integration development** | **Unlocked** (CONDITIONAL GO) |
| Wave 6 **production activation** | **Blocked** until live LTX/WAN/LatentSync cancel, VRAM-release, and playback tests pass |

Exposed via `GET /api/video-runtime/gate` (`wave6WiringUnlocked` vs `wave6ProductionActivationUnlocked`).

---

## 3. Scope delivered

| Wave | Deliverable | Status |
|---|---|---|
| **4.1A-1** | Capability audit + machine matrix + broken-connection dispositions | **Done** |
| **4.1A-2** | Canonical video job contract + concurrency classes | **Done** |
| **4.1A-3** | ComfyUI runtime: `ensure_queueable`, verified deep cancel, progress normalizer | **Done (code)** |
| **4.1A-3b** | Model Compatibility Registry | **Done** |
| **4.1A-3c** | Runtime Diagnostics Dashboard + API | **Done** |
| **4.1A-4** | Live `VRAM_*` states + explicit safe-config proposals | **Done (code)** |
| **4.1A-5** | Workflow honesty (I2V-only local, WAN middle-frame, upscale Deferred) | **Done** |
| **4.1A-6** | Output validation gate + poster/proxy helpers | **Done (code)** |
| **4.1A-7** | Typed failure classification for local/cloud | **Done** |
| **4.1A-8** | Pytest + Playwright smoke; **live GPU cert checklist outstanding** | **Partial** |

---

## 4. Production Ready vs Deferred

### Intended Production Ready (environment may Block-with-remediation)

| Mode | Anchor |
|---|---|
| LTX 2.3 simple I2V | `ltx.simple_i2v` |
| LTX 2.3 Director (+ simple fallback) | `ltx.scene` |
| WAN 2.2 first/last frame | `wan.first_last_frame` |
| LTX Ingredients IC-LoRA | `ltx.ingredients_ic_lora` |
| fal Seedance / Kling / Veo / Runway | `fal.*` + paid-fallback gate |
| LatentSync lip-sync | `lipsync.latentsync` |
| Timeline / scene render orchestration | `render_scene` / `render_timeline` |
| Video extend (generative continuation) | last-frame → I2V contract |

### Explicitly Deferred (stable contracts, no fake COMPLETE)

`video.upscale` · `video.motion_transfer` · `video.camera_motion` · `video.character_consistent` · `video.rife_interpolation` · `video.frame_restoration` · `video.pose_transfer` · `video.multi_character_temporal` · `video.local_t2v`

Machine matrix: [`artifacts/m41/41a/video-capability-matrix.json`](../../../artifacts/m41/41a/video-capability-matrix.json)

---

## 5. Architecture delivered

```text
UI / Gen Studio / Director
        │
        ▼
 Video Preflight  ←── Model Compatibility Registry
        │
        ▼
 Canonical VideoJobContract (on Job.params_json)
        │
        ▼
 JobQueue (heavy_local | light_local | cloud)
        ├─ local  → ComfyRuntime (ensure_queueable, progress, verified deep cancel)
        └─ cloud  → fal adapters (paid gate preserved)
        │
        ▼
 Normalized stages → Output gate → Asset / proxy / poster → Playback
        │
        ▼
 Diagnostics Dashboard (/diagnostics/video-runtime)
```

---

## 6. Key implementation surfaces

| Area | Path |
|---|---|
| Runtime package | `studio-api/app/video_runtime/` |
| Compatibility catalog | `config/video-runtime/compatibility-catalog.json` |
| Comfy client | `studio-api/app/comfy_client.py` (`halt_prompt` + `confirm_prompt_stopped`) |
| Queue | `studio-api/app/queue_worker.py` (`cancel_and_halt` verified lifecycle) |
| HTTP API | `/api/video-runtime/*` |
| Diagnostics UI | `/diagnostics/video-runtime` |
| Unit tests | `studio-api/tests/test_m41_41a_video_runtime.py` |

---

## 7. Hard requirement — verified deep cancellation

When a user cancels a local video job:

1. The Studio job enters `cancelling` (not `cancelled`).
2. The job is prevented from registering further successful progress or output.
3. ComfyUI receives `POST /interrupt` for active execution.
4. Any pending queue entry for the prompt ID is deleted.
5. `wait_for_prompt`, WebSocket listeners, and polling loops terminate within one observation cycle.
6. Adept UI confirms that the prompt ID is absent from both active and pending ComfyUI state.
7. Late outputs are quarantined and never registered as completed assets.
8. Temporary or partial files are cleaned up where safe.
9. Job-level queue, CPU, and VRAM *reservations* are released.
10. Safe memory cleanup is *requested* where supported (`free_memory`) — this is **not** proof that all models unloaded or GPU returned to idle.
11. Resource activity is observed for a bounded release / confirmation period.
12. **Only after confirmation** does the job transition to `cancelled`.

If the prompt remains active after the cancellation timeout, the job enters
`cancel_failed_runtime_active` with error code `COMFY_CANCEL_NOT_CONFIRMED`.

Cancellation requests are idempotent.

### Cancellation success threshold (practical)

| Required | Not required |
|---|---|
| Active sampling stops | Every cached model unloaded |
| Prompt disappears from running + pending | GPU returns to cold idle |
| No output file continues growing | Full CUDA allocator reclaim |
| Job reservation released | Unload of intentional model cache |
| Next job can preflight and execute | — |
| VRAM drops below a configured safe threshold (observed live) | — |

`free_memory` may leave cached CUDA allocations, loaded models, VAE/text-encoder state, node references, ffmpeg processes, or Python object refs. Certification must distinguish **active generation memory released** from **all models unloaded and GPU idle**.

Entry point: `POST /api/jobs/{id}/cancel` → `JobQueue.cancel_and_halt` → `ComfyClient.halt_prompt` + `confirm_prompt_stopped`.

---

## 8. API surfaces

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/video-runtime/diagnostics` | Full operator snapshot |
| GET | `/api/video-runtime/compatibility` | Registry catalog |
| POST | `/api/video-runtime/preflight` | Ready/Blocked preflight |
| GET | `/api/video-runtime/vram-estimate` | Live VRAM estimate |
| GET | `/api/video-runtime/gate` | Wave 6 wiring vs production unlock |
| POST | `/api/jobs/{id}/cancel` | Verified deep cancel (`cancelling` → `cancelled` / `cancel_failed_runtime_active`) |

---

## 9. Test results and evidence honesty

| Suite | Result | Proves |
|---|---|---|
| `tests/test_m41_41a_video_runtime.py` | **Passed** (unit/mocked) | Contracts, registry, VRAM states, gate logic, halt *request* + confirm *loop* against mocks |
| Playwright `m41-41a-video-runtime.spec.ts` | Smoke | Diagnostics page + API shape |
| Live GPU LTX / WAN / LatentSync / fal | **Not yet certified in this report** | — |

**Unit tests do not prove** that a real ComfyUI generation stops, releases resources, or that playback works. Mocked `halt_prompt` proves correct interrupt/delete/confirm *calls*, not live runtime behavior.

### Required live cancellation evidence (outstanding)

**LTX**

1. Start a sufficiently long generation; record prompt ID  
2. Cancel during sampling  
3. Confirm `/interrupt` was received  
4. Confirm prompt disappears from active execution  
5. Confirm absent from pending queue  
6. Confirm no completed output is registered  
7. Confirm VRAM drops toward post-load or idle baseline (or below safe threshold)  
8. Confirm the next queued generation starts normally  

**WAN** — repeat the same procedure.

**LatentSync** — cancel during processing; verify ffmpeg / decoding / child-process work does not continue after the job reaches `cancelled` (or surface `COMFY_CANCEL_NOT_CONFIRMED` if it does).

Also outstanding: live output-gate + browser playback certification on real renders.

Details: [`M41_41A_TEST_REPORT.md`](./M41_41A_TEST_REPORT.md)

---

## 10. Related reports

| Report | Role |
|---|---|
| [`M41_41A_VIDEO_RUNTIME_AUDIT.md`](./M41_41A_VIDEO_RUNTIME_AUDIT.md) | 4.1A-1 audit baseline |
| [`M41_41A_IMPLEMENTATION_REPORT.md`](./M41_41A_IMPLEMENTATION_REPORT.md) | File-level implementation log |
| [`M41_41A_TEST_REPORT.md`](./M41_41A_TEST_REPORT.md) | Test evidence + live checklist |
| [`M41_41A_VIDEO_RUNTIME_CERTIFICATION_REPORT.md`](./M41_41A_VIDEO_RUNTIME_CERTIFICATION_REPORT.md) | Formal CONDITIONAL GO stamp |

---

## 11. Residual risks

- Live Comfy node/weight installs remain machine-specific  
- fal paths require customer keys + explicit paid approval  
- Poster/proxy helpers need `ffmpeg`/`ffprobe`; soft-pass with warning when absent  
- Deep cancel confirmation depends on Comfy `/queue` honesty; orphaned CUDA/model cache may persist after `free_memory`  
- Wave 6 production tools must not be declared production-ready until live cert clears  

---

## 12. Final verdict

| Question | Answer |
|---|---|
| Is the video runtime architecture complete? | **Yes** |
| Are automated contracts / unit tests in place? | **Yes** |
| Are incomplete modes honestly Deferred? | **Yes** |
| Is live Comfy cancel / VRAM-release / playback proven? | **No — outstanding** |
| May Wave 5 specialists proceed? | **Yes** (no media execution) |
| May Wave 6 **wiring** begin? | **Yes** |
| May Wave 6 **production activation** proceed? | **No** |

**CONDITIONAL GO — 4.1A implementation complete and Wave 6 integration development unlocked; production activation remains gated until live LTX, WAN, LatentSync, cancellation, resource-release, and playback tests pass.**

When those live tests pass—and jobs use `cancelling` until runtime termination is confirmed—this report may be promoted to:

**GO — M41 Phase 4.1A Video Runtime & Generation Infrastructure complete.**
