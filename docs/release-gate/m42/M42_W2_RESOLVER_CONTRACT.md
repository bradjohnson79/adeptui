# M42 Wave 2 — Resolver Contract

## Production mode

- `allow_draft=False` by default on `/api/image-runtime/resolve`
- QueueWorker resolves or revalidates pinned `imageRuntime` snapshots
- Pinned fields: `workflowKey`, `workflowVersion`, `certificationRecordId`, `fingerprint`, `modelFamily`, `resolvedAt`
- Silent version switches while a job is queued/running are forbidden

## Multi-family routing

`ImageIntent` → Unified Workflow Resolver → `zimage.* | flux.* | qwen.* | imagen.*` → `CanonicalImageWorkflowContract`

Contract extensions: `modelFamily`, `modelVariant`, `capabilities.*` (references, editing, ControlNet, LoRA, inpaint/outpaint/fill, identity, batch).
