---
title: Local and API Models
summary: Local models run on your machine when they are installed. API models run through a hosted provider you have connected. Adept UI does not silently switch between them.
category: models
slug: local-vs-api-models
tags: [local, api, models, fal]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Local vs API Models in Adept UI
seoDescription: Local Adept UI models run on your machine. Hosted models use a connected provider. The model you select is the one that runs.
related: [running-ai-models-locally, using-hosted-models, choosing-a-video-model]
---

## What this does

Every generation has a home. Local means the model runs on the workstation. API, or hosted, means the request goes to a provider and the result comes back to the project.

## Why the split matters

Local work depends on the model files and the GPU. Hosted work depends on the connection and the provider accepting the request. A failure on one side is not fixed by pretending the other side ran.

## How to choose

Use a local model when it is installed and you want that engine on your machine. Use a hosted model when you want that provider and Setup shows the connection. Select it in the generation controls. The name on the control is the contract.

## What to expect

The clip or still in the library should identify the route you chose. If the studio cannot run that model, you get an error or a blocked state. You do not get a different model's picture with the first model's name.

## Technical notes

Open-weight models are weights you can run locally. They are not a license for Adept UI. Hosted models are someone else's service. Sending a shot to a provider sends that provider the prompt and the media the request requires. Do not put secrets into a prompt.

This page does not list prices. Provider billing is the provider's, and it is not published here.
