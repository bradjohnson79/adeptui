---
title: Troubleshooting Generation
summary: A stuck or failed generation needs a cause: model, connection, references, or session. This guide tells you what to check in the open project before you run anything else.
category: troubleshooting
slug: troubleshooting-generation
tags: [troubleshooting, generation, errors]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Troubleshooting Adept UI Generation
seoDescription: What to check when an Adept UI image or video generation fails, sticks, or returns the wrong model.
related: [generation-failed-or-stuck, retakes, using-hosted-models]
---

## What this does

Generation troubleshooting is a short list of real causes. The goal is a true status: finished, failed, or still running. Not a new project.

## Check in this order

1. **Is there a result in this project's library?** If the asset is there, the job finished. Placement on the Timeline is a separate step.
2. **Which model did you select?** Confirm the name. A missing local model will not be replaced by another engine.
3. **Is that model installed or connected?** Local models are checked in Adept Setup. Hosted models need the provider connection. Hosted video uses fal.ai.
4. **Did the request include a reference the model cannot take?** Remove or change the attachment and read the error. Do not keep stacking references.
5. **Is the job from an earlier session?** Opening the project does not resume it. If it was interrupted, start a new take only after you know you want one.
6. **What does the error actually say?** Keep the message. "It failed" is not enough to retake intelligently.

## GPU and memory

Local video expects a GPU path. If the machine cannot load the model, the job should block or fail. This guide does not publish a memory threshold. Closing unrelated GPU work is a machine decision. Killing processes by name is not a troubleshooting step.

## What not to do

- Do not start a second project to "clear" the failure
- Do not approve a result that names a different model than the one you selected
- Do not treat a spinner with no job as success
- Do not expect MAGI to repair a clip that never generated

## If Co-Director disagrees with the Timeline

Trust the Timeline and the library. Ask again after you have looked. Conversation is not a job status.
