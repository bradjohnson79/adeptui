---
title: Creating a Character
summary: Character Creator stores identity, appearance, references, and voice with the open project. Creating a profile does not create a new project.
category: characters
slug: creating-a-character
tags: [character, identity, voice]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Creating a Character in Adept UI
seoDescription: Build a character profile, references, and voice in the open Adept UI project so later shots can reuse the same identity.
related: [character-identity-and-references, voice-and-audio, your-first-project]
---

## What this does

A character is a reusable identity. The profile holds who they are. References hold how they look. Voice Studio holds how they sound. All of that stays with the project you have open.

## Why you would create one before the shot

A video model does not remember a person from a previous prompt unless you give it references and keep using the same character record. Building the character first gives Timeline and image generation something stable to point at.

## How to create one

1. Open the project that owns the film.
2. Open Character Creator.
3. Name the character and describe the identity you need to keep: face, build, wardrobe, and anything a later shot must not drift.
4. Add or generate reference images into this project's library. A character reference sheet is the CRS.
5. Design the voice in Voice Studio when the character speaks. The performance uses the voice engine approved for that character.
6. Leave and reopen the project. The character should still be there.

## What to expect

Generations from this work appear in the open project's library. You should not see a brand-new project named after the character.

## Global characters

The creator can mark a character global. A global character is edited from the project that created it. Other productions do not become a back door for changing that record.

![Character Creator](/product/adept-ui-ai-character-creator.webp)

## Common mistakes

Describing the character only inside a video prompt and never saving a profile. The next shot will not know which description was the one you approved.
