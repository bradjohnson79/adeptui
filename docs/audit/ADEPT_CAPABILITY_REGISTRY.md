# Adept Capability Registry — how it works and how to change it

**Code:** `studio-api/app/capabilities/`
**Contract:** `docs/audit/ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md`
**Baseline table:** `docs/audit/ADEPT_PRODUCTION_CAPABILITY_MATRIX.md`
**Tests:** `studio-api/tests/test_capabilities.py`

The matrix says *what* each capability is. The contracts document says *what the payload means*.
This document is for whoever has to change the thing: how the four modules divide the work, what
each probe knows, and what to do when you add a feature or find a status that lies.

---

## 1. Module layout

```
app/capabilities/
  registry.py   what the code can do        (static, from reading the code)
  probes.py     what the environment has    (live, one narrow question each)
  service.py    combines them into one status per capability
  models.py     the wire types + status groupings
  errors.py     reason codes, HTTP mapping, secret scrubbing
  api.py        publishes it
```

The split exists so the two kinds of wrongness stay separable. If `registry.py` is wrong, someone
read the code incorrectly and the fix is a baseline edit. If a probe is wrong, the environment was
misread and the fix is in `probes.py`. A single "figure out if this works" function would make
those two failures indistinguishable, which is how the pre-existing health check ended up
asserting three hardcoded model paths under one developer's home directory.

Supporting modules the registry depends on but does not own:

| Module | Answers |
|--------|---------|
| `app/comfy_health.py` | Is ComfyUI reachable, is its node catalogue readable, which model components are on disk |
| `app/workflows/readiness.py` | Can each registered workflow run right now; also the choke point that refuses to queue a provably-invalid graph |
| `app/services/scene_service.py` | Scene CRUD invariants, callable outside an HTTP request |
| `app/setup/status.py`, `app/setup/diagnostics.py` | Component install/verify state (reused, not reimplemented) |
| `app/source_manager/registry.py` | Provider availability and active downloads |

---

## 2. Subsystems

Capabilities are grouped so a consumer can filter without knowing individual ids. The Source
Manager page, for example, lists blockers only from the subsystems it can actually help with.

| Subsystem | Covers |
|-----------|--------|
| `storage` | Data directory writability, SQLite availability |
| `project`, `scenes`, `assets` | Project CRUD, scene CRUD and timeline, asset upload/read |
| `references` | Reference ingredients, sheets, IC-LoRA readiness |
| `codirector` | Chat, provider health, Production Bible read/propose/approve |
| `comfyui`, `extensions`, `workflows`, `models` | The generation dependency chain |
| `source_manager`, `downloads`, `setup` | Acquisition and installation |
| `generation`, `storyboard`, `director`, `editor`, `spatial`, `virtual_stage` | Production surfaces |
| `health`, `capabilities` | The introspection surfaces themselves |

---

## 3. Probes

Each probe answers one narrow question and is individually failure-tolerant: a probe that cannot
answer appends a warning and leaves its slice of the snapshot `None`, so one unhealthy subsystem
degrades a few capabilities to `unknown` instead of failing the whole registry read. A test
asserts that a deliberately broken probe still yields a complete snapshot.

| Probe | Question | Sets |
|-------|----------|------|
| `probe_storage` | Does the configured data root accept a write? | `storage_writable`, `storage_message` |
| `probe_database` | Is SQLite open and are the core tables present? | `database_ok`, `database_message` |
| `probe_setup` | What is each component's install/verify state? (read without persisting) | `setup_components`, `setup_overall` |
| `probe_source_manager` | Which providers are available; how many downloads are active? | `source_manager_ok`, counts |
| `probe_comfy` | Is ComfyUI reachable, and what node types does it offer? | `comfy`, `node_types` |
| `probe_codirector` | Is the local model provider reachable with a usable model? | `codirector` |
| `probe_workflows` | Can each workflow run, given the catalogue and component states? | `workflows` |
| `probe_project` | Does this project exist; what are its counts and reference readiness? | `project_*` |

Scheduling: the four blocking probes run together in one worker thread; ComfyUI and the model
provider are probed concurrently as async work; workflow readiness runs afterwards because it
consumes both the node catalogue and the component states. `probe_project` runs last and only when
a project id was supplied. Nothing probes twice — `probe_project` reuses the already-fetched node
catalogue rather than issuing another `/object_info` call.

---

## 4. Evaluators

`service.py` maps each capability id to an evaluator. Capabilities with no live dependency of
their own fall through to `_baseline`, which converts the registry status into an honest
evaluation (`not_implemented` becomes unavailable with `CAPABILITY_NOT_IMPLEMENTED`,
`partially_wired` becomes unavailable with `CAPABILITY_UNVERIFIED`, and so on).

| Evaluator | Applies to | Logic |
|-----------|-----------|-------|
| `_eval_storage`, `_eval_database` | `storage.*` | The probe result, with `None` reported as `unknown` rather than assumed good |
| `_eval_db_backed` | project / scene / asset / job / Bible entries | Blocked if the database is down (or storage, for writes); otherwise baseline |
| `_eval_comfy_health` | `comfyui.health` | Unreachable is blocked; catalogue unreadable or required weights missing is `degraded`; otherwise `locally_verified` |
| `_eval_comfy_dependent` | `comfyui.queue/cancel/outputs` | Blocked when ComfyUI is unreachable |
| `_eval_extensions_ready` | `extensions.comfyui.ready` | Union of node types missing across all workflows; `unknown` when the catalogue is unreadable |
| `_eval_models_image` / `_eval_models_video` | `models.*.ready` | Required components verified on disk; missing optional ones give `degraded`; source-pending gives `not_configured` |
| `_workflow_aggregate` | `workflows.ready`, `workflows.{image,video}.ready` | Ready if *any* workflow of that modality is runnable; all-unknown stays `unknown` |
| `_eval_workflow_discovery` | `workflows.discover/validate` | The registry was readable |
| `_eval_codirector_provider` / `_eval_codirector_chat` | `codirector.*` | Mock provider is `mock_verified` (never local truth); unreachable is blocked; no model is `not_configured` |
| `_eval_source_manager_read` | `source_manager.read`, `downloads.read` | The overview was readable |
| `_eval_source_manager_install` | `source_manager.install` | `not_configured` when no component has a usable source; otherwise `partially_wired` naming the source-pending ids |
| `_eval_references_project_scoped` | `references.*` | Blocked if storage is unwritable; otherwise baseline |
| `_eval_references_ic_lora` | `references.ic_lora.ready` | Project-scoped: needs the gated model file and the ComfyUI nodes |
| `_eval_generation_queue` | `generation.{image,video}.queue` | Requires ComfyUI plus a runnable workflow plus weights, and even then caps at `partially_wired` pending a real render |

An evaluator that raises does not break the read: the failure is recorded as
`evaluator_failed:{id}` in `probeWarnings` and the capability reports `unknown` with
`CAPABILITY_PROBE_FAILED`.

---

## 5. Live snapshot on the verification machine

Captured with `.venv/Scripts/python.exe scripts/dump_capability_snapshot.py`, with ComfyUI **not**
running, a real Ollama reachable, the LTX checkpoint installed, and the Essential Packs
unpublished:

```
total: 69   callable: 35

locally_verified 34   partially_wired 13   blocked 13
not_implemented   6   degraded         1   mock_verified 1   ui_only 1

probeWarnings: []
```

**Callable (35):** `project.create`, `project.list`, `project.read`, `project.update`,
`project.delete`, `project.scenes.read`, `project.scenes.create`, `project.scenes.update`,
`project.scenes.delete`, `project.timeline.propose`, `assets.upload`, `assets.read`, `assets.file`,
`references.upload`, `references.read`, `references.attach.project`, `references.exclude`,
`codirector.chat`, `codirector.provider`, `codirector.bible.read`, `codirector.bible.propose`,
`codirector.bible.approve`, `workflows.discover`, `workflows.validate`, `models.image.ready`,
`models.video.ready`, `source_manager.read`, `source_manager.refresh`, `downloads.read`,
`setup.read`, `health.read`, `capabilities.read`, `generation.jobs.read`, `storage.project_data`,
`storage.database`.

**Blocked (13):** all of them trace to two real environment facts, not to code gaps.

| Root cause | Blocked capabilities |
|------------|---------------------|
| ComfyUI not running (`DEPENDENCY_UNAVAILABLE`, action `start_comfyui`) | `comfyui.health`, `comfyui.queue`, `comfyui.cancel`, `comfyui.outputs`, `extensions.comfyui.ready`, `workflows.image.ready`, `references.ic_lora.ready`, `generation.image.queue`, `generation.video.queue`, `generation.lipsync.queue`, `storyboard.generate` |
| `ltx23_ic_lora_ingredients` not installed (`WORKFLOW_MISSING_MODELS`, action `open_source_manager`) | `workflows.ready`, `workflows.video.ready` |

Start ComfyUI and the first eleven resolve without a code change, which is the point of the
registry: the blocker list is a to-do list for the operator, not a bug list for the developer.

---

## 6. Adding or changing a capability

1. **Add the definition to `registry.py`.** Pick the baseline from what the code actually does
   today, not from what it is meant to do. Fill in `service_ref` and `http_ref`; a test asserts
   every `service_ref` resolves to a real importable attribute, so a typo or a renamed function
   fails the suite rather than rotting in a document.
2. **If the status depends on the environment, add an evaluator** to `EVALUATORS` in `service.py`.
   If it depends on something no probe answers yet, add a probe first — a narrow one, tolerant of
   its own failure.
3. **Declare `dependencies`.** Do not hand-code "blocked because ComfyUI is down" inside an
   evaluator when the dependency graph will derive it. Two tests guard the graph: no dangling ids,
   and no cycles.
4. **Regenerate the matrix row:** `python studio-api/scripts/dump_capability_matrix.py`.
5. **Add the honesty test.** If the capability is `not_implemented`, assert it stays
   `not_implemented`. If it is `locally_verified`, there must be a test that exercises the real
   round trip: HTTP or service call, through real storage, read back in a new session, with the
   failure path returning a structured code.

### Promoting a status

| To | Requires |
|----|----------|
| `mock_verified` | A test passes against a fixture or mock double |
| `locally_verified` | The full slice runs against real local storage or providers, persists, reads back in a new session, and its failure path returns a structured code. **A passing mock never qualifies.** |
| `production_ready` | `locally_verified` plus a documented contract and a real end-to-end run recorded in a report |
| `degraded` | Usable now, with a named reduction and a recommended action |

The direction that needs the most discipline is downward. When a probe reveals that something
believed to work does not, the fix is to lower the baseline and say why — not to widen the
evaluator until the status comes back green.

---

## 7. Consumers, and what they are allowed to do

| Consumer | Reads | Must not |
|----------|-------|----------|
| `SystemStatusStrip` (`StudioChrome.tsx`) | `blockers.length` for the badge | Count model paths or ping ComfyUI itself |
| `CapabilityReadinessPanel` (Home, Source Manager) | `callable`, `blockers`, `probeWarnings` | Start a download from a blocker action |
| `SetupSummary` (`SetupWizard.tsx`) | Blockers filtered to `REQUIRED_FOR_GENERATION` | Report "Ready" while a required capability is blocked |
| Co-Director M2.2 tool registry (future) | `callable`, `readOnly`, `requiresApproval` | Expose a tool whose capability is not callable, or cache readiness across turns |

`REQUIRED_FOR_GENERATION` lives in `studio-web/src/components/CapabilityPanel.tsx`:
`storage.project_data`, `storage.database`, `comfyui.health`, `models.video.ready`,
`workflows.video.ready`. It is the minimum set that must be usable before the Setup Wizard may
claim the studio is ready to generate.
