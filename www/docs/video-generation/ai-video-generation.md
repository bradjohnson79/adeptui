---
title: AI Video Generation in Adept UI
summary: Video generation runs a model you choose and returns a clip to the project. Adept UI is the production environment around that model. It is not a video model itself.
category: video-generation
slug: ai-video-generation
tags: [video, text-to-video, image-to-video, models]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: AI Video Generation in Adept UI
seoDescription: Generate video in Adept UI with MiniMax H3, LTX 2.5, or a hosted model you select. Clips return to the project library.
related: [choosing-a-video-model, shot-continuation, local-vs-api-models, what-is-timeline]
---

## What this does

You describe a shot, optionally give it frames or references, and run a video model. The clip comes back to the open project so Timeline can place it.

## Ways a shot can start

- **Text to video.** The prompt carries the shot. Use this when you do not have a frame yet.
- **Image to video.** A still you already approved is the starting picture.
- **Reference to video.** Character, environment, prop, or other references condition the shot when the model supports them.
- **Start frame and end frame.** You pin where the shot begins and where it should arrive, when that model offers those controls.

These are different requests. A start frame is not a style reference with a different name.

## How to generate

1. Stay in the open project.
2. Choose the video model. Local video is MiniMax H3, LTX 2.5, or Hunyuan 1.5 Distilled when that model is installed. Hosted video through fal.ai can be Seedance 2.0, Seedance 2.5, Kling 2.5 Turbo Pro, Kling 3.0, Veo 3.1, Runway Gen-3 Turbo, Flux 3.0, Happy Horse 1.0, or Google Gemini Omni.
3. Set the duration and frame the model allows. Do not assume every model shares one maximum length or one resolution.
4. Attach only the references that match the job.
5. Run the shot. Wait for a real result in the library or a visible failure.

## What to expect

A finished job gives you a clip you can place on the Timeline. Opening the Timeline later does not restart that job. A failed job stays failed until you deliberately run a new take.

## Technical notes

Adept UI checks what the selected model supports and exposes those controls. Capability is metadata on the model, not a guess by the interface. Local video uses the GPU path when the model is installed. There is no silent CPU fallback as the production default.

## Common mistakes

Mixing up the model family because an older name is familiar. WAN is not a current Adept UI video model. If a control you expected is missing, the selected model may not offer it. Switch models only by choosing the other model, not by hoping the studio substitutes one.
