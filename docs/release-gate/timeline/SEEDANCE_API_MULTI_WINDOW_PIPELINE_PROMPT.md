# Seedance API Multi-Window Pipeline

**Status:** LOCKED — `GO — API MULTI-WINDOW PIPELINE` (2026-09-23). Further edits require `Owner unlock: API multi-window pipeline` and `Owner unlock: timeline`.  
**Audience:** Primary agent  
**Binary verdict only:** `GO — API MULTI-WINDOW PIPELINE` or `NO-GO — <blocker>`

NEW BUILD CLOSED. The sequential batch chain already exists. Reconnect it so an API scene renders every planned window. Do not create a second queue, stitcher, prompt writer, or Seedance-only path.

## Mission

A creator sets a scene longer than one provider window. Generate or New Take sends window 1. When that window’s clip is saved, the next planned window is sent. This repeats until every planned window has a clip. Those clips appear on the timeline and are joined into one scene clip.

Seedance 2.0 Mini is the proof engine. The same chain serves every generator whose registry `executionType` is `api` (Seedance, Kling fal, Veo fal). Local MiniMax still waits on its memory and review gates.

## Prompt authority

Master is the only prompt authority. There is no second prompt system for API generators.

`assign_later_window_scripts` is the only writer of per-window story text. It runs from rematerialize and from `generate_scene` before the first submit, then the master is saved.

- Case A: a later window that already has story text stays unchanged. That text is what Inspector shows and what fal receives.
- Case B: a later window with no story text receives one slice from `slice_story_for_window`. That slice is stored on Master before submission. A one-block story stays whole. No second sentence splitter.
- After the slice is stored, Generate, New Take, Re-Take, rematerialize, `request_builder`, and `seedance_api.py` do not rewrite it.
- “Do not slice during Generate” means no hidden submit-time slicing. It does not forbid the H1 owner from persisting a slice before submit.
- Do not store `[CONTINUATION window …]`, `WINDOW SCOPE`, or “this scene continues across N sequential batches.”
- Empty later windows may inherit the first window’s checked pictures. That copy does not change story text.

The chain is: creator or H1 owner, then Master, then Inspector, then `request_builder` read-only, then fal.

## Existing authority

Use these. Do not replace them.

- `generate_scene` submits the first eligible window and stages the rest with `stage_batch_snapshot`.
- `complete_batch_candidate` calls `submit_next_queued_batch`. That is the only advancement mechanism. No frontend loop, no fal callback that submits the next window, and no GET that submits.
- `submit_next_queued_batch` skips `handoff_submit_block`, `bridge_blocks_submit`, `ensure_temporal_packet_before_submit`, and `packet_blocks_submit` when `uses_local_memory(batch)` is false.
- `uses_local_memory` is false only when the generator registry says `executionType == "api"`.
- `halt_queued_batches_after_failure` cancels staged windows after a provider failure or cancel.
- `ensure_deposited_scene_join` is the only join. It runs when every planned window on that take has a deposited asset. It does not mark the take ready. Do not hardcode two windows.
- Take readiness stays the H1 gate: `ready` only when every planned window is `Approved` or `CandidateReady`. A deposited clip, and a speech-check result, do not grant `ready`.
- fal Seedance submit lives in `studio-api/app/director_timeline_w46/generation/adapters/seedance_api.py` and sends `request.prompt`.
- Window length comes from the existing materializer and the provider `maxDurationSec`. Seedance max is 15 seconds. Do not hardcode “2 batches.”

## Required behavior

1. Scene clock is split into the existing planned windows. A 30-second Seedance scene is two 15-second windows. A longer scene is as many windows as the planner already creates. No window may exceed that provider’s max, and no window may be silently lengthened or shortened to force a count.
2. Generate and New Take send window 1 to the selected API model and stage every later window. One provider job at a time.
3. When window K saves a clip, window K+1 is submitted in the same Studio API session without waiting on local VRAM, the continuity bridge, Qwen Omni, or Dialogue QC.
4. A provider failure or an explicit Cancel stops the remaining staged windows. Dialogue QC `UNCERTAIN`, `FAIL`, or `OMNI_UNAVAILABLE` does not stop the next API window, does not block the join, and does not mark the take ready.
5. Each finished window places its own picture on the Visual lane. When every planned window has a picture, they join into one scene clip.
6. The selected model is the model that runs. Mini stays Mini. Do not substitute 2.0, 2.5, Fast, Kling, or Veo.
7. Resolution and native audio stay on the existing fal contract. Mini proof uses the resolution stored on the windows. Do not invent 1080p or 4K for Mini.
8. An API restart is passive. It must not submit a new fal job, advance a queued window, or replay a prior request. GET must not mutate generation into a new submit. A clip fal already finished may be kept. Continuing after a restart takes an explicit New Take or Re-Take.
9. Local MiniMax behavior stays as it is: memory gate, bridge, and temporal review still apply.

## Do not

- Restart, stop, or adopt Comfy `:8188` or MiniMax `:8192`.
- Start more than one paid proof render.
- Use Schnick Coffee House2 as the proof project, or hand-edit any project JSON.
- Add continuation or window-scope copy to Timed Prompts, including in Co-Director compile.
- Slice again inside `request_builder` or `seedance_api.py`.
- Weaken Dialogue QC for MiniMax H3, or mark an API take ready in order to continue the next window.
- Certify from a dry run, a unit test, or a single window.

## Proof

Tests, no charge:

- Case A text stays. Case B writes one slice onto an empty later window and a second pass does not move it.
- An API window 2 submits when window 1 completes, and the memory, bridge, and temporal functions are not called.
- A local window 2 still stops on the memory gate.
- Provider failure cancels the staged windows. Dialogue QC failure does not, and the take is not marked ready.
- Delivery prompt for Seedance equals the stored Master text, with no continuation header and no window-scope note. `request_builder` does not call the slicer.
- Opening a master from a previous API session does not call fal. GET `/master` does not call `submit_next_queued_batch`.
- Join waits until every planned window has a picture.

One paid proof, then stop:

- Disposable project. Seedance 2.0 Mini. 480p unless the creator stored another legal Mini tier. Scene clock 30 seconds. Two windows. At least one reference image, because Mini is reference-to-video.
- Ledger shows two fal request ids, one per window, in order. Window 2 starts only after window 1’s clip is saved.
- Both clips exist after reload, each on its own Visual bar, then one joined scene clip.
- Each fal request uses that window’s stored Master prompt and stored resolution.
- Speech-check result is recorded and does not block window 2 or the join.
- An API restart does not send another fal job.
- Comfy PID is the same before and after. Report `COMFY RESTARTED?: NO`.

## Verdict

`GO — API MULTI-WINDOW PIPELINE` only when the paid proof shows every planned window submitted, saved, placed, and joined.

Anything short of that is `NO-GO — <exact blocker>`.
