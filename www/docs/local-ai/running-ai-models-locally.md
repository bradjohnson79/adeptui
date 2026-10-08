---
title: Running AI Models Locally
summary: Local models run on your workstation after Adept Setup has installed them. You stay in Adept UI. You do not launch a separate generation app to make the shot.
category: local-ai
slug: running-ai-models-locally
tags: [local ai, gpu, setup]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Running AI Models Locally in Adept UI
seoDescription: Run installed local image, video, and voice models from Adept UI. Local video uses the GPU path when the model is installed.
related: [comfyui-and-the-local-runtime, local-vs-api-models, what-setup-does, installing-models]
---

## What this does

Local generation keeps the model on the machine that is running Adept UI. The studio prepares the runtime, loads the model you selected, and writes the result into the open project.

[Learn how Adept UI uses ComfyUI workflows](/docs/local-ai/comfyui-and-the-local-runtime).

## Why you would run locally

The shot does not have to leave for a hosted provider. That matters when you want a specific local engine, such as MiniMax H3 or LTX 2.5 for video, or an installed stills model such as Flux or Illustrious XL. It also means the GPU and the disk have to hold the model.

## How to run a local shot

1. Install the model through Adept Setup. A menu name without files will not generate.
2. Open the project and the room for the shot: image, video, or voice.
3. Select the local model by name.
4. Generate, and leave the job until it returns a result or a visible failure.
5. Find the asset in this project's library.

## What to expect

Local video uses a GPU path when the model is installed. If the GPU cannot take the job, the production behavior is to block or fail, not to quietly finish on CPU. Memory pressure is a real limit. This page does not publish a VRAM number, because no public minimum is published.

## Model storage

Model files live where Setup placed them. Do not move those folders by hand and then expect the studio to find them. If a model disappears from the list, check Setup before you download a second copy into a random directory.

## Common issues

A model that "won't load" is usually not installed, still downloading, or larger than the machine can hold. Read the generation or Setup message. Starting a second project does not free the GPU.
