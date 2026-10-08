---
title: Understanding the Adept UI Workflow
summary: Adept UI follows a film workflow. Develop the project, plan the frame, generate with a chosen model, assemble on Timeline, then finish in MAGI.
category: getting-started
slug: understanding-the-workflow
tags: [workflow, production, timeline]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Understanding the Adept UI Workflow
seoDescription: How an Adept UI shot moves from project and storyboard through generation, Timeline, and MAGI finishing.
related: [what-is-timeline, using-storyboard-studio, what-is-magi, ai-film-from-scratch]
---

## What this does

The workflow is the order of decisions, not a locked checklist. You can start from a character, a board, or a Timeline shot. The useful habit is knowing which decision you are making.

## Why the order matters

Video generation spends time and, for hosted models, a provider request. A storyboard or a reference still is a cheaper way to find out the shot is wrong. Timeline is where you find out the shot does not cut. MAGI is where you find out the shot does not match the look of the scene.

## How a shot usually moves

1. The project is open. Characters, environments, and props live there.
2. Storyboard Studio, when you use it, plans the frame. Supported board aspects are 16:9 and 9:16.
3. You choose an image or video model. Local and hosted models are different routes. The selected model is the one that runs.
4. The result returns to the project library.
5. Timeline places the shot in a scene. A continuation or a retake is a deliberate next step, not an automatic restart.
6. MAGI finishes media you send it: color, upscale when a GPU path is available, overlays, and export.

## What to expect

Continuity is a design of the Timeline and the references you attach. It does not guarantee that every third-party model will match the previous frame.

## Technical notes

Reference roles are explicit. A character reference, a style reference, a start frame, and an end frame are not the same attachment. The interface offers controls the selected model can actually use.

SceneCraft, the spatial reconstruction tool, is not part of the current production set. Environment Creator and Prop Creator are the current rooms for those assets.
