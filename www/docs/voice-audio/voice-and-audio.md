---
title: Voice and Audio
summary: Voice Studio designs how a character speaks. Audio Studio is for music, ambience, and Foley. They are different rooms, and both stay with the open project.
category: voice-audio
slug: voice-and-audio
tags: [voice, audio, dialogue, foley]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Voice and Audio in Adept UI
seoDescription: Use Voice Studio for a character performance and Audio Studio for music, ambience, and Foley in the same Adept UI project.
related: [creating-a-character, understanding-the-workflow, what-is-timeline]
---

## What this does

Spoken performance and soundtrack are separate jobs. Voice Studio is the character's voice: the person, the delivery, and the line. Audio Studio covers music, ambience, and Foley.

## Why they are split

A dialogue line has to match a character. A room tone does not. If both are treated as "audio," the wrong file ends up on the shot and the performance is buried under a bed, or the bed is missing because you only generated speech.

## How to work

1. Create or open the character in this project.
2. In Voice Studio, shape the voice and the performance. Generation uses the voice engine approved for that character. This guide does not name one vendor as the only engine.
3. Approve the take you want to keep. Approval is a decision, not an automatic pass.
4. Generate music, ambience, or Foley in Audio Studio when the scene needs them.
5. Place what you accepted on the Timeline with the picture. An audio reference used as conditioning is not the same object as a clip on the Timeline.

## What to expect

The voice stays with the character in the project. Reopening the project should still show the approved voice. A new line is a new generation, not a reason to recreate the character.

![Voice Studio](/product/adept-ui-ai-voice-studio.webp)

## Common issues

If speech generates but does not sound like the character, check that you are in the character's voice, not a one-off prompt. If the scene is silent, check whether you generated voice only and never placed it, or whether you expected Voice Studio to create the music bed.
