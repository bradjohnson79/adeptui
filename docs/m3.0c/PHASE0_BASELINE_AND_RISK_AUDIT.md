# M3.0c Phase 0 — Baseline and Risk Audit

| Field | Value |
|-------|-------|
| Milestone | M3.0c Full-System Green Gate |
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting tip SHA | `958edbe963fba69828acd5fecba05cb87411b115` |
| Implementation SHA (prior) | `87e1d47` |
| Documentation SHA (prior) | `d7d7257` |
| Remote | `origin/phase2/codirector-m2-9-production-suite` — **ahead by 5** (not pushed) |
| Provider Manifest sha256 | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` (**LOCKED — no change**) |
| Gate entering M3.0c | M3.0a ACCEPTED; M3.0b NOT READY; Manual User Beta CLOSED |

## Locked Product decisions (M3.0c)

- Keep Provider Manifest unchanged; do **not** add fal image endpoints.
- Stills: local ComfyUI Z-Image. Motion: fal.ai via unified Studio queue.
- Audio: import + edit path; generative audio labeled unavailable.
- fal spend hard cap ≈ **$15**; lowest-cost/shortest duration; no duplicate paid jobs for padding.
- Dirty starting tree is a **formal Phase 0 blocker** (this document).

## Commit list (local tip, not pushed)

| SHA | Summary |
|-----|---------|
| `958edbe` | docs(m3.0): complete the commit table in the M3.0 completion task report |
| `c9f45d9` | docs(m3.0): normalise stray CR CR LF line endings in three completion docs |
| `4879eef` | docs(m3.0): stamp implementation and documentation SHAs in the completion reports |
| `d7d7257` | docs(m3.0): record the completion evidence and the two honest gate verdicts |
| `87e1d47` | fix(m3.0): stop asserting work the system did not do, and prove the paths that do work |

## Working-tree classification (Phase 0 blocker)

### Bucket A — Keep for milestone (fold into m3.0c reports / evidence)

| Path | Classification |
|------|----------------|
| `docs/m3.0b/FINAL_BETA_BLOCKERS.md` (modified) | Keep — post-rerun B15–B21 content is source of truth for register |
| `docs/m3.0b/PRODUCTION_SCENARIO_MATRIX.md` (modified) | Keep — situation PARTIAL substrate |
| `docs/m3.0-completion/SITUATION_RERUN_RESULTS.md` (modified) | Keep — 12× PARTIAL evidence |
| `docs/m3.0a/CODIRECTOR_CAPABILITY_COVERAGE.md` (modified) | Keep — will append m3.0c cross-ref only |
| `docs/m3.0a/FULL_STACK_WIRING_MATRIX.md` (modified) | Keep — will append m3.0c cross-ref only |
| `docs/M3.0_COMPLETION_CLOSURE_STATUS_REPORT.md` (untracked) | Keep — clean UTF-8 Product summary; commit with docs pack when ready |

### Bucket B — Quarantine / leave untracked (never stage for gate)

- All `scripts/_emit_*.py`, `scripts/_patch_*.py`, `scripts/_write_*.py`, `scripts/_fix_*.py`, `scripts/_verify_*.py`
- `scripts/_payloads/`
- `scripts/_m30_*.py` probe helpers, `scripts/_m210*` emit helpers
- `.tmp-*` scratch files
- `artifacts/**` (audit, situations, fal media, Playwright outputs)
- Playwright traces/reports under `artifacts/functional-audit/test-output/`

### Bucket C — Encoding / line-ending risk

| Path | Note |
|------|------|
| `docs/m3.0-completion/PLAYWRIGHT_CLOSURE.md` | Working copy reported as Bin (UTF-16 risk). Prefer UTF-8 restore from intentional content or HEAD + re-apply totals in m3.0c report |
| `docs/m3.0a/PLAYWRIGHT_RESULTS.md` | LF/CRLF warning — normalize to UTF-8 CRLF if needed |
| `docs/m3.0b/PLAYWRIGHT_BETA_FINDINGS.md` | Same |

**Rule:** temporary emit scripts and undocumented scratch changes must not enter the final gate commit set.

## Security observations (Phase 0)

| Check | Result |
|-------|--------|
| `.env` tracked? | Must remain **untracked** / gitignored — re-verify before every commit |
| Provider Manifest | Locked hash above; size historically 39,547 bytes |
| Secrets in dirty tree | Scratch scripts must not be staged; do not print fal keys |
| Artifacts staged? | No — leave untracked |

## Test baselines entering M3.0c

| Suite | Recorded totals | Source |
|-------|-----------------|--------|
| Backend pytest | 591 passed / **20 failed** / 6 skipped | M3.0 completion + `artifacts/functional-audit/m30b-pytest.txt` (539/20/6 earlier) |
| Playwright | 111 passed / 0 failed / 6 skipped / 117 total | `docs/m3.0-completion/PLAYWRIGHT_CLOSURE.md` |
| Frontend unit | No vitest/jest suite in `studio-web` | lint + `npm run build` are the gate |
| Production situations | **0 EXECUTED / 12 PARTIAL / 0 FAILED / 0 NOT_RUN** | situation rerun docs |

### Twenty known backend failures

1. `test_capabilities.py::test_unproven_baselines_explain_themselves`
2. `test_capabilities.py::test_capability_matrix_doc_lists_every_capability`
3. `test_capabilities.py::test_absent_features_are_reported_as_not_implemented`
4. `test_closed_loop_m2_6_1.py::test_migration_clean_install_has_m006_m007`
5. `test_codirector_intelligence.py::test_prompt_library_loads_all_markdown_prompts`
6. `test_codirector_intelligence.py::test_specialist_selector_bounded_and_mappings`
7. `test_codirector_intelligence.py::test_evaluation_fixtures_present`
8. `test_codirector_tools.py::test_capability_project_not_configured_without_project_id`
9. `test_codirector_tools.py::test_capability_bible_not_configured_before_bible_exists`
10. `test_m211_production_intelligence.py::test_dag_order`
11. `test_migrations.py::test_default_registry_migrations_are_idempotent`
12. `test_pack_install.py::test_empty_download_url_prevents_installation`
13. `test_pack_providers_github.py::test_missing_provider_configuration`
14. `test_pack_providers_github.py::test_public_release_lookup_and_install`
15. `test_pack_providers_github.py::test_github_rate_limit_separate_code`
16. `test_phase0_baseline.py::test_sqlite_initialization_is_isolated` (order-dependent)
17. `test_production_executive.py::test_queue_order_by_priority` (order-dependent)
18. `test_setup_refactor.py::test_atomic_state_preserves_legacy_fields`
19. `test_setup_refactor.py::test_status_does_not_auto_bind_asset_packs`
20. `test_setup_refactor.py::test_missing_source_install_fails_without_creating_directory`

### Playwright skips (6)

1. capability-intelligence-m28 flags-off inverse
2. production-executive-m27 flag-off inverse
3. production-executive-m27 restart recovery hard skip (B14)
4–5. m30-completion-local-live gated
6. m30a-fal-ai-provider live gated

## Provider / platform inventory snapshot

| Area | Status entering M3.0c |
|------|------------------------|
| Local ComfyUI Z-Image | VERIFIED (prior real PNG path) |
| fal.ai video | Artifact VERIFIED; **not** through Studio queue Job row |
| fal image models | `FAL_IMAGE_MODELS` empty — PRODUCT_APPROVAL_REQUIRED (no code this milestone) |
| Intelligence (Ollama) | Provider path reachable; B15 discards analysis |
| Native platforms | 18 platforms / 29 UI sections — many PARTIAL |
| Unified job inspect | Co-Director executive 404 for Studio-queue IDs |
| Audio | Import→timeline CLOSED; generation unavailable |
| Export | Pack omits `director_json` (B18) |

## Outstanding Critical / High blockers (enter register Phase 1)

B5 (partial), B6, B7→B15, B8, B9, B11, B15, B16, B17, B18, B19, B20; unified jobs; fal queue proof; 20 pytest failures; 12 situation EXECUTED gap.

## Phase 0 exit criteria

- [x] Branch / tip / remote recorded
- [x] Manifest lock recorded
- [x] Dirty tree classified (A/B/C)
- [x] Test baselines inventoried
- [x] Security observations recorded
- [ ] Product code may proceed only after this file exists (**satisfied by this write**)

**Phase 0 status: COMPLETE for gate-start.** Implementation may proceed; quarantine bucket B remains unstaged through final commit.
