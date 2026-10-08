---
title: What Is Timeline?
summary: Timeline turns individual clips into a scene. You sequence shots, continue them, review them, and retake them on purpose. Opening Timeline does not restart an abandoned render.
category: timeline
slug: what-is-timeline
tags: [timeline, scene, shots]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: What Is the Adept UI Timeline?
seoDescription: The Adept UI Timeline sequences generated shots into a scene, with continuations and deliberate retakes.
related: [shot-continuation, retakes, ai-video-generation, what-is-magi]
---

## What this does

Timeline is where generated shots become a production. A clip in the library is a result. A clip on the Timeline is a shot in a scene, with a place in time and neighbors it has to match.

## Why you would use it

Isolated clips do not cut. Timeline is how you see duration, order, and whether the next shot continues the previous one. It is also where generation status for a shot is visible while you are assembling the scene.

## How a scene is built

1. Open the project and the scene.
2. Add a shot. Generate it from the Timeline or place a clip you already accepted.
3. Give the shot the references it needs: character, style, start frame, end frame, or motion. Each role is explicit.
4. Review the clip in place.
5. Continue the shot or retake it only when you mean to run another generation.
6. When the picture is the one you want to finish, send it to MAGI.

## What to expect

The Timeline is designed to preserve continuity across the shots you connect. It does not guarantee that every third-party model will match the previous frame. Look at the cut.

Opening a project, opening Timeline, or reloading the page does not resume a render that belonged to an earlier session. A shot that was abandoned stays abandoned until you start a new take.

![Timeline](/product/adept-ui-ai-filmmaking-timeline.webp)

## Technical notes

Each active render belongs to the studio session that started it. A previous session's job is not auto-resumed. The asset from a job that actually finished can still be in the library. The render itself does not wake up because you looked at the scene.

## Common mistakes

Scrubbing the Timeline to "wake up" a failed shot. Status does not change until a new take runs or a finished asset is placed.
