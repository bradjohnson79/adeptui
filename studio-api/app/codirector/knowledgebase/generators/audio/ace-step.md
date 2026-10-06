---
id: ace-step
kind: generator
modality: audio
registry_ids:
  - ace-step-local
aliases:
  - ace step
  - acestep
  - music engine
spoken: ACE-Step writes music for this project. It is not a character voice and it is not a sound-effects engine.
workspace_tags:
  - audio
  - magi
version: "2026.09.04"
authority: adept-integrated
---

# ACE-Step

## Purpose

Local music generation.

## Identity

Adept row `ace-step-local`. Certified music path when installed.

## Supported modes

- Music / beds / songs from text.
- MAGI sequence music when asked.

## Unsupported modes

- Character speech.
- Sound effects (use MMAudio).
- Timeline Reference-to-Video.

## Inputs

Music prompt, duration if the room offers it.

## Output contract

Audio file in this project's Library.

## Runtime semantics

READY when the music engine is installed. Otherwise NOT INSTALLED / REQUIRES SETUP.

## Selection guidance

Any “write a song / bed” request.

## What Co-Director must never claim

That ACE-Step spoke a character line.

## Persistence

This project Library.

## Relationships

- Audio room: `audio-sfx`
- Effects: `mmaudio`
- Voice: `qwen-tts`
