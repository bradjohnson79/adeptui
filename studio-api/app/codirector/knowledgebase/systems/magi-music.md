---
id: magi-music
kind: system
modality: system
registry_ids:
  - ace-step-local
aliases:
  - magi music
  - finishing score
  - post music
spoken: MAGI can queue music onto the sequence via magi.audio.generate kind=music. Confirm before placing onto a locked sequence.
workspace_tags:
  - magi
  - magieditor
version: "2026.09.14"
authority: adept-integrated
---

# MAGI Music

## Purpose

Music generate onto the MAGI sequence.

## Allowed CD tools

- `magi.audio.generate` with kind=music
- `magi.inspect_post_context` (domains=music)
- `magi.inspect_tracks` / `magi.inspect_job` / `magi.verify_action`

## NOT_SUPPORTED (refuse)

- Mix assist / ducking under dialogue
- Claiming professional final-mix replacement

## Confirm

Audio generate onto a locked sequence requires creator confirm.
