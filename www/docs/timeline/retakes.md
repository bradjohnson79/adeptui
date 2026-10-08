---
title: Retakes
summary: A retake is a new generation of a shot you chose to run again. It does not silently replace the project, and it does not resume a render from a session that already ended.
category: timeline
slug: retakes
tags: [timeline, retake, generation]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Retakes on the Adept UI Timeline
seoDescription: A Timeline retake is a deliberate new generation of a shot. It does not resume an abandoned render.
related: [shot-continuation, what-is-timeline, troubleshooting-generation]
---

## What this does

A retake asks the selected model to generate that shot again. You use it when the clip is wrong: performance, motion, continuity, or a failure you have already understood.

## Why it is explicit

Automatic retries can spend another hosted generation or fill the GPU without you deciding the shot is worth it. A retake is a decision. The new job belongs to the current studio session.

## How to retake

1. Open the shot on the Timeline.
2. Check the model, the references, and the frame roles before you run. A retake repeats the request you send now, including any mistake still attached.
3. Start the new take. Do not expect an old failed job to wake up because the project was reopened.
4. Review the new clip. Keep the one you accept.

## What to expect

The library can hold more than one result for the same shot idea. The Timeline shows the take you place. A failed previous attempt remains a failed attempt.

## When not to retake

Do not retake to escape a setup problem. If the model is missing, the GPU cannot load it, or the hosted connection failed, another take with the same broken setup fails again. Fix the condition, then retake.
