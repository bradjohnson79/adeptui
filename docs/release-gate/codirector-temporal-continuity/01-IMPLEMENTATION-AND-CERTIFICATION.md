# Co-Director Temporal Video Intelligence — Implementation and Certification

**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)  
**Branch:** `feat/codirector-temporal-continuity`  
**Status:** Implementation complete. Live VideoChat3 inference and two-batch visual inspect are **not** certified.

## Verdict

`NO-GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY NOT CERTIFIED`

Blockers:

1. VideoChat3-4B weights are **not installed** on this machine. Live perception cannot run. Setup correctly reports VideoChat3 as a required essential.
2. Real two-batch visual inspect of a joined walk/turn sequence was **not** executed. Stub/JSON observation is not visual proof.

## What was implemented

Co-Director is an embedded Timeline governing service. Perception never submits generation. Names do not collide with Wave 5 `ContinuityPacket`.

| Layer | Behavior |
|---|---|
| Gate 0 | VideoChat3 and InternVideo3 pinned Apache-2.0. TimeLens excluded. |
| Contracts | `TemporalContinuityPacket` (`temporal-continuity-v1`) + `CoDirectorContinuityPolicy` on `SceneTimelineMaster` |
| Perception | Isolated `worker.py` (stub / live / fail). ffmpeg window extract. Sequential Comfy `POST /free` then worker exit. |
| Compare | `compare_intent_vs_actual()` default `keep_and_continue`. Reads prompt, Scene Intent, camera, Spatial Map ids, prior packet. |
| Submit gate | `ensure_temporal_packet_before_submit` + `packet_blocks_submit` before adapter `submit`. Missing packet is invalid. Degraded packet releases the gate and does not invent directives. |
| Compile | `request_builder` prompt continuation only. `supportsTemporalConditioning=false`. Adapters stamp packet id. |
| Setup | `videochat3_4b` `required=True`. `internvideo3_8b` optional. Isolated HF snapshot. Health probe is more than filenames. |
| UX | Continuity ON/OFF, Automatic / 3s / 5s / Every batch, Protection, Advanced, reject, next-shot note, markers. Shot matching remains the last-frame control. |

## Tests measured

| Suite | Result |
|---|---|
| `studio-api/tests/test_temporal_continuity.py` | **15 passed** (packet, gate, stub perception, catalog, pins, sequential-when-Continuity-ON) |
| `studio-api/tests/test_timeline_generation_adapters.py` + continuity contracts | **39 passed** |
| `scripts/temporal_continuity_smoke.py` | **exit 0** — catalog required, packet round-trip, degraded compile invents nothing. `videochat3Installed=false` |
| Playwright `codirector-temporal-continuity.spec.ts` against Beta | **2 passed, 1 failed** on first run (strict locator). Locator fixed. Setup + live catalog required **passed**. UI persist test not re-certified after the fix (follow-up Playwright launch hung). |
| Independent verifier | **READY FOR PRIMARY REVIEW** — no GO. Confirmed the nine source/test claims. |
| Live VideoChat3 infer | **NOT VERIFIED** — weights absent |
| Two-batch visual join inspect | **NOT VERIFIED** |

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continuity controls in Extend & Continuity; Setup Video Intelligence checkmarks |
| Frontend | PASS (source) | Inspector / Master markers / Setup card wired to API |
| API | PASS | Policy, reject, temporal-continuity GET, lifecycle video-intelligence, submit gate |
| Backend | PASS | Review service + request_builder compile |
| Persistence | PASS | Packets on master + bridge pointer + snapshot freeze |
| Runtime | FAIL | VideoChat3 not installed; worker live path not run |
| Result | N/A | No live reviewed clip |
| Reload | PASS (policy) | Policy persisted on `SceneTimelineMaster`, not localStorage |
| Downstream | PASS (contract) | Next request receives compiled continuation only after a packet exists |

## MULTI-BATCH GOVERNANCE LAW

Proven in unit tests: `submit_next_queued_batch` does not call `submit_batch_generation` while the packet is missing (`temporal_review_pending`). After a ready or degraded packet exists, submit proceeds. Continuity OFF skips the CD gate. Last-frame `ContinuityBridge` is unchanged.

## Setup / GPU honesty

- VideoChat3 is a required Setup essential (same class as ComfyUI). Missing weights = Needs Attention, not an optional add-on.
- `codirector.video_intelligence.ready` is **not** folded into `models.video.ready` and is **not** in `REQUIRED_FOR_GENERATION`, so missing VideoChat3 does not deadlock LTX/MiniMax generation.
- Insufficient VRAM or missing weights emit `availability=unavailable` and release Batch N+1.
- Law 26: live worker refuses CPU-only torch.

## Limitations

- Live VideoChat3 / InternVideo3 inference not run on this host.
- Hosted Gemini vision remains stills-only and is not a silent substitute.
- MiniMax T2V consumes prompt continuation only — no fake start-frame.
- TimeLens is excluded and is not a catalog component.

## Beta

Refreshed after the `studio-web` build.

- Creator UI: `http://127.0.0.1:8760/` (HTTP 200)
- Web health: `http://127.0.0.1:8760/__beta_web_health` (HTTP 200)
- Studio API: `http://127.0.0.1:8758/api/health` (HTTP 200)
- `GET /api/setup/lifecycle/video-intelligence` — `timelineVisualReview=false` (VideoChat3 not installed)

## Independent verifier

[Independent temporal verifier](2ba67106-b655-421b-b621-d3904cb8caa2) returned **READY FOR PRIMARY REVIEW**. Residuals repaired in this pass:

- Comfy `/free` is now a synchronous HTTP POST (the previous async `free_memory()` was never awaited).
- Live worker uses `device_map={"": 0}` instead of `auto`.
- Continuity ON forces sequential scene submit so parallel mode cannot enqueue N+1 before review.
- HF revisions are asserted in unit tests.

Remaining mandatory gaps: live VideoChat3 infer and two-batch visual inspect.

## Manual review

1. Open Setup and confirm VideoChat3 is listed as required.
2. Use Prepare My Studio / Source Manager to install VideoChat3 (pinned `MCG-NJU/VideoChat3-4B` rev `37fa901ec5913f84bc31108ebc1e60ad1903634c`).
3. In one named project, generate two sequential batches with Continuity ON (walk + unfinished turn).
4. Confirm Batch 2 does not enter the provider queue until a Temporal Continuity Packet exists.
5. Inspect the joined sequence visually.

Until those steps are observed, this milestone stays **NO-GO**.
