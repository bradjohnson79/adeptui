---
id: magi-sound
kind: system
modality: system
registry_ids:
  - mmaudio-local
aliases:
  - magi sfx
  - finishing sfx
  - sound design post
spoken: MAGI can queue SFX onto the sequence via magi.audio.generate. Mix assist is not supported. Audio Studio mix is a separate authority.
workspace_tags:
  - magi
  - magieditor
version: "2026.09.14"
authority: adept-integrated
---

# MAGI Sound

## Purpose

SFX generate onto the MAGI sequence.

## Allowed CD tools

- `magi.audio.generate` with kind=sfx (propose→approve→VERIFY)
- `magi.inspect_post_context` (domains=sound)
- `magi.inspect_job` / `magi.verify_action` for VERIFY
- Adjacent: `audio.scene_status` (Audio Studio — NOT MAGI authority)

## NOT_SUPPORTED (refuse)

- Mix assist (gain / duck / loudness)
- Claiming unified MAGI+Audio Studio mix
- Silence placebo as a real engine
- EQ / compression / limiter / de-ess
- Cinema 5.1 / 7.1 and other sound profiles belong on `magi.upscale` (`soundProfile`), not a separate sound workspace
