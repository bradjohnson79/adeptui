---
title: From Storyboard to Video
summary: A storyboard panel is a plan you can hand toward video. This guide covers the handoff from a 16:9 or 9:16 board into a generated clip on the Timeline.
category: workflows
slug: storyboard-to-video
tags: [storyboard, video, workflow]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Storyboard to Video Workflow in Adept UI
seoDescription: Turn an Adept UI storyboard into a video shot by carrying the frame and aspect into the model and the Timeline.
related: [using-storyboard-studio, ai-video-generation, what-is-timeline]
---

## What this does

The board decides the frame. Video generation makes the motion. Timeline gives the clip a place in the scene. This workflow is the handoff between those three.

## Steps

1. Finish the panel you mean to shoot. An empty or placeholder panel is not a start frame.
2. Note the aspect, 16:9 or 9:16, and keep the video request in that shape if the model allows it.
3. Use the panel image as an image-to-video start, or as a reference, depending on what the selected model accepts. Do not drop it in a style slot and call it a start frame.
4. Choose the video model by name and generate into this project.
5. Review the clip against the panel. Motion will add things the still did not have. If the composition broke, retake with a clearer frame rather than boarding a different film.
6. Place the accepted clip on the Timeline in the scene that matches the board order.

## What to expect

The clip should be recognizable as the panel plus motion. It will not be a frame-by-frame trace of the still unless the model and the start frame actually constrain it that way.

## Technical notes

Storyboard references are stored as production assets and can be passed into generation workflows that accept them. The pass is not automatic for every model. If the control is missing, that model is not offering the handoff.
