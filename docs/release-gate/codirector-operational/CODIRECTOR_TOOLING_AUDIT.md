# Co-Director Operational Integrity Audit — Tooling Registry Audit

| Field | Value |
|---|---|
| Milestone | Co-Director Operational Integrity Audit |
| Sub-milestone | Tooling Registry Audit (Co-Director tool surface) |
| Date | 2026-08-07 |
| Status | AUDIT COMPLETE — repairs tracked in milestone phases c1/c2 |
| Governing law | Build Law 30 (Documentation canon) — this is the single governing audit document for the tooling-registry sub-milestone |
| Source of truth | `data/tmp/codirector-audit-sources/tool-registry-report.md` (read-only audit subagent output) |
| Scope | Co-Director tool registry, handler contracts, sanitizer, prompt-surface exposure, and persistence integrity for all 485 registered tools |
| Verification | 22 file:line citations spot-verified against the working tree (see Verification log, Section 9) |

---

## 1. Executive Summary

The Co-Director tool registry exposes **485 tools** to the model: **247 read** tools and **238 mutating** tools. The registry architecture is sound at the structural level — every tool is declared as a `ToolDefinition`, routed through a single `aliases.py` resolver, sanitized by a single `sanitize_arguments` gate, and surfaced to the model through one static instruction block. The mutating-tool preview/proposal/apply split is consistently enforced, and the audited-write escape hatch (`requires_approval=False`) is narrowly scoped and documented.

The audit identified **one dominant defect class** that accounts for almost every serious finding: **`ToolDefinition.parameters` tuples that do not match the argument contract their handlers actually read.** Because `sanitize_arguments` silently drops any key not declared in the schema, every handler that reads an undeclared key receives `None`/empty for that key at apply time — regardless of what the model emits. This single root cause produces three P0 production-blocking failures (two tools that always raise `ValueError`, one tool that silently persists empty authoritative data) and a family of P1 silent-default defects across the Bible, references, and library domains.

No defect was found in the registry plumbing itself (alias resolution, sanitizer logic, instruction generation, or the audited-write path). The defects are localized to per-tool schema/handler drift and to two `ToolPreview` field-violation clusters. All findings are repairable without touching shared infrastructure: the fixes are schema additions, handler field renames, and dead-code removal.

**Severity distribution:** 3 × P0, 9 × P1, 3 × P2, 2 × P3 (informational). See Section 5 for the rubric and per-defect severity.

**Verdict for the sub-milestone:** NO-GO until the three P0s are repaired (milestone phase c1). P1 repairs track to phase c2. P2/P3 may ride alongside c2.

---

## 2. Registry Architecture

The Co-Director tool layer is a closed pipeline. A model emission travels through exactly these stages, in order, with no bypass:

1. **Definition** — `studio-api/app/codirector/tools/definitions.py`. Each tool is a `ToolDefinition` (read or mutating) carrying `tool_id`, `kind`, `parameters` (tuple of `ToolParameter`), `requires_approval`, `pinned_resources`, and `result_char_budget`. The `ToolPreview` model (`definitions.py:107-114`) is the server-owned, human-reviewable description of what a mutating tool *would* do; it declares only `summary`, `lines`, `resourceKind`, `resourceId`, `warnings`.

2. **Registry / binding** — `studio-api/app/codirector/tools/registry.py`. Maps every tool id to a `MutationHandler` (`(preview, apply)` pair) or a read handler. Read tools and mutating tools are bound in separate maps; aliases are resolved before lookup.

3. **Alias resolution** — `studio-api/app/codirector/tools/aliases.py` (`resolve_tool_id`). Canonicalizes dotted ids (e.g. `scene.list` ↔ `list_scenes`) so legacy and canonical names both resolve to one handler. Designed to support dotted canonical ids; aliasing is intentional, not a defect.

4. **Sanitization** — `studio-api/app/codirector/tools/sanitize.py`. `sanitize_arguments` (`sanitize.py:90-110`) is the single gate between model-supplied arguments and handler code. It validates each declared parameter (type, required, min/max, length) and **drops any key not present in `ToolDefinition.parameters`**. This is the load-bearing contract for the entire defect class in Section 5: a handler reading a key the schema never declared receives nothing.

5. **Execution** — `studio-api/app/codirector/tools/execution.py`. Three paths: `execute_read` (immediate), `execute_audited` (immediate audited write, only for `requires_approval=False` tools — Wave 4 `production_plan.create_draft` only), and `propose` (never executes; computes a server-side `ToolPreview`, pins resource versions, hands a durable `tool_call` proposal to the user for approval).

6. **Prompt surface** — `studio-api/app/codirector/service.py`. `_tool_instructions()` (`service.py:304-334`) iterates **all 485** definitions from `tool_registry.all_definitions()` and builds one static text block appended to the system message at `service.py:347`. Tools are split into "Read tools (run immediately)" and "Change tools (require the user's approval)". **No capability filtering is performed at composition time** — the comment at `service.py:307-309` states this explicitly: capability probing is deferred to execution time, where a model asking for a blocked tool receives a `capability_blocked` event. This keeps chat-turn composition cheap and is the honest answer.

7. **Wire protocol** — `studio-api/app/codirector/structured_output.py`. The model does **not** use native provider tool-calling. It emits a fenced code block:

   ````tool
   {"responseType": "read_tool_call"|"mutation_proposal", "toolId": "...", "arguments": {...}}
   ````

   `extract_tool_block` (`structured_output.py:120-121`) parses the fence. Arguments are passed through untouched at this stage — validating here would duplicate the registry's schema, so the registry stays the single authority on what a tool accepts (per the function docstring, `structured_output.py:121-126`).

**Architectural health:** the pipeline is single-path, single-gate, and single-source-of-truth. There is no second sanitizer, no alternate binding map, and no parallel instruction generator. This is why the defect class is uniform: every bad tool shares the same plumbing, so the failures are uniformly traceable to per-tool schema/handler drift rather than to infrastructure.

---

## 3. Tool Count Summary

| Class | Count |
|---|---|
| Total tools | 485 |
| Read tools | 247 |
| Mutating tools | 238 |
| Audited-write tools (`requires_approval=False`) | scoped set — `production_plan.create_draft` confirmed (`definitions.py:1975`); emergency cancel paths also use the flag |
| Domains inventoried in source | 25 sections (§4.1–§4.25); this document condenses §4.18–§4.25 in Section 4 with defect flags preserved |

The 247/238 split is the authoritative count supplied with the milestone and is consistent with the `_tool_instructions()` iteration over `all_definitions()` (`service.py:314`).

---

## 4. Per-Domain Inventory (condensed)

The source report's per-domain inventory runs §4.1 through §4.25. The provided source fragment begins at §4.18 ("Continuing from §4.18"); domains §4.1–§4.17 precede the fragment and are reflected here only through the authoritative aggregate counts in Section 3. The condensed tables below cover §4.18–§4.25. **Defect flags are preserved verbatim**; full defect detail lives in Section 5.

### 4.18 Setup Guided (`setup_guided.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `setup.approve_source`, `create_install_job`, `install_component`, `install_recipe`, `link_existing_runtime`, `repair_component`, `restart_runtime`, `verify_component`, `calibrate_component`, `certify_component`, `update_component`, `remove_component`, `archive_component`, `move_installation` | mutating | yes | yes | yes | Healthy. Native store `lifecycle.*`. |

### 4.19 System & Status (`system.py`, `system_status.py`)

| Tools | Kind | Structured? | Notes |
|---|---|---|---|
| `get_provider_health`, `get_selected_model`, `get_comfyui_health`, `get_source_manager_status`, `get_reference_capabilities`, `get_engine_capabilities`, `get_cloud_render_status`, `hosted_providers.recommend` | read | yes (dicts) | Healthy. Strips endpoint/models from health (security). |
| `system.status_check`, `status_summary`, `status_check_component`, `status_list_blockers`, `status_list_warnings`, `status_recovery_options`, `deep_diagnostic` | read | yes | Healthy. |

### 4.20 Vision (`vision.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `vision_validation_status`, `vision_validation_report` | read | yes | n/a | n/a | Healthy. |
| `propose_vision_correction`, `propose_asset_bible_link`, `record_vision_review` | mutating | yes | yes | yes | Healthy. |

### 4.21 Timeline References (`timeline_references.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `get_timeline_image`, `list_timeline_images`, `get_reference_set`, `list_reference_bindings`, `build_generation_reference_package`, `suggest_reference_bindings` | read | yes | n/a | n/a | Healthy. |
| `create_reference_set_proposal`, `propose_add_reference_binding`, `propose_remove_reference_binding`, `propose_update_reference_binding`, `propose_apply_reference_preset` | mutating | yes | yes | yes | Healthy. |

### 4.22 Prompt Intelligence (`prompt_intelligence.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `prompt.enhance`, `analyze`, `benchmark_plan`, `benchmark_status`, `compare_results`, `recommend_strategy`, `review_evidence`, `certification_status` | read | yes | n/a | n/a | Healthy. |
| `prompt.apply_enhancement`, `benchmark_run`, `promote_strategy`, `rollback_strategy` | mutating | yes | yes | yes | Healthy. |

### 4.23 Production Plans (`wave4_plans.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `production_plan.list`, `get`, `get_version`, `list_versions`, `list_events`, `validate`, `get_readiness` | read | yes | n/a | n/a | Healthy. Native store `PlanService.*`. |
| `production_plan.propose`, `approve`, `reject`, `revise`, `pause`, `resume`, `cancel`, `archive`, `resolve_blocker` | mutating | yes (`_plan_payload`) | yes | yes | Healthy. |
| `production_plan.create_draft` | mutating | yes | yes | **No** (`requires_approval=False`, declared at `definitions.py:1975`) | Intentional — unapproved draft, cannot authorize production. Handler at `wave4_plans.py:251` (`apply_create_draft`); audited-write path documented in `execution.py:449-453`. |

### 4.24 Wave 3 Reads (`wave3_reads.py`)

| Tools | Kind | Structured? | Notes |
|---|---|---|---|
| `project.get_summary`, `project.list_blockers`, `scene.search`, `scene.list_characters`, `scene.list_assets`, `character.search`, `production_bible.search`, `asset.get`, `asset.list`, `asset.search`, `asset.list_by_character`, `proposal.list`, `proposal.get`, `job.list`, `job.get`, `workspace.get_active_context`, `system.list_capabilities` | read | yes | Healthy. **`asset.list` and `asset.search` bind the same handler (`registry.py:236-237`) — duplicate binding (P3, §5.5).** |

### 4.25 Storyboard (`storyboard.py`)

| Tools | Kind | Structured? | Verifies state? | Approval-gated? | Notes |
|---|---|---|---|---|---|
| `propose_storyboard_generation` | mutating | yes | yes | yes | Healthy. |

## 5. Defects (full detail, root causes, severity)

### 5.0 Severity rubric

| Severity | Meaning |
|---|---|
| **P0** | Production-blocking: tool always fails, or silently corrupts/persists malformed authoritative data. Must repair before any GO. |
| **P1** | Silent wrong behavior at runtime: lost structured data, silent defaults the model cannot override, or weak verification of authoritative state. Repair in milestone phase c2. |
| **P2** | Dead/unreachable code or cosmetic data loss that does not corrupt state. Repair alongside c2. |
| **P3** | Informational: intentional aliases, verified-clean references, wasteful-but-correct surface area. Track; no urgent repair. |

### 5.1 Schema/Handler Mismatch — handlers read undeclared parameters (P0/P1)

**Symptom.** `sanitize_arguments` (`sanitize.py:90-110`) silently drops any argument key not declared in the tool's `ToolDefinition.parameters`. The following handlers read keys that are **not declared**, so those keys are always `None`/empty/missing at apply time. The model cannot pass these values through the tool layer regardless of what it emits.

**Root cause (single, shared).** The `ToolDefinition.parameters` tuples for these tools were never updated to match the handler's actual argument contract. Either the schema is stale (missing parameters) or the handler is reading dead fields. This is the single most important class of defect for the milestone: it is not a sanitizer bug and not a handler bug in isolation — it is a **contract drift** between two files that the sanitizer faithfully enforces in one direction only.

| Tool | Handler file:line | Undeclared keys read | Schema declares | Impact | Severity |
|---|---|---|---|---|---|
| `propose_character_update` | `bible_domain.py:97, 105` | `data` | `stableId`, `entityKey`, `displayName` | Silently persists empty `CharacterData` when creating a new character entity. `CharacterData.model_validate({})` → empty object. Reports success (`bibleVersionNumber`) with malformed data. | **P0** (see §5.2.3) |
| `propose_canon_record` | `bible_domain.py:141-142` | `entityStableId`, `sceneId` | `claim` only | Canon records lose entity/scene binding — always `None`. | P1 |
| `propose_canon_supersession` | `bible_domain.py:162` | `entityStableId` | `claim`, `supersedesStableId` | Supersession loses entity binding. | P1 |
| `propose_continuity_update` | `bible_domain.py:189-193` | `entityStableId`, `sceneId`, `expectedValue`, `actualValue`, `resolved` | `aspect` only | Continuity state loses all detail except `aspect`. `expectedValue`/`actualValue` always `""`, `resolved` always `False`. | P1 |
| `propose_production_decision` | `bible_domain.py:242-244` | `rationale`, `entityStableId`, `sceneId` | `decision` only | Decision loses rationale and entity/scene binding. | P1 |
| `propose_reference_link` | `bible_domain.py:215-216` | `purpose`, `primary` | `assetId`, `targetStableId` | `purpose` defaults to `"identity"`, `primary` to `False` — model cannot override. | P1 |
| `propose_visual_language_update` | `bible_domain.py:264` | `data` | `description` only | `data` always `None` → falls back to `{"description": args.get("description","")}`. Works but `data` path is dead code. | P1 |
| `character_creator.propose_traits` | `character_creator.py:305-308` | `traits`, `provenance` | `characterId` only | **Tool always fails**: `traits` always `None` → `raise ValueError("traits array is required")` (`character_creator.py:307`). | **P0** (see §5.2.1) |
| `character_creator.propose_relationships` | `character_creator.py:348-350` | `relationships` | `characterId` only | **Tool always fails**: `relationships` always `None` → `raise ValueError("relationships array is required")` (`character_creator.py:350`). | **P0** (see §5.2.2) |
| `references.attach` | `scene_references_w6p.py:110-111` | `usageModes`, `referenceRoles` | `assetId`, `scopeType`, `scopeId`, `referenceType`, `identityId`, `identityVersionId` | Defaults to `["informational"]`/`[]` — model cannot set usage modes or roles. | P1 |
| `propose_asset_library_assignment` | `library.py:144` | `folderId` | `assetId`, `systemKey`, `path`, `query`, `entityType`, `entityName`, `entityId`, `override` | `folderId` always `None` — dead code path in handler. | P1 |

### 5.2 Tools That Always Fail or Silently Persist Bad Data (P0)

Derived from §5.1, called out explicitly because they are the production-blocking subset.

1. **`character_creator.propose_traits`** (`character_creator.py:307`) — **always raises `ValueError`** because `traits` is stripped by the sanitizer before the handler runs. The model can never successfully call this tool. **Root cause:** the `ToolDefinition.parameters` tuple declares only `characterId`; the handler reads `traits` and `provenance`, which the sanitizer drops. **Severity: P0.**

2. **`character_creator.propose_relationships`** (`character_creator.py:350`) — **always raises `ValueError`** because `relationships` is stripped. **Root cause:** same as 5.2.1 — schema declares only `characterId`; handler reads `relationships`. **Severity: P0.**

3. **`propose_character_update`** (`bible_domain.py:90-122`, empty-data path at `:97`) — **silently persists empty `CharacterData`** for new entities while reporting success with a new Bible version number. **Root cause:** schema declares `stableId`, `entityKey`, `displayName` but not `data`; the new-entity branch (`bible_domain.py:97`) calls `CharacterData.model_validate(args.get("data") or {})`, which validates an empty dict into an empty `CharacterData` and persists it. The returned `bibleVersionNumber` is a real persisted artifact that encodes bad data. This violates Build Law #8 (no silent behavior) and Law #11 (failure recovery): the tool reports success without verifying meaningful authoritative state. **Severity: P0.**

### 5.3 `ToolPreview` Field Violations — silently dropped detail (P1/P2)

**Symptom.** `ToolPreview` (`definitions.py:107-114`) declares only `summary`, `lines`, `resourceKind`, `resourceId`, `warnings`. The following handlers pass fields that do not exist on the model. In Pydantic v2 default behavior, extra fields are **silently ignored** (not stored), so the preview still constructs but the extra data is lost.

**Root cause.** The handlers were written against an intended `ToolPreview` shape that was never added to the model — i.e., the `ToolPreview` schema is narrower than its callers assume. The fix is either to extend `ToolPreview` with the missing fields (if the intent is to surface them to the human reviewer) or to remove the dead kwargs from the handlers (if the intent was abandoned). Either way the two files drifted.

| Handler file:line | Invalid field(s) | Lost information | Severity |
|---|---|---|---|
| `posecraft.py:201, 217, 246, 276, 298, 317, 336, 352, 377, 394, 418, 433, 454` (13 preview handlers) | `affectedResources=("project",)` | Affected-resource annotation (intent: signal project-level impact). All posecraft previews lose this. Summary is preserved, so previews still render. | P2 (cosmetic; summary preserved) |
| `library.py:121, 127` (`preview_propose_asset_library_assignment`) | `title=`, `diff={...}` | The diff (containing `assetId`, `targetPath`, `systemKey`, `override`) is entirely lost. Preview degrades to `summary`-only. | P1 (structured change details lost for human reviewer) |

**Impact:** Posecraft previews still render (summary is preserved), but the `affectedResources` intent is dead. The library preview is more serious — the `diff` block with the target folder path and asset ID is silently discarded, so the human reviewer sees only a summary line without the structured change details the handler intended to show.

### 5.4 Dead / Unreachable Code (P2)

| Location | Issue | Root cause | Severity |
|---|---|---|---|
| `director_timeline_tools.py:542-557` | Unreachable code block. `_resolve_camera_clip` ends with `return clip` at line 541, then has a second `return {...}` block (lines 542-557) referencing undefined variables (`project_id`, `scene_id`, `master`, `batches`, `empty_tracks`). | Leftover from a refactor: the function's return was narrowed to `clip` but the old dict-return body was not deleted. Dead code that would raise `NameError` on every local if it were ever reached. | P2 |

### 5.5 Duplicate / Overlapping Bindings (P3)

| Tool IDs | Same handler | Notes | Severity |
|---|---|---|---|
| `list_scenes` / `scene.list` | `scenes.list_scenes` | Canonical alias via `aliases.py` | P3 (intentional) |
| `get_scene` / `scene.get` | `scenes.get_scene` | Canonical alias | P3 (intentional) |
| `list_character_profiles` / `character.list` | `character_identity.list_character_profiles` | Canonical alias | P3 (intentional) |
| `inspect_character_profile` / `character.get` | `character_identity.inspect_character_profile` | Canonical alias | P3 (intentional) |
| `get_production_bible_summary` / `production_bible.get_summary` | `bible_domain.get_production_bible_summary` | Canonical alias | P3 (intentional) |
| `list_bible_entities` / `production_bible.list_entries` | `bible_read.list_bible_entities` | Canonical alias | P3 (intentional) |
| `get_bible_entity` / `production_bible.get_entry` | `bible_read.get_bible_entity` | Canonical alias | P3 (intentional) |
| `scene.list_assets` / `asset.list_by_scene` | `wave3_reads.scene_list_assets` | Canonical alias | P3 (intentional) |
| `asset.list` / `asset.search` | `wave3_reads.asset_list` (`registry.py:236-237`) | **Same handler bound to two tool IDs** — true duplicate, not just alias | P3 (wasteful surface area; not broken) |
| `runtime.preview_install` / `runtime.install` | same `(preview_install, apply_install)` pair | Intentional alias pair | P3 (intentional) |
| `runtime.preview_update` / `runtime.update`, `runtime.preview_repair` / `runtime.repair`, `runtime.preview_uninstall` / `runtime.uninstall` | same pairs | Intentional alias pairs | P3 (intentional) |

**Root cause (for the `asset.list`/`asset.search` duplicate only).** Two distinct tool names were bound to the identical handler function with no semantic difference. The alias system (`aliases.py:resolve_tool_id`) is designed to support dotted canonical IDs, so the canonical aliases above are correct by design; the `asset.list`/`asset.search` case is the only true duplicate and is wasteful model surface area rather than a functional defect.

### 5.6 Tools Reporting Success Without Verifying Authoritative State (P1)

| Tool | Handler file:line | Issue | Root cause | Severity |
|---|---|---|---|---|
| `propose_character_update` | `bible_domain.py:90-122` | Returns `{"bibleVersionNumber": new_version.version_number}`. A new Bible version is created (persistence is real), but the **content** of that version is empty/malformed `CharacterData` because `data` was stripped (§5.1). The version number is a real persisted artifact, but it encodes bad data. | Schema/handler drift (§5.1 root cause) combined with no post-mutation validation that the persisted entity is non-degenerate. This is "success without verifying meaningful state." | P0 (overlap with §5.2.3; the verification gap itself is P1) |
| `posecraft.apply_apply_pose` | `posecraft.py:340-346` | Re-persists the scene unchanged (no actual pose mutation — comment says pose is applied client-side by the Babylon viewport). Marks scene modified and returns the doc summary. | The "mutation" is a no-op at the persistence layer by design; it records intent only. This is **honest** (documented in comments) but technically reports `scene` modified without a real state change. | P1 (honest but weak) |
| `posecraft.apply_set_eyeline` | `posecraft.py:381-388` | Appends an eyeline intent string to `scene.notes` and persists. Real write, but the "eyeline" is a prose annotation, not structured authoritative state. | Handler treats a free-text annotation as authoritative state. | P1 (honest but weak) |

### 5.7 Stale Module References — verified clean (P3)

The audit flagged `app/continuity.py` (deleted, replaced by `app/continuity/` package) for verification. Result: **clean — no handler references the deleted file.**

| Import site | Resolves to | Status |
|---|---|---|
| `continuity_w5.py:7-8` | `from ....continuity import service` / `correction_service` → `app.continuity.service` (the package) | Correct, not stale |
| `scriptwriter_tools.py:8` | `from app.scriptwriter.continuity import analyze_continuity` → `app.scriptwriter.continuity` | Correct |
| `environment_reference_sheet.py:18` | `from ....environment_reference_sheet.continuity import validate_sheet` → `app.environment_reference_sheet.continuity` | Correct (different module, not the deleted one) |

**Root cause:** n/a — no defect. Severity: P3 (informational, verified clean).

## 6. Healthy Patterns

The audit confirmed several patterns that are working correctly and should be preserved during repairs:

- **Single sanitizer gate.** `sanitize_arguments` (`sanitize.py:90-110`) is the only path from model arguments to handler code. Its "drop unknown keys" behavior is intentional and correct as a security boundary — the defect is that handlers read keys the schema never declared, not that the sanitizer is wrong. Repairs must update schemas (and/or handlers), not weaken the sanitizer.
- **Preview/proposal/apply split.** Every mutating tool is bound to a `MutationHandler(preview, apply)` pair (`registry.py`). The `propose` path never executes; it computes a server-side `ToolPreview`, pins resource versions, and hands a durable `tool_call` proposal to the user. This is the correct creator-first, approval-gated model.
- **Audited-write escape hatch is narrowly scoped.** `requires_approval=False` is used only for `production_plan.create_draft` (`definitions.py:1975`) and a small set of emergency cancel paths, all documented (`execution.py:449-453`). Drafts stay non-authoritative and cannot authorize production.
- **Capability probing deferred to execution.** `_tool_instructions()` (`service.py:304-334`) emits all 485 tools statically and lets a blocked tool surface as a `capability_blocked` event at execution time. This keeps chat-turn composition cheap and is the honest answer (per the comment at `service.py:307-309`).
- **Security-conscious health reads.** `system.py` read tools strip endpoint/models from health payloads before returning them to the model.
- **Alias system is intentional.** `aliases.py:resolve_tool_id` canonicalizes dotted ids so legacy and canonical names resolve to one handler. The canonical aliases in §5.5 are by design.
- **Structured returns.** Every read tool returns structured dicts; every mutating tool returns a structured result and (where applicable) verifies state by returning the updated entity.

---

## 7. Repair Recommendations (mapped to milestone phases)

### Phase c1 — P0 (production-blocking; blocks any GO)

| # | Defect | Repair | Files |
|---|---|---|---|
| c1.1 | `character_creator.propose_traits` always raises `ValueError` (§5.2.1) | Add `traits` (array, required) and `provenance` (string, optional) to the `ToolDefinition.parameters` for `character_creator.propose_traits`. Verify the sanitizer now passes them through; add a regression test that calls the tool with a non-empty `traits` array and asserts success. | `definitions.py`; regression test in `studio-api/tests/` |
| c1.2 | `character_creator.propose_relationships` always raises `ValueError` (§5.2.2) | Add `relationships` (array, required) to the `ToolDefinition.parameters`. Same regression pattern as c1.1. | `definitions.py`; regression test |
| c1.3 | `propose_character_update` silently persists empty `CharacterData` (§5.2.3) | Add `data` (object, required for new-entity creation) to the `ToolDefinition.parameters`. Add a post-mutation validation in `apply_propose_character_update` that rejects an empty/degenerate `CharacterData` before returning a success version number (fail loud, not silent — Law #8/#11). Regression test: new-entity call with empty `data` must fail, not succeed. | `definitions.py`; `bible_domain.py:90-122`; regression test |

### Phase c2 — P1 (silent wrong behavior; tracks alongside c1)

| # | Defect | Repair | Files |
|---|---|---|---|
| c2.1 | `propose_canon_record` loses `entityStableId`/`sceneId` (§5.1) | Add `entityStableId`, `sceneId` (both optional) to the schema. | `definitions.py` |
| c2.2 | `propose_canon_supersession` loses `entityStableId` (§5.1) | Add `entityStableId` (optional) to the schema. | `definitions.py` |
| c2.3 | `propose_continuity_update` loses `entityStableId`/`sceneId`/`expectedValue`/`actualValue`/`resolved` (§5.1) | Add all five (optional) to the schema. | `definitions.py` |
| c2.4 | `propose_production_decision` loses `rationale`/`entityStableId`/`sceneId` (§5.1) | Add all three (optional) to the schema. | `definitions.py` |
| c2.5 | `propose_reference_link` cannot override `purpose`/`primary` (§5.1) | Add `purpose` (optional, default `"identity"`) and `primary` (optional, default `False`) to the schema. | `definitions.py` |
| c2.6 | `propose_visual_language_update` `data` path is dead code (§5.1) | Either add `data` (object, optional) to the schema and keep the handler's `data`-first path, or remove the dead `args.get("data")` read and keep the `description` path. Pick one; do not leave both. | `definitions.py` and/or `bible_domain.py:264` |
| c2.7 | `references.attach` cannot set `usageModes`/`referenceRoles` (§5.1) | Add `usageModes` (array, optional) and `referenceRoles` (array, optional) to the schema. | `definitions.py` |
| c2.8 | `propose_asset_library_assignment` `folderId` is dead (§5.1) | Either add `folderId` (optional) to the schema or remove the dead `folder_id=args.get("folderId")` read in the handler. | `definitions.py` and/or `library.py:144` |
| c2.9 | `library` preview loses `title`/`diff` (§5.3, P1) | Extend `ToolPreview` (`definitions.py:107-114`) with optional `title: str` and `diff: dict` fields (Pydantic v2 will then store them), OR refactor the library preview to encode the diff into `summary`/`lines`. Extending the model is preferred — the diff is structured change detail the human reviewer needs. | `definitions.py:107-114`; optionally `library.py:121,127` |
| c2.10 | `posecraft` apply_apply_pose / apply_set_eyeline are weakwrites (§5.6) | Document the intent-only semantics in the tool description shown to the model, or promote eyeline to structured state. At minimum, ensure the tool description does not imply a structural mutation. | `definitions.py` (tool descriptions); optionally `posecraft.py:340-346, 381-388` |

### Phase c2 (ride-along) — P2 (dead code / cosmetic)

| # | Defect | Repair | Files |
|---|---|---|---|
| c2.11 | `director_timeline_tools.py:542-557` dead unreachable block (§5.4) | Delete lines 542-557 (the second `return {...}` after `return clip` at 541). Add a regression test that asserts `_resolve_camera_clip` returns the clip and not a dict. | `director_timeline_tools.py:541-557`; regression test |
| c2.12 | `posecraft` previews lose `affectedResources` (§5.3, P2) | Either extend `ToolPreview` with an optional `affectedResources: list[str]` field, or remove the dead `affectedResources=("project",)` kwargs from the 13 posecraft preview handlers. If the project-level-impact signal is desired by the reviewer, extend the model; otherwise remove the kwargs. | `definitions.py:107-114` and/or `posecraft.py` (13 sites) |

### Phase c2 (track) — P3 (informational)

| # | Defect | Repair | Files |
|---|---|---|---|
| c2.13 | `asset.list` / `asset.search` bind the same handler (§5.5) | Either give `asset.search` a distinct handler with search semantics, or collapse the two tool ids into one canonical id and alias the other. Reduces model surface area. Not blocking. | `registry.py:236-237`; `definitions.py`; `aliases.py` |
| c2.14 | Stale module references (§5.7) | None required — verified clean. Track for future continuity-package moves. | n/a |

### Cross-cutting repair guardrails

- **Do not weaken `sanitize_arguments`.** The drop-unknown-keys behavior is the security boundary; repairs add keys to schemas, they do not relax the sanitizer.
- **Every schema repair gets a regression test** that calls the tool through the full sanitizer → handler path and asserts the previously-stripped key now reaches the handler (Build Law #13: repair ⇒ regression test).
- **Every P0 repair re-runs the Co-Director Playwright certification** against a disposable project (Law #28) before the sub-milestone can return to GO.
- **No silent behavior after repair.** For `propose_character_update` (c1.3), the post-mutation validation must fail loud on degenerate data, not silently persist and report success (Law #8/#11).

---

## 8. Sub-milestone Verdict

**NO-GO.** Three P0 production-blocking defects are open: two tools that always raise `ValueError` (`character_creator.propose_traits`, `character_creator.propose_relationships`) and one tool that silently persists empty authoritative data (`propose_character_update`). None of the registry plumbing is at fault; all three are per-tool schema/handler drift repairable in phase c1 without touching shared infrastructure.

The sub-milestone returns to GO only after:

1. All three c1 repairs land with regression tests.
2. The Co-Director Playwright certification passes against a fresh disposable project (Law #28).
3. Beta is refreshed and the live URLs are confirmed (Law #1).
4. This document is updated with repair evidence and re-certified as the governing doc (Law #30).

P1 repairs (c2.1–c2.10) and ride-along P2/P3 repairs (c2.11–c2.14) track to phase c2 and do not block the c1 GO, but the sub-milestone is not fully closed until c2 is complete.

---

## 9. Verification log

The source report (`data/tmp/codirector-audit-sources/tool-registry-report.md`) was spot-verified against the working tree at audit time. **22 file:line citations were checked; all are accurate.** No citation required correction. Two clarifications are noted in §9.2.

### 9.1 Citations verified correct (no drift)

| # | Citation (as in source) | Verified at | Result |
|---|---|---|---|
| 1 | `definitions.py:107-114` — `ToolPreview` fields `summary`, `lines`, `resourceKind`, `resourceId`, `warnings` | `studio-api/app/codirector/tools/definitions.py:107-114` | Correct. `class ToolPreview(BaseModel)` with exactly those five fields. |
| 2 | `sanitize.py:90-110` — unknown-key drop behavior | `studio-api/app/codirector/tools/sanitize.py:90-110` | Correct. `sanitize_arguments` iterates only `declared` params and returns `out`; unknown keys dropped. |
| 3 | `character_creator.py:307` — `raise ValueError("traits array is required")` | `studio-api/app/codirector/tools/handlers/character_creator.py:307` | Correct. Line 305 reads `traits = args.get("traits") or []`; line 307 raises. |
| 4 | `character_creator.py:305-308` — reads `traits`, `provenance` | `studio-api/app/codirector/tools/handlers/character_creator.py:305-308` | Correct. |
| 5 | `character_creator.py:350` — `raise ValueError("relationships array is required")` | `studio-api/app/codirector/tools/handlers/character_creator.py:350` | Correct. Line 348 reads `relationships`; line 350 raises. |
| 6 | `character_creator.py:348-350` — reads `relationships` | `studio-api/app/codirector/tools/handlers/character_creator.py:348-350` | Correct. |
| 7 | `bible_domain.py:97, 105` — reads undeclared `data` | `studio-api/app/codirector/tools/handlers/bible_domain.py:97, 105` | Correct. Line 97 new-entity path `args.get("data") or {}`; line 105 merge path. |
| 8 | `bible_domain.py:141-142` — reads `entityStableId`, `sceneId` | `studio-api/app/codirector/tools/handlers/bible_domain.py:141-142` | Correct. |
| 9 | `bible_domain.py:162` — reads `entityStableId` | `studio-api/app/codirector/tools/handlers/bible_domain.py:162` | Correct. |
| 10 | `bible_domain.py:189-193` — reads `entityStableId`, `sceneId`, `expectedValue`, `actualValue`, `resolved` | `studio-api/app/codirector/tools/handlers/bible_domain.py:189-193` | Correct. |
| 11 | `bible_domain.py:215-216` — reads `purpose`, `primary` | `studio-api/app/codirector/tools/handlers/bible_domain.py:215-216` | Correct. |

| 12 | `bible_domain.py:242-244` — reads `rationale`, `entityStableId`, `sceneId` | `studio-api/app/codirector/tools/handlers/bible_domain.py:242-244` | Correct. |
| 13 | `bible_domain.py:264` — reads `data` | `studio-api/app/codirector/tools/handlers/bible_domain.py:264` | Correct. |
| 14 | `scene_references_w6p.py:110-111` — reads `usageModes`, `referenceRoles` | `studio-api/app/codirector/tools/handlers/scene_references_w6p.py:110-111` | Correct. |
| 15 | `library.py:121, 127` — passes `title=`, `diff={...}` | `studio-api/app/codirector/tools/handlers/library.py:121, 127` (title); `diff` at `:123` and `:129-134` | Correct. `title=` at 121 and 127; `diff={...}` adjacent at 123 and 129-134. |
| 16 | `library.py:144` — reads `folderId` | `studio-api/app/codirector/tools/handlers/library.py:144` | Correct. `folder_id=args.get("folderId") or args.get("folder_id") or None`. |
| 17 | `posecraft.py:201, 217, 246, 276, 298, 317, 336, 352, 377, 394, 418, 433, 454` — 13 sites pass `affectedResources=("project",)` | `studio-api/app/codirector/tools/handlers/posecraft.py` (all 13 lines) | Correct. All 13 occurrences confirmed at the exact cited lines. |
| 18 | `director_timeline_tools.py:542-557` — dead unreachable block after `return clip` at 541 | `studio-api/app/codirector/tools/handlers/director_timeline_tools.py:541-557` | Correct. Line 541 `return clip`; lines 542-557 second `return {...}` referencing undefined locals. |
| 19 | `registry.py:236-237` — `asset.list` and `asset.search` both bind `wave3_reads.asset_list` | `studio-api/app/codirector/tools/registry.py:236-237` | Correct. Both lines map to `wave3_reads.asset_list`. |
| 20 | `service.py:304-334` — `_tool_instructions` iterates `all_definitions()` | `studio-api/app/codirector/service.py:304-334` | Correct. |
| 21 | `service.py:307-309` and `service.py:347` — capability comment and system-message append | `studio-api/app/codirector/service.py:307-309, 347` | Correct. Comment at 307-309; `system += "\n\n" + _tool_instructions()` at 347. |
| 22 | `structured_output.py:121` — `extract_tool_block` | `studio-api/app/codirector/structured_output.py:120-121` | Correct. `def extract_tool_block` at 120; docstring at 121. |

### 9.2 Clarifications (not corrections)

1. **`production_plan.create_draft` `requires_approval=False` location.** The source's §4.23 table cites `wave4_plans.py:251` for `production_plan.create_draft`. That line is the `apply_create_draft` **handler** and is accurate as a handler locator. The `requires_approval=False` **flag** itself is declared in the `ToolDefinition` at `definitions.py:1975` (verified via search). This document cites both: the handler at `wave4_plans.py:251` and the flag at `definitions.py:1975`. No source citation was wrong; the additional pointer aids repair.

2. **Source report truncation.** The provided source file `tool-registry-report.md` is 15,988 bytes and ends mid-sentence at §6.2 ("- `extract_tool_block` (`structured_output.py:121-`"). The truncation affects only the tail of §6.2 (the wire-protocol narrative); all defect findings (§5.1–§5.7) and the per-domain inventory (§4.18–§4.25) were intact and are preserved here in full. The cut-off citation (`structured_output.py:121`) was completed by direct inspection of `studio-api/app/codirector/structured_output.py:120-126` (verification row 22). No finding was lost to truncation; the source's §6.2 narrative was reconstructed from the live code and is consistent with the source's intact portion.

### 9.3 Verification method

Each citation was checked by reading the cited line range in the working tree (excluding `backup/` copies). Where a citation referenced a function rather than an exact line (e.g. `extract_tool_block` at `structured_output.py:121`), the function definition and its docstring were both confirmed. The 22 verified citations exceed the 10-citation minimum required by the audit task.

---

*End of governing audit document. This file is the single source of truth for the Co-Director Tooling Registry sub-milestone under Build Law 30. Supersession requires a new governing document with this one clearly marked as superseded.*


