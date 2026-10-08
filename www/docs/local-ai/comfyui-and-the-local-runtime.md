---
title: The Local Generation Runtime
summary: Adept UI runs local generation for you. The local runtime is part of the studio, not a separate application you configure before each shot.
category: local-ai
slug: comfyui-and-the-local-runtime
tags: [local runtime, comfyui, technical]
difficulty: technical
updated: 2026-10-06
status: published
seoTitle: Local Generation Runtime in Adept UI
seoDescription: Adept UI manages the local generation runtime, including ComfyUI, so creators stay inside the studio.
related: [running-ai-models-locally, local-services, architecture-overview]
---

## What this does

When you run a local model, Adept UI talks to a local generation runtime on your machine. That runtime is how installed models actually execute. You do not build a node graph, and you do not start the runtime from a separate window to make a shot.

## Why this is a technical note

Creators can ignore the runtime's name. It is documented here because people looking under the hood will find it, and because "ComfyUI Integration" is a real part of local generation rather than a second product inside the film workflow.

ComfyUI is the local generation runtime Adept UI manages. The film workflow still starts and ends in Adept UI: pick a model, run the shot, get an asset in the project.

## What you should not do

- Do not launch a separate ComfyUI and expect Adept UI to adopt it
- Do not free memory by killing processes
- Do not treat a port number as a creator setting
- Do not restart the runtime because a single shot failed. Read the shot's error first

## What to expect

If the local runtime is not ready, Setup and the generation error should say so. The repair path is Adept Setup and the studio's own runtime handling, not a manual server start.

## Technical notes

The studio service and the local runtime are different processes. A problem in one is not automatically a problem in the other. Developer-facing service names and ports are listed in the local services reference. They are not steps in a shot.
