# 09 — Gate I Performance and dead architecture

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

Measured after correctness gates. No new event bus.

## Pollers still present (not deleted)

| Surface | Interval | Notes |
|---|---|---|
| SystemStatusStrip | 15s | Comfy / runtime strip |
| useProductionDock | interval | Footer Dock |
| CoDirectorSession | 5s | session tick |
| Gpu / Voice / Magi / Job / Preview | 1.5–4s | job-scoped or workspace-scoped |

`requestCache` already TTL-caches `/api/health` and related reads. No soak-proven waste was removed this pass.

## Not deleted

- `SpatialSceneWorkspace` / `ImageGenPanel` / `UnifiedExperience` / `ApprovalCenterPanel` — still imported or historical; grep did not prove zero consumers.
- Live `:8760` process left running (Law 14). Product supervisor does not start it.
- Historical cert evidence and migrations kept.
- Scratch `studio-api/_tmp_*` not mass-deleted from the dirty tree.

## Retired start path

`scripts/beta_runtime` defaults to Vite `:5173` and refuses `:8760` unless `ADEPT_ALLOW_RETIRED_8760`.
