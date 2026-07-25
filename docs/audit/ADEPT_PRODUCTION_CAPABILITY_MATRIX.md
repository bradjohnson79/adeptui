# Adept Production Capability Matrix

**Source of truth:** `studio-api/app/capabilities/registry.py`
**Live values:** `GET /api/capabilities` (add `?projectId=…` or use `GET /api/projects/{id}/capabilities`)
**Kept honest by:** `studio-api/tests/test_capabilities.py`
**Payload contract:** `ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md`
**How to change the registry:** `ADEPT_CAPABILITY_REGISTRY.md`

This table is the *baseline* — what the code can do, judged by reading it. The runtime status
returned by the API can only be equal to or **weaker** than the baseline: a probe may downgrade
`locally_verified` to `blocked` when ComfyUI is down, but no probe ever promotes a capability
above what the code has earned.

Two tests keep this document from drifting: one asserts every capability id below appears in the
registry, and one asserts every `service_ref` resolves to real code.

To regenerate the rows: `python studio-api/scripts/dump_capability_matrix.py`

---

## Status vocabulary

| Status | Meaning | Callable now? |
|--------|---------|---------------|
| `not_implemented` | The behaviour does not exist in this build. Absent, not broken. | no |
| `ui_only` | A UI affordance exists with no durable backend behind it. | no |
| `backend_only` | A working backend surface exists that no UI reaches yet. | no |
| `partially_wired` | Both ends exist; the round trip is not proven. | no |
| `mock_verified` | Proven only against a mock/fixture double. | no |
| `locally_verified` | Full vertical slice exercised against real local storage/providers. | yes |
| `production_ready` | `locally_verified` plus a documented contract and real end-to-end proof. | yes |
| `blocked` | Implemented, but a real dependency is missing. | no |
| `degraded` | Usable with reduced function or a documented fallback. | yes |
| `not_configured` | Implemented, but required configuration is absent. | no |
| `unknown` | Not yet probed in this environment. | no |

`available: true` in the API payload is exactly `status ∈ {locally_verified, production_ready,
degraded}`. Nothing else is offered to a caller, including Co-Director.

## What "locally_verified" required in this branch

```
UI / HTTP → application service → SQLite or filesystem → persisted
          → read back in a *new* session → failure path returns a structured code
```

Mock success never qualifies (`mock_verified` exists for that case). This is why
`downloads.queue` stays `mock_verified` even though the download engine works: the only proof is
the Playwright fixture HTTP provider, and no test performs a real multi-GB download.

---

## Matrix

| Capability | Subsystem | Baseline | Mode | Approval | Depends on | Surface |
|------------|-----------|----------|------|----------|------------|---------|
| `project.create` | project | `locally_verified` | write | no | - | `POST /api/projects` |
| `project.list` | project | `locally_verified` | read | no | - | `GET /api/projects` |
| `project.read` | project | `locally_verified` | read | no | - | `GET /api/projects/{projectId}` |
| `project.update` | project | `locally_verified` | write | yes | - | `PATCH /api/projects/{projectId}` |
| `project.delete` | project | `locally_verified` | write | yes | - | `DELETE /api/projects/{projectId}` |
| `project.duplicate` | project | `partially_wired` | write | yes | - | `POST /api/projects/{projectId}/duplicate` |
| `project.archive` | project | `partially_wired` | write | yes | - | `POST /api/projects/{projectId}/archive` |
| `project.scenes.read` | scenes | `locally_verified` | read | no | - | `GET /api/projects/{projectId}/scenes` |
| `project.scenes.create` | scenes | `locally_verified` | write | yes | - | `POST /api/projects/{projectId}/scenes` |
| `project.scenes.update` | scenes | `locally_verified` | write | yes | - | `PATCH /api/projects/{projectId}/scenes/{sceneId}` |
| `project.scenes.delete` | scenes | `locally_verified` | write | yes | - | `DELETE /api/projects/{projectId}/scenes/{sceneId}` |
| `project.scenes.reorder` | scenes | `not_implemented` | write | no | - | `-` |
| `project.scenes.active` | scenes | `ui_only` | write | no | - | `-` |
| `project.timeline.propose` | scenes | `degraded` | read | no | - | `POST /api/projects/{projectId}/timeline/propose` |
| `project.timeline.apply` | scenes | `partially_wired` | write | yes | - | `POST /api/projects/{projectId}/timeline/apply` |
| `assets.upload` | assets | `locally_verified` | write | yes | `storage.project_data` | `POST /api/projects/{projectId}/assets` |
| `assets.read` | assets | `locally_verified` | read | no | - | `GET /api/projects/{projectId}/library` |
| `assets.tag` | assets | `partially_wired` | write | yes | - | `PATCH /api/projects/{projectId}/assets/{assetId}` |
| `assets.file` | assets | `locally_verified` | read | no | - | `GET /api/assets/{assetId}/file` |
| `references.upload` | references | `locally_verified` | write | yes | `assets.upload`, `storage.project_data` | `POST /api/projects/{projectId}/assets` |
| `references.read` | references | `locally_verified` | read | no | - | `GET /api/projects/{projectId}/references/ingredients` |
| `references.attach.project` | references | `locally_verified` | write | yes | `references.read` | `POST /api/projects/{projectId}/references/ingredients` |
| `references.attach.scene` | references | `not_implemented` | write | no | - | `-` |
| `references.remove` | references | `not_implemented` | write | no | - | `-` |
| `references.exclude` | references | `locally_verified` | write | yes | - | `POST /api/projects/{projectId}/references/ingredients` |
| `references.thumbnail` | references | `not_implemented` | read | no | - | `-` |
| `references.sheet.build` | references | `partially_wired` | write | yes | `references.read`, `storage.project_data` | `POST /api/projects/{projectId}/references/sheets/build` |
| `references.ic_lora.ready` | references | `backend_only` | read | no | `comfyui.health` | `GET /api/projects/{projectId}/references/capabilities` |
| `codirector.chat` | codirector | `backend_only` | read | no | `codirector.provider` | `POST /api/codirector/chat/stream` |
| `codirector.provider` | codirector | `backend_only` | read | no | - | `GET /api/codirector/health` |
| `codirector.bible.read` | codirector | `locally_verified` | read | no | - | `GET /api/codirector/projects/{projectId}/bible` |
| `codirector.bible.propose` | codirector | `locally_verified` | write | yes | - | `POST /api/codirector/projects/{projectId}/proposals` |
| `codirector.bible.approve` | codirector | `locally_verified` | write | yes | - | `POST /api/codirector/proposals/{proposalId}/approval` |
| `codirector.vision.validate` | codirector | `not_configured` | write | no | - | `POST /api/codirector/vision/validate` |
| `codirector.vision.review` | codirector | `not_configured` | write | yes | `codirector.vision.validate` | `POST /api/codirector/vision/approve` |
| `codirector.tools` | codirector | `not_implemented` | write | no | - | `-` |
| `comfyui.health` | comfyui | `backend_only` | read | no | - | `GET /api/comfy/health` |
| `comfyui.queue` | comfyui | `backend_only` | write | yes | `comfyui.health`, `workflows.validate` | `-` |
| `comfyui.cancel` | comfyui | `partially_wired` | write | no | `comfyui.health` | `POST /api/jobs/{jobId}/cancel` |
| `comfyui.outputs` | comfyui | `backend_only` | read | no | `comfyui.health`, `storage.project_data` | `-` |
| `workflows.discover` | workflows | `locally_verified` | read | no | - | `GET /api/workflows` |
| `workflows.validate` | workflows | `locally_verified` | read | no | `workflows.discover` | `GET /api/workflows/{workflowId}/readiness` |
| `workflows.ready` | workflows | `backend_only` | read | no | `workflows.validate`, `comfyui.health` | `-` |
| `workflows.image.ready` | workflows | `backend_only` | read | no | `workflows.validate`, `comfyui.health` | `-` |
| `workflows.video.ready` | workflows | `backend_only` | read | no | `workflows.validate`, `comfyui.health` | `-` |
| `models.image.ready` | models | `backend_only` | read | no | - | `-` |
| `models.video.ready` | models | `backend_only` | read | no | - | `-` |
| `extensions.comfyui.ready` | extensions | `backend_only` | read | no | `comfyui.health` | `-` |
| `source_manager.read` | source_manager | `locally_verified` | read | no | - | `GET /api/source-manager/overview` |
| `source_manager.refresh` | source_manager | `locally_verified` | write | no | - | `POST /api/setup/components/{componentId}/refresh-source` |
| `source_manager.install` | source_manager | `partially_wired` | write | yes | `source_manager.read`, `downloads.queue` | `POST /api/setup/components/{componentId}/action` |
| `source_manager.repair` | source_manager | `partially_wired` | write | yes | - | `POST /api/setup/components/{componentId}/recommended-action` |
| `downloads.read` | downloads | `locally_verified` | read | no | - | `GET /api/downloads` |
| `downloads.queue` | downloads | `mock_verified` | write | yes | - | `-` |
| `setup.read` | setup | `locally_verified` | read | no | - | `GET /api/setup/status` |
| `setup.prepare` | setup | `partially_wired` | write | yes | `setup.read` | `POST /api/setup/prepare` |
| `health.read` | health | `locally_verified` | read | no | - | `GET /api/health` |
| `capabilities.read` | capabilities | `locally_verified` | read | no | - | `GET /api/capabilities` |
| `generation.image.queue` | generation | `backend_only` | write | yes | `comfyui.queue`, `workflows.image.ready`, `models.image.ready` | `POST /api/projects/{projectId}/imagegen` |
| `generation.video.queue` | generation | `backend_only` | write | yes | `comfyui.queue`, `workflows.video.ready`, `models.video.ready` | `POST /api/projects/{projectId}/render` |
| `generation.lipsync.queue` | generation | `backend_only` | write | yes | `comfyui.queue`, `generation.video.queue` | `POST /api/projects/{projectId}/lipsync` |
| `generation.jobs.read` | generation | `locally_verified` | read | no | - | `GET /api/projects/{projectId}/jobs` |
| `storyboard.read` | storyboard | `partially_wired` | read | no | - | `GET /api/projects/{projectId}/script` |
| `storyboard.generate` | storyboard | `backend_only` | write | yes | `generation.image.queue` | `POST /api/projects/{projectId}/storyboard/generate` |
| `director.timeline.read` | director | `partially_wired` | read | no | - | `GET /api/projects/{projectId}/scenes/{sceneId}/director` |
| `director.timeline.update` | director | `partially_wired` | write | yes | - | `PUT /api/projects/{projectId}/scenes/{sceneId}/director` |
| `editor.sequences.read` | editor | `partially_wired` | read | no | - | `-` |
| `spatial.scene.read` | spatial | `partially_wired` | read | no | - | `GET /api/projects/{projectId}/scenes/{sceneId}/spatial` |
| `virtual_stage.render` | virtual_stage | `not_implemented` | read | no | - | `-` |
| `storage.project_data` | storage | `locally_verified` | read | no | - | `app.capabilities.probes:probe_storage` |
| `storage.database` | storage | `locally_verified` | read | no | - | `app.capabilities.probes:probe_database` |

---

## Notes on the deliberately unflattering entries

**`project.scenes.reorder` — `not_implemented`.** There is no reorder route and no service
call. Scene indices are assigned on create and re-packed on delete, and nothing else moves
them. Reordering was not invented to make the matrix look complete.

**`project.scenes.active` — `ui_only`.** The focused scene lives in React state
(`studio-web/src/directorSelection.ts`). There is no `active_scene_id` column and no endpoint
to set one, so the selection does not survive a reload on another client. Adding persistence
would have been a schema decision outside this branch's scope.

**`references.remove` — `not_implemented`.** The references router exposes upsert, list,
replace, sheets, and presets; there is no `DELETE`. The supported approximation is re-upserting
with `include: false`, which is a separate, honestly-labelled capability
(`references.exclude`) rather than a removal in disguise.

**`references.attach.scene` — `not_implemented`.** Ingredients are stored once per project in
`data_dir/projects/{id}/references/ingredients.json`. `BuildSheetBody.scene_id` is accepted for
sheet builds, but ingredient records themselves carry no scene scope.

**`downloads.queue` — `mock_verified`.** The queue, pause/resume/cancel, and receipts are
exercised against the Playwright fixture HTTP provider. No test downloads a real archive, and
no capability UI triggers a download without an explicit user action.

**`source_manager.install` — `partially_wired`, degrading to `not_configured`.** Install works
for components that have a real source. The Essential Packs have no published archive, so at
runtime this reports `not_configured` with `MODEL_SOURCE_PENDING` and the action
`add_source_url`. No download URL was invented to change that.

**`virtual_stage.render` — `not_implemented`.** Virtual Stage appears in architecture
documentation. No route, service, table, or component implements it in this build.

**`codirector.tools` — `not_implemented`.** Tool registry and dispatch belong to Co-Director
M2.2. This branch publishes the capability truth source that M2.2 will read; it does not
implement orchestration.

**Generation (`generation.*`) — never better than `partially_wired` here.** Even with ComfyUI
reachable, a ready workflow, and verified weights, the best status this branch will report is
`partially_wired` with the action `run_verification_render`, because no real render was
performed in the verified environment. `production_ready` is reserved for a claim backed by an
actual end-to-end run.
