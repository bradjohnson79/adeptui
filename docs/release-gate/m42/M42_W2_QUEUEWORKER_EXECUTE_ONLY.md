# M42 Wave 2 — QueueWorker Execute-Only

`QueueWorker._imagegen` no longer imports image builders.

Flow:

1. Normalize legacy params → `ImageIntent` (sunset adapter) or accept caller intent
2. Use pinned `imageRuntime` or resolve once and pin
3. `workflow_execute.build_leaf_graph` + fingerprint drift check
4. Comfy execute via legacy registry key mapping for `ensure_queueable`
5. Atomic Output Gate → asset + provenance → `done`
6. Registration failure → `output_valid_but_unregistered` (retry reuses validated file)

Sole production builder import site: `studio-api/app/image_runtime/workflow_execute.py`.
