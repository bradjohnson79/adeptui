# Queue and Storage

## Paths

```
data/prompt_intelligence/
  suites/
  runs/{runId}.json
  reviews/{comparisonId}.json
  evidence/{providerId}/{modelRevision}/{domain}/{category}.json
  feedback/queue/
```

## Queue safety

- heavy_local concurrency 1 for video
- pause / resume suite
- cancel pending + cancel_and_halt active
- retention: keep_all | keep_winners | keep_reviewed | delete_failed
- preflight disk estimate before enqueue
