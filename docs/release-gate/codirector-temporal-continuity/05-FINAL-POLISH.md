# Revision A Final Polish

**Law 30 live evidence for this polish pass.** [REVISION-A-UNIFIED-COMPLETION.md](./REVISION-A-UNIFIED-COMPLETION.md) is the prior program GO report and is **historical** for this closure. Do not cite UNIFIED as current polish truth.

**Branch:** `feat/codirector-temporal-continuity`  
**Polish HEAD:** `b45d2ef` (last-frame sampler wiring). Hop-merge follow-up committed with this report.  
**Pushed:** `origin/feat/codirector-temporal-continuity`  
**Named project:** `Revision A Temporal Continuity`  
**Project ID:** `42ff15c3-5c39-4a7c-a430-e58e3719b6da`  
**Scene ID:** `2e3a2cfc-0094-4f7c-887a-5befa08db347`  
**Batches:** `bb_176e3046b4b0` (B1, Approved) → `bb_6c4b9668c339` (B2, CandidateReady)

**Beta (left running):** creator UI http://127.0.0.1:8760/ · Studio API http://127.0.0.1:8758/

Architecture stayed frozen. Revision B / C / MAGI / SceneCraft were not started by this polish. Chat was not used.

---

## Prior GO

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

This polish does not erase that program GO.

---

## Why polish was required

The unified report disclosed required gaps in the automatic Timeline path:

| ID | Previously | Closed by |
|---|---|---|
| A | Automatic B2 `0eb25e3b-…` stayed Adept `queued` | Reuse `schedule_job_queue_enqueue`; enqueue failure fails the Job |
| F | Adept queued while Comfy `/queue` empty | Provider accept = Comfy `prompt_id` only; `QUEUED != GENERATING` |
| B | `unfinishedActions` split into characters | `_as_str_list` + live packets no longer character-split |
| C | Timeline `ltx-2.5-distilled` ran LTX 2.3 | Timeline id preserved through `originalGeneratorId` → `ltx_25.i2v` |
| D | Some LTX jobs wrote `videoModel=minimax-h3` | `local_video_identity` never copies `scene.engine` |
| E | Fresh automatic B2 pixels never inspected | Live B2 `f3b1b291-…` / `34c9879f-…` visual YES |

---

## Queue root cause

`LtxLocalAdapter.submit` wrote a Job then swallowed enqueue failures (`except Exception: pass`). `providerJobId` was the Adept job id.

**Repair:** reuse CRS `schedule_job_queue_enqueue`. Enqueue failure marks the Job `failed` and raises. `providerJobId` stays empty until `comfy_prompt_id` exists. Hops live under `videoRuntime.queueHops`.

Stuck historical job `0eb25e3b-1976-4628-ac2d-5205a027755d` was cancelled (`confirmedStopped`, `reason=no_prompt_id`).

---

## Fresh automatic B2

Committed runtime `b45d2ef`. Policy: Continuity ON, Review Automatic, Protection Strong. Chat not opened.

| Field | Value |
|---|---|
| Packet | `tcp_90a37106360b` `availability=ready` `perceptionModelId=videochat3-4b` cadence `interval_3` |
| Packet created | `2026-08-20T19:17:01Z` |
| Adept job | `f3b1b291-515f-4444-8363-1c2b75ed8cee` created `2026-08-20T19:17:48Z` |
| Packet before job | **true** |
| Review / generate accept | `generateMs=47106` |
| Comfy `prompt_id` | `34c9879f-ca35-46bd-beff-62b27e858ada` |
| Provider accepted | **true** (`POST /prompt` success) |
| Job status | `done` / `complete` |
| Media | `data/projects/42ff15c3-…/renders/scene_0_9c641887.mp4` (1,505,941 bytes) |
| Reload | packet, B2 `CandidateReady`, bridge `Applied`, media path still present |

Comfy before generate: `SOCKET_PRESENT` + `HTTP_RESPONSIVE` + `WORKFLOW_READY`. nvidia-smi ~29 GB free, 0% util. `/free` 200 was requested; VRAM was already idle.

---

## Packet

Live packet `tcp_90a37106360b`:

- `unfinishedActions=[]` — **not** character-split (`Finish: T` did not recur)
- `parseOk=false` — VideoChat3 returned prose without a JSON tail on this pass
- `continue_`: `Continue: The background is a dark, industrial-looking corridor with pipes and vents.`
- Preserve / Avoid remain material (do not restart walk, turn, or camera; do not regenerate the batch)
- Observed state describes the two-shot corridor walk and the left character looking back

An earlier live packet (`tcp_979b4f50b3d1`) had `unfinishedActions=["[],"]` because `_extract_listed` scraped the JSON tail `"unfinishedActions": [],`. That second iteration site is fixed: empty JSON lists stay empty; Continue then uses the last motion sentence when present.

---

## Provider acceptance

Hop log for job `f3b1b291-…`:

| Hop | Observed |
|---|---|
| batchId | `bb_6c4b9668c339` |
| temporalPacketId | `tcp_90a37106360b` |
| Adept jobId | `f3b1b291-515f-4444-8363-1c2b75ed8cee` |
| adapter | `ltx-local` (request canonical) |
| requested model | `ltx-2.5-distilled` |
| resolved runtime model | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` |
| enqueue | `2026-08-20T19:17:48.406771Z` `enqueueOk=true` |
| claimedAt | **missing on this live row** (written at claim, then shallow-replaced). Deep-merge of `queueHops` is in this polish follow-up. |
| provider submit | `2026-08-20T19:17:48.612446` |
| Comfy `prompt_id` | `34c9879f-ca35-46bd-beff-62b27e858ada` |
| Comfy `/queue` after complete | empty |
| media asset | `scene_0_9c641887.mp4` |

`QUEUED != GENERATING`. Creator-facing generating begins after `POST /prompt` + `prompt_id`.

Interrupted prior hop `e3c6aee5-…` / `2bf2b818-…` completed in Comfy after the API died (`batch_bb_6c4b9_00005.mp4`, 2.3 graph). Adept marked that job `failed` / `interrupted` and did not silently rebind. Recovery law: interrupted jobs are not resumed.

---

## Fresh visual boundary

Independent inspection of B1 last 1–2s vs **this** wired 2.5 B2 first 1–2s:

| Clip | Artifact |
|---|---|
| B1 last frame | `artifacts/polish-b1-last-frame.png` |
| B2 first frame | `artifacts/polish-b2-25-wired-first.png` |
| B2 t=0.5s | `artifacts/polish-b2-25-wired-t0p5.png` |
| B2 first 1.5s | `artifacts/polish-b2-25-wired-first-1p5s.mp4` |
| B2 media | `artifacts/polish-b2-25-wired.mp4` |

**Visual YES — continuation, not a new shot.** Same two blonde-braided characters, same grey crop/shorts/belts, same bamboo corridor, stained-glass wall panels, and far door. First frame holds the mutual glance; t=0.5s continues the walk.

A previous 2.5 job (`58447965-…`) completed with `prompt_id` but **reset** to a photoreal locker-hallway because `LTXVBaseSampler.optional_cond_images` was unwired. That reset is retained as `polish-b2-25-first-frame.png` and is **not** the certified pair.

Historical 2.3 Comfy success `2bf2b818-…` also continued the last frame (queue-path proof) and remains in `polish-b2-2.3-comfy-success.mp4`.

B1 pixels are the historical approved 2.3 clip. Polish B2 is live 2.5 last-frame I2V from that approved last frame. Continuity is last-frame I2V, not a same-checkpoint B1 re-render.

---

## Parser

Character-split is closed (unit + two live packets).

Remaining usefulness limitation (not a split): VideoChat3 often returns empty `unfinishedActions` after describing a completed glance. Continue then uses a material observed sentence (motion preferred; otherwise last prose). Live Continue on `tcp_90a37106360b` is the corridor sentence, not “Finish Korri’s turn.” Preserve/Avoid still forbid restarting the turn/walk/camera.

---

## LTX routing

2.5 weights are on disk and Comfy-visible:

- `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`
- `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`
- `ltx-2.5-video-vae-bf16.safetensors`

Live Comfy graph for `34c9879f-…`:

- `UNETLoader` = 2.5 transformer
- `LoadImage` = `studio/cbr_8471441e8250_last.png`
- `LTXVBaseSampler` `optional_cond_images` index `0`, `strength=0.95`, `1280x704`

720p is snapped to 704 so latent height is patch-aligned (720 → 45, not divisible by 2).

Request builder still canonicalizes the adapter to `ltx-local`. The adapter keeps `providerOptions.originalGeneratorId` as `requestedModel` / `variant`. Orchestrator `GENERATOR_MISMATCH` is unchanged.

---

## Provenance

Job `f3b1b291-…` `localFirstProvenance`:

- `requestedModel=ltx-2.5-distilled`
- `resolvedRuntimeModel=ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`
- `videoModel` = that checkpoint (**not** `minimax-h3`)
- `workflowKey=ltx_25.i2v`

---

## Last-frame

- `continuityStrategy=last_frame_i2v`
- `lastFrameAssetId=d23cd9cbfb5440f28062daf11224de97`
- Bridge `cbr_8471441e8250` status `Applied` after reload
- `temporalContinuation.applied=true`
- `supportsTemporalConditioning=false`

---

## Performance

| Stage | Observed |
|---|---|
| Comfy `/free` + nvidia-smi before review | ~29 GB free, 0% util |
| VideoChat3 review + compile + Adept submit | 47.1 s (`generateMs`) |
| Worker claim → `POST /prompt` | ~0.2 s |
| Comfy 2.5 I2V (121 frames, 1280x704) | ~72 s to job `done` |
| Script wall | 121.7 s |

The earlier ~97 s “delay” was VideoChat3 + VRAM contention while Comfy Desktop held ~30 GB (`/free` 200 ≠ GPU idle). No GPU stack rewrite. VideoChat3 was not kept resident.

---

## Playwright

`npm run test:e2e:beta -- --project=chromium --retries=0 --workers=1 tests/e2e/codirector/codirector-temporal-continuity.spec.ts`

**5 passed, 0 failed** (21.4s) on Beta `http://127.0.0.1:8760/`.

Covers persist/reload, Setup Essential VideoChat3, packet-before-generate gate, Automatic/Strong post, Automatic / 3s / 5s / Every / Standard / Strong values.

---

## Unit / smoke

| Suite | Result |
|---|---|
| `test_temporal_continuity.py` + adapters + LTX 2.5 builder + resolver | **124 passed** |
| `scripts/temporal_continuity_smoke.py` | **exit 0** — parser, `ltx_25.i2v` routing, provenance not MiniMax |

New tests: Timeline 2.5 identity through `originalGeneratorId`; Adept queued ≠ provider accepted; empty JSON unfinished ≠ `Finish: []`; 720→704 snap; `optional_cond_images` last-frame wiring; hop merge keeps `claimedAt`.

---

## Persistence

After API recycle and after generate:

- Packet `tcp_90a37106360b` still on master
- Bridge `cbr_8471441e8250` `Applied` with the same last-frame id
- B2 `CandidateReady`, generator `ltx-2.5-distilled`
- Output file still on disk
- Provenance fields still on the job row

---

## Git / runtime identity

Revision A-only commits on this polish (MAGI commits on the same branch were not reverted):

| SHA | Why |
|---|---|
| `c180985` | Queue handoff, 2.5 resolver, MiniMax-free provenance |
| `894c864` | Keep Timeline 2.5 id through `ltx-local` |
| `a38dcc8` | Patch-safe 704p; empty JSON unfinished |
| `b45d2ef` | Wire last-frame into `LTXVBaseSampler` |

Concurrent MAGI / Timeline store-reconcile / `workflow_execute.py` diffs were left unstaged. No secrets. No `data/venvs/videochat3-worker`.

Live generate ran on `apiRevision=b45d2ef` after official Stop/Start.

---

## GLM 5.2

Pending peer review.

---

## Kimi K3

Pending peer review.

---

## Repair ledger

| Finding | Disposition |
|---|---|
| Adept queued forever / Comfy empty | **FIXED + VERIFIED** — live `prompt_id` on `f3b1b291-…` |
| `unfinishedActions` character split | **FIXED + VERIFIED** — live packets are not split |
| JSON empty list became `Finish: []` | **FIXED + VERIFIED** (unit); live `tcp_90a37106360b` is empty, not `[],` |
| Timeline 2.5 ran 2.3 via `ltx-local` | **FIXED + VERIFIED** — Comfy loaded 2.5 unet/vae/clip |
| MiniMax-on-LTX provenance | **FIXED + VERIFIED** — `videoModel` is the 2.5 checkpoint |
| 720p shape mismatch | **FIXED + VERIFIED** — live graph `1280x704` |
| 2.5 I2V ignored last-frame pixels | **FIXED + VERIFIED** — visual YES on wired B2 |
| `claimedAt` missing on live hops | **FIXED** in hop deep-merge; **not re-proven** on a new generate |
| Continue is not “finish the turn” | **OUT OF SCOPE BY EXPLICIT GOVERNING LAW** as a new perception model; disclosed usefulness limitation. Parser no longer mangles. |

---

## Final verifier

Pending after both peers return `PEER REVIEW CLEAR — NO REQUIRED GAPS FOUND`.

---

## Remaining limitations (never erased)

| Closed this polish | Still true / disclosed |
|---|---|
| Eternal Adept `queued` | Interrupted jobs are not resumed (recovery law). `e3c6aee5-…` stayed failed after Comfy finished. |
| Silent 2.5→2.3 | Historical B1 pixels remain 2.3. Polish B2 is 2.5 last-frame I2V from that last frame. |
| MiniMax-on-LTX | Scene DB default `engine` is still `minimax-h3`; Timeline LTX jobs override it from params. |
| Character-split unfinished | VideoChat3 often returns empty unfinished after a completed glance. Continue is observed prose, not a turn-completion command. |
| `/free` 200 | Not GPU idle. nvidia-smi is authoritative. Comfy Desktop was not killed. |
| Hop `claimedAt` | Missing on the certified live row; deep-merge added after. |

---

## Polish verdict

Not issued until both peers and the independent verifier clear.

Required language when clear:

```text
REVISION A FINAL POLISH COMPLETE — NO REQUIRED GAPS REMAIN
```
