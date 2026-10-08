---
title: What Setup Does
summary: Adept Setup checks whether the studio is ready and prepares required components. It is the readiness room, not a second application.
category: setup-manager
slug: what-setup-does
tags: [setup, readiness, models]
difficulty: start
updated: 2026-10-06
status: published
seoTitle: What Adept Setup Does
seoDescription: Adept Setup checks studio readiness and prepares components. Guided, AI-Guided, and Manual are ways through the same setup.
related: [guided-and-manual-setup, installing-adept-ui, running-ai-models-locally]
---

## What this does

Adept Setup tells you what the studio can run and helps prepare components that are missing. The screen is titled Adept Setup. Its job is readiness, install of required pieces, and a way to see what is not ready.

## Why you would open it

Open Setup when a model is missing, a first launch is incomplete, or a local generator that used to run now reports that it is not available. Do not open a new project to fix a setup problem.

## How it is organized

Setup Mode has three experiences:

- **Guided** keeps the Prepare My Studio flow in front.
- **AI-Guided** recommends certified providers and walks through install, calibration, and certification.
- **Manual** keeps the full setup catalog, advanced actions, and Source Manager tools visible.

You can switch modes. They are views of setup, not three different products.

## What to expect

Suggested locations for components come from the studio. Type a path only when you know that folder is the one the studio asked for. This guide does not publish install paths.

## Technical notes

Health in Setup means the component check the studio performed. A green check is not a promise that a particular shot will succeed. Generation still depends on the model, the references, and the request.

## Repairing an incomplete setup

Use Setup's own prepare and verify actions for the component that failed. Installing the desktop app again does not replace a model that was never downloaded. If a repair action reports an error, keep that message. It is the diagnostic. Do not clear it and assume the component is fine.
