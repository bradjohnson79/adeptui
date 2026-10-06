# WAVE 5 assist — Timeline Generation (dead-helper cleanup + generate-path prove)

**Status:** WAVE 5 ASSIST DONE  
**Time (PT):** 2026-09-18 ~1:05 PM PT  
**Machine:** BRAD-5090  
**Owner:** Timeline Generation + Comfy Pipeline Bot

## (1) Dead helpers deleted

From `director_timeline_w46/generation/request_builder.py` (0 callers after WAVE 2):

- `_scene_level_timed_prompt`
- `_adapt_scene_prompt_for_extension`
- `_is_extension_batch` (only served deleted inherit path)
- `_extension_window` (same)

**Kept:** `_scope_root_batch_prompt`, `_frames_full_scene`, `_batch_windows_for_prompt` — WINDOW SCOPE for own-segment root batches that still wrongly frame full scene (not inheritance).

Empty batch still raises `BATCH_PROMPT_REQUIRED` (WAVE 2 refuse). **Empty-batch inherit NOT restored.**

Backup: `request_builder.py.wave5bak`

## (2) Generate-path prove (for Systems)

| Check | Result |
|---|---|
| `orchestrator.py` `reconcile_legacy_to_master` | **0** |
| `generation/*` active scene-level inherit / `_scene_level_timed_prompt(` | **0** |
| Remaining `reconcile_legacy_to_master` call sites | def in `reconcile.py` + `routers/api.py` `put_director` only |

## (3) put_director / Master-native proposal

`put_director` still runs windowed `reconcile_legacy_to_master` so FE Timed Prompt lane edits reach master. That is **FE sync**, not generate authority.

**Proposal (Role 2 lane / Timeline UX):**
1. FE reads/writes Timed Prompt via **batch.promptSegments** on master (`PATCH` batch / `touch_batch_config`) — Master-native.
2. After FE ships that, **delete** `put_director` reconcile call.
3. Until then: leave labeled FE sync; generate path stays batch-only.

Out of Role 2 alone to drop `put_director` reconcile without UX — **flag Timeline UX**.

## Dialogue import

`request_builder.py` now imports `app.codirector.dialogue_authority` directly (shim still OK elsewhere).

## Tests

`tests/test_timeline_architecture_guard.py` — **15 passed** (pins updated: helpers must stay deleted; WINDOW SCOPE helpers kept).

## Scene 12 / Comfy

HOLD / observe-only.
