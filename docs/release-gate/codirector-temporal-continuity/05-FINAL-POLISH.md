# Revision A Final Polish

**Status:** LIVE EVIDENCE IN PROGRESS  
**Law 30 live evidence for this polish pass.** [REVISION-A-UNIFIED-COMPLETION.md](./REVISION-A-UNIFIED-COMPLETION.md) remains the prior program GO report and is historical for this closure.

**Branch:** `feat/codirector-temporal-continuity`  
**Polish commit:** `c1809856bccf8d91252cfd61c2b8b81f0e80d014`  
**Pushed:** `origin/feat/codirector-temporal-continuity`  
**Runtime identity:** `GET /api/health` `apiRevision=c180985` after official Stop/Start.

**Beta:** http://127.0.0.1:8760/  
**API:** http://127.0.0.1:8758/

---

## Prior GO

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

This polish does not erase that program GO.

---

## Why polish was required

The unified report disclosed required gaps in the automatic Timeline path:

| Previously | Now (implementation) |
|---|---|
| Automatic B2 `0eb25e3b-…` stayed Adept `queued` | Root cause: LTX adapter swallowed enqueue failure (`except Exception: pass`). Provider id was the Adept job id. |
| Comfy `/queue` empty while Adept queued | Job never reached `JobQueue` / never `POST /prompt`. Confirmed: `comfy_prompt_id=null`. |
| `unfinishedActions` split into characters | `_as_str_list` treats a string as one item. Unit + smoke proven. Live packet pending this pass. |
| Timeline `ltx-2.5-distilled` ran LTX 2.3 | Resolver now selects `ltx_25.i2v` for `ltx-2.5-*`. |
| Some LTX jobs wrote `videoModel=minimax-h3` | Provenance uses requested/resolved checkpoint, never scene.engine default. |

---

## Queue root cause

`LtxLocalAdapter.submit` wrote a `Job` row then tried to hop onto `job_queue`. Failures were swallowed. `providerJobId` was set to the Adept job id, so creator-facing state looked like a provider job existed.

**Repair:** reuse `schedule_job_queue_enqueue` (same helper CRS already repaired). Enqueue failure marks the Job `failed` and raises. `providerJobId` stays empty until `comfy_prompt_id` exists. Hop timestamps live under `videoRuntime.queueHops`.

`QUEUED != GENERATING`. `job exists != provider accepted`.

Stuck historical job `0eb25e3b-1976-4628-ac2d-5205a027755d` was cancelled (`confirmedStopped`, `reason=no_prompt_id`).

---

## LTX routing correction

2.5 weights are on disk (checkpoint, Gemma text encoder, video VAE, audio VAE).

`resolve_from_scene_params(..., generator_id="ltx-2.5-distilled")` → `ltx_25.i2v`. Timeline LTX jobs also override `scene.engine` from params (`engine=ltx`) so the scene default `minimax-h3` cannot win.

No silent 2.3 substitute when the Timeline id is 2.5.

---

## Provenance correction

`local_video_identity` records:

- `requestedModel` (Timeline id)
- `resolvedRuntimeModel` (checkpoint filename)
- `videoModel` = resolved checkpoint
- `workflowKey`

LTX jobs must not write `minimax-h3`.

---

## Tests

| Suite | Result |
|---|---|
| `test_temporal_continuity.py` + LTX adapter + resolver | **68 passed** |
| Playwright `codirector-temporal-continuity.spec.ts` on Beta | **5 passed, 0 failed** (22.1s) |
| `scripts/temporal_continuity_smoke.py` | **exit 0** — parser, `ltx_25.i2v` routing, provenance not MiniMax |

---

## Fresh automatic B2

**Pending live GPU window.** Comfy Desktop standalone-env was holding ~30 GiB VRAM (`/free` 200 ≠ GPU idle). Adept Comfy: `WORKFLOW_READY`. Named project batches remain `ltx-2.5-distilled`. B2 `bb_6c4b9668c339` is Ready. Continuity ON / Automatic / Strong. Chat not used.

When VRAM ≥ 8 GiB: live `/batches/{id}/generate` → VideoChat3 review → packet → last-frame B2 → `POST /prompt` + `prompt_id` → render → visual YES.

---

## Git / runtime identity

- Commit `c180985` contains only Revision A closure/polish files.
- Concurrent MAGI / Timeline store-reconcile / `workflow_execute.py` diffs were left unstaged.
- After recycle: `apiRevision=c180985` equals `git rev-parse --short HEAD`.
- Worker: `data/venvs/videochat3-worker/Scripts/python.exe`.

---

## Polish verdict

Not issued until the fresh automatic B2 has a provider `prompt_id`, rendered media, a coherent live packet, and both peers plus the final verifier clear.
