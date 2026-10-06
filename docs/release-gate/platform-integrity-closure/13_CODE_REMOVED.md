# 13 — Code removed / not removed (Gate I / P)

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

## Removed or retired in this mission

- Unscoped `/api/assets/{id}/file` and `/thumb` no longer serve bytes — **403** `ASSET_SCOPE_REQUIRED`.
- Timeline `list_generators()` is no longer a second catalog (join view).
- Inspector / Job / Txt2Vid fossil engine lists replaced by `EngineAuthoritySelect` (earlier Gate B).
- Watcher `auto_approve=not draft` removed; product path is `auto_approve=False`.
- Public MiniMax preflight “need 4–15s” copy removed.
- Timed Prompt X no longer writes only legacy `prompt_segments` — shell mutate + master `promptSegments` patch.

## Not deleted (grep did not prove zero consumers, or Law 14)

- `SpatialSceneWorkspace` / `ImageGenPanel` / `UnifiedExperience` / `ApprovalCenterPanel`
- Live `:8760` process (not killed). Product start refuses it.
- Pollers (SystemStatus 15s, Dock, Co-Director 5s, GPU 1.5–4s). No new event bus.
- `studio-api/_tmp_*` scratch on the dirty tree
- Historical cert evidence and migrations
- `dropPromptIdsFromMaster` helper is now called (was previously unused)

## Hygiene scan (touched production files)

| Location | Leftover | Disposition |
|---|---|---|
| `generator_authority.py` MiniMax `max_dur = 5.0` if adapter missing | stale fallback | ACCEPTED NON-BLOCKING — live join uses adapter 5/24 |
| `.runtime/verify-copy` MiniMax adapters `duration=5.0` | sandbox | ACCEPTED NON-BLOCKING |
| Orchestrator leftover `except` lanes | not all swallowed writes | ACCEPTED NON-BLOCKING — critical projection/cancel now log |
| `test_ltx_i2v_lora_failures.py` collection broken | WIP | not weakened; new `test_ltx_leaf_graph_lora_kwargs.py` |
| Home Models badge vs Comfy offline | creator copy | ACCEPTED NON-BLOCKING |
| Beta watchdog `ensure_comfy` without GPU admission | retired start path | ACCEPTED NON-BLOCKING |
