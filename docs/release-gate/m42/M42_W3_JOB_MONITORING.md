# M42 Wave 3 — Job Monitoring

QueueWorker `_imagegen` emits `ImageJobStage` values on `job.stage`:

Queued → Preparing → LoadingModels → Sampling → Validating → RegisteringAsset → Completed  
(Failed / Cancelled terminal)

JobPanel renders the stage pipeline for image jobs.

Artifact: `artifacts/m42/w3/job_monitor_results.json`.
