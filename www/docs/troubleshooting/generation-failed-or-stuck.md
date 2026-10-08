---
title: Generation Failed or Stuck
summary: A failed generation stops with an error. A stuck one never reaches the library. Neither state is fixed by reloading the project in the hope that an old job resumes.
category: troubleshooting
slug: generation-failed-or-stuck
tags: [troubleshooting, stuck, failed]
difficulty: practice
updated: 2026-10-06
status: published
seoTitle: Adept UI Generation Failed or Stuck
seoDescription: Tell a failed Adept UI generation from a stuck one, and start a new take only in the current session after you know why.
related: [troubleshooting-generation, local-services, retakes]
---

## What this does

Two different problems get called "stuck." One is a job that failed. The other is a job that is still running, or a job that died with the last session and will not come back.

## How to tell them apart

- **Failed.** The shot shows an error, or the library has no asset and the status is no longer running. Read the message. Fix the model, the connection, or the references. Then retake if you still want the shot.
- **Running.** The studio still reports the job in this session. Wait. A long local video is not the same thing as a hang. Do not start a second copy of the same shot on top of it.
- **Abandoned.** The studio was closed, or the session changed, before the job finished. That render is not resumed when you reopen Timeline. A finished asset, if one was written, remains. Otherwise the shot needs a new take.

## What to expect after a retake

The new take is a new job. It uses the model you select now. It does not inherit a promise from the failed attempt.

## Technical notes

Active renders are tied to the studio session that started them. Health checks and merely opening the Timeline are read-only for abandoned work. That is why reload feels like "nothing happened." Nothing was supposed to restart.

## Collecting what you need

Keep the model name, the room you generated from, the error text, and whether a file landed in the library. Those four facts identify the failure. A screenshot of a spinner without the model name does not.
