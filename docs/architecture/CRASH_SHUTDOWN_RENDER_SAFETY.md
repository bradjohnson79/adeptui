# Crash / Shutdown Render Safety

A render may consume GPU resources only when the creator explicitly started it in the current Studio API session, or reconciliation proves that same session is still genuinely active. A job left queued, running, sampling, generating, stitching, or waiting on the next window when the computer or the API session ends does not resume on the next session.

## Startup

Previous-session active jobs are marked interrupted. They are removed from active-job selection. The active take link is cleared. A completed asset that was already saved stays in the project. The job is still closed.

Startup does not submit a render, does not touch the GPU, and does not wake Comfy.

## Opening Timeline

Opening a project, opening Timeline, reading the master, polling the workspace, loading Preview, reloading the browser, and opening the Inspector are read-only with respect to an abandoned render. None of those actions start GPU work.

## Continuing

New Take or Re-Take is the explicit start. That creates a new job stamped with the current session. There is no automatic recovery render.

## Identity

The session id is created when the Studio API process starts. New jobs receive it. A stored id that does not match the running process is stale.
