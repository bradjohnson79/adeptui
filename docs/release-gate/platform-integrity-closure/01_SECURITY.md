# 01 — Gate A Security (asset / project isolation)

**Surface:** BOTH (route existed on released and current). Repair is CURRENT DEVELOPMENT.  
**Date:** 2026-08-29

## Defect

`GET /api/assets/{id}/file` and `/thumb` served any asset UUID with no project match and no `resolve_data_file_path`. Lock middleware only gated password-protected projects.

## Repair

Canonical routes (owner decision: project-path):

- `GET /api/projects/{projectId}/assets/{assetId}/file`
- `GET /api/projects/{projectId}/assets/{assetId}/thumb`

Authority: [studio-api/app/project_security/asset_file.py](../../../studio-api/app/project_security/asset_file.py)

Chain: request → project exists → asset exists → `asset.project_id` match → `resolve_data_file_path` → reject traversal / ambiguous scope / path-project mismatch → FileResponse.

Retired unscoped routes return **403** `ASSET_SCOPE_REQUIRED`.

First-party URL builders updated (backend emitters + `api.assetUrl` + `characterMediaUrl`). `bindAssetUrlProject` on Project Editor / Co-Director so existing `api.assetUrl(id)` call sites emit the scoped path.

## Tests

`cd studio-api; python -m pytest tests/test_project_lock_media.py -q`

**20 passed** including:

| Case | Result |
|---|---|
| correct project + asset | 200 |
| wrong project + asset | 403 ASSET_PROJECT_MISMATCH |
| unknown asset | 404 |
| malformed ids | 400 |
| traversal `../` path | 403 FILE_API_RESTRICTED |
| valid thumb | 200 |
| unscoped file/thumb | 403 ASSET_SCOPE_REQUIRED |
| locked project scoped file | 403 then 200 with unlock |

Frontend: `characterMediaUrl.test.ts` **3 passed**.

## Peer close

- Kimi K3 (`bfc64016`): **PASS WITH NON-BLOCKING** — no BLOCKING. Defect closed; unscoped file/thumb 403. Non-blocking: stale Playwright unscoped assertions, WIP CharacterV2 presence test, unused `hydrate_multiview` TypeError. **ACCEPTED NON-BLOCKING** (WIP / test debt, not byte-serving).
- GLM 5.2 (`5980f759`): **PASS WITH NON-BLOCKING** — 20 pytest verified. Same class of leftovers. **ACCEPTED NON-BLOCKING**.

**Gate A: CLOSED**

## Classification

| Finding | Surface | After repair |
|---|---|---|
| Unscoped asset file/thumb | BOTH | HISTORICAL (403) + CURRENT canonical scoped |
