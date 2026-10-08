---
title: What Is Co-Director?
summary: Co-Director is project-scoped production intelligence. It understands the open film well enough to help you plan and continue work. It does not silently rewrite the project.
category: co-director
slug: what-is-co-director
tags: [co-director, production, chat]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: What Is Co-Director in Adept UI?
seoDescription: Co-Director helps you work across the open Adept UI project, from characters and storyboard to Timeline and MAGI.
related: [what-co-director-can-and-cannot-do, working-across-the-production, where-co-director-fits]
---

## What this does

Co-Director is the production guide inside Adept UI. You talk to it about the film that is open: the characters, the scenes, the board, the Timeline, the voice, and the finish. Quick actions include continuing the project, reviewing the Timeline, generating assets, and opening chat.

## Why you would use it

A film has more state than a prompt. Co-Director is useful when you want the next shot to respect the project you already built, instead of retyping the whole production into a blank box.

## How it works

1. Open the project. Production tools are limited when no project is open.
2. Ask about a scene, a character, or the next shot in ordinary language.
3. Co-Director can help you move into the room that owns the work: Storyboard, Timeline, character, voice, or MAGI.
4. A change becomes part of the film when the project saves it through the normal approval path.

## What to expect

You should see the project you named, not a generic assistant. If the reply ignores the open film, check that the project is actually open before you rewrite the request.

## Technical notes

Co-Director reads project context. Conversation history is not the same as system state. A claim that a shot was generated, a character was saved, or a clip was placed is only true when that subsystem shows it.

Memory of intent does not override the Timeline, the library, or the character record. When those disagree, the project record is the one to trust.

![Co-Director](/product/adept-ui-co-director.webp)

## Common mistakes

Asking Co-Director to "just use a different model" as a shortcut. Model choice stays explicit. Co-Director must not silently swap the model, the asset, or the project.
