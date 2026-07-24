# Essential Pack Downloads — Completion Report

**Date:** 2026-07-23  
**Scope:** Essential Photoreal / Anime / Cinematic packs — provisioning, download, verification, state, UI  
**Phase 1:** Not started

## Final confirmation

**No pack reports installed / Ready unless required files exist on disk and verification passes.**  
Installed size is filesystem truth only (never catalog estimates). Empty directories are never treated as successful installs. With no real download URLs configured, all three packs report **Download Unavailable** and Install is disabled.

```text
pytest (full studio-api): 46 passed — exit 0
pytest (pack + setup refactor): 37 passed — exit 0
npx tsc -b (studio-web): exit 0
npm run build (studio-web): exit 0
```

## 1. Root cause (each pack)

| Pack | Root cause |
|------|------------|
| `pack_essential_photoreal` | Catalog used `installer=path_link` + auto-bind mkdir; no download URL; Install only bound an empty folder |
| `pack_essential_anime` | Same |
| `pack_essential_cinematic` | Same |

Secondary contributors: catalog `installed_bytes` mirrored as UI “installed”; stale diagnostics; operation could appear successful after path mkdir.

## 2. Existing source configuration found

| Source | Location | Value |
|--------|----------|--------|
| Canonical setup catalog | `studio-api/app/setup/catalog.py` | Was `path_link` / `linked_files` (now `asset_pack`) — **no URL fields** |
| Pack manifests (new) | `studio-api/app/setup/packs/*.json` | `source.type=http`, **`url` omitted** |
| Legacy detect catalog | `studio-api/app/setup_wizard.py` | `source_repo: adept://marketplace/pack_essential_*` (pseudo URI) |
| Marketplace | `studio-api/app/marketplace.py` | `source_url: ""` |

## 3. Real downloadable source?

| Pack | Real HTTPS archive URL? |
|------|-------------------------|
| Photoreal | **No** |
| Anime | **No** |
| Cinematic | **No** |

Do **not** invent URLs. Cards ship as **Download Unavailable** until manifests gain valid `source.url` values (and accurate `requiredFiles` / checksums).

## 4. Download API changes

- Install for `asset_pack` runs staging pipeline in `studio-api/app/setup/pack_install.py` when a valid source exists.
- Missing source → operation finishes `failed` with `download_source_missing` (no directory creation).
- New routes:
  - `POST /api/setup/components/{id}/refresh-source`
  - `POST /api/setup/components/{id}/link-existing`
- Phases: `validating` → `downloading` → `verifying_download` → `extracting` → `verifying_install` → completed/failed.
- Success requires verified files in the final directory.

## 5. State reconciliation changes

- Canonical status `download_unavailable` for missing source (optional; does not block overall Ready).
- Status refresh reconciles stale Ready when required files disappear.
- `installed_bytes` for packs = recursive filesystem sum; unhealthy/empty → `0`.
- `pack_install_attempts` / `pack_installs` record honest attempt history.
- Auto-bind / mkdir for Essential packs **removed**.

## 6. Installed-size calculation changes

- `_reported_installed_bytes` never returns catalog estimates for asset packs.
- UI shows `Download size: … · Installed size: 0 B` for packs (split labels).

## 7. Staging and rollback

- Staging: `{data_dir}/downloads/{pack_id}/{operation_id}/`
- Download → verify → extract to `content/` → requiredFiles check → atomic promote to final path
- On failure: staging cleaned; final directory left unchanged / uncreated

## 8. UI state changes

- Download Unavailable + Refresh Download Source; Install disabled without source
- Link Existing Folder secondary action (non-empty + `pack.json` required)
- Deduplicated issue vs recommended next step
- Failure labels: Download Failed / Verification Failed where issue codes apply

## 9. Files changed (primary)

- `studio-api/app/setup/packs/*.json` (new manifests)
- `studio-api/app/setup/pack_manifests.py` (new)
- `studio-api/app/setup/pack_install.py` (new)
- `studio-api/app/setup/catalog.py`
- `studio-api/app/setup/paths.py`
- `studio-api/app/setup/diagnostics.py`
- `studio-api/app/setup/status.py`
- `studio-api/app/setup/orchestrator.py`
- `studio-api/app/setup/__init__.py`
- `studio-api/app/routers/extra.py`
- `studio-api/tests/test_pack_install.py` (new)
- `studio-api/tests/test_setup_refactor.py`
- `studio-web/src/setup/types.ts`
- `studio-web/src/setup/helpers.ts`
- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/api.ts`

## 10. Tests added / updated

Covered via `test_pack_install.py` + updated refactor tests:

- Empty/missing URL → no install, no dir create, `download_source_missing`
- Refresh source does not create folders
- Empty destination → 0 installed bytes, not Ready
- Successful mocked zip → Ready with filesystem size
- HTTP 403 / 404 / zero-byte / HTML-as-archive / checksum / missing required files
- Failed staging leaves final dir unchanged
- Stale Ready downgraded after file removal
- Link existing populated path → Ready
- Invalid `adept://` URL rejected

## 11. Browser verification

Automated API/status behavior covered by tests. A live probe against a still-running pre-change API process still showed legacy pack fields — **restart the API** (`npm run dev:restart`) then hard-refresh Setup. After reload, all three packs should show **Download Unavailable**, Installed size **0 B**, Install disabled / Refresh Download Source, and no empty `creative_assets` dirs created merely by opening Setup.

## 12. Remaining source / API configuration required

To enable real Install for each pack, set in the corresponding JSON under `studio-api/app/setup/packs/`:

1. `source.url` — HTTPS archive URL (or later a provider resolver)
2. `archive.format` / `checksum` / `checksumAlgorithm` when available
3. Accurate `install.requiredFiles` matching archive contents
4. Optional: signed-URL refresh provider (persist id/version/`retrieved_at` only; fetch fresh URL at install time)

Until then, users may **Link Existing Folder** to a directory that already contains `pack.json` (and future required files).

## 13. Non-goals respected

- No fake archives or placeholder files to force Ready
- No invented production download URLs
- No unrelated Phase 1 work
