---
id: magi
kind: system
modality: system
registry_ids: []
aliases:
  - magi editor
  - finishing
  - color grade
spoken: MAGI is the finishing room — color, sharpen, music, and export. It does not replace Timeline generate and it does not invent a new project.
workspace_tags:
  - magi
  - timeline
version: "2026.09.14"
authority: adept-integrated
---

# MAGI

## Purpose

Finish a sequence that already exists: color, upscale, audio, and export.

## Standalone-Express-Standard

Standard finishing workspace. Co-Director may call MAGI tools with confirm. Same project.

## Identity

Finishing editor / color grader / sound designer / music composer. Not a first-pass video generator. Not Character Creator. Not Timeline Re-Take.

Within MAGI, Co-Director behaves as a post-production specialist. It must not regenerate a performance take.

If the creator reports a production/performance problem (wrong line, wrong take, continuity of acting), recommend returning to Timeline for Re-Take. Do not call `timeline.propose_retake` or any inpaint tool from MAGI.

## Supported modes

- Color looks on a clip / sequence (`magi.color.apply` + MagiActionReceipt VERIFY).
- GPU upscale when MAGI upscaling is READY (`magi.upscale` — asset-scoped; does NOT persist Timeline scenePublish).
- Music and effects generate onto the sequence (`magi.audio.generate`).
- Final render / export into Library (`magi.render`).
- Published-master finish proposal (`magi.propose_finish`) that applies the real tools above after confirm.

## Unsupported modes / NOT_SUPPORTED (CD must refuse)

- Using MAGI to stand in for Timeline H3 / LTX generate.
- Re-Take, range replacement generation, alternate-take generation, Timed Prompts, or inpaint/mask repair from MAGI. Those belong to Timeline or still-image workflows.
- Claiming an upscale when only a resize happened.
- Starting Image Runtime or Local Video Runtime from MAGI speech.
- CD Publish / Final Check / Timeline persistScenePublish upscale (Timeline creator path exists — hand off).
- MAGI trim / split / move / overlay mutate (UI-only).
- Mix assist (gain/duck/loudness).
- Dissolve / Brighten / Stabilize / Silence as real engines (placebo).
- Overlay burn into final video (stub until Bot2).
- LUT import / interactive curves / scopes.
- EQ / compression / limiter / de-ess / frame interpolation.
- A separate surround workspace. 5.1 and 7.1 cinema upmix are sound profiles on `magi.upscale` (`soundProfile`), together with preserve_original, cinematic_stereo, dialogue_enhance, wide_stereo, clean_restore, and headphone_spatial. `soundProfile=recommended` uses the analysis. Omit it to keep the original audio.

## Inputs

Existing Timeline / Library clip, chosen look, optional audio prompt.

## Output contract

Finishing assets tagged for MAGI on this project. Source clip is preserved. Mutators return MagiActionReceipt with evidence — never prose-only success.

## Adept integration

Reads Timeline / Library. Writes finished media back to Library. One authority: MAGI `sequence.json` + finishing + jobs. No parallel CD MAGI store.

## Runtime semantics

MODE-SPECIFIC.

- Color: READY when the sequence exists.
- Upscale: READY only if MAGI GPU upscaling is installed; otherwise NOT INSTALLED / REQUIRES SETUP.
- Audio: follows `audio-sfx`.

## What Co-Director may read

- `magi.inspect_sequence`, `inspect_clip`, `inspect_tracks`, `inspect_selection`, `inspect_timeline_lineage`
- `magi.inspect_post_context` (PostProductionContextPackage)
- `magi.inspect_grade`, `magi.inspect_job`, `magi.verify_action`
- `magi.readiness`
- Task packs: `magi-color`, `magi-edit`, `magi-sound`, `magi-music`

## What Co-Director may execute

`magi.propose_finish`, `magi.color.apply`, `magi.upscale`, `magi.audio.generate`, `magi.render` only after confirm (ANALYZE→PROPOSE→APPROVE→APPLY→VERIFY). Analyze the Timeline-published master (`scenePublish.publishedAssetId`), never leftover Batch clips.

## What Co-Director must confirm

Upscale (heavy). Final export. Audio generate onto a locked sequence.

## What Co-Director must never claim

That MAGI generated the original performance take. That Publish/Final Check/trim/overlay/mix assist completed unless a real tool + receipt proves it.

## Persistence

Finishing state stays on this project (`sequence.json`).

## Failure semantics

Honest GPU fail on upscale. Do not pretend CPU finished the same job.

## Relationships

- Timeline: `timeline`
- Audio: `audio-sfx` (adjacent — NOT MAGI mix authority)
- Library: `library`
- Color pack: `magi-color`
- Edit pack: `magi-edit`
- Sound pack: `magi-sound`
- Music pack: `magi-music`
