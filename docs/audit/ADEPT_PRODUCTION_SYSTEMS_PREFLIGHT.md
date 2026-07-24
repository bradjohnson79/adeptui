# Adept Production Systems Readiness — Preflight

**Date:** 2026-07-24
**Worktree:** `C:\AdeptFilmWorks\AIVideoStudio-psr` (isolated git worktree)
**Branch:** `phase2/production-systems-readiness`, cut from `a5b7106` (Co-Director M2.1 tip)
**Checkpoint tag:** `checkpoint/production-systems-readiness-start` (= `a5b7106`)
**Untouched:** `C:\AdeptFilmWorks\AIVideoStudio` (main checkout, `phase2/codirector-m2-2-tool-registry` WIP)
and `C:\AdeptFilmWorks\AIVideoStudio-pack-authoring` (`phase1c/essential-pack-authoring` WIP).

This document records the current state of the system **before** any Production Systems
Readiness (PSR) change, so every readiness claim later in this branch can be traced back to
evidence rather than optimism.

---

## 1. Why this work exists

Adept has a large amount of UI surface and a large amount of backend surface, but no single
machine-readable answer to the question *"can this capability actually be used right now?"*.
Today the answer is scattered across:

- `/api/health` (ComfyUI reachability + three hardcoded model-path checks),
- `/api/setup/status` (component install/verify state),
- `/api/source-manager/overview` (providers, saved sources, download queue),
- `/api/codirector/health` (local model provider),
- `/api/projects/{id}/references/capabilities` (IC-LoRA ingredient readiness only),
- and a lot of implicit knowledge in component code.

Co-Director M2.2 will need to ask "which capabilities may I call for this project?" before it
orchestrates anything. If that answer is guessed — or worse, inferred from a mock — the
assistant will confidently attempt operations that cannot succeed. PSR builds the truth source
first.

**Relationship to M2.2:** PSR **precedes** tool orchestration and deliberately does not
implement a Co-Director tool registry, tool dispatch, or autonomous execution. It publishes
`GET /api/capabilities` (+ project scope) as the contract M2.2's CapabilityAdapter will read.

## 2. Core verification principle used in this branch

A capability may only be labelled `locally_verified` when the whole vertical slice was
exercised in the verified environment:

```
UI → API client → route → application service → DB / filesystem / provider
  → persisted result → UI shows it → reload restores it → failure path is structured
```

Rules that are treated as hard gates:

- Mock/fixture success never produces `locally_verified` (`mock_verified` exists for that).
- Absent features are `not_implemented`, not "broken".
- Missing configuration is `not_configured`; a real dependency gap is `blocked`.
- No download URL is ever invented; unpublished packs stay unpublished.

## 3. Baseline test state (recorded before edits)

Python suite, run from this worktree with the interpreter at
`C:\AdeptFilmWorks\AIVideoStudio\studio-api\.venv\Scripts\python.exe` (the worktree has no
venv of its own; the interpreter is used read-only):

```
python -m pytest tests -q        →  8 failed, 183 passed
```

Pre-existing failures at `a5b7106` (all in pack/source-state expectations, none related to PSR
scope). These are **not** introduced by this branch and are **not** fixed by it — the Essential
Pack authoring branch owns that surface:

| Test | Observed |
|------|----------|
| `test_pack_install.py::test_empty_download_url_prevents_installation` | expects issue code in `{download_source_missing, pack_provider_not_configured, pack_release_not_found}`, gets `source_not_published` |
| `test_pack_install.py::test_refresh_source_does_not_create_folders` | same family (`source_not_published`) |
| `test_pack_providers_github.py::test_missing_provider_configuration` | expects `github`-specific codes, gets `source_not_published` |
| `test_pack_providers_github.py::test_public_release_lookup_and_install` | release lookup returns unpublished manifest state |
| `test_pack_providers_github.py::test_github_rate_limit_separate_code` | expects `github_rate_limited`, gets `source_not_published` |
| `test_setup_refactor.py::test_atomic_state_preserves_legacy_fields` | `assert 3 == 2` (legacy field count) |
| `test_setup_refactor.py::test_status_does_not_auto_bind_asset_packs` | expects `download_unavailable`, gets `source_pending` |
| `test_setup_refactor.py::test_missing_source_install_fails_without_creating_directory` | expects `download_unavailable`, gets `source_pending` |

`test_phase0_baseline.py::test_sqlite_initialization_is_isolated` fails **only** in a full-suite
run and passes in isolation (`3 passed`) — an existing test-ordering interaction where an earlier
module leaves `settings.data_dir` patched. Recorded here so it is not misread later as a PSR
regression.

Playwright: `tests/e2e` boots its own stack via `scripts/e2e-start.mjs` (API `:8742`, web `:5173`,
pack fixture `:8765`). Because the main checkout may be running the same ports for another
agent's work, all PSR Playwright runs in this worktree use shifted ports
(`STUDIO_API_PORT`, `PLAYWRIGHT_WEB_PORT`, `E2E_FIXTURE_PORT`, `STUDIO_API_BASE`,
`PLAYWRIGHT_BASE_URL`) so no other agent's server is reused or killed.

## 4. Subsystem inventory (as found)

### 4.1 Routes

| Router | Prefix | Notable surface |
|--------|--------|-----------------|
| `routers/api.py` | `/api` | health, projects, scenes, assets, spatial, render/lipsync/export jobs, timeline propose/apply, assistant aliases |
| `routers/codirector.py` | `/api` | Co-Director gateway: health, models, chat, chat/stream, cancel, bible, proposals, approvals |
| `routers/extra.py` | `/api` | Setup Wizard, download sources, profiles, learning, preview SSE, dashboard, duplicate/archive, txt2vid, imagegen, library, marketplace, spatial scene, script/storyboard |
| `references/api.py` | `/api` | reference ingredients, sheets, presets, validate, `references-used` |
| `source_manager/api.py` | `/api` | Source Manager overview, providers, sources, verify, assignments |
| `source_manager/downloads/api.py` | `/api` | download queue + install receipts |
| `master_sheet.py`, `avatar_studio.py`, `editor_sequences.py`, `knowledgebase_api.py` | `/api` | feature routers |
| `routers/e2e.py` | `/api` | test control surface, mounted only when `STUDIO_E2E=1` |

### 4.2 Application services / stores

- **Projects & scenes:** no service layer. All CRUD is inline in `routers/api.py`
  (`_project_out`, `create_project`, `add_scene`, `update_scene`, `delete_scene`), so there is
  nothing a future Co-Director tool could call except HTTP.
- **Co-Director:** `codirector/service.py` (+ `bible/`), provider abstraction under
  `codirector/providers/` (ollama, mock).
- **Setup:** `setup/status.py` (`build_status`), `setup/diagnostics.py`, `setup/operations.py`,
  `setup/orchestrator.py`, `setup/pack_*`.
- **Source Manager:** `source_manager/service.py`, `registry.py` (`overview_payload`),
  `persistence.py`, `downloads/queue.py`, provider adapters.
- **References:** `references/store.py` (JSON files under
  `data_dir/projects/{id}/references/`), `references/capabilities.py`, `sheet_builder.py`.
- **Workflows:** `workflows/registry.py` — a static, metadata-only inventory of 8 builders,
  with `required_node_types` per entry. Not exposed over HTTP today.
- **Comfy:** `comfy_client.py` (`health`, `object_info`/`get_object_info`, `queue_prompt`,
  `get_queue`, `interrupt`, uploads), `adapters/comfy.py`.
- **Queue:** `queue_worker.py` (in-process job queue consumed by render/imagegen/txt2vid).

### 4.3 Storage

- SQLite at `settings.data_dir/studio.db`, schema provisioned by `init_db()`
  (`Base.metadata.create_all` + `_add_col` ALTERs). Migration runner exists
  (`app/migrations/`) with `M001`, `M002` registered but is **not** wired into startup.
- Project media under `data_dir/assets/{project_id}/`, references under
  `data_dir/projects/{project_id}/references/`, previews under `data_dir/projects/.../lipsync_preview`.

## 5. Risks and known gaps confirmed by reading the code

1. **Hardcoded Comfy model root.** `routers/api.py::health` probes
   `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models` literally, then
   `rglob`s for three filenames. It is user-specific, ignores `settings`, and returns an
   opaque `missing_models: string[]` with no component IDs or recommended actions. Health is
   also all-or-nothing: any exception yields `ok: false` with a raw exception string in
   `message`.
2. **No global capabilities API.** Nothing aggregates readiness; every consumer re-derives it.
3. **Scenes have no summary field.** `SceneIn`/`SceneOut`/`Scene` carry `name`, `prompt`,
   `camera_note`, but no `summary`, so a scene cannot carry a short human/agent-readable
   description.
4. **Active scene is frontend-only.** There is no `active_scene_id` on `Project` and no
   endpoint that sets one — selection lives in React state / `directorSelection.ts`.
   PSR documents this rather than inventing persistence.
5. **Scene reorder is not implemented.** Indices are only assigned on create and re-packed on
   delete; there is no reorder route or service call.
6. **References have no HTTP delete.** `references/api.py` exposes upsert (`POST
   .../references/ingredients`), list, replace, sheets, presets — no `DELETE`. Removal today
   is only expressible as `include: false` on an upsert.
7. **Reference attach is project-scoped.** Ingredients live in one project-level JSON file;
   `BuildSheetBody.scene_id` is accepted but ingredients themselves are not scene-scoped.
8. **Workflow readiness is unexposed.** `workflows/registry.py` knows required node types but
   nothing compares them against a live `/object_info`, so nothing can say "this workflow is
   missing node X / model Y" before queueing.
9. **Unpublished Essential Packs.** `pack_essential_*` manifests have no published archive.
   `setup/status.py` already reports `source_pending` / `download_unavailable` and disables
   install; PSR must surface that as `blocked`/`not_configured` **without** inventing a URL.
10. **Setup completion is status-driven, not blocker-driven.** `build_status()` computes
    `overall_status` from component states only; it has no notion of "a required capability is
    blocked".

## 6. Selected first vertical slices

| Slice | Subsystem | Why first |
|-------|-----------|-----------|
| 1 | Projects & scenes | Highest-value Co-Director target, fully local (SQLite), no external dependency, currently router-inline |
| 2 | References | Real filesystem + DB interaction; exposes an honest gap (no delete) instead of hiding it |
| 3 | Source Manager / model readiness | Determines whether generation is even possible; already has rich state to expose accurately |
| 4 | ComfyUI + workflows | Turns opaque health into structured readiness and prevents queueing invalid workflows |
| 5–6 (optional) | Image / video generation | Only if slice 4 proves Comfy reachable and a workflow readiness path is exercisable |

## 7. Guardrails for this branch

- No Co-Director tool registry / orchestration (M2.2 owns it).
- No invented pack download URLs; no silent multi-GB downloads triggered from capability UI.
- No rewriting of the working Source Manager / download engine.
- No `production_ready` claim for Virtual Stage or generation without real end-to-end proof.
- Capability payloads contain no secrets and no stack traces.
