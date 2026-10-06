# Revision A — Unified Review Report

**Status:** READY FOR MANUAL REVIEW  
**Law 30 live review document** for Co-Director Temporal Video Intelligence & Continuity (Revision A), including Final Polish closure.

**Governing:** [00-GOVERNING.md](./00-GOVERNING.md)

**Absorbed / historical (do not cite as current truth):**

- [REVISION-A-UNIFIED-COMPLETION.md](./REVISION-A-UNIFIED-COMPLETION.md) — prior program GO working report
- [05-FINAL-POLISH.md](./05-FINAL-POLISH.md) — polish working ledger
- [03-LIVE-CLOSURE.md](./03-LIVE-CLOSURE.md), [02-LIVE-CERTIFICATION.md](./02-LIVE-CERTIFICATION.md), [01-IMPLEMENTATION-AND-CERTIFICATION.md](./01-IMPLEMENTATION-AND-CERTIFICATION.md)

---

## Verdicts (do not collapse)

| Gate | Language | Status |
|---|---|---|
| Program | `GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED` | **Stands.** Not reopened. |
| Polish | `REVISION A FINAL POLISH COMPLETE — NO REQUIRED GAPS REMAIN` | **Issued.** Separate from the program GO. |

Independent polish verifier: [Verifier](9747aa07-54e1-4206-99e2-e26602d59828)

```text
VERIFIED — FULL-STACK E2E PASSED
NO — ALL REQUIRED WORK IS COMPLETE
```

Peers (review-only; they do not issue either GO):

| Peer | Emphasis | Result |
|---|---|---|
| [GLM 5.2](72af11c1-3a2e-436c-b86c-13adac48b442) | Requirements, architecture, routing, provenance, lifecycle, frozen integrity | `PEER REVIEW CLEAR — NO REQUIRED GAPS FOUND` |
| [Kimi K3](5e13898d-db07-4132-ab43-86de745893dd) | Runtime E2E, hops, media, visual YES, tests, persistence | `PEER REVIEW CLEAR — NO REQUIRED GAPS FOUND` |

Architecture stayed frozen. Revision B / C / MAGI / SceneCraft were not started by this work. Co-Director chat was not used.

---

## Identity

| Item | Value |
|---|---|
| Branch | `feat/codirector-temporal-continuity` |
| Report commit | `8c28eaaf45ad232572f071589dd6b0e3ce5b9955` (`8c28eaa`) |
| Live generate commit | `b45d2ef` (last-frame sampler wiring) |
| Peer/verifier API | `apiRevision=ff3cabf` after official Stop/Start (hop-merge + polish evidence) |
| Named project | `Revision A Temporal Continuity` |
| Project ID | `42ff15c3-5c39-4a7c-a430-e58e3719b6da` |
| Scene ID | `2e3a2cfc-0094-4f7c-887a-5befa08db347` |
| B1 | `bb_176e3046b4b0` Approved |
| B2 | `bb_6c4b9668c339` CandidateReady |
| Worker | `data/venvs/videochat3-worker/Scripts/python.exe` |
| Creator UI | http://127.0.0.1:8760/ |
| Studio API | http://127.0.0.1:8758/ |

`8c28eaa` is the verdict-report commit only. The certified generate ran on `b45d2ef`. Peers and the verifier inspected live API at `ff3cabf`.

---

## Product law (frozen)

```text
VideoChat3 observes → Co-Director decides → Timeline executes
```

- `TemporalContinuityPacket` / `temporal-continuity-v1` — never `ContinuityPacket`
- Automatic Timeline governance; the filmmaker does not open chat
- Last-frame `ContinuityBridge` is pixel authority
- `supportsTemporalConditioning=false` (prompt continuation, not native temporal APIs)
- VideoChat3-4B Essential; InternVideo3 optional; TimeLens excluded
- Unavailable perception must degrade honestly and must not deadlock N+1
- Reuse Timeline Master, `ContinuityBridge`, and existing `JobQueue` / `schedule_job_queue_enqueue`
- No second JobQueue, no CRS spinner redesign

---

## Why polish existed

The program GO disclosed required automatic-path gaps. This review closes them without reopening architecture.

| ID | Gap | Closure |
|---|---|---|
| A | Automatic B2 `0eb25e3b-…` stayed Adept `queued` | Reuse `schedule_job_queue_enqueue`; enqueue failure fails the Job |
| F | Adept queued while Comfy `/queue` empty | Provider accept = Comfy `prompt_id` only; `QUEUED != GENERATING` |
| B | `unfinishedActions` split into characters (`Finish: T`…) | `_as_str_list` + empty-JSON guard; live packets are not split |
| C | Timeline `ltx-2.5-distilled` ran LTX 2.3 | `originalGeneratorId` → `ltx_25.i2v` + 2.5 checkpoint |
| D | Some LTX jobs wrote `videoModel=minimax-h3` | `local_video_identity` never copies `scene.engine` |
| E | Fresh automatic B2 pixels never inspected | Certified pair visual **YES** |

---

## Certified pair (only this pair)

Do **not** treat older failed or reset jobs as the polish pair.

| Field | Value |
|---|---|
| Packet | `tcp_90a37106360b` `availability=ready` `temporal-continuity-v1` |
| Packet created | `2026-08-20T19:17:01Z` |
| Adept job | `f3b1b291-515f-4444-8363-1c2b75ed8cee` created `2026-08-20T19:17:48Z` |
| Packet before job | **true** |
| Policy | Continuity ON · Review Automatic · Protection Strong · `videochat3-4b` · cadence `interval_3` |
| Comfy `prompt_id` | `34c9879f-ca35-46bd-beff-62b27e858ada` |
| Requested | `ltx-2.5-distilled` |
| Resolved | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` |
| Workflow | `ltx_25.i2v` |
| Strategy | `last_frame_i2v` |
| Last-frame asset | `d23cd9cbfb5440f28062daf11224de97` |
| Bridge | `cbr_8471441e8250` `Applied` |
| Media | `data/projects/42ff15c3-5c39-4a7c-a430-e58e3719b6da/renders/scene_0_9c641887.mp4` |
| Size / encode | 1,505,941 bytes · 1280×704 · 121 frames · ~5.04s h264 |
| Visual | **YES** — continuation, not a new shot |

`videoModel` is the 2.5 checkpoint. **Not** `minimax-h3`.

### Not the certified pair

| Job | Why excluded |
|---|---|
| `0eb25e3b-1976-4628-ac2d-5205a027755d` | Eternal Adept `queued`; cancelled `confirmedStopped` / `no_prompt_id` |
| `e3c6aee5-07c3-474c-b0cf-dd4965d1da0c` | Interrupted after API death; Comfy later finished a **2.3** graph; Adept did not rebind |
| `7fc745c8-71c9-4884-914d-6656cab4cd26` | 2.5 graph accepted, then failed: 720p latent height 45 not patch-aligned |
| `58447965-5658-4812-83f6-8eb5692928d1` | 2.5 completed as T2V-like reset (photoreal locker hallway); `optional_cond_images` unwired |

---

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continuity ON / Automatic / Strong. Named project only. Chat not opened. Packet `19:17:01Z` before job `19:17:48Z`. |
| Frontend | PASS | Beta http://127.0.0.1:8760/ 200. Playwright **5 passed**. B2 CandidateReady Take D hydrated. |
| API | PASS | http://127.0.0.1:8758/ `apiRevision=ff3cabf` for peer/verifier. Generate on `b45d2ef`. |
| Backend | PASS | `ltx-local` keeps Timeline 2.5 id; enqueue via `schedule_job_queue_enqueue`; `QUEUED != GENERATING`. |
| Persistence | PASS | Packet, Applied bridge, B2 CandidateReady, job provenance, and media still present after the 19:22 API recycle. |
| Runtime | PASS | Comfy `WORKFLOW_READY`. `POST /prompt` → `34c9879f-…`. 2.5 unet/vae/clip. Last-frame `studio/cbr_8471441e8250_last.png` into `LTXVBaseSampler.optional_cond_images`. RTX 5090. No silent CPU. No fal. |
| Result | PASS | 1,505,941-byte 1280×704 clip. Visual YES. |
| Reload | PASS | Same packet / bridge / B2 / media IDs after recycle. |
| Downstream | PASS | Last-frame I2V applied. `temporalContinuation.applied=true`. `supportsTemporalConditioning=false`. Older fail/reset jobs not treated as the pair. |

---

## Visual boundary

Inspect these artifacts (gitignored, on disk under `docs/release-gate/codirector-temporal-continuity/artifacts/`):

| File | Role |
|---|---|
| `polish-b1-last-frame.png` | B1 last frame — two blonde-braided characters, grey crop/shorts/belts, bamboo corridor |
| `polish-b2-25-wired-first.png` | Certified B2 first frame — same two-shot, mutual glance held |
| `polish-b2-25-wired-t0p5.png` | B2 at 0.5s — same scene, walk continues |
| `polish-b2-25-wired-first-1p5s.mp4` | B2 first 1.5s |
| `polish-b2-25-wired.mp4` | Certified B2 media copy |
| `polish-b2-25-first-frame.png` | **Excluded reset** — photoreal locker hallway |

**Visual YES.** Same characters, wardrobe, corridor, panels, far door. First frame holds the glance; 0.5s continues the walk. Not a new production.

B1 pixels are the historical approved **2.3** clip. Polish B2 is live **2.5** last-frame I2V from that last frame. Continuity is last-frame I2V, not a same-checkpoint B1 re-render.

---

## Queue and lifecycle

Root cause: `LtxLocalAdapter.submit` wrote a Job, then swallowed enqueue failures (`except Exception: pass`). `providerJobId` was the Adept job id, so Adept looked busy while Comfy `/queue` was empty.

Repair:

- Reuse CRS `schedule_job_queue_enqueue` (no second JobQueue)
- Enqueue failure marks the Job `failed` and raises
- `providerJobId` empty until `comfy_prompt_id`
- Hops under `videoRuntime.queueHops`

Certified hop row `f3b1b291-…`:

| Hop | Observed |
|---|---|
| enqueue | `2026-08-20T19:17:48.406771Z` `enqueueOk=true` |
| claimedAt | Missing on this live row (predates deep-merge `ff3cabf`) |
| provider submit | `2026-08-20T19:17:48.612446` |
| prompt_id | `34c9879f-ca35-46bd-beff-62b27e858ada` |
| providerAccepted | true |
| Comfy `/queue` after done | empty |

`QUEUED != GENERATING`. Creator-facing generating begins after `POST /prompt` + `prompt_id`. Interrupted jobs are not resumed.

---

## Routing and provenance

Timeline request builder still canonicalizes the adapter to `ltx-local`. The adapter keeps `providerOptions.originalGeneratorId` as `requestedModel` / `variant`. Orchestrator `GENERATOR_MISMATCH` is unchanged.

Live Comfy graph for `34c9879f-…`:

- `UNETLoader` = `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`
- `VAELoader` = `ltx-2.5-video-vae-bf16.safetensors`
- `CLIPLoader` = `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`
- `LoadImage` = `studio/cbr_8471441e8250_last.png`
- `LTXVBaseSampler` `optional_cond_images` index `0`, `strength=0.95`, **1280×704**

720p is snapped to 704 so latent height is patch-aligned (720 → 45, not divisible by 2).

`local_video_identity` records requested Timeline id, resolved checkpoint, `videoModel` = checkpoint, `workflowKey`. LTX jobs do not copy scene default `minimax-h3`.

---

## Packet and parser

Live packet `tcp_90a37106360b`:

- `unfinishedActions=[]` — **not** character-split
- `parseOk=false` — VideoChat3 returned prose without a JSON tail
- Continue: `Continue: The background is a dark, industrial-looking corridor with pipes and vents.`
- Preserve / Avoid remain material (do not restart walk, turn, or camera; do not regenerate the batch)
- Observed state describes the corridor two-shot and the left character looking back

An earlier live packet (`tcp_979b4f50b3d1`) had `unfinishedActions=["[],"]` because `_extract_listed` scraped `"unfinishedActions": []`. That site is fixed. Continue now prefers a motion sentence when unfinished is empty.

Usefulness limitation (not a split): VideoChat3 often reports no unfinished action after a completed glance. Continue is observed prose, not “Finish Korri’s turn.”

---

## Performance

| Stage | Observed |
|---|---|
| nvidia-smi before review | ~29 GB free, 0% util |
| VideoChat3 review + compile + Adept submit | 47.1 s |
| Claim → `POST /prompt` | ~0.2 s |
| Comfy 2.5 I2V 121 frames 1280×704 | ~72 s to job `done` |
| Script wall | 121.7 s |

The earlier ~97 s wait was VideoChat3 + VRAM contention while Comfy Desktop held ~30 GB. `/free` 200 ≠ GPU idle. Desktop / user processes were not killed. VideoChat3 was not kept resident. No GPU stack rewrite.

---

## Tests

| Suite | Result |
|---|---|
| `test_temporal_continuity.py` + adapters + LTX 2.5 builder + resolver | **124 passed** |
| Playwright `tests/e2e/codirector/codirector-temporal-continuity.spec.ts` on Beta | **5 passed, 0 failed** (21.4s) |
| `scripts/temporal_continuity_smoke.py` | **exit 0** |

Playwright covers persist/reload, Setup Essential VideoChat3, packet-before-generate, Automatic/Strong post, Automatic / 3s / 5s / Every / Standard / Strong.

New/extended units: Timeline 2.5 identity through `originalGeneratorId`; Adept queued ≠ provider accepted; empty JSON unfinished ≠ `Finish: []`; 720→704 snap; `optional_cond_images` last-frame wiring; hop merge keeps `claimedAt`.

---

## Git (Revision A polish only)

MAGI commits on the same branch were not reverted. Concurrent MAGI / Timeline store-reconcile / `workflow_execute.py` dirty files were left unstaged. No secrets. No `data/venvs/videochat3-worker`.

| SHA | Why |
|---|---|
| `c180985` | Queue handoff, 2.5 resolver, MiniMax-free provenance |
| `894c864` | Keep Timeline 2.5 id through `ltx-local` |
| `a38dcc8` | Patch-safe 704p; empty JSON unfinished |
| `b45d2ef` | Wire last-frame into `LTXVBaseSampler` (certified generate) |
| `ff3cabf` | Hop deep-merge + polish evidence (peer/verifier API) |
| `8c28eaa` | Peer CLEAR + independent verification + polish verdict |

---

## Repair ledger

Every required finding is closed. Optional/doc items are treated, not deferred as “future scope.”

| Finding | Disposition |
|---|---|
| Adept queued forever / Comfy empty | **FIXED + VERIFIED** — live `prompt_id` on `f3b1b291-…` |
| `unfinishedActions` character split | **FIXED + VERIFIED** — live packets are not split |
| JSON empty list became `Finish: []` | **FIXED + VERIFIED** |
| Timeline 2.5 ran 2.3 via `ltx-local` | **FIXED + VERIFIED** — Comfy loaded 2.5 weights |
| MiniMax-on-LTX provenance | **FIXED + VERIFIED** |
| 720p shape mismatch | **FIXED + VERIFIED** — live graph 1280×704 |
| 2.5 I2V ignored last-frame pixels | **FIXED + VERIFIED** — visual YES |
| `claimedAt` missing on live hops | **FIXED** in hop deep-merge; **not re-proven** on a new generate |
| Continue is not “finish the turn” | **OUT OF SCOPE BY EXPLICIT GOVERNING LAW** as a new perception model |
| Kimi L1 — params 512×288 vs graph 1280×704 | **REJECTED WITH EVIDENCE** as a required gap. Encoded media is 1280×704. |
| Kimi L2 — VideoChat3 prose loop | **REJECTED WITH EVIDENCE** as a required gap. Disclosed usefulness. |
| GLM MEDIUM — `claimedAt` not live-reproven | **REJECTED WITH EVIDENCE** as a required gap. Provider-accept hops are on the live row. |
| GLM LOW — small white artifact on B2 first frame | **REJECTED WITH EVIDENCE** as a required gap. Cosmetic. |
| GLM LOW — commit table omitted `ff3cabf` | **FIXED** in this report. |

---

## Remaining limitations (never erased)

| Closed | Still true |
|---|---|
| Eternal Adept `queued` | Interrupted jobs are not resumed. `e3c6aee5-…` stayed failed after Comfy finished. |
| Silent 2.5→2.3 | Historical B1 pixels remain 2.3. Polish B2 is 2.5 last-frame I2V from that frame. |
| MiniMax-on-LTX | Scene DB may still default `engine=minimax-h3`; Timeline LTX jobs override from params. |
| Character-split unfinished | VideoChat3 often returns empty unfinished after a completed glance. Continue is observed prose. |
| `/free` 200 | Not GPU idle. nvidia-smi is authoritative. |
| Hop `claimedAt` | Missing on the certified live row; deep-merge added after. |

---

## Manual review path

1. Open http://127.0.0.1:8760/ on the named project `Revision A Temporal Continuity`.
2. Timeline scene `2e3a2cfc-…`. Continuity ON, Review Automatic, Protection Strong. Do not open Co-Director chat.
3. Confirm B1 Approved and B2 CandidateReady.
4. Confirm last-frame bridge `cbr_8471441e8250` Applied.
5. Play B2 (`scene_0_9c641887.mp4`) against B1 last frame. Expect the same corridor two-shot, not a locker-hallway reset.
6. Optional API checks:
   - `GET http://127.0.0.1:8758/api/health` — `apiRevision`
   - `GET /api/jobs/f3b1b291-515f-4444-8363-1c2b75ed8cee` — `comfy_prompt_id`, 2.5 `videoModel`, `last_frame_i2v`

Leave Beta running. Do not mutate the named project for disposable cert spam.

---

## Binary close

```text
GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED
REVISION A FINAL POLISH COMPLETE — NO REQUIRED GAPS REMAIN
```
