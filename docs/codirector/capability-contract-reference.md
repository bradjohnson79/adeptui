# Capability Contract Reference

**Status:** Architecture specification — binding guidance for M2.9 native suite and M2.10 add-on registration.  
**Branch context:** Written after M2.8 Capability Intelligence (conditionally accepted).  
**Runtime source of truth:** `studio-api/app/capabilities/registry.py` + live evaluation in `service.py`.  
**Versioned native baseline (comparison):** `config/capabilities/adept-ui-v1.0-native.json`

This document defines, in one place, how capabilities are identified, contracted, gated, executed, validated, approved, and versioned. It prevents drift as M2.9 and M2.10 register dozens (eventually hundreds) of capabilities across native features and add-ons.

It does **not** replace the audit matrix or HTTP payload guide. Cross-links:

| Doc | Role |
| --- | --- |
| [ADEPT_CAPABILITY_REGISTRY.md](../audit/ADEPT_CAPABILITY_REGISTRY.md) | How to change the Python registry / probes |
| [ADEPT_PRODUCTION_CAPABILITY_MATRIX.md](../audit/ADEPT_PRODUCTION_CAPABILITY_MATRIX.md) | Human baseline table |
| [ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md](../audit/ADEPT_PRODUCTION_CAPABILITY_CONTRACTS.md) | API snapshot / CapabilityOut semantics |
| [m2.10-addon-integration-contracts.md](./m2.10-addon-integration-contracts.md) | Add-on category readiness gaps |
| [m2.8-prompt.md](./m2.8-prompt.md) / [m2.9-prompt.md](./m2.9-prompt.md) | Milestone capability expectations |

---

## 1. Principles

1. **One registry.** Every user-facing or orchestrated ability must have a capability ID in the PSR (`capabilities/registry.py`).
2. **Honest status.** Buttons and types do not invent availability. Live evaluation may only lower confidence vs baseline (or resolve `unknown`).
3. **Native vs add-on.** Native capabilities use `source: native` in the versioned baseline. Add-ons must declare `source: addon` and cannot silently override an accepted native ID.
4. **Durable work uses M2.7.** Long-running / failure-prone operations map to Production Job handlers that declare required capability IDs.
5. **M2.5 owns visual validation lifecycle.** Only the vision service may clear `visualValidationPending`.
6. **Approval is metadata, not vibes.** `requires_approval` and Bible/proposal gates are explicit.
7. **Flags gate exposure.** Feature flags default off; flag-off must hide routes and prevent background work.
8. **Mock-only is not production-ready.** `mock_verified` / fixture paths must not be labeled `production_ready` or baseline `accepted` without real evidence.

---

## 2. Capability ID contract

### 2.1 Format

```text
<namespace>.<area>.<action>
```

Examples: `storyboard.generate`, `codirector.vision.validate`, `m28.sandbox.install`.

Rules:

- Lowercase ASCII, dot-separated.
- Stable once shipped; prefer new IDs over redefining meaning.
- Namespace reflects ownership (see section 2.2).
- Do not reuse an ID for a different semantic contract.

### 2.2 Namespaces in use

| Namespace | Owner / meaning |
| --- | --- |
| `project.` | Project and scene CRUD / timeline propose-apply |
| `assets.` | Asset upload/read/tag/file |
| `references.` | Reference sets, IC-LoRA readiness, timeline bindings |
| `codirector.` | Chat, Bible, tools, vision |
| `comfyui.` | Comfy health/queue/cancel/outputs |
| `workflows.` / `models.` / `extensions.` | Readiness probes |
| `source_manager.` / `downloads.` / `setup.` | Install / pack / setup |
| `generation.` | Image/video/lipsync queues |
| `storyboard.` | Storyboard generate/read |
| `director.` / `editor.` / `spatial.` | Director / editor / spatial |
| `virtual_stage.` | Virtual Stage render |
| `m28.` | M2.8 Capability Intelligence surfaces |
| `health.` / `capabilities.` / `storage.` | Platform |

**Reserved for M2.9 native suite (aspirational until registered):** `frame.`, `audio.`, `mouth.`, `lipsync.` (beyond queue), `scene.` (render), and department-specific generate IDs from [m2.9-prompt.md](./m2.9-prompt.md).

### 2.3 Registry record (runtime)

`CapabilityDefinition` fields (`studio-api/app/capabilities/models.py`):

| Field | Purpose |
| --- | --- |
| `id` | Stable capability ID |
| `display_name` | UI label |
| `subsystem` | Grouping |
| `baseline_status` | Declared honesty floor |
| `summary` | Short description |
| `dependencies` | Other capability IDs that must be available |
| `read_only` | No mutating side effects when true |
| `requires_approval` | Human gate before effective mutation / publish |
| `component_ids` | Setup / component linkage |
| `service_ref` | Backend service identifier |
| `http_ref` | Primary HTTP route hint |
| `baseline_reason` | Why baseline status was chosen |
| `scope` | Evaluation scope (global / project) |

### 2.4 Live evaluation statuses

`CapabilityStatus` values:

`not_implemented`, `ui_only`, `backend_only`, `partially_wired`, `mock_verified`, `locally_verified`, `production_ready`, `blocked`, `degraded`, `not_configured`, `unknown`

| Group | Statuses | Callable? |
| --- | --- | --- |
| USABLE | `locally_verified`, `production_ready`, `degraded` | Yes (`available: true`) |
| BLOCKING | `blocked`, `not_configured` | No |
| UNPROVEN | all others | No |

Wire shape: `CapabilityOut` (camelCase) via `GET /api/capabilities` — see audit contracts doc.

### 2.5 Versioned native baseline record

For M2.10 comparison, each native capability should also appear (or be intentionally absent) in `config/capabilities/adept-ui-v1.0-native.json` with:

```text
capabilityId, displayName, department, status (accepted|conditional|unavailable),
source (native), providerIds[], workflowAdapterIds[], jobHandlerIds[],
assetTypes[], validationMode, approvalRequired, timelineCompatible,
productionBibleCompatible, featureFlag, version, acceptanceEvidence[],
knownLimitations[]
```

Regenerate via `scripts/gen_native_capability_baseline.py` when the native suite changes. Runtime registry remains authoritative for live probes.

---

## 3. Provider contracts

Protocols in `studio-api/app/providers/contracts.py`:

| Protocol | Responsibilities |
| --- | --- |
| `CapabilityProvider` | `kind`; `capabilities()` |
| `AuthenticatingProvider` | `authenticate()`, `clear_authentication()` |
| `LifecycleProvider` | `start()`, `stop()`, `state()` |
| `ExecutionProvider` | `estimate_cost()`, `submit()`, `execution_status()`, `cancel()`, `retrieve()` |

Composites: `LocalProvider`, `ExternalApiProvider`, `AdeptCloudProvider`.

| Enum | Values |
| --- | --- |
| `ProviderKind` | `local`, `external_api`, `adept_cloud` |
| Execution / lifecycle | `ProviderState`, `ExecutionState`, `CostOwnership` |

**Rules for new providers:**

- Declare which capability IDs they satisfy.
- Local vs external must be explicit in routing metadata.
- Add-on providers must not mark their own outputs approved.
- Secrets never appear in capability details, manifests, or logs.

---

## 4. Workflow contracts

`WorkflowMetadata` (`studio-api/app/workflows/registry.py`):

| Field | Purpose |
| --- | --- |
| `key` | Stable workflow adapter ID (e.g. `image.zimage_reference`) |
| `family` / `modality` | Classification |
| `builder` / `builder_path` | Construction entry |
| `capabilities` | Feature tags (not PSR IDs) — e.g. `text_to_video` |
| `template_version` | Adapter version |
| `supported_provider_kinds` | Usually includes `LOCAL` |
| `required_inputs` | Input contract |
| `compatibility` / `validator` | Compatibility + validation hooks |

**Rules:**

- Link workflow keys from capability baseline `workflowAdapterIds`.
- Do not treat prompt text as source of truth when structured Shot Profile / camera data exists (M2.8+).
- Fixture/mock workflows must remain distinguishable from production adapters.

Native keys today include: `ltx.scene`, `ltx.simple_i2v`, `ltx.ingredients_ic_lora`, `wan.first_last_frame`, `lipsync.latentsync`, `image.txt2img`, `image.img2img_edit`, `image.zimage_reference`.

---

## 5. Validator contracts

| Concern | Owner | Capability IDs (examples) |
| --- | --- | --- |
| Visual validation lifecycle | M2.5 VisionEngine | `codirector.vision.validate`, `codirector.vision.review` |
| `visualValidationPending` clear | M2.5 only (with planId where required) | — |
| Workflow input validation | Workflow registry `validator` | via `workflows.validate` |
| Compatibility verdicts | M2.8 compat service | `m28.compat.evaluate` |

**Rules:**

- Validators must not auto-approve assets or mutate Production Bible.
- Add-on validators cannot clear M2.5 pending state directly.
- Validation mode strings in the native baseline (`m2.5_vision`, `m2.5_owns_lifecycle`, `n/a`, …) must match actual ownership.

---

## 6. Processor contracts

Deterministic processors (non-model transforms) must declare:

| Field | Meaning |
| --- | --- |
| `processorId` | Stable ID |
| `capabilityIds` | PSR IDs satisfied |
| `jobHandlerIds` | M2.7 handlers if durable |
| `inputs` / `outputs` | Asset / JSON contracts |
| `idempotent` | Safe retry behavior |
| `sandboxBound` | Whether execution is confined to sandbox roots |

Today many processors are embedded in services rather than a first-class registry. M2.9/M2.10 must not invent silent side processors outside this contract. Missing formal processor registry is an M2.10 prerequisite (see add-on contracts doc).

---

## 7. Routing metadata

Capability routing must expose enough for Co-Director / Production Recipe selection:

| Metadata | Purpose |
| --- | --- |
| Capability ID + status | Hard availability |
| Provider kind + IDs | Local vs API |
| Workflow adapter IDs | Execution path |
| Hardware / license constraints | Compat / routing filters |
| Filmmaking summary vs technical details | UX layering (M2.8 routing) |
| Shot model lock | Never silently change an existing shot model |

M2.8 routing recommendations remain suggestions until the user (or an approval-gated job) applies them.

---

## 8. Approval metadata

| Mechanism | When |
| --- | --- |
| `requires_approval` on capability | Declared need for human gate |
| M2.7 `await_approval` / mark-approval | Durable job pause |
| `ProposalService.approve` | Production Bible / canon mutation |
| Sandbox plan approve / promote approve | M2.8 install and promotion |

**Forbidden:**

- Silent approve, silent install, silent promote, silent canon mutate
- Capability self-approving its own output
- Discovery metadata mutating Bible or production model set

---

## 9. Versioning

| Layer | Versioning rule |
| --- | --- |
| Capability ID | Immutable semantics; bump via new ID if contract breaks |
| Workflow `template_version` | Adapter revisions |
| Native baseline `version` | e.g. `1.0.0-native-baseline` |
| Shot Profile / assets / Bible | Domain version tables; approved assets not overwritten |
| Feature flags | Gate new surfaces without removing old IDs |

Breaking changes require a new capability ID or an explicit migration note in milestone docs.

---

## 10. Feature flag linkage

Env pattern: `STUDIO_FEATURE_<NAME>` (default **off**).

| Flag field | Gates (examples) |
| --- | --- |
| `production_executive_v1` | M2.7 Production Executive |
| `vision_validation_v1` | M2.5 vision |
| `timeline_references_v1` | Timeline reference bindings |
| `codirector_intelligence_v2` | Intelligence v2 |
| `model_radar_v1` | Model Radar / discover |
| `sandbox_runtime_v1` | Sandbox plan/install/validate/promote |
| `virtual_stage_v1` | Virtual Stage |
| `shot_profiles_v1` | Shot Profiles |
| `production_recipe_v1` | Production Recipes |
| `location_spin_v1` | Location Spin |

**Rules:**

- New M2.9 section → dedicated flag until section Accepted.
- Flag-off: routes unavailable, no background jobs, no unnecessary provider load, no console errors.
- Baseline `featureFlag` field should name the env var or flag field consistently.

---

## 11. Job handler linkage

M2.7 `JOB_TYPE_CAPABILITIES` (`studio-api/app/codirector/executive/models.py`) maps each job type to required capability IDs. Missing or unusable capabilities must block honestly.

| JobType | Required capabilities |
| --- | --- |
| `storyboard_generate` | `comfyui.health`, `storyboard.generate` |
| `image_generate` | `comfyui.health`, `storyboard.generate` |
| `validate` | `codirector.vision.validate` |
| `create_proposal` / `await_approval` / `apply_canon` | `codirector.bible.propose` |
| `generic` | _(none)_ |
| `model_discover` | `m28.radar.discover` |
| `evaluate_compatibility` | `m28.compat.evaluate` |
| `sandbox_plan` | `m28.sandbox.plan` |
| `sandbox_install` | `m28.sandbox.install` |
| `sandbox_validate` | `m28.sandbox.validate` |
| `sandbox_promote` | `m28.sandbox.promote` |
| `recipe_stage` | `m28.recipe.execute` |
| `apply_shot_profile` | `m28.shot_profile.apply` |

**Rules for new jobs:**

1. Add `JobType` value.
2. Add `JOB_TYPE_CAPABILITIES` entry.
3. Register or update capability IDs with honest baseline.
4. Implement handler that calls real service or fixture-mode only when explicitly enabled.
5. Wire approval if mutating production or installing software.
6. Update this document and the native baseline.

---

## 12. M2.8 capability IDs (registered)

| ID | Typical HTTP / path |
| --- | --- |
| `m28.radar.discover` | `POST /api/codirector/m28/radar/discover` |
| `m28.compat.evaluate` | `POST /api/codirector/m28/compat/evaluate` |
| `m28.sandbox.plan` | `POST /api/codirector/m28/sandbox/plan` |
| `m28.sandbox.install` | approve → M2.7 job |
| `m28.sandbox.validate` | sandbox validate route |
| `m28.sandbox.promote` | promote approve → M2.7 job |
| `m28.recipe.execute` | recipe run |
| `m28.shot_profile.apply` | apply via jobs |

Related: `virtual_stage.render` (pre-existing ID; gated by Virtual Stage flag when implemented).

---

## 13. Registration checklist (native or add-on)

Before claiming a capability is production-ready:

- [ ] ID chosen under correct namespace; documented here or in milestone acceptance
- [ ] `CapabilityDefinition` added to `registry.py` with honest `baseline_status`
- [ ] Live evaluator added if status can diverge from baseline
- [ ] Provider / workflow / processor links declared
- [ ] Feature flag linked (default off until Accepted)
- [ ] M2.7 job handler linked if durable
- [ ] Validation owner declared (M2.5 when visual)
- [ ] Approval path declared (`requires_approval` / proposal / sandbox approve)
- [ ] Native baseline JSON updated (native) or add-on manifest fields complete (addon)
- [ ] Tests: registry uniqueness, flag-off, approval boundary, no silent override of native IDs
- [ ] Fixture vs real execution distinguished in acceptance evidence

---

## 14. Anti-drift rules for M2.9 / M2.10

1. No department-local queues that bypass M2.7 for durable work.
2. No duplicate capability IDs across native and add-on sources.
3. Add-ons cannot override native `accepted` capabilities without an explicit proposal and approval.
4. Announcement-only / gated / API-only classifications must remain visible in Model Radar metadata.
5. Update this reference in the same PR that adds a new capability family.

---

## Related docs
- [m2.10-addon-integration-contracts.md](./m2.10-addon-integration-contracts.md) -- Add-on category contract readiness

- [M2.8_ACCEPTANCE_REPORT.md](./M2.8_ACCEPTANCE_REPORT.md)
- [M2.8_PHASE1_TASK_REPORT.md](./M2.8_PHASE1_TASK_REPORT.md)
- [m2.9-prompt.md](./m2.9-prompt.md)
- [m2.10-prompt.md](./m2.10-prompt.md)
- [m2.9-readiness-remediation.md](./m2.9-readiness-remediation.md)
