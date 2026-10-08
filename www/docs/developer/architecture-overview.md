---
title: Architecture Overview
summary: Adept UI is a desktop studio in front of a local studio service and the model you selected. This public overview names those parts without secrets, ports-as-settings, or internal runbooks.
category: developer
slug: architecture-overview
tags: [architecture, studio api, models]
difficulty: technical
updated: 2026-10-06
status: published
seoTitle: Adept UI Architecture Overview
seoDescription: A public look at Adept UI: the desktop interface, the studio service, project data, and explicit model selection.
related: [local-services, local-vs-api-models, comfyui-and-the-local-runtime, contributing, website-guide]
---

## What this page is for

It is a map for someone extending or integrating with the product. It is not a setup guide for a filmmaker, and it does not include credentials, internal host names, or unreleased service flags.

## The parts that matter

- **The studio interface.** Rooms such as Character Creator, Storyboard, Timeline, and MAGI. The open project is the context for all of them.
- **The studio service.** Local API the interface calls for projects, generation, and setup. Creators do not address it directly.
- **The local generation runtime.** Executes installed local models. ComfyUI is that runtime. Adept UI owns when it is used. A creator does not operate it as a separate app. [Learn how Adept UI uses ComfyUI workflows](/docs/local-ai/comfyui-and-the-local-runtime).
- **Hosted providers.** A configured connection, including fal.ai for hosted video. The provider sees the request. The project stores the result.
- **Project data.** Characters, scenes, references, and assets for one film. Generation writes into that project.

## Model selection

The interface asks the selected model what it supports. Controls follow that capability metadata. A generation that completes on a different model than the one requested is a defect, not a fallback feature.

## What is intentionally absent

No connection strings, no tokens, no private paths, and no instruction to bind or restart services. Port numbers for developers are on the local services page so this overview stays a map.

## Contributing boundary

Public documentation can describe behavior a creator or an integrator can see. It does not publish certified internal gate notes, license claims, or a version number that has not been released. Adept UI 1.1 is free software built around an open AI ecosystem. It does not have a public open-source license.
