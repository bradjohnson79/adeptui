---
title: System Requirements
summary: Adept UI is intended for desktop Windows, macOS, and Linux. Specific CPU, RAM, VRAM, and disk minimums are not published on this site, so this page does not guess them.
category: installation
slug: system-requirements
tags: [requirements, gpu, desktop]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: Adept UI System Requirements
seoDescription: Adept UI targets desktop Windows, macOS, and Linux. Hardware minimums are not published here and are not estimated.
related: [installing-adept-ui, running-ai-models-locally, what-setup-does]
---

## What this page will and will not say

The published platform list is Windows, macOS, and Linux desktop. A phone browser is not a substitute for the studio.

This site does not publish a minimum processor, a minimum amount of memory, a minimum GPU, or a disk budget. Those figures are omitted on purpose. A guessed number would be worse than none.

## What you can still know

- Local video generation uses a GPU path when that model is installed. Silent fallback to CPU is not the production default.
- Hosted video models do their generation on the provider side. Your machine still runs Adept UI.
- Model files are large. Disk space depends on which models you install. Adept Setup is where installed components are checked. This page will not invent a gigabyte figure.
- The studio is a desktop application. Local services that support it are started with the product. Creators are not asked to configure ports.

## GPU in plain language

A local model has to fit the work you ask of it. If the GPU cannot load the model, the honest result is a failed or blocked generation, not a quiet switch to a different engine. Use Adept Setup and the generation error to see what failed.

## Technical notes

When hardware figures are published with a release, they belong on this page with the release they describe. Until then, treat any RAM or VRAM number you see elsewhere as unverified.
