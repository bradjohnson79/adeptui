# Co-Director Status Cross-Check Repository Audit

This audit is the hard gate for the Status Gauge + Full-System Cross-Check work. It identifies the real systems Co-Director depends on and the existing source-of-truth endpoints or server contracts that status checks must compose.

## Scope

Status must stay creator-facing and honest:

- The frontend may only use `/api/codirector/status/*` plus SSE for status UI.
- The backend must compose existing readiness sources instead of inventing parallel provider/runtime lists.
- Missing evidence must remain `warning`, `blocked`, `not_tested`, `not_configured`, or `unknown` as appropriate. It must never be upgraded to `healthy` by assumption.

## Canonical systems and readiness sources

### 1. Studio API core

- Purpose: overall API health, partial probe failures, operator flags, Comfy summary, provider summary, registry summary.
- Source of truth:
  - `GET /api/health`
  - `GET /api/gpu/stats`
- Code anchors:
  - `studio-api/app/routers/api.py`
- Notes:
  - `/api/health` already composes Comfy reachability, capabilities snapshot, Co-Director provider health, feature flags, Bible storage probe, and partial probe failures.
  - This is the best top-level “platform pulse” source, but not enough by itself for detailed Co-Director explainability.

### 2. Capability registry and Comfy workflow readiness

- Purpose: authoritative capability blockers, callable counts, deferred counts, workflow readiness, Comfy health.
- Source of truth:
  - `GET /api/capabilities`
  - `POST /api/capabilities/refresh`
  - `GET /api/projects/{project_id}/capabilities`
  - `GET /api/comfy/health`
  - `GET /api/workflows/{workflow_id}/readiness`
- Code anchors:
  - `studio-api/app/capabilities/api.py`
- Notes:
  - This is the canonical blocker/readiness surface already used by Setup and Source Manager flows.
  - Status weighting should treat capability blockers as primary evidence, not a secondary opinion.

### 3. Co-Director provider + session binding

- Purpose: local model/provider reachability, selected model, model availability, session binding, project/scene/workspace context.
- Source of truth:
  - `GET /api/codirector/providers`
  - `GET /api/codirector/providers/{provider_id}/health`
  - `GET /api/codirector/providers/{provider_id}/models`
  - `GET /api/codirector/session-context`
- Code anchors:
  - `studio-api/app/routers/codirector.py`
- Notes:
  - Provider health is already creator-safe and should remain the single provider readiness source for Co-Director.
  - Session context is the canonical project binding signal and should drive project-status checks instead of deriving binding from frontend state.

### 4. Co-Director tool registry and proposal surface

- Purpose: tool catalog availability, project-scoped tool availability, proposal-service surface, bounded read/write execution readiness.
- Source of truth:
  - `GET /api/codirector/tools`
  - `GET /api/codirector/projects/{project_id}/tools`
  - `GET /api/codirector/projects/{project_id}/tools/availability`
  - `GET /api/codirector/projects/{project_id}/proposals`
- Code anchors:
  - `studio-api/app/routers/codirector.py`
  - `studio-api/app/codirector/tools/definitions.py`
  - `studio-api/app/codirector/tools/registry.py`
- Notes:
  - Tool registry readiness must be computed from the existing tool catalog and availability output, not from a manually maintained status list.
  - Proposal endpoints are part of the readiness path because proposal service failure should block mutating Co-Director flows.

### 5. Production Control

- Purpose: resolved production status, model resolution, queue counts, provider switching safety.
- Source of truth:
  - `GET /api/production-control/status`
  - `GET /api/production-control/models`
  - `GET /api/production-control/queue`
- Recovery-only endpoints:
  - `POST /api/production-control/providers/switch`
  - `POST /api/production-control/providers/switch/confirm`
- Code anchors:
  - `studio-api/app/production_control/router.py`
- Notes:
  - Status should consume `status`, `models`, and `queue` for read-only checks.
  - Switch endpoints are recovery actions only and require explicit confirmation.

### 6. Source Manager and install jobs

- Purpose: registered sources, provider detections, component assignments, install job queue, stalled installs, capability requirements.
- Source of truth:
  - `GET /api/source-manager/overview`
  - `GET /api/source-manager/providers`
  - `GET /api/setup/install-jobs`
  - `GET /api/setup/install-jobs/{job_id}`
  - `GET /api/setup/install-jobs/events`
  - `GET /api/source-manager/download-queue`
  - `GET /api/source-manager/install-history`
  - `GET /api/source-manager/capabilities/{capability_id}/required-components`
- Recovery-only endpoints:
  - install pause/resume/cancel/retry/repair/verify endpoints under `/api/setup/install-jobs/*`
- Code anchors:
  - `studio-api/app/source_manager/api.py`
  - `studio-api/app/source_manager/install_jobs/router.py`
- Notes:
  - Install-job stalling can be detected from existing job timestamps/state without inventing a second queue.
  - These routes should power “Setup” and “Retry issue” recovery links.

### 7. Image runtime

- Purpose: image workflow readiness, provider inventory, production gate, runtime capabilities.
- Source of truth:
  - `GET /api/image-runtime/readiness`
  - `GET /api/image-runtime/capabilities`
  - `GET /api/image-runtime/providers`
  - `GET /api/image-runtime/gate`
  - `GET /api/image-runtime/foundation`
- Code anchors:
  - `studio-api/app/image_runtime/api.py`
- Notes:
  - Status should use these runtime surfaces directly instead of synthesizing separate image-provider health rows.

### 8. Video runtime

- Purpose: certified video workflow registry, diagnostics, preflight, provider health, production gates.
- Source of truth:
  - `POST /api/video-runtime/preflight`
  - `GET /api/video-runtime/diagnostics`
  - `GET /api/video-runtime/certified-registry`
  - `GET /api/video-runtime/gate`
  - `GET /api/video-runtime/wave6p-gate`
  - `GET /api/video-runtime/hunyuan/providers`
  - `GET /api/video-runtime/hunyuan/providers/{provider_id}/preflight`
  - `GET /api/video-runtime/hunyuan/providers/{provider_id}/health`
- Recovery-only endpoints:
  - Hunyuan install/remove/repair/benchmark routes
- Code anchors:
  - `studio-api/app/video_runtime/api.py`
- Notes:
  - Provider readiness should be read from existing Hunyuan/library surfaces, not inferred from filesystem assumptions.

### 9. Voice runtime / Voice Performance M410

- Purpose: provider catalog, per-character readiness, M410 runtime availability, M410 capabilities.
- Source of truth:
  - `GET /api/voice-performance/providers`
  - `GET /api/voice-performance/characters/{character_id}/readiness`
  - `GET /api/voice-performance/m410/runtime/status`
  - `GET /api/voice-performance/m410/capabilities`
- Code anchors:
  - `studio-api/app/voice_performance/router.py`
- Notes:
  - Co-Director status should treat the M410 runtime endpoint as the runtime source, while character readiness remains a scoped evidence source when character context is available.

### 10. MAGI editor

- Purpose: MAGI readiness and production gates.
- Source of truth:
  - `GET /api/magi/readiness`
  - `GET /api/magi/gate/wave4b`
  - `GET /api/magi/gate/wave4c`
  - `GET /api/magi/gate/wave5-may-begin`
- Code anchors:
  - `studio-api/app/magi/api.py`
- Notes:
  - MAGI status should not be inferred from overlay endpoints; readiness comes from the dedicated readiness/gate contracts.

### 11. Director Timeline

- Purpose: scene-specific editorial/timeline preflight and tool surface.
- Source of truth:
  - `GET /api/director-timeline/projects/{project_id}/scenes/{scene_id}/preflight`
  - `GET /api/director-timeline/tools`
- Code anchors:
  - `studio-api/app/director_timeline_w46/router.py`
- Notes:
  - Timeline preflight is scene-scoped. If the current session has no scene, status should mark this source `not_applicable` or `not_tested`, not silently pass it.

### 12. Project Library / persistence preflight

- Purpose: storage placement and library-path readiness for Co-Director actions.
- Source of truth:
  - `POST /api/projects/{project_id}/library/preflight`
  - `GET /api/projects/{project_id}/library/codirector-context`
- Code anchors:
  - `studio-api/app/routers/extra.py`
- Notes:
  - This is the best current source for project asset persistence/storage readiness and should be used for persistence-critical checks.

### 13. Production Bible

- Purpose: versioned Bible presence and retrievability for project continuity.
- Source of truth:
  - `GET /api/codirector/projects/{project_id}/bible`
  - `GET /api/codirector/projects/{project_id}/bible/versions`
  - `GET /api/codirector/projects/{project_id}/bible/versions/{version_number}`
- Code anchors:
  - `studio-api/app/routers/codirector.py`
- Notes:
  - Version endpoints are the best live source to verify Bible persistence and version history.

### 14. Scriptwriter

- Purpose: script/document availability for project writing flows.
- Source of truth:
  - `GET /api/projects/{project_id}/scriptwriter`
  - `GET /api/projects/{project_id}/scriptwriter/documents`
  - `GET /api/projects/{project_id}/scriptwriter/documents/{document_id}`
- Code anchors:
  - `studio-api/app/scriptwriter/api.py`
- Notes:
  - There is no dedicated “scriptwriter readiness” endpoint; status must probe these lightweight read surfaces honestly and downgrade to `not_tested` or `warning` on missing evidence.

## Cross-check categories implied by the audit

The audited systems map cleanly onto the requested status categories:

- `core`: `/api/health`, `/api/capabilities`
- `project`: session-context, Bible, library preflight
- `creative_studio`: scriptwriter, MAGI, timeline, voice-performance project readiness
- `provider`: Co-Director provider health, Source Manager provider overview, video/image provider inventories
- `runtime`: Comfy health, GPU stats, image-runtime, video-runtime, M410 runtime
- `persistence`: library preflight, Bible versions, latest run history store
- `jobs`: production-control queue, install jobs, download queue
- `integration`: tool registry, project tools availability, proposal-service reachability, timeline tools

## Systems that must be treated as blocking

Per the requested contract and current repository structure, these systems must be modeled as critical blockers when they fail:

- Co-Director provider/model runtime
- project binding from session-context
- tool registry / project tool availability
- persistence/library preflight
- proposal-service path

These align with existing source surfaces and do not require inventing new readiness inputs.

## Gaps and honest handling rules

Some connected systems do not yet expose a single dedicated readiness endpoint:

- Scriptwriter readiness is inferred from document bundle/list endpoints.
- Proposal-service health is inferred from live proposals/tool availability routes and backend wiring, not from a standalone `/health` route.
- Timeline readiness is scene-scoped, so status must degrade gracefully when the session has no active scene.
- Bible presence can be `not_configured` for a project without a Bible; that should not be mislabeled as infra failure.

For these gaps, status may add lightweight probes against existing read endpoints, but it must never synthesize a fake `healthy` state without live evidence.

## Implementation guardrails derived from the audit

- Build one backend status registry that wraps these existing surfaces.
- Reuse existing response contracts where possible and redact sensitive nested fields before persisting or returning history.
- Keep recovery actions mapped to existing UI/workflow destinations or already-confirmed backend actions.
- Do not duplicate provider/model lists in status storage or frontend state.
- Treat deep diagnostics as a separate explicit run mode because some checks are slower or more contextual than the standard cross-check.

## Gate verdict

The repository audit is complete enough to proceed. The concrete readiness sources exist for all major Co-Director dependencies, and the remaining implementation should compose them behind `/api/codirector/status/*`.
