---
title: Using Hosted Models
summary: Hosted image and video models run through a provider connection, including fal.ai for the hosted video set. Credentials stay in Setup. They are never written into a guide or a prompt.
category: api-models
slug: using-hosted-models
tags: [api, fal, hosted, privacy]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Using Hosted AI Models in Adept UI
seoDescription: Connect hosted generators in Adept Setup. fal.ai carries hosted video such as Seedance, Kling, Veo, and Runway. No keys belong in docs.
related: [local-vs-api-models, troubleshooting-generation, choosing-a-video-model]
---

## What this does

A hosted model generates on the provider's side. Adept UI sends the request and stores the result in your project. The connection is configured in Setup. This page does not contain keys, and it will not ask you to paste one into a document.

## How a hosted generation works

1. In Adept Setup, connect the provider you intend to use. Hosted video in the current product goes through fal.ai.
2. Choose that model on the shot. Hosted video models are Seedance 2.0, Seedance 2.5, Kling 2.5 Turbo Pro, Kling 3.0, Veo 3.1, Runway Gen-3 Turbo, Flux 3.0, Happy Horse 1.0, and Google Gemini Omni.
3. Generate. The studio submits the prompt and the references that model requires.
4. The clip or still returns to the open project's library, or the request fails with a visible error.

## Privacy

The provider receives the content of the request. That can include the prompt and reference images. Do not attach material you are not willing to send to that provider. Adept UI should not hide which model received the job.

## Costs and limits

This documentation does not publish prices, credit balances, or rate limits. Those belong to the provider account and change. A failed request is not billed by Adept UI in this guide, and this guide will not guess how the provider bills.

## If the request fails

A failed API call should remain a failure. Check the connection in Setup, the model name, and the error text. Do not switch to a local model and call it the same shot unless you choose that local model on purpose and accept that it is a different engine.

## What to expect

No hosted result appears without a request that the provider accepted. A spinner with no job is not success.
