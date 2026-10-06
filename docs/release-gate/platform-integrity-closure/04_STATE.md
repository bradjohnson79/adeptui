# 04 — Gate D State and persistence

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-29

## Timeline

`timelineMaster` inside `scenes.director_json` remains the write authority (`store.save_master`). PUT `/director` still merges without wiping embedded master.

**Approval:** watcher now passes `auto_approve=False`. Generate → CandidateReady → Approve. Draft no longer auto-approves. Tests in `test_timeline_auto_approve_gate.py` expect this.

**Legacy projection:** orchestrator no longer swallows prompt projection / reconcile / adapter-cancel failures. They log with `exc_info`. Master remains authority if projection fails.

## Spatial

`spatial_map_documents` is the scene write authority. `project.spatial_map_json` is a projection written from `save_spatial_doc`. Projection failure is logged and raised — not swallowed. Project-level PUT `/spatial` remains the project SpatialMap (tags/points) and does not overwrite scene documents.

## Jobs

Install, render, and H3 job families stay separate. No mega-job abstraction.

## Tests

`pytest tests/test_timeline_auto_approve_gate.py tests/test_spatial_document_authority.py -q`

## Peer close

- Kimi K3 (`898c6442`): **PASS WITH NON-BLOCKING** — `timelineMaster` remains write authority; `auto_approve=False`; PUT `/director` merges; spatial write is `spatial_scenes` with `project.spatial_map_json` as projection. Non-blocking: leftover silent `except` lanes outside the repaired critical writes. **ACCEPTED NON-BLOCKING**.
- GLM 5.2 (`7650bdce`): **PASS WITH NON-BLOCKING** — same four core claims verified; job families stay separate. **ACCEPTED NON-BLOCKING**.

**Gate D: CLOSED**
