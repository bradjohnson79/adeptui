# M3.0c Backend Failure Closure

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Original list | `artifacts/functional-audit/m30b-pytest.txt` (20 failed) |
| Verification | 20/20 passed as a group (2026-07-27) |

## Summary

| Result | Count |
|--------|------:|
| Product fix | 3 |
| Test expectation update (product intentionally evolved) | 5 |
| Already green / prior fix retained | 12 |
| Remaining failed | **0** |

## Per-failure disposition

| ID | Test | Classification | Resolution |
|----|------|----------------|------------|
| PY01 | `test_unproven_baselines_explain_themselves` | Already green | Capability docs/matrix aligned before this pass |
| PY02 | `test_capability_matrix_doc_lists_every_capability` | Already green | Same |
| PY03 | `test_absent_features_are_reported_as_not_implemented` | Already green | Same |
| PY04 | `test_migration_clean_install_has_m006_m007` | Already green | Migration registry OK |
| PY05 | `test_prompt_library_loads_all_markdown_prompts` | Product fix | Added `tone`, `music`, `dialogue` to `KNOWN_CONTEXT_KEYS` in `prompts/validator.py` for M2.14 specialists |
| PY06 | `test_specialist_selector_bounded_and_mappings` | Already green | — |
| PY07 | `test_evaluation_fixtures_present` | Cascading | Unblocked by PY05 prompt key fix |
| PY08 | `test_capability_project_not_configured_without_project_id` | Already green | — |
| PY09 | `test_capability_bible_not_configured_before_bible_exists` | Already green | — |
| PY10 | `test_dag_order` | Test update | `DEFAULT_PIPELINE` now includes storyteller, sound-producer, VPC (B8); expectations updated |
| PY11 | `test_default_registry_migrations_are_idempotent` | Already green | — |
| PY12 | `test_empty_download_url_prevents_installation` | Test + product | Primary action is `add_source_url`; orchestrator fails closed for missing source |
| PY13 | `test_missing_provider_configuration` | Test update | Accept `source_pending` or `download_unavailable` |
| PY14 | `test_public_release_lookup_and_install` | Already green after pack fixes | — |
| PY15 | `test_github_rate_limit_separate_code` | Already green | — |
| PY16 | `test_sqlite_initialization_is_isolated` | Already green | Order-dependent previously; passes in group |
| PY17 | `test_queue_order_by_priority` | Already green | Same |
| PY18 | `test_atomic_state_preserves_legacy_fields` | Already green | — |
| PY19 | `test_status_does_not_auto_bind_asset_packs` | Test update | Allow `source_not_published` issue code |
| PY20 | `test_missing_source_install_fails_without_creating_directory` | Product fix | `execute_recommended_action` fails closed for `add_source_url`/`refresh_source` when source invalid — no queued install, no directory created |

## Files touched for closure

- `studio-api/app/codirector/prompts/validator.py`
- `studio-api/app/setup/orchestrator.py`
- `studio-api/tests/test_m211_production_intelligence.py`
- `studio-api/tests/test_pack_install.py`
- `studio-api/tests/test_pack_providers_github.py`
- `studio-api/tests/test_setup_refactor.py`

## Command evidence (original 20)

```text
20 passed, 5 warnings in 4.53s
```

## Full-suite follow-up (after original 20 closed)

Full `pytest -q` then reported **2 failed / 622 passed / 6 skipped**. Dispositions:

| Test | Resolution |
|------|------------|
| `test_global_github_env_does_not_validate_unpublished_pack` | Product fix: unpublished packs no longer validate from global GitHub env alone (`pack_manifests.has_valid_source`) |
| `test_queue_order_by_priority` | Test isolation: clear `ProductionJob*` tables in executive `db` fixture before each test |

Target for final gate: **0 failed** on full suite re-run after these fixes.
