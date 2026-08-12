# M42 Wave 3 — Architecture

Product surfaces never build Comfy graphs. Ownership:

```text
ProductSurface → CreativeContext → recommend/prompt_intel → ImageIntent
  → WorkflowResolver (allow_draft=False) → pinned imageRuntime
  → QueueWorker execute-only → Output Gate → Asset Library + ImageProvenance
```

Package: `studio-api/app/image_product/` (compile, recommend, presets, prompt_intel, references, collections, history, service, api, production_gate).

Wave 2 runtime (resolver, certification ledger, workflow_execute, Output Gate) is preserved unchanged in responsibility.
