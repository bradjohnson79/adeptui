# M3.0j Studio Project Library Report

**Status:** IN PROGRESS — implemented API/tests **PASS**; Playwright and REAL_LOCAL proof **PENDING**.

**Scope:** Virtual taxonomy, lazy entity folders, authority fields, migrate/repair, resolve paths, Co-Director integration hooks.

Does **not** claim M3.0j YES or full platform beta GREEN.

## Verdict summary

| Area | Verdict | Notes |
|------|---------|-------|
| Taxonomy + system keys | **PASS** | `studio-api/app/project_library/taxonomy.py`; `test_project_library_taxonomy.py` |
| Library init / migrate / repair | **PASS** | Idempotent migrate; repair endpoint; no empty folder seed rows |
| Tree + folder map API | **PASS** | `GET /api/projects/{id}/library`; `test_library_get_includes_tree_and_folder_map` |
| Path resolve | **PASS** | `POST …/library/resolve-path` |
| Asset override + entity folder | **PASS** | PATCH authority; canonical folder id over path |
| Classification | **PASS** | Music → Audio/Music; low-confidence clarification; USD unsupported |
| Duplicate detection | **PASS** | Content-hash dedupe in service tests |
| Co-Director resolve/preflight | **PASS** | Covered in `test_codirector_library_awareness.py` |
| Playwright UI proof | **PENDING** | No REAL_LOCAL browser cert in `artifacts/m30j/playwright/` yet |
| Cross-project isolation E2E | **PENDING** | LIBRARY-CD-17 |
| Full storage-rule matrix | **PENDING** | Character/scene/video/3D/scripts rows open in Co-Director report |

## Test inventory (automated)

### `studio-api/tests/test_project_library_taxonomy.py`

- `test_all_system_keys_unique_and_cover_taxonomy`
- `test_system_folder_ids_are_prefixed`
- `test_classify_music_to_audio_music`
- `test_classify_low_confidence_needs_clarification`
- `test_usd_extension_unsupported`
- `test_init_project_library_sets_schema_version`
- `test_lazy_entity_folder_path`
- `test_authority_fields_canonical_folder_id_over_path`
- `test_library_api_filter_by_system_key`
- `test_migrate_project_library_idempotent`
- `test_create_project_does_not_seed_empty_folder_rows`

### `studio-api/tests/test_project_library_api.py`

- `test_library_get_includes_tree_and_folder_map`
- `test_library_migrate_endpoint`
- `test_library_repair_endpoint`
- `test_library_resolve_path_endpoint`
- `test_patch_asset_library_override`
- `test_patch_asset_library_entity_folder`

### `studio-api/tests/test_project_library_service.py`

- `test_find_duplicates_by_content_hash`
- `test_usd_assign_is_not_applicable_not_failure`
- `test_override_blocks_auto_reclassify`

## API surface

- `GET /api/projects/{id}/library`
- `POST /api/projects/{id}/library/migrate`
- `POST /api/projects/{id}/library/repair`
- `POST /api/projects/{id}/library/resolve-path`
- `POST /api/projects/{id}/library/resolve`
- `GET /api/projects/{id}/library/codirector-context`
- `POST /api/projects/{id}/library/preflight`
- `PATCH /api/projects/{id}/assets/{asset_id}/library`

Implementation: `studio-api/app/project_library/`, routes in `studio-api/app/routers/extra.py`.

## Evidence (pending)

- Playwright: `tests/e2e/m30j/` (skeleton only)
- Artifacts: `artifacts/m30j/project-library/` (empty — Phase 0 layout only)

## Next steps

1. REAL_LOCAL Playwright runs for library panel + migrate/repair flows
2. Cross-project isolation proof (LIBRARY-CD-17)
3. Full entity storage-rule certification aligned with [`M30J_CODIRECTOR_LIBRARY_AWARENESS_REPORT.md`](M30J_CODIRECTOR_LIBRARY_AWARENESS_REPORT.md)
