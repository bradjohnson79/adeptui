---
title: Installing Local Models
summary: Adept Setup installs the local models Adept UI can run. There is no official Adept UI model page to download from yet, and a normal install of the application does not require Git or Hugging Face.
category: local-ai
slug: installing-models
tags: [models, setup, local ai]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Installing Local Models in Adept UI
seoDescription: Install supported local models through Adept Setup. Adept UI does not yet publish an official Hugging Face destination.
related: [running-ai-models-locally, what-setup-does, local-vs-api-models]
---

## What this does

Installing a local model means the studio has the files for the engine you selected. Adept Setup is the place that prepares those components. The desktop installer, when it is published, is a separate step from model files.

## Why you would not start at a model site

A filmmaker needs the model inside the project workflow. Downloading a weight file into a random folder does not tell Adept UI that the model is ready. Setup records the installation state the studio will actually use.

## How installation works

1. Open Adept Setup in the studio.
2. Choose Guided, AI-Guided, or Manual. Manual shows the full catalog when you are looking for one component.
3. Prepare the model you intend to run. Local video is MiniMax H3 or LTX 2.5. Local stills, when installed, include Illustrious XL, Qwen-Image, Z-Image, and Flux.
4. Use the studio's verify action and read the result.
5. Generate from the project only after that model is available. Select it by name.

## What to expect

A model that is not installed stays unavailable. Adept UI does not silently run a different engine under its name. Hosted models are a connection in Setup, not a file you store.

## Where model files live

Suggested locations come from the studio. This guide does not publish folder paths or file sizes. If you move a model directory by hand, Setup may no longer see it. Repair that in Setup rather than copying files into a new project.

## Hugging Face

Some model authors publish weights on Hugging Face. That is their distribution, not an Adept UI catalog. Adept UI does not yet have an official Hugging Face destination, so this page does not link one. When an official Adept UI model resource exists, the link will be added here. Until then, supported installation stays in Adept Setup.

> Note: Do not treat another organization's Hugging Face page as Adept UI. A shared word in a name is not this product.

## Technical notes

The studio keeps installation state for the component it prepared. A generation job should see that state, not a browser download. Verification is the Setup check, not a guess from a filename.
