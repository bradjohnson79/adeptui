# TIMELINE AUTO-CONTINUITY + MEMORY RE-TAKE — COMPLETION REPORT

**Date:** 2026-08-13  
**Branch:** `beta`  
**Starting SHA:** `ba9b4a68ef3ce3d65bfe65dcef79daacfc31d1ff`  
**Governing audit:** [TIMELINE_AUTO_CONTINUITY_MEMORY_RETAKE_AUDIT.md](./TIMELINE_AUTO_CONTINUITY_MEMORY_RETAKE_AUDIT.md)  
**Beta (after refresh):** Creator UI `http://127.0.0.1:8760/` (HTTP 200). This machine’s web proxy targets Studio API `http://127.0.0.1:8761/` (`/api/health` 200). Canonical scripts also expect `http://127.0.0.1:8758/` (currently also 200 with the new routes). Hard-refresh the browser so the new Inspector accordions load.

Playwright is out of this mission. Final live certification is the Manual Beta checklist below.

---

## Verdict

**NO-GO**

Automated unit/integration tests and the production web build passed. Live Manual Beta checklist A–K has not been executed against generated video. That checklist is the remaining mandatory gate.

---

## Scope (IMPLEMENTED)

Extend remains the creator-facing Adept UI capability. ContinuityBridge is the internal Timeline handoff. No Extend track. No Continuity Score / Continuity Review.

### Frozen contracts

- `ContinuityBridge.contextVersion = 1`
- `effectiveTailDuration = min(configuredTailDuration, actualGeneratedDuration)`
- Strategies persisted as used: `native_tail | native_extend | multi_frame | last_frame_i2v | prompt_context | none`
- Structured Re-Take memory on every candidate: `sequenceMemory`, `incomingContinuity`, `originalTakeIntent`, `takeState`, `userCorrection`

### Backend

- After approve, `prepare_outgoing_bridge` extracts a last frame (ffmpeg) and stores a `continuity_last_frame` Library asset.
- Sequential submit waits on incoming bridge Waiting/Analyzing/Failed. Failed retries once, then surfaces Retry / Continue without matching / Cancel.
- MiniMax T2V continuity is `prompt_context` only. It never claims native extend or last-frame I2V.
- LTX uses last-frame as start image (`last_frame_i2v`). A dedicated new-angle start image wins framing. Native tail is never claimed.
- API Auto Continuity defaults Off (`0` / `3` / `5`). Off forbids background paid continuity. Reconcile never spends API credits without `spendApiCredits`.
- Local Auto Continuity is locked on, configured window 5s, runtime clamp applied.
- Re-Take creates Take B without overwriting Take A. Activate take supersedes outgoing bridges and marks downstream stale. Reconcile vs Keep Existing are explicit.

### Inspector

Accordions: Scene, Generation (open); Extend & Continuity, Re-Take, Advanced (collapsed). Subtle batch-boundary chip (Matched / Matching… / Match failed / Needs update). Not a track.

---

## Files

- `studio-api/app/director_timeline_w46/contracts.py`
- `studio-api/app/director_timeline_w46/continuity.py`
- `studio-api/app/director_timeline_w46/orchestrator.py`
- `studio-api/app/director_timeline_w46/router.py`
- `studio-api/app/director_timeline_w46/generation/contracts.py`
- `studio-api/app/director_timeline_w46/generation/request_builder.py`
- `studio-api/app/director_timeline_w46/generation/completion.py`
- `studio-api/app/director_timeline_w46/generation/adapters/minimax_h3_local.py`
- `studio-api/app/director_timeline_w46/generation/adapters/minimax_h3_i2v_local.py`
- `studio-api/app/director_timeline_w46/generation/adapters/ltx_local.py`
- `studio-web/src/timelineMaster/contracts.ts`
- `studio-web/src/api.ts`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/DirectorTracks.tsx`
- `studio-web/src/styles/timeline-master/timeline-editor-shell.css`
- `studio-api/tests/test_timeline_continuity_contracts.py`
- `studio-api/tests/test_timeline_generation_adapters.py`
- `studio-web/src/timelineMaster/continuityContracts.test.ts`

---

## Tests (TESTED)

| Suite | Result |
| --- | --- |
| `tests/test_timeline_continuity_contracts.py` + `tests/test_timeline_generation_adapters.py` | **31 passed** |
| `tests/test_m42_w46_director_timeline.py` + `tests/test_timeline_retakes.py` + `tests/test_timeline_context_gates.py` | **18 passed** |
| `studio-web` `tsc -b && vite build` | **passed** |

Playwright: **not run** (out of mission).

### Covered automatically

- Tail clamp 3.2 / 5 / 15 / Off
- Local lock ON 5s vs API Off/3/5 persist + reject 4s
- MiniMax T2V → `prompt_context`, no start image
- LTX last frame → `last_frame_i2v`, never `native_tail`
- New-angle start image wins framing
- Sequential gate on Waiting/Failed; Off does not block
- Downstream stale on supersede
- Five-section Re-Take memory
- Retake does not overwrite Take A (`asset-take-a` stays approved; Take B unapproved)

---

## Live verification (NOT VERIFIED)

Real MiniMax/LTX two-batch generation, ffmpeg last-frame on disk, inspector UX, and reload persistence after generated video are **NOT VERIFIED**. Use checklist A–K.

---

## Manual Beta certification checklist (creator)

Open Timeline on a real project. Do not create a new project per take.

**A — 2-batch local.** Two batches, MiniMax or LTX, Auto Continuity on. Generate scene. Batch 2 must wait until batch 1 is approved and a last-frame match exists. Batch 2 should feel like a continuation, not a hard cut. Reload: both clips and the match status remain.

**B — 4-batch local.** Four batches sequential. Each later batch waits on the previous match. No parallel submit. No extra Extend track.

**C — API Off / 3 / 5 persist.** With an API generator selected, set Auto Continuity Off, then 3s, then 5s. Reload. Off must not start a background paid match job. 3 and 5 persist. Local generators ignore Off and stay on 5s.

**D — Continuity Re-Take.** On batch 2, New take with a delta such as “walk behind the cruiser, not in front.” The new take must keep scene, previous-shot match, and original intent, plus only that delta.

**E — Take A / Take B.** After D, both takes remain. Activating B places B on the Timeline. A is still listed. Reload preserves both.

**F — Stale downstream.** With batches 1–2 approved, activate a new take on batch 1. Batch 2 shows Needs update. Batch 2 media does not regenerate by itself.

**G — Reconcile / Keep existing.** Update later shots regenerates stale batches (API requires an explicit credit confirm). Keep existing clears the stale mark and leaves the old media.

**H — Multi-angle.** Batch 2 has its own start image (new angle). Framing follows that image. Continuity is context, not a camera override.

**I — Fail / retry.** If matching fails, Retry, Continue without matching, and Cancel are available. No infinite retry loop.

**J — Reload.** Refresh the browser after A–E. Takes, match chips, and Auto Continuity window survive.

**K — Inspector UX.** Right pane shows Scene and Generation open; Extend & Continuity, Re-Take, and Advanced collapsed. No Continuity Score. No Extend track. Language is creator-facing.

---

## Limitations (honest)

- MiniMax T2V cannot consume a last-frame image. Continuity is prompt context, not native video extend.
- LTX does not consume a video tail graph. Strategy is last-frame I2V, never `native_tail`.
- Seedance/Kling remain non-executable dock adapters. API Off/3/5 is policy + persistence only.
- First sequential snapshots are still staged before the previous last frame exists; the live bridge is attached at submit time.
- ffmpeg must be on PATH for last-frame extract. Missing ffmpeg fails the bridge (Retry / Continue without matching).
- Manual Beta A–K not yet run.

---

## Manual review path

1. Confirm Beta UI and Studio API are up.
2. Open the current project Timeline (do not spawn a new project).
3. Run checklist A–K in order.
4. Record pass/fail per letter. One fail = overall NO-GO until repaired.

Creator UI and API URLs are reported after Beta refresh in the handoff message.

---

## Build-law checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated
[x] Full-stack implementation completed
[x] Every visible control wired
[x] Real runtime path (no mock completion in adapters)
[ ] Persistence after reload verified (manual J)
[x] Error/cancel/retry/recovery implemented (I); live fail path manual
[x] Authz + project isolation unchanged (scene-scoped master)
[x] Unit/API/integration/regression passed (49 related tests)
[ ] Playwright creator workflow (explicitly out of mission)
[x] Failures repaired and documented (inspector signature restored during implementation)
[x] Production build passed
[x] Beta updated and running; URL reported
[x] Manual review path documented (A–K)
[ ] Screenshots + live evidence (creator Manual Beta)
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: NO-GO
```
