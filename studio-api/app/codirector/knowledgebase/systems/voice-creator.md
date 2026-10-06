---
id: voice-creator
kind: system
modality: voice
registry_ids:
  - qwen3-tts
  - index-tts2-local
aliases:
  - voice studio
  - voice engine
  - character voice
spoken: Voice Creator gives a character a speakable voice on this project. Qwen designs or clones the voice. IndexTTS is the performance engine when you need a full take.
workspace_tags:
  - voice-creator
  - character-creator
version: "2026.09.04"
authority: adept-integrated
---

# Voice Creator

## Purpose

Design, clone, preview, and attach a character voice. Keep it on the open project.

## Standalone-Express-Standard

Opened from Character Creator (Advanced / Voice). Not a Timeline video generator. Not Express PoseCraft.

## Identity

Voice belongs to a character id on this project. It is not a music bed and not an environment sound.

## Supported modes

- Qwen Voice Engine: design and clone, short previews.
- IndexTTS 2: performance takes when that engine is READY.
- Attach an approved voice so Timeline MiniMax H3 can use it as a voice reference when the path is wired.

## Unsupported modes

- Treating ACE-Step music or MMAudio effects as a character voice.
- Inventing a voice file that was not generated or uploaded.
- Teaching the creator to start a hidden voice process by hand.

## Inputs

Character, script line or preview text, optional clone clip.

## Reference semantics

A clone clip is timbre only. It does not become a CRS.

## Output contract

Voice versions and clips in Library, linked to the character.

## Adept integration

MiniMax H3 Timeline may attach an approved voice as audio reference. Other Timeline generators usually name the voice in prose only.

## Runtime semantics

MODE-SPECIFIC.

- Qwen Voice Engine: READY or REQUIRES SETUP / NOT INSTALLED.
- IndexTTS 2: READY, NOT INSTALLED, or REQUIRES SETUP.
- On Demand does not apply unless Adept labels that engine On Demand.

## Selection guidance

- First voice / design: Qwen Voice Engine.
- Longer acted take: IndexTTS 2 when READY.

## What Co-Director may read

Saved voice versions for this character.

## What Co-Director may execute

Preview or generate when asked.

## What Co-Director must confirm

Clone-from-file. Long takes. Replacing an approved voice.

## What Co-Director must never claim

That a preview is already the approved character voice.

## Persistence

Voice links survive reload on this project.

## Failure semantics

If the Voice Engine is NOT INSTALLED, say Requires Setup / Not Installed. Do not pretend a music model spoke the line.

## Relationships

- Character: `character-creator`
- Engines: `qwen-tts`, `indextts2`
- Timeline H3: `minimax-h3`
