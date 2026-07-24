# Component Source Registry Fix Report

**Date:** 2026-07-24  
**Branch:** `phase1b/download-queue-install-receipts` (working tree)  
**Verdict:** Fixed false “Download Unavailable” for unpublished Essential Packs; fal.ai credential card corrected

---

## Root cause

Essential Pack manifests used `source.providerId: github_releases` with **no per-pack owner/repository/asset**. Status/diagnostics treated missing `ADEPT_PACK_GITHUB_OWNER` / `ADEPT_PACK_GITHUB_REPOSITORY` as a configuration failure and instructed users to set a **universal** GitHub repo for all packs. That cannot identify distinct release assets, destinations, or verification rules per component.

**Official pack archives:** None are published in this repository. Packs are correctly marked `distributionStatus: "not_published"`.

---

## What changed

### Per-component manifests (`schemaVersion: 2`)

Updated:

- `studio-api/app/setup/packs/pack_essential_photoreal.json`
- `studio-api/app/setup/packs/pack_essential_anime.json`
- `studio-api/app/setup/packs/pack_essential_cinematic.json`

Each includes:

- `kind: downloadable_pack`
- `distributionStatus: not_published`
- empty `sources: []` (no invented URLs)
- verification + specification stubs (`pack.json`, optional directories)
- legacy `source.providerId` retained for fixture_http / future published wiring

### Source validity

`AssetPackManifest.has_valid_source()` no longer treats global GitHub env as valid for unpublished packs. Valid when:

1. Explicit / override URL  
2. Explicit `sources[]` entries  
3. `fixture_http` + `ADEPT_PACK_FIXTURE_BASE_URL` (E2E)  
4. Legacy global GitHub env **only if** `distributionStatus` is published  

### Source states

New / clarified issue codes and UI statuses:

| State | Meaning |
|-------|---------|
| `source_pending` | Official distribution not published |
| `source_not_published` | Issue code for unpublished packs |
| `source_not_configured` | Published/catalog component without assigned source |

Removed ADEPT_PACK_GITHUB_* copy from Setup Wizard diagnostics for these cases.

### Credential card (fal.ai)

- `component_kind: credential`
- Primary action: **Configure API Key** (never Download and Install)
- `show_download_sizes: false`
- Labels: Not Configured / Configured / Verification Failed

### Component kinds helper

`studio-api/app/setup/component_kinds.py` — kind + action mapping.

---

## Files changed (primary)

- `studio-api/app/setup/pack_manifests.py`
- `studio-api/app/setup/packs/pack_essential_*.json`
- `studio-api/app/setup/diagnostics.py`
- `studio-api/app/setup/status.py`
- `studio-api/app/setup/orchestrator.py`
- `studio-api/app/setup/component_kinds.py`
- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/setup/helpers.ts`
- `studio-web/src/setup/types.ts`
- `studio-web/src/styles.css`
- `studio-api/tests/test_component_source_registry.py`
- `tests/e2e/setup/component-source-states.spec.ts`

---

## Remaining unpublished packs

All three Essential Packs remain **Source Pending** until real GitHub Release or Hugging Face archives exist. Then:

1. Set `distributionStatus` to `published`  
2. Populate per-pack `sources[]` with exact owner/repo/revision/asset or HF paths  
3. Verify metadata-only, then enable Download and Install  

Commands to publish are not automated here; do not invent repositories.

---

## Test results

| Suite | Result |
|-------|--------|
| `test_component_source_registry.py` + `test_download_sources.py` | **26 passed** |
| Playwright `@critical` (clean-room) | **21 passed / 0 failed** |

```bash
cd studio-api
.\.venv\Scripts\python.exe -m pytest tests\test_component_source_registry.py tests\test_download_sources.py -q
# from repo root, with e2e stack:
npx playwright test --grep "@critical" --retries=0
```
