# WAVE 2 — Dual-authority purge (Timeline Generation)

**Status:** WAVE 2 DONE  
**Time (PT):** 2026-09-18 ~12:50 PM PT  
**Machine:** BRAD-5090  
**Owner:** Timeline Generation + Comfy Pipeline Bot  
**Chief:** PHASE 2 CLEAR accepted; Systems WAVE 1 DONE noted

## Files changed

| File | Change |
|---|---|
| `director_timeline_w46/orchestrator.py` | Removed `reconcile_legacy_to_master` from `submit_batch_generation`, `generate_scene`, `touch_batch_config` |
| `director_timeline_w46/generation/request_builder.py` | Empty batch → `ValueError(BATCH_PROMPT_REQUIRED)`; removed scene-level inherit + extension adapt on empty path |
| `codirector/production/timeline_builder.py` | Documented `scene.prompt=compiled_prompt` as NON-GENERATION metadata; batch.promptSegments sole generate authority |
| `routers/api.py` | `put_director` reconcile retained as FE lane→master creator sync only; labeled NOT generate authority |
| `director_timeline_w46/generation/completion.py` | Hardened modern clip metadata with `assetId` alongside `sourceBatchId` / `sceneTakeId` |

Backups: `*.py.wave2bak` beside each edited file.

## Before / after authority map

| Concern | BEFORE | AFTER |
|---|---|---|
| Generate prompt source | batch.promptSegments OR legacy scene Timed Prompt via reconcile + `_scene_level_timed_prompt` | **batch.promptSegments only**; empty → refuse |
| On `submit_batch_generation` / `generate_scene` | reconciled legacy→master before build | **no reconcile** |
| On `touch_batch_config` | re-pulled legacy lane into master | **no reconcile**; master→legacy projection only |
| `scene.prompt` | dual authority risk | display/Library metadata only |
| `put_director` | legacy→master (FE edits) | **same FE sync**, explicitly not generate path |
| Video track place | media_type + sourceBatchId + sceneTakeId + asset_id field | + metadata.`assetId` |

## Remaining reconcile_legacy_to_master call sites

- `reconcile.py` def only
- `routers/api.py` `put_director` — FE Timed Prompt → master (creator edits), windowed; not generate

## Tests

`tests/test_timeline_architecture_guard.py` — **15 passed**

## Not done this wave (owned later / cert)

- Live 30s/45s H3 multi-batch cert (needs Chief/Brad GO; Scene 12 HOLD)
- Deleting `_scene_level_timed_prompt` / `_adapt_scene_prompt_for_extension` function bodies (now unused on generate empty path; still referenced in comments/weave helpers)
- Removing `put_director` reconcile entirely (needs Timeline UX master-native Timed Prompt writes)

## Comfy

Observe-only — not touched.

## Scene 12

HOLD
