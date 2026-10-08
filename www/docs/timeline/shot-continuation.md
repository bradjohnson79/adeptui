---
title: Shot Continuation
summary: Continuation extends a shot from what you already have, often by carrying the last frame forward. It is a new generation you start on purpose. It is not a promise that the next model frame will match exactly.
category: timeline
slug: shot-continuation
tags: [timeline, continuation, continuity, last frame]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Shot Continuation on the Adept UI Timeline
seoDescription: Continue an Adept UI shot from the previous frame. Continuation is a deliberate new generation, not an exact frame match.
related: [what-is-timeline, retakes, ai-video-generation]
---

## What this does

Continuation is how a scene moves forward without starting from a blank prompt. You take the shot you have and ask for the next stretch, using the last frame or another explicit reference as the bridge.

## Why you would continue instead of starting over

A new text-to-video prompt re-invents the person, the room, and the lens. A continuation tries to begin where the previous clip ended. That is the right tool when the camera should keep moving, or when the next beat is the same setup a moment later.

## How to continue

1. Select the shot on the Timeline that already has a clip you accept.
2. Use the continuation action for that shot, not a brand-new unrelated shot, when you want the scene to carry forward.
3. Confirm the bridge you intend. Last-frame continuity means the end of the current clip is the start of the next request. A start frame or end frame you attach by hand is a different instruction. Name the role you mean.
4. Run it. This creates a new generation in the current session.
5. Watch the join. If the character or the lens jumps, the continuation did not hold. Decide whether to retake.

## What to expect

You should get a new clip that starts from the bridge you set. You should not expect the join to match perfectly. Models differ. The Timeline can pass the frame. The model still interprets it.

> Note: Designed to preserve continuity. Not a guarantee that every third-party model matches the previous frame.

## Technical notes

Reference roles stay explicit. Putting the last frame in a style slot does not make it a start frame. The generation is a new job. It does not resume a job from a previous time you had the studio open.

## Common mistakes

Continuing a shot that failed and has no clip. There is no last frame to carry. Retake or generate the shot first. Also avoid continuing in a different aspect than the shot you are leaving. The join will show the crop.
