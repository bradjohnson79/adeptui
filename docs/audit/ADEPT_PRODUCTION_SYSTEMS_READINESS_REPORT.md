# Adept Production Systems Readiness Report

**Branch:** `phase2/production-systems-readiness`
**Worktree:** `C:\AdeptFilmWorks\AIVideoStudio-psr`
**Base:** `a5b7106` (M2.1 tip) — tagged `checkpoint/production-systems-readiness-start`
**Date:** 2026-07-24

Companion documents: `ADEPT_PRODUCTION_SYSTEMS_PREFLIGHT.md` (what was true before),
`ADEPT_PRODUCTION_CAPABILITY_MATRIX.md` (baseline per capability),
`ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md` (API contract),
`ADEPT_CAPABILITY_REGISTRY.md` (how to change it).

---

## 1. What this milestone was for

The studio had a truthfulness problem, not a feature problem. Three surfaces each decided
independently whether it was usable, using different evidence:

- the chrome status strip counted `health.missing_models`;
- the Setup Wizard summed component install states;
- the Source Manager looked at source availability.

They could disagree, and did. The strip could report "ComfyUI Connected" while a render was
guaranteed to fail on a node type ComfyUI does not have installed, because nothing compared the
workflow's requirements against the live catalogue. The old `/api/health` asserted three
hardcoded model paths under one developer's `%LOCALAPPDATA%`, so on any other machine it reported
missing weights that were present.

This milestone did not add production features. It made the studio able to answer, in one place
and without lying, *what can be used right now, and if not, why not*.

---

## 2. What was built

### 2.1 Capability registry (`studio-api/app/capabilities/`)

69 capabilities across 20 subsystems, each with a static baseline read off the code and a live
evaluation from environment probes. Eight probes, each individually failure-tolerant. Four public
endpoints plus structured ComfyUI health and workflow readiness.

The status vocabulary is exactly the eleven values the plan specified, and a test asserts no
twelfth value can appear. The distinction that carries the most weight is between
`not_implemented` (absent — nothing to fix) and `blocked` (implemented, dependency missing — an
operator can fix it). Conflating them is what turns a blocker list into noise operators learn to
ignore.

### 2.2 Slice 1 — projects and scenes

`SceneService` (`app/services/scene_service.py`) extracts scene CRUD out of router bodies so the
invariants live in one place and are callable without an HTTP request. Extracting it surfaced a
real bug: `PATCH /api/projects/{id}/scenes/{sceneId}` dumped the whole request model, so any field
the client omitted was silently reset to the schema default. A request that only meant to rename a
scene blanked its prompt. The service now writes only the keys present in the request, and an E2E
test asserts a rename preserves the prompt.

Added `Scene.summary` (migration `M010`, additive and idempotent, no-op when the table does not
yet exist so `init_db()` keeps ownership of first creation) and threaded it through `SceneIn`,
`SceneOut`, and the frontend `Scene` type. Added the missing dedicated read routes,
`GET /api/projects/{id}/scenes` and `GET .../scenes/{sceneId}`.

**Status:** scene create/read/update/delete are `locally_verified` — real SQLite, read back in a
new session, structured `SCENE_NOT_FOUND` / `PROJECT_NOT_FOUND` on the failure paths, and
verified through the browser as well as the API.

Two scene capabilities are deliberately *not* claimed:

- `project.scenes.reorder` — `not_implemented`. There is no reorder route or service call.
  Indices are assigned on create and re-packed on delete; nothing else moves them.
- `project.scenes.active` — `ui_only`. The focused scene lives in React state
  (`studio-web/src/directorSelection.ts`). There is no `active_scene_id` column and no endpoint,
  so the selection does not survive a reload on another client. Adding persistence is a schema
  decision outside this branch.

### 2.3 Slice 2 — references

Verified the real chain: upload a real PNG through the file input the AssetTray drives, attach it
as an ingredient, list it, and confirm it survives a reload — ingredients live in durable JSON at
`data_dir/projects/{id}/references/ingredients.json`.

Two honest negatives, both asserted by tests rather than merely documented:

- `references.remove` — `not_implemented`. The router exposes upsert, list, replace, sheets, and
  presets; there is no `DELETE`. The E2E test issues the `DELETE` and asserts it fails, then reads
  the capability and asserts it reports `not_implemented`. The supported approximation is
  re-upserting with `include: false`, which is a separate, honestly-named capability
  (`references.exclude`) rather than a removal in disguise.
- `references.attach.scene` — `not_implemented`. Ingredients are stored once per project.
  `BuildSheetBody.scene_id` is accepted for sheet builds, but ingredient records carry no scene
  scope.

### 2.4 Slice 3 — Source Manager

Component states now map to distinct capability statuses instead of one "not ready":

| Component reality | Capability status | Reason code | Action |
|---|---|---|---|
| Installed and verified | `locally_verified` | — | — |
| Published source, not installed | `partially_wired` | `CAPABILITY_UNVERIFIED` | `open_source_manager` |
| No published archive (`source_pending`) | `not_configured` | `MODEL_SOURCE_PENDING` | `add_source_url` |
| Credential required, absent | `not_configured` | `DEPENDENCY_NOT_CONFIGURED` | `add_source_url` |

The Essential Packs have no published archive. `source_manager.install` therefore reports
`not_configured` with `MODEL_SOURCE_PENDING` and asks the operator to add a Source URL. **No
download URL was invented to make that look better.**

### 2.5 Slice 4 — ComfyUI and workflows

`app/comfy_health.py` separates three questions the previous single try/except conflated: is the
service reachable, is its node catalogue readable, and which catalogued model components are on
disk. Model presence is answered by the Setup component verifiers — the same source the Setup
Wizard and Source Manager use — so the answer names real component ids and cannot disagree with
the wizard. Nothing in the payload is machine-specific; an E2E test asserts no user path leaks.

`GET /api/workflows` and `GET /api/workflows/{id}/readiness` report `missingModels`,
`missingExtensions`, and a `recommendedAction`. Readiness has three outcomes, not two: `ready`,
`blocked`, and `unknown` — because with ComfyUI down, "this workflow needs nodes we cannot see"
is not the same claim as "this workflow is broken".

**Never queue an invalid workflow** is enforced at a graph-level choke point.
`assert_graph_runnable()` inspects the *compiled graph* rather than a workflow id, so every
producer (scene render, Txt2Vid, ImageGen, lip sync, IC-LoRA) is covered without each call site
remembering to ask. Deliberately, `unknown` is not treated as invalid: when `/object_info` cannot
be read we submit anyway, because refusing on missing evidence would break a working install
whose catalogue endpoint is merely slow.

### 2.6 Integrations

| Surface | Before | Now |
|---|---|---|
| Chrome status strip | Counted `health.missing_models` itself | Renders a badge from `blockers.length` |
| Home | No readiness view | `CapabilityReadinessPanel`: callable count, blockers with actions, explicit Refresh |
| Setup Wizard | "Ready" from component states alone | Cannot claim ready while a required capability is blocked; lists blockers with a jump link to the relevant component card |
| Source Manager | Sources only | "What is blocked right now", filtered to subsystems it can help with |

Every blocker action navigates (Source Manager, or the Setup Wizard card for the named component)
or re-probes. **None starts a download.** An E2E test clicks Refresh and asserts no
download/install/prepare `POST` is issued. Installing remains an explicit per-component decision.

Also fixed: the Vite dev proxy hardcoded `127.0.0.1:8742`, so a second checkout's browser silently
proxied `/api` to the first checkout's backend. It now honours `STUDIO_API_PORT`, which is what
made an isolated E2E run in this worktree possible at all.

---

## 3. Verification

### 3.1 Python

```
pytest tests/test_capabilities.py tests/test_scene_service.py -q   →  51 passed
pytest tests -q                                                    →  233 passed, 9 failed
```

The 9 failures are exactly the set recorded at the M2.1 tip in the preflight document — 8
pack/source-state expectations owned by the pack-authoring branch, plus
`test_phase0_baseline.py::test_sqlite_initialization_is_isolated`, which fails only in a full-suite
run and passes in isolation (an existing test-ordering interaction where an earlier module leaves
`settings.data_dir` patched). No new failure was introduced, and none was "fixed" by weakening an
assertion.

`test_capabilities.py` covers the status vocabulary, registry integrity (no dangling dependency
ids, acyclic graph, every `service_ref` resolving to real importable code), the HTTP surface,
probe-failure tolerance, and the honesty rules — including that the mock Co-Director provider is
never reported as local truth, and that a deliberately broken probe still yields a complete
snapshot.

### 3.2 Playwright

```
npx playwright test --grep @critical --retries=0   →  41 passed (6.7m)
```

All 41, including the pre-existing M1/M2.1 Co-Director, setup, pack, a11y, responsive, and
resilience specs. New or extended:

| Spec | Covers |
|---|---|
| `projects/project-crud.spec.ts` (extended) | Scene CRUD via API with partial-PATCH proof, index repacking, project isolation, cross-project 404; plus a scene added in the browser surviving a reload |
| `projects/references.spec.ts` (new) | Real PNG upload through the file input, attach ingredient, list, reload; `DELETE` fails and `references.remove` reports `not_implemented` |
| `capabilities/capabilities.spec.ts` (new) | Snapshot well-formedness, `callable` agreeing with per-item `available`, blockers as a strict subset, scene CRUD reported callable, `not_implemented` staying so, project-scope 404, Comfy health and workflow readiness contracts, no user paths in health, Home badge agreeing with the API, Refresh starting no download, Source Manager blocker list, Setup Wizard refusing to claim ready |

### 3.3 Live snapshot on the verification machine

ComfyUI not running, real Ollama reachable, LTX checkpoint installed, Essential Packs unpublished:

```
total: 69   callable: 35   probeWarnings: none

locally_verified 34   partially_wired 13   blocked 13
not_implemented   6   degraded         1   mock_verified 1   ui_only 1
```

All 13 blockers trace to two environment facts, not code gaps: ComfyUI is not running (11), and
`ltx23_ic_lora_ingredients` is not installed (2). Start ComfyUI and eleven resolve with no code
change — which is the intended shape. The blocker list is a to-do list for the operator.

---

## 4. Capability ids that are Co-Director-callable now

These 35 report `available: true` and are safe for the M2.2 tool registry to expose. Grouped by
what a tool would do with them:

**Read, no approval needed** — `project.list`, `project.read`, `project.scenes.read`,
`assets.read`, `assets.file`, `references.read`, `codirector.bible.read`, `workflows.discover`,
`workflows.validate`, `models.image.ready`, `models.video.ready`, `source_manager.read`,
`downloads.read`, `setup.read`, `health.read`, `capabilities.read`, `generation.jobs.read`,
`storage.project_data`, `storage.database`, `project.timeline.propose`, `codirector.chat`,
`codirector.provider`

**Write, approval required** — `project.create`, `project.update`, `project.delete`,
`project.scenes.create`, `project.scenes.update`, `project.scenes.delete`, `assets.upload`,
`references.upload`, `references.attach.project`, `references.exclude`,
`codirector.bible.propose`, `codirector.bible.approve`, `source_manager.refresh`

The scene write capabilities are the interesting ones: a Co-Director that can create, retitle,
re-prompt, and delete scenes through `SceneService` — with approval — is a meaningful step toward
an actual co-director, and it is now backed by a verified slice rather than a hope.

**Not callable, and why:** all `generation.*` queue capabilities, every `comfyui.*` capability, and
`workflows.{ready,video.ready}` are blocked on ComfyUI and the missing IC-LoRA weights.
`codirector.tools` is `not_implemented` — this branch publishes the truth source M2.2 will read;
it does not implement orchestration.

---

## 5. Honest blockers and limits

**Environment blockers** (fixable by the operator, no code change):

1. ComfyUI is not running. Blocks 11 capabilities including all generation.
2. `ltx23_ic_lora_ingredients` is not installed, and its source is gated. Blocks
   `workflows.ready`, `workflows.video.ready`, and IC-LoRA references.
3. The Essential Packs have no published archive. `source_manager.install` reports
   `not_configured` and asks for a Source URL.

**Deliberately unclaimed** (would require work outside this branch):

4. **Generation is capped at `partially_wired`, never `production_ready`.** Even with ComfyUI
   reachable, a ready workflow, and verified weights, the best status this branch reports is
   `partially_wired` with the action `run_verification_render`, because no real render was
   performed in a verified environment. The optional image/video generation slices were therefore
   not attempted; ComfyUI was not reachable and workflow readiness could not be exercised
   end-to-end.
5. **`downloads.queue` is `mock_verified`.** Queue, pause/resume/cancel, and receipts are
   exercised against the Playwright fixture HTTP provider. No test downloads a real archive.
6. **Virtual Stage is `not_implemented`.** It appears in architecture documents; no route,
   service, table, or component implements it.
7. **`Scene.summary` has no editor.** The column, schemas, service, and API all carry it, and it
   round-trips, but no UI field edits it. `project.scenes.update` is `locally_verified` for the
   field via API; the *UI* for summary is future work.
8. **A pre-existing TypeScript error remains** in `CoDirectorSession.tsx` (a `const` assertion
   TS 6.0 rejects). It is unrelated to this branch, present at the M2.1 tip, and does not affect
   the E2E run because Vite dev uses esbuild. Left for the branch that owns that file rather than
   touched from here.

---

## 6. What a reviewer should check first

1. **Is any `locally_verified` claim unearned?** The rule is a real round trip through real
   storage, read back in a new session, with a structured failure code. Mocks give
   `mock_verified`.
2. **Does any consumer still derive readiness?** Grep for `missing_models` and direct ComfyUI
   pings in `studio-web/src`. The only remaining use is inside the capability-aware badge, reading
   the structured field.
3. **Can any blocker action start a download?** `actionTarget()` in `CapabilityPanel.tsx` returns
   only navigation targets, and refresh only drops the probe cache.
4. **Does the registry lie about what exists?** Every `service_ref` is asserted to resolve to real
   importable code, so a renamed function fails the suite instead of rotting in a table.
