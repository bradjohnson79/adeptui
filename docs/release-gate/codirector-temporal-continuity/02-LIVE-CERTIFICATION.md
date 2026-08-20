# Co-Director Temporal Continuity — Live Certification

**SUPERSEDED / HISTORICAL (Law 30).** Do not cite this file as current truth. Closure evidence and the current binary verdict are in [03-LIVE-CLOSURE.md](./03-LIVE-CLOSURE.md).

**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)  
**This file** is historical live evidence from the first VideoChat3 install session.  
**Historical:** [01-IMPLEMENTATION-AND-CERTIFICATION.md](./01-IMPLEMENTATION-AND-CERTIFICATION.md) is also superseded.

**Branch:** `feat/codirector-temporal-continuity`  
**HEAD (committed):** `c8c5133ec1d0d4beb10901606c4f7d889daf5c9f`  
**Working tree:** follow-up implementation is on disk and loaded by scripts; the listening Studio API on `:8758` reported `apiStartedAt=2026-08-20T06:45:22Z` / `apiRevision=c8c5133` after a ghost listen blocked a full reload.

**Named cert project:** `Revision A Temporal Continuity`  
**Project ID:** `42ff15c3-5c39-4a7c-a430-e58e3719b6da`  
**Scene ID:** `2e3a2cfc-0094-4f7c-887a-5befa08db347`  
**Beta:** creator UI `http://127.0.0.1:8760/` · Studio API `http://127.0.0.1:8758/`

## Verdict

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

Independent verifier ([Review](8743b939-1879-4801-aba6-a02b5e227a41)): `VERIFIED — FULL-STACK E2E PASSED`. Playwright was not re-run by the verifier (`:8760` was down at that moment). Beta was then restarted and is live for manual review.

## Automatic NO-GO checklist

| Condition | Result |
|---|---|
| License pin broken | **PASS** — Apache-2.0 at `37fa901ec5913f84bc31108ebc1e60ad1903634c`; commercial + redistribution remain pinned. Memo: `docs/models/videochat3-4b/LICENSE_CLEARANCE.md` |
| Setup install skipped / manual-copied | **PASS** — `install_component('videochat3_4b')` (same function as Source Manager `huggingface_snapshot`). Second call reused dest (`reused=True`). Prepare plan no longer lists VideoChat3 |
| Filename-only ready | **PASS** — poll-safe SHA/size + one-shot certify receipt. `codirector.video_intelligence.ready` requires receipt |
| CPU-only infer | **PASS** — RTX 5090, CUDA torch 2.10.0+cu130, `device_map={"": 0}`, SDPA (flash-attn absent). No CPU fallback |
| Gemini fallback | **PASS** — local clip only |
| N+1 queued before packet | **PASS** — first B2 submit carried `temporalContinuityPacketId=tcp_4f65e6e5dab5` (`unavailable`). Gate released. Missing packet is invalid; this was explicit degraded |
| Last-frame bridge dropped | **PASS** — B2 `continuityStrategy=last_frame_i2v`, `lastFrameAssetId` + `continuityBridgeId` set |
| Visual reset at the cut | **PASS** — B1 last frame and B2 first frame are the same bamboo corridor two-shot walk, not a reset to the fire-hut start still |
| Playwright uncertified after diagnosed hang | **PASS** — `3 passed` in 8.0s after ready-probe + Setup card-on-load fix |

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continuity controls + Setup Essential in Playwright; named project reused |
| Frontend | PASS | Setup Video Intelligence card visible while catalog status builds; Timeline persist via policy API + reload |
| API | PASS | `/api/setup/lifecycle/video-intelligence` `videochat3Certified=true`, `timelineVisualReview=true`. Director-timeline generate + policy + master |
| Backend | PASS | Isolated worker, poll-safe verify, submit gate, request_builder compile |
| Persistence | PASS | Weights at `data/models/video_understanding/videochat3-4b`. Receipt `.adept-certify.json`. Packets on scene master |
| Runtime | PASS | VideoChat3 live infer + LTX local I2V on Adept Comfy `:8188` (`/system_stats` 200) |
| Result | PASS | Structured observation; two approved batch videos in the named project Library |
| Reload | PASS | Playwright reload persist; Setup card after refresh |
| Downstream | PASS | Retake B2 `normalizedRequest` includes compiled `temporalContinuation.applied=true` and last-frame I2V |

## Gate 0 — license

Live HF reconfirm this session:

- Repo `MCG-NJU/VideoChat3-4B` revision `37fa901ec5913f84bc31108ebc1e60ad1903634c`
- Card `apache-2.0`, `gated=false`
- Weight SHA-256 pins in memo + `studio-api/app/codirector/video_intelligence/paths.py`

## Priority 1 — Setup install

Dest: `data/models/video_understanding/videochat3-4b`  
Installer: sequential `hf_hub_download` of `VIDEOCHAT3_REPO_FILES` with resume (parallel snapshot was disconnecting).  
Integrity + full shard SHA matched pins. Second `install_component` reused existing dest.

## Two-tier readiness

1. **Poll-safe:** markers + pinned small-file SHA + shard sizes + cached CUDA `--health`. No 8.5GB load on `/api/setup/status`. Worker `--health` is not spawned on status verify (`spawn_worker=False`).
2. **Certify receipt:** isolated worker loads pinned VideoChat3 on GPU, infers a short local window, writes `.adept-certify.json`. Status/capability reads the receipt.

`GET /api/setup/status` after restart: **200 in 37167 ms** (first uncached catalog). Playwright no longer waits on that wall (`/api/health` + `/api/setup/lifecycle/video-intelligence`). Setup wizard also renders Video Intelligence during “Checking studio status…”.

## Live GPU infer

| Field | Observed |
|---|---|
| Clip | `Annie-Korri_00002_.mp4` (local). Review window 3s / 512px / 2 fps (`extract_review_clip`) |
| Worker Python | `data/venvs/videochat3-worker` (Comfy CUDA torch + `transformers==4.57.1`) |
| Device | `NVIDIA GeForce RTX 5090` |
| Attention | SDPA (vision `attn_impl` flash_attention_2 overridden in-memory; config.json SHA unchanged) |
| VRAM before / during / after | 29.33 GB free / **10.211 GB used** / 29.68 GB free after process exit (receipt) |
| Load+infer | 24.202 s |
| Observation | Blonde woman by fire, cut to elf-eared girl; `unknown` fields valid; `parseOk=true`; `confidence=0.9` |
| Mode | `live` — not stub, not Gemini, not stills |

Receipt: `data/models/video_understanding/videochat3-4b/.adept-certify.json`  
Sidecar: `probe-review.review512.perception.json`

## Timeline runtime

`scripts/temporal_continuity_live_runtime.py` → `RUNTIME_GATE_OK` (unit/script gate).

Live named-project chain:

1. Continuity ON, `every_batch`.
2. Batch 1 LTX I2V draft submitted `cdae2b91-bfe8-4329-9f49-25cffd8917c1` → Approved `4c4f5888-e16f-4e67-90db-c5bdc0aa692c`.
3. First B2 submit used degraded packet `tcp_4f65e6e5dab5` (`reason=No module named 'torch'` on the stale API worker). `temporalContinuation.applied=false`. **N+1 still submitted.** Last-frame I2V intact.
4. Out-of-process live VideoChat3 review of Batch 1 (GPU worker venv) wrote **ready** packet `tcp_0e215cf9554f`.
5. Retake generate of Batch 2 on the live API stamped the **actual** request:

```text
temporalContinuation.applied=true
packetId=tcp_0e215cf9554f
availability=ready
directives=["Continue from the last successful frame with the same cinematic state."]
continuityStrategy=last_frame_i2v
supportsTemporalConditioning=false
```

Retake job `b8f8b579-6ce3-4ce7-b9fc-60c959d8b75e` later reached `status=done` / `stage=complete`. Output: `data/projects/42ff15c3-.../renders/scene_0_5ebb0c87.mp4`.

Decoded stamps: `artifacts/temporal-continuation-stamps.json`. Raw jobs: `artifacts/batch2-job.json` (degraded) and `artifacts/batch2-retake-ready-job.json` (ready).

## Playwright

```text
npm run test:e2e:beta -- --project=chromium --retries=0 --workers=1 tests/e2e/codirector/codirector-temporal-continuity.spec.ts
3 passed (8.0s)
```

Hang cause confirmed: `waitForAppReady` used to poll `/api/setup/status` (30s+). Fixed. Setup card hang: wizard blocked on full catalog; Video Intelligence now mounts on the cheap lifecycle route.

## Two-batch visual inspect

Generator path: Timeline `ltx-2.5-distilled` → Comfy graph used `ltx-2.3-22b-distilled-fp8.safetensors` (local LTX distilled). I2V + last-frame bridge. Draft 5s, 24 fps, 1280×704 output.

| Clip | Path |
|---|---|
| Start still (from Annie-Korri) | `artifacts/batch1-start.png` — one woman, fire, bamboo hut |
| B1 first | `artifacts/batch1-first-frame.png` — same hut sit |
| B1 last | `artifacts/batch1-last-frame.png` — two blonde braided women walking a bamboo corridor; left looks over shoulder |
| B2 first | `artifacts/batch2-first-frame.png` — same corridor, same outfits, same two-shot; walk continues; left still looking toward companion |

**Did Batch 2 continue Batch 1 or reset?** Continue. It did not snap back to the fire-hut start still. Wardrobe (grey crop, detached sleeves, brown belt), corridor architecture (bamboo rails, mosaic wall tiles, far door), camera angle, and lighting hold. The unfinished look-back is still unfinished at the B2 open.

Honesty on identity: both figures at the cut are near-copies of the Annie-Korri blonde braid, not clearly distinct Anadriya vs Korri. That is a generation/start-still limitation, not a cut reset. B1 itself morphs hut sit → corridor two-shot; the cert question is the Batch 1→2 cut.

A/B OFF was not run (first ON run was inspectable; compute used for live review + retake stamp).

## Tests measured

| Suite | Result |
|---|---|
| `studio-api/tests/test_temporal_continuity.py` | **19 passed** |
| Playwright Beta spec | **3 passed, 0 failed** |
| Live certify script | **exit 0** |
| Two-batch visual script | **exit 0** (plus forced live review + retake stamp) |

## Limitations (honest)

- The `:8758` listener was not fully recycled after the GPU-worker pin; first Timeline review on approve used API Python (no torch) and correctly degraded. Live review used the pinned Adept worker venv. Product fix is in source (`worker_python()`).
- Flash-Attention 2 is not installed; SDPA is the documented fallback. Pinned `config.json` SHA was not rewritten.
- Full-resolution VideoChat3 SDPA OOM’d (~111 GiB attn). Review uses a 3s / 512px / 2 fps window.
- Comfy executed LTX 2.3 distilled weights while the Timeline generator id was `ltx-2.5-distilled`.
- Hosted Vercel path was not re-certified in this follow-up.
- A/B Continuity OFF visual was not run.
- Batch 1 live review packet `tcp_0e215cf9554f` is `availability=ready` with compiled directives, but `observation.parseOk=false` (repetitive caption). Certify-clip receipt remains `parseOk=true`.
- Job provenance labels some LTX local jobs `videoModel=minimax-h3`. The Comfy graph comment on `batch2.mp4` is `ckpt_name=ltx-2.3-22b-distilled-fp8.safetensors`.

## Independent verifier

[Review](8743b939-1879-4801-aba6-a02b5e227a41) independently read receipts, stamps, license pins, SHA of small weight files, live `/api/health` + `/api/setup/lifecycle/video-intelligence`, and the four cut PNGs.

Result: `VERIFIED — FULL-STACK E2E PASSED`.

Verifier-noted non-blockers already disclosed above: VRAM-after typo (corrected to receipt 29.68), `parseOk=false` on the Timeline B1 packet, LTX 2.3 vs requested 2.5, `videoModel=minimax-h3` provenance label, Playwright not re-run while `:8760` was down.

## Manual review

1. Open `http://127.0.0.1:8760/` → project **Revision A Temporal Continuity**.
2. Timeline inspector → Extend & Continuity.
3. Setup workspace → Co-Director Video Intelligence (VideoChat3 required / Ready).
4. Compare `artifacts/batch1-last-frame.png` vs `artifacts/batch2-first-frame.png`.

## Files (follow-up, not all committed)

- `studio-api/app/codirector/video_intelligence/{paths,health,worker,worker_client,certify,clip_extract}.py`
- `studio-api/app/setup/{status,diagnostics}.py`
- `studio-web/src/components/SetupWizard.tsx`
- `tests/e2e/helpers/app.ts`, `tests/e2e/codirector/codirector-temporal-continuity.spec.ts`
- `scripts/videochat3_live_certify.py`, `scripts/temporal_continuity_two_batch_visual.py`
- `docs/models/videochat3-4b/LICENSE_CLEARANCE.md`
- Artifacts under `docs/release-gate/codirector-temporal-continuity/artifacts/`
