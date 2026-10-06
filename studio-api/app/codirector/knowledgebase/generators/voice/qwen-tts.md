---
id: qwen-tts
kind: generator
modality: voice
registry_ids:
  - qwen3-tts
aliases:
  - qwen voice
  - qwen3 tts
  - qwen tts
  - voice design
spoken: Qwen Voice Engine designs and clones a character voice and plays short previews. It is not IndexTTS performance takes and it is not music.
workspace_tags:
  - voice-creator
version: "2026.09.04"
authority: adept-integrated
---

# Qwen Voice Engine

## Purpose

Design, clone, and preview character voices.

## Identity

Adept provider `qwen3-tts`. Voice Engine language for creators.

## Supported modes

- Voice design from written traits.
- Clone from an approved clip.
- Short previews on the character.

## Unsupported modes

- Replacing IndexTTS 2 for a full acted scene when that is the selected performance engine.
- Music or effects.
- Teaching the creator to install packages by hand.

## Inputs

Character, preview line, optional clone clip.

## Reference semantics

Clone clip = timbre. Not a CRS.

## Output contract

Voice version + preview clip on this character / project.

## Runtime semantics

READY, NOT INSTALLED, or REQUIRES SETUP. Never “offline.”

## Selection guidance

First voice and short previews. Hand long takes to IndexTTS 2 when READY.

## What Co-Director must confirm

Clone-from-file.

## What Co-Director must never claim

That a preview is already the approved locked voice.

## Persistence

Linked on this project character.

## Relationships

- Voice room: `voice-creator`
- Performance: `indextts2`
