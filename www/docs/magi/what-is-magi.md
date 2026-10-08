---
title: What Is MAGI?
summary: MAGI is the finishing room. You send it media to grade, upscale when a GPU is available, compose overlays, and export. Generation happens before MAGI.
category: magi
slug: what-is-magi
tags: [magi, color, upscale, export]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: What Is MAGI in Adept UI?
seoDescription: MAGI finishes Adept UI shots with color, GPU upscale when available, overlays, and export.
related: [what-is-timeline, ai-film-from-scratch, understanding-the-workflow]
---

## What this does

MAGI takes a shot you already have and finishes it. Color and look, scale, overlay composition, and export live here. It is not where you invent the performance.

## Why finishing is its own room

A grade on a bad cut hides the cut. Upscaling a shot that jumped continuity makes a larger jump. MAGI is the step after you have a clip you mean to keep.

## What you can do

- Grade the image, including exposure and look presets
- Upscale when a GPU path is available
- Compose overlays
- Export the finished media

## What MAGI is not doing

Dissolves are not a current MAGI engine. Stabilization is not a current MAGI engine. If you need a transition, it is not something this room will invent for you today.

## How to use it

1. Accept the clip on the Timeline, or choose the library asset you intend to finish.
2. Send that media to MAGI.
3. Set the grade and any overlay. Check the picture at the size you will deliver, not only as a thumbnail.
4. Upscale only if you need a larger master and the GPU path is available.
5. Export. Confirm the file is the shot you graded.

## What to expect

The export is a finished view of the media you sent. It does not re-run the video model. If the performance is wrong, go back to a retake. Do not try to grade your way out of the wrong clip.

![MAGI](/product/adept-ui-magi.webp)

## Technical notes

Upscale uses the GPU when that path is available. If it is not available, the honest state is that the upscale did not run. MAGI should not quietly skip and still describe the file as upscaled.
