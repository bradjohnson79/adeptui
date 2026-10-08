---
title: Character Identity and References
summary: Identity is the saved character. References are the images and sheets generation can use. A reference has a role, and that role is what later shots follow.
category: characters
slug: character-identity-and-references
tags: [character, reference, crs]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Character Identity and References in Adept UI
seoDescription: How Adept UI character identity, reference sheets, and reference roles keep a person consistent across shots.
related: [creating-a-character, glossary, ai-video-generation]
---

## What this does

Identity answers "who is this?" References answer "which pictures are we allowed to follow?" A prompt without a reference asks the model to invent. A reference with a role tells the shot what kind of continuity you mean.

## Reference roles you will actually see

| Mark | Name | Use |
| --- | --- | --- |
| @ | CRS | Character reference sheet |
| # | ERS | Environment reference sheet |
| % | PRS | Prop reference sheet |

Those marks show up where the studio accepts reference tokens. They are not three words for the same image. A prop sheet will not hold a face, and a character sheet will not define the room.

Video, audio, and generic image references exist as their own kinds of conditioning. An audio reference is not the same thing as a clip sitting on the Timeline's audio bed.

## Why roles matter

On the Timeline, a start frame, an end frame, a character reference, and a style reference are different jobs. Attaching the last frame of the previous shot as "style" does not make it a continuation frame.

## What to expect

Continuity is only as strong as the reference and the model. Some models accept reference images. Some do not. Adept UI is supposed to offer the controls that model supports, not pretend every model can lock a face.

## Troubleshooting recognition

If a shot ignores the character, check three things before you change the prompt: the character belongs to this project, the reference is actually attached with the character role, and the selected model accepts that kind of reference. A new project will not make the model more consistent.
