# M3.0j Co-Director Project Library Awareness Report

**Status:** IN PROGRESS — partial implementation; **not** full M3.0j YES.

**Scope:** Co-Director first-class awareness of Studio Project Library (virtual taxonomy + lazy entity folders).

## Matrix (LIBRARY-CD-01..22)

| Row | Requirement | Status | Evidence |
|-----|-------------|--------|----------|
| LIBRARY-CD-01 | Co-Director folder map awareness | PASS | `get_library_folder_map` tool; `GET …/library/codirector-context`; `test_library_codirector_context_endpoint` |
| LIBRARY-CD-02 | Character storage rules | PENDING | |
| LIBRARY-CD-03 | Prop storage rules | PASS | `storage_preflight` + entity lazy create; `test_library_entity_folder_lazy_create` |
| LIBRARY-CD-04 | Scene storage rules | PENDING | |
| LIBRARY-CD-05 | Video storage rules | PENDING | |
| LIBRARY-CD-06 | Audio storage rules | PASS | `test_library_resolve_audio_music`, NL resolve test |
| LIBRARY-CD-07 | 3D storage rules | PENDING | |
| LIBRARY-CD-08 | Scripts / Exports storage rules | PENDING | |
| LIBRARY-CD-09 | Indexed asset retrieval | PASS | `search_library_assets` tool + enhanced `searchLibrary` execute path |
| LIBRARY-CD-10 | Retrieval prioritizes approved/canonical | PENDING | sort key implemented; no dedicated test |
| LIBRARY-CD-11 | Entity-scoped retrieval (prop/character/scene) | PENDING | NL parser stub; partial via `search_library_assets` |
| LIBRARY-CD-12 | Ambiguity reporting (no silent guess) | PASS | `test_library_resolve_ambiguous_audio`; resolve + search return `ambiguous` + `candidates` |
| LIBRARY-CD-13 | Rename/move ID-stable references | PENDING | |
| LIBRARY-CD-14 | Frozen/canonical overwrite protection | PENDING | |
| LIBRARY-CD-15 | Single library init per project | PENDING | covered by project_library migrate tests |
| LIBRARY-CD-16 | Production Bible entity folder linking | PASS | `link_bible_entity_folder` tool; `test_codirector_tool_link_bible_entity_folder` |
| LIBRARY-CD-17 | Cross-project library isolation | PENDING | |
| LIBRARY-CD-18 | No silent misfile to Miscellaneous | PENDING | |
| LIBRARY-CD-19 | Storage preflight before generation | PASS | `plan_library_storage` tool; `POST …/library/preflight` |
| LIBRARY-CD-20 | Post-generation storage location report | PENDING | |
| LIBRARY-CD-21 | Manual classification override persists | PASS | `test_manual_override_not_reverted_by_auto_assign`; existing `test_patch_asset_library_override` |
| LIBRARY-CD-22 | Co-Director does not silently revert override | PASS | `assign_asset` respects `override` flag; test above |

## API / Tool Surface

- `POST /api/projects/{id}/library/resolve` — path/NL/systemKey resolution with ambiguity
- `GET /api/projects/{id}/library/codirector-context` — session folder map + recent assets
- `POST /api/projects/{id}/library/preflight` — storage preflight
- Co-Director tools: `get_library_folder_map`, `get_library_context_summary`, `resolve_library_location`, `search_library_assets`, `plan_library_storage`, `link_bible_entity_folder`, `propose_asset_library_assignment`
- Web execute actions: `searchLibrary` (enhanced), `resolveLibraryLocation`, `planLibraryStorage`

## Tests

- `studio-api/tests/test_codirector_library_awareness.py`
- `studio-api/tests/test_project_library_api.py` (existing)
- `tests/e2e/m30j/codirector-library-awareness.spec.ts` (skeleton)

## Notes

- Does **not** claim M3.0j beta YES or full LIBRARY-CD GREEN.
- Remaining rows require Playwright proof, cross-project isolation, versioning E2E, and full storage-rule matrix certification.
