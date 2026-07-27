# M3.0d Backend Failure Closure

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting tip (M3.0d) | `aff00c131a464ee9cdf156fd8a2977016264b375` |
| Original failure list | `artifacts/functional-audit/m30b-pytest.txt` (20 failed) |
| M3.0c group closure | 20/20 passed (see `docs/m3.0c/BACKEND_FAILURE_CLOSURE.md`) |
| M3.0d full-suite gate | **631 passed, 6 skipped, 0 failed** |
| Gate command | `cd studio-api && python -m pytest -q` |
| Gate artifact | `.tmp-m30d-pytest.txt` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Summary

| Result | Count |
|--------|------:|
| Original PY01–PY20 (M3.0c) | 20 closed |
| Additional fixes before M3.0d gate | 2 (github env validation, queue priority isolation) |
| M3.0d focused regressions added | 7 tests in `test_m30d_closures.py` |
| **Remaining failed** | **0** |

## Full-suite evidence

```text
631 passed, 6 skipped, 5 warnings in 87.05s (0:01:27)
EXIT:0
```

Six skips are expected and documented (live provider gates, fixture-only paths). They are not gate failures.

## PY01–PY20 disposition (carried forward from M3.0c)

All twenty original failures are **Closed**. Dispositions unchanged from `docs/m3.0c/BACKEND_FAILURE_CLOSURE.md`:

| ID | Test | Classification | Status |
|----|------|----------------|--------|
| PY01 | `test_unproven_baselines_explain_themselves` | Already green | **Closed** |
| PY02 | `test_capability_matrix_doc_lists_every_capability` | Already green | **Closed** |
| PY03 | `test_absent_features_are_reported_as_not_implemented` | Already green | **Closed** |
| PY04 | `test_migration_clean_install_has_m006_m007` | Already green | **Closed** |
| PY05 | `test_prompt_library_loads_all_markdown_prompts` | Product fix (KNOWN_CONTEXT_KEYS) | **Closed** |
| PY06 | `test_specialist_selector_bounded_and_mappings` | Already green | **Closed** |
| PY07 | `test_evaluation_fixtures_present` | Cascading from PY05 | **Closed** |
| PY08 | `test_capability_project_not_configured_without_project_id` | Already green | **Closed** |
| PY09 | `test_capability_bible_not_configured_before_bible_exists` | Already green | **Closed** |
| PY10 | `test_dag_order` | Test update (B8 DAG) | **Closed** |
| PY11 | `test_default_registry_migrations_are_idempotent` | Already green | **Closed** |
| PY12 | `test_empty_download_url_prevents_installation` | Product + test | **Closed** |
| PY13 | `test_missing_provider_configuration` | Test update | **Closed** |
| PY14 | `test_public_release_lookup_and_install` | Already green | **Closed** |
| PY15 | `test_github_rate_limit_separate_code` | Already green | **Closed** |
| PY16 | `test_sqlite_initialization_is_isolated` | Already green | **Closed** |
| PY17 | `test_queue_order_by_priority` | Already green (M3.0c); isolation fix in M3.0d | **Closed** |
| PY18 | `test_atomic_state_preserves_legacy_fields` | Already green | **Closed** |
| PY19 | `test_status_does_not_auto_bind_asset_packs` | Test update | **Closed** |
| PY20 | `test_missing_source_install_fails_without_creating_directory` | Product fix | **Closed** |

## M3.0d additive regressions

`studio-api/tests/test_m30d_closures.py` adds focused coverage for items closed in this pass:

| Test | Register item |
|------|---------------|
| `test_b9_normalize_rejects_contradictory_success` | B9 |
| `test_b9_pending_approval_is_not_success` | B9 |
| `test_b13_sync_event_resolves_bar_timing` | B13 |
| `test_b13_place_cue_persists_sync_event` | B13 |
| `test_b19_override_requires_reason` | B19 |
| `test_b19_override_with_reason_records` | B19 |
| `test_director_to_editor_preserves_scene_and_order` | Director→Editor |

## Files touched (M3.0c + M3.0d cumulative)

- `studio-api/app/codirector/prompts/validator.py`
- `studio-api/app/setup/orchestrator.py`
- `studio-api/app/codirector/m211/honesty.py`
- `studio-api/app/codirector/m29/audio/service.py`
- `studio-api/app/codirector/vision/approval.py`
- `studio-api/app/routers/e2e.py`
- `studio-api/tests/test_m211_production_intelligence.py`
- `studio-api/tests/test_pack_install.py`
- `studio-api/tests/test_pack_providers_github.py`
- `studio-api/tests/test_setup_refactor.py`
- `studio-api/tests/test_m30d_closures.py`

## Gate verdict

**Backend final gate: PASS** — 631/0/6 satisfies the M3.0d entry requirement measured before documentation stamp.
