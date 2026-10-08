---
title: AI Image Generation in Adept UI
summary: Image generation makes stills and reference art with a model you select. The results stay in the open project's library so storyboard, characters, and video can reuse them.
category: image-generation
slug: ai-image-generation
tags: [image, stills, reference, library]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: AI Image Generation in Adept UI
seoDescription: Generate character, environment, and prop stills in Adept UI with a chosen image model and keep them in the project library.
related: [creating-a-character, choosing-a-video-model, using-storyboard-studio]
---

## What this does

Image generation is the stills room. You use it for character art, environments, props, and frames you may later hand to a video model. It is not the Timeline, and a still is not a shot until you place or animate it.

## Why you would generate a still first

A reference image is something you can look at and approve. Video is harder to correct. Character sheets, environment sheets, and prop sheets are the stills with a defined production role: CRS, ERS, and PRS.

## How to use it

1. Open the project.
2. Choose the image model you mean to run. Local stills, when installed, include Illustrious XL, Qwen-Image, Z-Image, and Flux. Hosted stills can include Flux, Krea 2, and other models configured in Setup.
3. Write the frame you need, and attach a reference when the model supports one.
4. Generate. The image should return as an asset in this project's library.
5. Use that asset on a storyboard or as a reference for video. Do not generate a second copy in a new project.

## What to expect

The model you selected is the model that runs. If it is not installed or the hosted connection is missing, the generation should fail visibly. It should not quietly switch engines.

## Technical notes

Reference-conditioned generation only works when that model accepts references. Profile-guided local character work, when you use Illustrious XL that way, is a specific path. A dropdown that lists a model is not proof the runtime finished a job.

## Common issues

An image that ignores a character usually means the reference was not attached, or the model cannot use that reference. Check the asset in the library before you rewrite the prompt from scratch.
