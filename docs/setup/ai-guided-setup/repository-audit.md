# AI-Guided Setup Repository Audit

This audit is the hard gate for `AI-Guided Setup -> Provider Lifecycle Manager`. It documents the existing repository surfaces that already own setup catalog data, source verification, install execution, proposal gating, status propagation, capability wiring, and production-dock exposure.

## Gate outcome

Proceed with implementation only by composing the existing setup, Source Manager, capability, and production-control systems. Do not create a parallel "ready" registry, do not bypass Source Manager for installs, and do not let Co-Director execute shell/install behavior directly.

## Existing catalog and status foundations

### Setup component catalog

- Canonical file: `studio-api/app/setup/catalog.py`
- Current shape:
  - `ComponentDefinition`
  - `COMPONENTS`
  - `BY_ID`
  - `get_component()`
- Observed patterns:
  - Each component already declares `id`, `name`, `description`, `required`, sizes, dependencies, `verifier`, `installer`, and `category`.
  - Existing image-adjacent entries already include:
    - `zimage_models`
    - `qwen_image_2512_models`
  - Existing lifecycle-relevant entries already include:
    - `index_tts2`
    - `hunyuan_video_15`
    - `hunyuan_video_13b`
    - avatar runtimes
    - ComfyUI extension entries
- Constraint:
  - Provider Lifecycle Manager should extend this catalog instead of inventing a second provider catalog for setup.

### Setup verification and canonical component state

- Canonical files:
  - `studio-api/app/setup/diagnostics.py`
  - `studio-api/app/setup/status.py`
- Observed patterns:
  - `verify_component()` is the live verifier for setup components.
  - `build_status()` is the canonical state builder that maps verification/install activity into creator-facing component states.
  - Current UI-facing states are:
    - `ready`
    - `not_installed`
    - `update_available`
    - `installing`
    - `error`
    - `download_unavailable`
    - `source_pending`
  - Install jobs and setup operations are already merged into setup status.
- Constraint:
  - Lifecycle work must flow through `build_status()` and related capability probes so Setup, Source Manager, and Production Dock stay aligned.

## Install execution and trusted boundary

### Source Manager install jobs

- Canonical files:
  - `studio-api/app/source_manager/install_jobs/service.py`
  - `studio-api/app/source_manager/install_jobs/router.py`
- Key trusted entrypoints already present:
  - `create_or_resume_install()`
  - `repair()`
  - `retry()`
  - `pause()`
  - `resume()`
  - `cancel()`
  - `get_job()`
  - `jobs_for_component()`
  - `list_jobs()`
- Existing install patterns already implemented:
  - explicit confirmation gate via `confirm`
  - second confirmation gate for model downloads via `confirm_download_models`
  - custom runtime installs for `index_tts2`
  - custom runtime installs for avatar runtimes
  - queue-backed installs for `huggingface_snapshot`
  - ComfyUI extension installs with restart + probe verification
  - repair/reverify flows
- Constraint:
  - All Provider Lifecycle mutation paths must reuse these Source Manager/install-job services or equivalent existing trusted service methods.
  - Co-Director may propose and approve; Source Manager must execute.

### Source verification and assignment

- Canonical files:
  - `studio-api/app/source_manager/service.py`
  - `studio-api/app/source_manager/install_jobs/sources.py`
- Existing trusted patterns:
  - `verify_and_select()`
  - `save_verified_source_for_component()`
  - normalized source records + assignments
  - provider selection via `source_manager.registry`
  - artifact listing through provider adapters
- Constraint:
  - Source approval in lifecycle tools must terminate in these normalized source/assignment flows rather than bespoke repo or URL handling.

## Proposal gating and Co-Director tool model

### Tool definitions and registry

- Canonical files:
  - `studio-api/app/codirector/tools/definitions.py`
  - `studio-api/app/codirector/tools/registry.py`
  - reference handler pattern: `studio-api/app/codirector/tools/handlers/docker_runtime_tools.py`
- Observed patterns:
  - Every tool is declared in `TOOL_DEFINITIONS`.
  - Every declared tool must be bound in `registry.py` import-time validation.
  - Read tools execute directly.
  - Mutating tools follow proposal-gated `preview -> apply`.
  - `ToolPreview` is the server-owned review artifact for mutating requests.
- Constraint:
  - New setup lifecycle tools must be added as explicit read or mutating tool definitions.
  - Mutating lifecycle tools must follow the existing Docker runtime pattern:
    - preview explains the plan
    - apply reuses trusted backend services
    - no dynamic handler lookup
    - no direct shell execution

### Security boundary derived from current code

- Safe, existing execution owners:
  - Setup catalog and verification: `setup/*`
  - Source verification and assignment: `source_manager/*`
  - install execution: `source_manager/install_jobs/*`
  - production model listing: `production_control/*`
- Unsafe for lifecycle execution:
  - any LLM-generated script path
  - unreviewed shell commands
  - direct mutation outside the existing service boundaries
- Required implementation rule:
  - Co-Director discovers, compares, diagnoses, and proposes.
  - Source Manager or other trusted backend services execute installs/repairs/moves/removals.

## Version, certification, and update patterns already present

### Existing version-aware patterns

- `setup/status.py`
  - derives `update_available` when `available_version != installed_version`
- `setup/diagnostics.py`
  - existing verifiers already surface:
    - `pinned_revision_mismatch`
    - `updateAvailable`
    - version/revision fields
- `source_manager/install_history()`
  - persists install history entries with verification state
- `production_control/model_registry.py`
  - already distinguishes honest labels such as:
    - `Certified`
    - `Testing`
    - `Available`
    - `Unavailable`
    - `Requires Setup`
- Constraint:
  - Provider Lifecycle update awareness should be certified-registry driven and must not chase arbitrary upstream latest versions.

### Existing certification-style registries

- Relevant config already in repo:
  - `config/image-runtime/provider-registry.json`
  - `config/image-runtime/compatibility-catalog.json`
  - `config/image-workflows/certified-registry.json`
  - `config/image-workflows/production-gate.json`
  - `config/video-runtime/compatibility-catalog.json`
  - `config/video-workflows/certified-registry.json`
  - `config/video-workflows/production-gate.json`
- Constraint:
  - New lifecycle recipe/version logic should be rooted in the existing certified and compatibility registries, extended where needed, not replaced.

## Image catalog expansion evidence

### Existing image provider/runtime surfaces

- Canonical files:
  - `config/image-runtime/provider-registry.json`
  - `studio-api/app/image_runtime/provider_registry.py`
  - `studio-api/app/image_runtime/api.py`
  - `studio-api/app/production_control/model_registry.py`
- Observed patterns:
  - Provider registry already separates `local` and `cloud` image providers.
  - Existing cloud providers already represented:
    - `google_imagen`
    - `openai`
    - `kie`
    - `wavespeed`
    - `fal`
    - `black_forest_labs`
    - `stability`
  - Current Production Dock image entries already include:
    - `qwen-image-2512-local`
    - `flux-local`
    - `zimage-local`
    - hosted `flux-*` variants
- Constraint:
  - The setup catalog expansion should align component IDs, categories, and honest readiness labels with production-control and image-runtime registries.
  - Cloud Providers must remain a separate category from local installable components.

## Current UI composition constraints

### Setup Wizard

- Canonical file: `studio-web/src/components/SetupWizard.tsx`
- Observed patterns:
  - `SetupWizardPanel` currently renders:
    - `SetupSummary`
    - setup component grids for required/optional components
    - Source Manager and Runtime Manager links
    - install preflight dialog
    - install jobs
  - It already consumes `useInstallJobsPoll()` and `api.setupStatus()`.
- Constraint:
  - AI-Guided mode should sit on top of these setup/status/install-job surfaces.
  - Mode chooser must be introduced before `SetupSummary`.

### Source Manager

- Canonical file: `studio-web/src/pages/SourceManager.tsx`
- Observed patterns:
  - already shows providers, saved sources, install actions, install jobs, active downloads, and install history
  - already uses setup component status and install jobs together
- Constraint:
  - Lifecycle states such as `Certified`, `Repair Recommended`, and `Update Available` should be surfaced by extending existing setup/install data, not by bolting on an unrelated flag.

### Production Dock

- Canonical files:
  - `studio-api/app/production_control/model_registry.py`
  - `studio-web/src/components/production-dock/ModelMenuDrawer.tsx`
- Observed patterns:
  - Dock already maps setup component IDs to install chips.
  - Local image/video models already appear based on the production-control model registry.
- Constraint:
  - Installed/certified image lifecycle entries should be exposed by reusing the production-control registry and setup-driven install state.

## Existing gates and patterns to preserve

- Explicit confirmation already exists for installs.
- Large model/runtimes already support a second `confirm_download_models` gate.
- ComfyUI extensions already require post-install restart and live node probe before becoming ready.
- Setup/capability/production surfaces already prefer honest labels over optimistic labels.
- API startup already recovers stale setup operations and interrupted download/install queues in `studio-api/app/main.py`.

## Implementation rules derived from this audit

1. Extend `setup/catalog.py` and `setup/status.py` instead of creating a parallel lifecycle catalog.
2. Add lifecycle contracts under dedicated setup/lifecycle modules, but bridge all mutations to trusted Source Manager services.
3. Register Co-Director lifecycle tools in the existing definitions/registry system and use proposal-gated mutation handlers.
4. Root certified recipes and update awareness in existing config registries, especially image/video certified registries and compatibility catalogs.
5. Surface lifecycle state through existing setup status, install jobs, capabilities, and production-control model registry.
6. Keep cloud image providers separate from local installable models in both catalog and UI grouping.

## Audit verdict

The repository has enough existing structure to implement Provider Lifecycle Manager and the certified image catalog expansion without inventing a new execution path. The correct strategy is extension and composition of `setup`, `source_manager`, `codirector.tools`, `image_runtime`, and `production_control` rather than replacement.
