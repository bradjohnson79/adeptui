# M3.0a Phase 3 - Co-Director Capability Coverage

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Sources | `studio-api/app/codirector/tools/registry.py`, `tools/definitions.py`, `tools/handlers/*`, `codirector/executive/*`, `codirector/m211/*`, `codirector/m214/kinds.py` |
| Question | For each native platform, what can the Co-Director actually do - and where does its authority stop? |

---

## 1. The authorized range

This is the part that matters most, so it goes first.

| Rule | Enforced by |
|------|-------------|
| The tool registry is closed. A tool that is not in `_READ_HANDLERS` or `_MUTATION_HANDLERS` cannot execute. | `tools/registry.py` - no dynamic lookup, no name-to-import resolution, no runtime registration |
| A declared tool with no binding is an import-time crash, not a runtime surprise. | `tools/registry.py::_validate_bindings` |
| Every mutating tool is a preview/apply pair that produces a **proposal**. There is no tool that writes canon directly. | All 20 entries in `_MUTATION_HANDLERS` |
| **There is no approve tool.** Approval is a human action against `/api/codirector/proposals/{id}/approve`. | Absence from the registry; `executive/handlers.py::_handle_apply_canon` returns Blocked without `proposalApproved` |
| There is no tool that enqueues a generation job. The model proposes; a human approves; the Production Executive executes. | Absence from the registry |
| The model cannot ask for a fixture success. `fixtureComplete`, `mockAdapter` and `forceMock` are stripped from every job payload at executive ingress unless the environment enables fixtures. | `executive/handlers.py::_sanitize_ingress_payload` -> `m29/providers.py::sanitize_client_payload` |
| The model receives no credential material, not even a mask. | `tools/handlers/system.py::get_cloud_render_status` |
| Specialists advise; they do not execute. | `prompts/specialists/*.md` carry `may_execute_tools: false`; asserted for the VPC in `tests/test_m213_virtual_environment_studio.py` |

The registry currently holds **31 read tools** and **20 mutation tools**, all 20 of which are
proposal-producing.

---

## 2. Verb definitions

| Verb | Means |
|------|-------|
| Read | A tool returns this platform's real state |
| Propose | A tool can create an approval-gated proposal against this platform |
| Invoke | The model can cause real execution - always indirectly, after human approval |
| Monitor | The model can observe work in flight on this platform |
| Revise | The model can amend or supersede its own earlier proposal |
| Approve | The model can approve - **NO everywhere, by design** |
| Publish | The model can push a result to the timeline, library or editor |
| Coordinate | The platform participates in multi-specialist coordination |

Values: YES / INDIRECT / PARTIAL / NO.

---

## 3. Coverage per platform

| Platform | Read | Propose | Invoke | Monitor | Revise | Approve | Publish | Coordinate |
|----------|------|---------|--------|---------|--------|---------|---------|------------|
| image | PARTIAL | INDIRECT | INDIRECT | PARTIAL | NO | NO | INDIRECT | YES |
| video | PARTIAL | NO | INDIRECT | PARTIAL | NO | NO | NO | YES |
| animation | NO | NO | NO | NO | NO | NO | NO | YES |
| refs | YES | YES | N/A | N/A | YES | NO | YES | YES |
| 3D (M2.13) | PARTIAL | NO | NO | NO | NO | NO | PARTIAL | YES |
| VP / virtual stage | NO | NO | NO | NO | NO | NO | NO | YES |
| blocking / spatial | PARTIAL | NO | NO | NO | NO | NO | NO | YES |
| camera | PARTIAL | NO | NO | NO | NO | NO | NO | YES |
| lighting | NO | NO | NO | NO | NO | NO | NO | YES |
| storyboard | YES | YES | INDIRECT | PARTIAL | YES | NO | YES | YES |
| screenplay | PARTIAL | PARTIAL | N/A | N/A | YES | NO | NO | YES |
| sound | NO | NO | NO | NO | NO | NO | NO | YES |
| timeline | PARTIAL | PARTIAL | N/A | N/A | YES | NO | PARTIAL | YES |
| edit | NO | NO | NO | NO | NO | NO | NO | YES |
| color | NO | NO | NO | NO | NO | NO | NO | NO |
| comp | NO | NO | NO | NO | NO | NO | NO | YES |
| subs | NO | NO | NO | NO | NO | NO | NO | NO |
| delivery | PARTIAL | NO | NO | PARTIAL | NO | NO | NO | YES |

`Coordinate = YES` is generous and deliberately so: it means a specialist contract exists that
owns the platform in conversation (`intelligence/contracts.py` declares 31), not that any
wiring connects that specialist to the platform's API.

---

## 4. Coverage per core system

| System | Read | Propose | Invoke | Monitor | Approve | Notes |
|--------|------|---------|--------|---------|---------|-------|
| Production Bible | YES | YES | N/A | N/A | NO | 7 read tools, 7 proposal tools including canon supersession |
| Scenes | YES | YES | N/A | N/A | NO | `create_scene`, `update_scene_title`, `set_scene_prompt` - all preview/apply |
| Timeline references | YES | YES | N/A | N/A | NO | 6 read, 5 proposal; the deepest wired surface the model has |
| Vision validation | YES | YES | N/A | N/A | NO | `vision_validation_status`, `vision_validation_report`, `propose_vision_correction`, `record_vision_review` |
| Provider / model health | YES | N/A | N/A | N/A | N/A | `get_provider_health`, `get_selected_model`, `get_comfyui_health` |
| Source Manager | YES | NO | NO | NO | NO | `get_source_manager_status` is read-only; installs are user-driven |
| Cloud render (fal.ai) | YES | NO | NO | NO | NO | `get_cloud_render_status` - new in M3.0a, section 5 |
| Jobs | PARTIAL | N/A | N/A | PARTIAL | N/A | Aggregate only - section 6 |
| Capabilities | YES | N/A | N/A | N/A | N/A | `get_engine_capabilities`, `get_reference_capabilities` |

---

## 5. `get_cloud_render_status`

Added in M3.0a Phase 2. It is the model's only window onto the fal.ai integration.

| Property | Value |
|----------|-------|
| Kind | read |
| Handler | `tools/handlers/system.py::get_cloud_render_status` |
| Returns | `provider`, `credentialState`, `cloudRenderUsable`, `verifiedAt`, `engines[]`, `guidance` |
| Never returns | The key, the masked hint, or the fingerprint |
| Engines | Sourced from `fal_catalog.list_fal_models()`, each with `mediaType` |
| Guidance | One sentence per credential state, written for the model to relay to the user |

The redaction is stricter than `GET /api/fal/key`, which does return a mask and a fingerprint
to the settings UI. The reasoning is that model output can be echoed into a chat transcript,
so the model gets the answer to "will cloud rendering work?" and nothing that identifies the
credential.

Because `FAL_IMAGE_MODELS` is empty, the tool reports four video engines and no image engines.
A model asked to recommend a fal image model has nothing to recommend, which is the correct
answer today.

---

## 6. Gaps

| Gap | Impact | Evidence |
|-----|--------|----------|
| **No per-job status tool.** `get_project_status` returns `activeJobCount` and a status label; there is no tool that reads a single job's status, progress or error. | The model can say "3 jobs are running" but cannot say which, how far along, or why one failed. Every Monitor cell above is PARTIAL or NO because of this one gap. | `project_service.py::project_status`; absence from `_READ_HANDLERS` |
| **No generation tool outside storyboard.** Image, video, lipsync and audio have no proposal tool. | The model cannot propose a render even though the Production Executive has job types for all of them. | `_MUTATION_HANDLERS` |
| **M2.9 production suite is invisible to the model.** Nine sections, no tools. | Everything in `/production-suite` is user-driven only. | `m29/api.py` has no tool bindings |
| **M2.13 / M2.8 workspaces are invisible to the model.** | The VPC specialist can advise about virtual environments but cannot read one. | No `m213`/`m28` entries in `_READ_HANDLERS` |
| **M2.14 capability IDs are registered but unwired.** 42 IDs, all `partially_wired`. | Honest, but they are a plan rather than coverage. | `m214/kinds.py` |
| **No revise path for generation proposals.** Canon proposals can be superseded; a storyboard proposal cannot be amended, only re-proposed. | Minor. | `propose_canon_supersession` has no generative equivalent |

None of these gaps is a safety hole. They are all the same shape: the model can see and
propose less than the platform can do. That is the safe direction to be wrong in, and it is
the honest state to record before M3.0b.


## Post-fix snapshot -  2026-07-27

The closed registry and approval boundary remain unchanged: the Co-Director reads/proposes but
cannot self-approve, inject fixture success, receive credentials, or silently mutate canon or
timeline. New evidence adds a real local image inspect chain, reused fal Asset provenance, real
audio import-to-timeline, and a working Bible approval path.

| Surface | Current reality |
|---|---|
| Image | Local Z-Image real artifact, Asset/Job persistence and inspect: PASS for that path. |
| Video | Reused fal Asset with provenance; no new queue proof: PARTIAL. |
| Audio/timeline | Real WAV import/promote/gain: PASS for import path; generated audio provider absent. |
| Bible | Approve/reject persistence proven: PASS for covered character proposal. |
| Provider health | Missing workspace flags now serialize: PASS. |
| Jobs/fal/export | Partial; executive and Studio job scopes differ, and no full situation export is proven. |

Remaining gaps include per-job Co-Director inspection, direct generation proposals, M2.13/M2.8
state reads, proposal revision, and all declared M2.11 specialist execution.
