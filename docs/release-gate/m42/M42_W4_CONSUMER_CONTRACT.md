# M42 Wave 4 — Consumer Contract

| Surface | Class |
|---|---|
| ImageEditWorkspace | enqueue-only |
| propose_image_edit | enqueue-only |
| QueueWorker._imagegen | execution |
| LibraryPanel | display-only |

No product builder imports; no direct queue_prompt from UI. Legacy specialized edit callers migrated via ImageEditIntent. Unresolved bypass list empty.

Artifacts: consumer_contract_results.json, legacy_edit_callers.json, legacy_edit_callers_migrated.json.
