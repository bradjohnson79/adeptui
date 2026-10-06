# 18 — Remaining non-blocking items

**Date:** 2026-08-30

These do not, by themselves, reopen a closed A–H gate. Final peers may still treat any of them as blocking if they judge owner-testing readiness fails.

1. Full Vitest suite and full backend pytest tree were not run.
2. Playwright did not re-walk Character / Prop / Spatial / ERS / Scene handoff / Retake / Stop.
3. MiniMax Route A live generate was not re-run this closure (honest max ~0.21s; no 15s media).
4. `generator_authority` MiniMax 5.0s fallback if the adapter is unregistered.
5. `.runtime/verify-copy` MiniMax adapters still hardcode `duration=5.0`.
6. Beta watchdog can spawn Comfy without GPU admission when `ADEPT_COMFY_LAUNCH` is set.
7. Diagnostics still probe retired `:8760`. The process may still be listening (Law 14 — not killed).
8. Home Models badge can read Ready while Comfy is offline.
9. Library asset `ffd1e38a-…` still tagged `batch_bb_c1eb5-draft` / `approvalState=draft` after Timeline Approve.
10. Take-state draft dims (`512x288`) disagree with measured 1280×704 LTX media.
11. Dirty tree (~1500+ porcelain). No commit authorized.
12. Supervisor `restart` often reuses a healthy uvicorn and does not load new Python.
13. Collection-broken WIP tests left in place.
14. Residual `fal_*` tokens in Inpaint default mapping.
15. `scripts/Start-AdeptUI-H3-RouteA.ps1` can spawn Route A without GPU admission (`start_route_a` is not the operator path).
16. Tracked Playwright `library-refs-accordion.spec.ts` still fetches retired unscoped `/api/assets/{id}/file`.
17. Historical Audio Studio candidates may keep unscoped `audio_url` (fail-closed 403; new batches are scoped).
18. Unscoped `/api/assets/{id}/{library,meta,graph,…}` metadata routes (no bytes).
19. Watcher `registry.get` failure can return without a log (`watcher.py`).
20. PC Hunyuan resolve copy can disagree with the join label on the same surface.

No secrets in this directory.
