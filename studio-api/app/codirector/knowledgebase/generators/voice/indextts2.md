---
id: indextts2
kind: generator
modality: voice
registry_ids:
  - index-tts2-local
aliases:
  - index tts
  - index tts 2
  - indextts
  - performance voice
spoken: IndexTTS 2 performs a full voice take for a character. Use it when you want the line acted, not just a short voice preview.
workspace_tags:
  - voice-creator
version: "2026.09.04"
authority: adept-integrated
---

# IndexTTS 2

## Purpose

Local performance takes for a character voice.

## Identity

Adept provider `index-tts2-local`. Not Qwen Voice design. Not ACE-Step.

## Supported modes

- Scene / line takes when the engine is READY.
- Use an approved character voice as the speaker.

## Unsupported modes

- Designing a brand-new voice from adjectives (that is Qwen Voice).
- Music.
- Video lip-sync by itself.

## Inputs

Approved voice, script line, optional emotion / style the room exposes.

## Output contract

Take in Library, linked to the character / scene.

## Runtime semantics

READY, NOT INSTALLED, or REQUIRES SETUP. Installing is a Settings / Voice Engine job, not a creator terminal lesson.

## Selection guidance

Longer acted lines. If NOT INSTALLED, say so and offer a Qwen preview if that engine is READY — with confirm, not silent swap for a performance take.

## What Co-Director must confirm

Long takes. Replacing a kept take.

## Persistence

This project Library.

## Relationships

- Design: `qwen-tts`
- Room: `voice-creator`
