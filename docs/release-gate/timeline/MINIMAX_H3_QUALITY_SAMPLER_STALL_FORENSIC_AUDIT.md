# MiniMax H3 Quality Sampler Stall — Forensic Audit

**Status:** LIVE EVIDENCE (BRAD-5090 reconnected)  
**Machine:** BRAD-5090 (`2e617bbd-2bab-493a-a2e2-e98cb445b5cf`) — `connected=true`  
**Mode:** READ-ONLY. No telemetry / watchdog / Comfy / API / Timeline changes. No reproduce. Scene 12 HOLD.  
**Audit time (PT):** 2026-09-16 ~9:30–9:45 PM PT  

---

## Specimen (LIVE — studio.db)

| Field | Live value | Source |
|-------|------------|--------|
| Job | `fd0c9c58-184d-4846-a789-91629cf4559f` | `C:\AdeptFilmWorks\AIVideoStudio\data\studio.db` `jobs.id` |
| Comfy prompt | `d6727573-3f5e-43fb-a1d0-ad5504c3ef6e` | `jobs.comfy_prompt_id` |
| Scene | Anadriya's Quarters `6a7a8a8b-71a1-41e2-8900-871c1b3d71db` | `jobs.scene_id` |
| Project | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` | `jobs.project_id` |
| Status | `failed` / stage `failed` | `jobs.status` |
| Created | 2026-09-17 03:05:23 | `jobs.created_at` (DB clock) |
| Updated | 2026-09-17 04:07:44 | `jobs.updated_at` |
| Wall clock | **3741 s (~62.4 min)** | updated − created |
| Failure message | `ComfyUI stall: prompt d6727573-3f5e-43fb-a1d0-ad5504c3ef6e has been queue_running for 3600s with no history (stall_limit=3600s).` | `jobs.message` + `history_json.videoRuntime.failure` |
| failureClass | `provider_timeout` | `history_json` |
| computeConsumed | true | `history_json.videoRuntime.failure` |
| partialOutputExists | false | same |
| Adapter | `minimax-h3-t2v-local` | `params_json.adapterId` |
| Engine | `minimax-h3` | `params_json.engine` |
| requestedModel | `minimax-h3` | `params_json` |
| resolvedRuntimeModel / unet | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | params + `history.videoRuntime.r2v` |
| generationMode | `reference` | params |
| r2v mechanism | `h3_ref2va` | params + history |
| fast_generation | **false** | params |
| cache | **none** | `history.videoRuntime.r2v.cache` |
| duration / legal | 15.0 s / 15.0833 s | params |
| frames | **362** (`legalFrameCount`) | params |
| width × height | **1920 × 1088** | params |
| aspect | 16:9 | params |
| runtime | `adept-comfy-8188` | history.r2v |
| seed | requested −1 → resolved `4176922547` | history.videoRuntime.seed |
| negativePrompt | null | params |
| startImageAssetId | `7e5a01f4-…` (set) | params — **not I2V**; disclosure: H3 R2V is not first-frame I2V |
| refs | 4 slots: 2 character + 1 place + 1 audio; tensorSlotCount 3 | params.r2v + runtimeDependencies.staged |
| prompt length | 2044 chars | params.prompt |
| Telemetry node | **125** — `Executing node 125 · still running (3597s)` | `history.progressTelemetry` |
| progressGrounded | **false** | same |
| lastProgressAt | 2026-09-17T03:05:36Z (**12 s** after start) | same |
| progressSource | `heartbeat` | same |
| elapsedActiveTime | 3737.0 s | same |
| stalled (telemetry flag) | **false** (watchdog is what failed the job) | same |

DB timestamps are naive local-or-UTC as stored; wall 3741 s matches the briefed ~62 min.

---

## Q1 — Failed vs known-good H3 (same production path)

Same adapter `minimax-h3-t2v-local`, same unet, same 362 frames / 15 s legal, same scene, same `adept-comfy-8188`.

| Dimension | Failed `fd0c9c58` | Known-good 15 s (scene, 2026-09-13) | Class |
|-----------|-------------------|--------------------------------------|-------|
| Job | fd0c9c58 / prompt d6727573 | `3075a62c` / `bb455e62` (done); also `6df40cba` | — |
| Wall | 3741 s FAIL | **189 s / 186 s DONE** | **SUSPECT** |
| adapter | minimax-h3-t2v-local | same | SAME |
| unet | minimax_h3_ref2va_pruned_int8_convrot.safetensors | same | SAME |
| frames / legalDuration | 362 / 15.083 s | same | SAME |
| runtime | adept-comfy-8188 | same | SAME |
| fast_generation | **false** | **true** | **SUSPECT** |
| cache | **none** | **EasyCache** | **SUSPECT** |
| WxH | **1920×1088** | **864×480** | **SUSPECT** |
| r2v mechanism | h3_ref2va | same | SAME |
| refs | 4 (2 char + place + audio) | not re-diffed on peer graph | UNKNOWN |
| Quality 15 s peer (lower res) | — | `137deb99` / `a7a6543e` / `37124cbf` **done in ~499 s** at **1152×640**, fast=false, cache=none | **EXPECTED DIFF** (res) + **SUSPECT** (1920 Quality has no successful 15 s peer) |

1920×1088 pressure (same DB):

| Job | Status | fast | cache | Wall | Note |
|-----|--------|------|-------|------|------|
| `63969c02` | failed | true | EasyCache | 19 s | `Allocation on device 0 would exceed allowed memory` |
| `80d8e608` | failed | true | EasyCache | 3707 s | **same 3600 s no-history stall** |
| `fd0c9c58` | failed | false | none | 3741 s | this specimen |
| `b4b9bcbb` | done | false | none | (0.5 s clip) | Quality+1920 exists only as a **short** complete, not 15 s |

**Q1 verdict:** Path is the **Quality branch** (fast=false, cache=none) at **1920×1088**. Known-good 15 s H3 on this scene is Fast+EasyCache at 864×480 (~3 min). Quality 15 s at 1152×640 completes in ~8.3 min. No successful Quality 15 s @ 1920×1088 peer.

---

## Q2 — Node 125

| Probe | Result |
|-------|--------|
| Cited executing | **yes** — `progressTelemetry.currentNode = "125"`, message `Executing node 125 · still running (3597s)` (`studio.db` `history_json`) |
| Class / inputs / model handle / latent / steps / scheduler / dtype / conditioning | **UNKNOWN** — submitted Comfy graph JSON for `d6727573` was **not found** on disk (no file named d6727573/fd0c9c58 under `.runtime`, `data/minimax_h3`, `ComfyUI/`, `data/tmp`) |
| Behavior | Telemetry claims **sampling** for 3597 s with `progressGrounded=false` and last grounded progress **12 s** after start. Compatible with true sampler hang **or** fake-busy / sync / offload. **Cannot distinguish** without node class + Comfy execute logs. |

---

## Q3 — GPU during stall

**UNKNOWN** for the 03:05–04:07 window. No retained nvidia-smi dmon / DCGM / thermal log for that interval was found. Live `nvidia-smi` now would not be the stall window. Briefed “GPU 100% / VRAM ~32 GB” remains **unverified**.

---

## Q4 — Reference-conditioning pressure vs known-good

Failed: 4 R2V slots (Anadriya CRS sheet, Korri front, #ERS place, Korri audio wav); tensorSlotCount 3; staged bytes ~5.1 MB images + 242 KB wav. Anadriya identity is **CRS-only** (`WARN_CRS_ONLY`).  
Known-good 15 s Fast peer graph **not loaded**. Class: **UNKNOWN** (payload has more refs/audio than a typical T2V; pressure vs 1152 Quality complete **not measured**).

---

## Q5 — Memory / offload / allocator / OOM / silent fallback

- This job: **no OOM** in `history_json` (contrast `63969c02` OOM at 1920 Fast).  
- `cache=none`, `fast_generation=false` (no EasyCache offload path).  
- No CUDA OOM / allocator dump located for `d6727573`.  
- Class: **UNKNOWN** for silent fallback; **not OOM** on this specimen.

---

## Q6 — Attention / kernel backend

**UNKNOWN.** No Comfy/custom-node log line naming sage/flash/xformers/SDPA for this prompt.

---

## Q7 — Accelerator path vs expected

| Path | Failed | Known-good 15 s (3075a62c) | Class |
|------|--------|----------------------------|-------|
| Quality branch | fast=false, cache=none | fast=true, EasyCache | **SUSPECT** (failed is Quality; good is Fast) |
| Cache node | none | EasyCache | **SUSPECT** |
| Legacy sampler | UNKNOWN (no graph) | UNKNOWN | UNKNOWN |

Failed job **is** the Quality accelerator-off path. Known-good production 15 s on this scene is Fast+EasyCache.

---

## Q8 — Scene payload diffs

| Field | Failed | Known-good 15 s Fast 864×480 | Class |
|-------|--------|------------------------------|-------|
| Prompt length | 2044 chars (full interview Timed Prompt) | UNKNOWN (not dumped) | UNKNOWN |
| Refs | 4 (2 char + place + audio) | UNKNOWN | UNKNOWN |
| R2V | h3_ref2va, 3 tensors + audio | same mechanism | SAME |
| Aspect | 16:9 | 16:9 (864×480) | EXPECTED DIFF (res) |
| Duration / frames | 15 s / 362 | 15 s / 362 | SAME |
| Timed prompt | preserved (`timedPromptBytesPreserved=true`) | — | SAME (honesty) |
| Continuity | strategy none; no I2V start-frame attach | — | SAME / EXPECTED (H3 T2V) |
| Resolution | 1920×1088 | 864×480 | **SUSPECT** |
| Cache / fast | none / false | EasyCache / true | **SUSPECT** |

---

## Q9 — Event path Comfy → WS → Studio API

| Hypothesis | Evidence |
|------------|----------|
| NO STEP EVENTS | **SUPPORTED for this job.** `progressGrounded=false`; `lastProgressAt` 03:05:36Z only; thereafter `progressSource=heartbeat`. Live Preview real step/max correctly stayed empty. |
| EMITTED-LOST | **Not proven.** No WS/API log showing a step event that was dropped. |
| TOO LATE | **Not proven.** Heartbeats continued until 04:07:41Z; watchdog used queue+history, not step ticks. |

Preserve Live Preview real step/max. This job did **not** invent ticks.

---

## Q10 — History absence

Watchdog definition (live code): fail when prompt stays `queue_running` with **no Comfy history** for `stall_limit` seconds.

- `jobs.history_json` **is** written (Studio-side runtime/failure/telemetry).  
- Comfy `/history` for `d6727573` is **absent** (that is the stall condition; `partialOutputExists=false`).  
- History is **not** “write-on-complete only” for Studio — Studio wrote failure telemetry. Comfy never completed, so no Comfy history / no output.  
- Queue was still `queue_running` at kill (per failure string).  

Class: **F is not the defect.** Absence of Comfy history is the stall signal, not proof the sampler was idle-complete.

---

## Q11 — Watchdog 3600s

**Source (read-only):** `studio-api/app/comfy_client.py`

- `RUNNING_WITHOUT_HISTORY_STALL_SEC = 3600.0` (line 22)  
- Comment: Wave 3B — do **not** early-abort at 900 s while Comfy still owns `queue_running`; cap at job wall / 3600 s (lines 17–21, 349–352).  
- Fail early only when prompt vanished from queue+history or Comfy reports failure/cancel.  
- Trip: `running_without_history_sec >= stall_limit_sec` → `TimeoutError` with the exact message on `jobs.message` (lines 606–612).  
- Stack: `queue_worker._wait_comfy` → `comfy.wait_for_prompt` → `_wait_for_prompt_poll`.

**Can H3 Quality legitimately run >60 min with no progress events?**  
No evidence. Quality 15 s @ 1152×640 completed in **~499 s**. Quality/Fast 12 s @ 1280×704 completed in **972–1695 s**. This 1920 Quality job had **no grounded progress after 12 s**. Prior 1920 Fast+EasyCache 15 s either **OOM in 19 s** or **same 3600 s stall**.

**WATCHDOG VERDICT: VALID** — predicate matches the live failure; 3600 s is the intended Wave 3B wall.  
**Do NOT extend** without a measured Quality 1920×1088 15 s / 362 f run that still emits (or correctly withholds) progress and finishes.

---

## Q12 — Reproduce

**SKIPPED.** Not safe to start another Quality 1920 15 s generate to “force” a finish. No identical job was already running (a later Fast 1120×480 job `598bde24` was `running` at 03:58 — different settings).

---

## Classification

**CLASSIFICATION: I MIXED**

Evidenced axes (not a single-bucket pick):

| Bucket | Status |
|--------|--------|
| A Sampler hung | **Open / likely** — node 125 claimed sampling 3597 s, no Comfy history, no grounded steps after 12 s |
| B Attention/kernel | UNKNOWN (no backend log) |
| C Ref-conditioning | UNKNOWN (4 refs; no graph timings) |
| D Offload/sync fake-busy | **Open** — GPU clocks during stall UNKNOWN; cache=none Quality path |
| E Telemetry loss | **Not a defect** — Live Preview correctly ungrounded (`progressGrounded=false`) |
| F History-on-complete only | **Not the stall** — Studio wrote failure; Comfy never completed |
| G Watchdog too aggressive | **Not supported** — Quality 15 s @ 1152 finished in ~8 min; do not extend 3600 s |
| H Payload/path vs known-good | **SUPPORTED** — Quality (fast=false, cache=none) @ 1920×1088 vs Fast+EasyCache @ 864×480 (~3 min) and Quality @ 1152×640 (~8 min); 1920 is a known OOM/stall pressure (two prior 1920 fails) |

### DEFECT FOUND

**No single root-cause defect confirmed.**  
Proven: Quality 1920×1088 15 s / 362 f / cache=none **stalled** under a **VALID** 3600 s no-history watchdog, with **no Comfy history**, **no grounded step ticks**, and **no successful same-res Quality peer**.

### Evidence

- `data/studio.db` jobs.`fd0c9c58-184d-4846-a789-91629cf4559f`  
- `comfy_client.py` `RUNNING_WITHOUT_HISTORY_STALL_SEC = 3600.0` + trip message match  
- Known-good `3075a62c` / `6df40cba` (~187 s, Fast, EasyCache, 864×480)  
- Quality 15 s `137deb99` (~499 s, 1152×640, fast=false, cache=none)  
- 1920 peers `63969c02` (OOM 19 s) / `80d8e608` (3600 s stall)

### Recommended repair (do NOT implement in this mission)

1. Retain / dump submitted Comfy graph for `d6727573` and inspect **node 125** class/inputs (still missing).  
2. Do **not** extend 3600 s.  
3. If a follow-on is approved: Quality 1920×1088 15 s should be compared to the completing Quality 1152×640 path (cache, attention, VRAM) — not more prompt prose.  
4. Preserve Live Preview real step/max.

---

## UNKNOWN fields that remain

Submitted graph / node 125 class+inputs; GPU clocks/P-state/power/thermals in the stall window; attention backend; Comfy execute logs; known-good peer ref-graph diff; WS emit logs (EMITTED-LOST unproven).

---

AUDIT COMPLETE  
FAILED JOB: fd0c9c58  
COMFY PROMPT: d6727573  
SAMPLER NODE: 125  
CLASSIFICATION: I MIXED (H payload/path + A/D no-progress; G not supported)  
PRIMARY EVIDENCE: studio.db job fd0c9c58-184d-4846-a789-91629cf4559f / prompt d6727573-3f5e-43fb-a1d0-ad5504c3ef6e; history.progressTelemetry node 125 ungrounded after 12s; comfy_client.py RUNNING_WITHOUT_HISTORY_STALL_SEC=3600 VALID; known-good 15s Fast+EasyCache 864x480 ~187s; Quality 15s 1152x640 ~499s; 1920x1088 has no successful Quality 15s peer (OOM + prior stall)  
WATCHDOG VERDICT: VALID  
RECOMMENDED NEXT MISSION: Dump Comfy graph for d6727573 and inspect node 125; do NOT extend 3600s; if repair is approved later, treat Quality 1920x1088 15s/362f/cache=none as the pressure path vs completing Quality 1152x640 — not more prose. Scene 12 HOLD. Preserve Live Preview real step/max.
