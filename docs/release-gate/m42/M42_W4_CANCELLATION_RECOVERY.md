# M42 Wave 4 — Cancellation & Retry

Cancel/retry guarantees preserved on the QueueWorker execute-only path. Queued and validation-stage cancel covered; mid-sampling may be NOT_OBSERVABLE depending on Comfy observability. Retry reuses pinned contract; no duplicate successful registration.

Artifacts: cancellation_results.json, 
etry_results.json.
