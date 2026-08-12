# Timeline Generation Wiring Audit

- **Date:** 2026-08-07
- **Auditor:** Read-only subagent (GLM 5.2)
- **Scope:** Verify end-to-end Timeline generation wiring: UI selection → router → orchestrator → ExecutionSnapshot → request builder → provider adapter → completion. Per-area verdicts with file:line evidence.
- **Method:** Read code end-to-end. No repo/DB/service mutation. Items requiring live runtime behavior marked `NEEDS RUNTIME VERIFICATION`.
- **Verdict scope:** This report records findings only. It does NOT issue a GO/NO-GO. Final certification belongs to the primary agent.

## Per-Area Verdict Table

| # | Area | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Generate Current uses SELECTED batch | **DEFECT** | `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:146-152` |
| 2 | Generate Scene eligible-batch order + orchestratorMode honored + invalid surfaced | **OK** (with note) | `orchestrator.py:917-955`, `router.py:163-171` |
| 3 | Request contents per batch (immutable batchBlockId, startImageAssetId, prompt, duration, generatorId, seed, lineage) | **OK** | `request_builder.py:74-95`, `contracts.py:52-70` |
| 4 | Provider adapter audit (Phase 7): registry, capability flags, request builder, I2V, batch, interrupt, retake, preview, completion | **DEFECT** (UI capability gating) | `capabilities.py:17-145`, `registry.py:29-81`, `studio-web/src/components/timeline-master/TimelineInspector.tsx:821-828` |
| 4a | MiniMax H3 + LTX READY; WAN/Hunyuan capability-gated | **OK** | `capabilities.py:46-89`, `orchestrator.py:210-223,822-829` |
| 4b | Hardcoded provider-name UI conditionals that should be capability-gated | **DEFECT** | `TimelineInspector.tsx:821-828`, `TimelineInpaintWorkspace.tsx:83-91`, `TimelineEditorShell.tsx:37-40`, `ModelMenuDrawer.tsx:93,120-124,135` |

## Defect Details

### DEFECT-W1 — Generate Current silently falls back to `batches[0]` when no batch is selected

- **Root cause:** The "Generate Current" handler prefers the director selection but, when nothing is selected, silently submits `batches[0]?.id` instead of informing the creator to select a batch.
- **File:line:** `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:146-152`
- **Code:**
  ```ts
  const selectedBatchId =
    selection?.kind === "batch" && selection.id ? selection.id : null;
  const id = selectedBatchId || batches[0]?.id;
  if (!id) return;
  const result = await api.directorTimelineGenerateBatch(projectId, sceneId, id);
  ```
- **Severity:** Medium. The in-code comment acknowledges the prior bug ("Previously this always submitted batches[0]") but the silent fallback remains. A creator who clicks "Generate Current" with no selection unknowingly generates Batch 1 — wrong batch, chargeable op, no confirmation. Violates "no silent behavior" (Build Law #8) and creator-clarity principles.
- **API side is correct:** `router.py:174-176` `generate_batch` uses the path-param `batch_id` (never `batches[0]`). The defect is purely UI-side.
- **Fix direction:** When `selectedBatchId` is null, disable the button or show a message ("Select a batch to Generate Current") instead of silently falling back.

### DEFECT-W2 — "Generate Selected" submits ALL batches, not the selection

- **Root cause:** The "Generate Selected" handler passes every batch id (`batches.map((b) => b.id)`) as `batchBlockIds`, making it functionally equivalent to "Generate Full Scene" rather than a selection-scoped action.
- **File:line:** `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:160-169`
- **Code:**
  ```ts
  const result = await api.directorTimelineGenerateScene(projectId, sceneId, {
    scope: "selected",
    batchBlockIds: batches.map((b) => b.id),
  });
  ```
- **Severity:** Medium. The button label "Generate Selected" is misleading. `orchestrator.generate_scene` with `scope="selected"` filters by `batch.id not in selected` (`orchestrator.py:922-923`), so passing all ids yields all eligible batches — identical to `scope="full"` minus the Approved/CandidateReady skip. A creator intending to generate only the selected batch gets the whole scene.
- **Fix direction:** Pass only the selected batch id(s): `batchBlockIds: selection?.kind === "batch" && selection.id ? [selection.id] : []`.

### DEFECT-W3 — TimelineInspector generator dropdown is hardcoded, not capability-driven

- **Root cause:** The batch generator `<select>` lists fixed `<option>` strings instead of rendering from the capability registry (`/director-timeline/generators` → `list_generators()`). New generators added to `capabilities.py` will not appear; capability flags (`supportsTimelineGeneration`, `capabilityLabel`, `executable`) are ignored at the UI layer.
- **File:line:** `studio-web/src/components/timeline-master/TimelineInspector.tsx:821-828`
- **Code:**
  ```tsx
  <option value="">Select generator</option>
  <option value="minimax-h3-i2v-local">MiniMax H3 Image-to-Video (Local)</option>
  <option value="minimax-h3-t2v-local">MiniMax H3 Text-to-Video (Local)</option>
  <option value="minimax-h3-local">MiniMax H3 Text-to-Video (Local, legacy id)</option>
  <option value="ltx-local">LTX 2.3 (Local)</option>
  <option value="seedance-api">Seedance (API)</option>
  <option value="kling-api">Kling (API)</option>
  ```
- **Severity:** Medium. The backend gates correctly (`orchestrator.py:217-223` rejects `supportsTimelineGeneration=False`), so WAN/Hunyuan are not offered here — but only because they are manually omitted, not because the UI reads the flag. If a future capability flip enables WAN, the UI will not reflect it without a code change. This is exactly the "hardcoded provider-name UI logic that should be capability-gated" the audit asked to find. `studio-web/src/modelRegistry/contracts.ts:52` already exposes `capabilityLabel`; the dropdown should consume the registry list and filter by `supportsTimelineGeneration`.
- **Note:** `seedance-api`/`kling-api` are registry aliases (`registry.py:43-46`) and resolve correctly, so functionally OK today.

### DEFECT-W4 — Hardcoded engine→generatorId mapping in TimelineInpaintWorkspace

- **Root cause:** `generatorFromSceneEngine` hardcodes a 1:1 mapping from legacy `scene.engine` strings to generator ids rather than resolving through the registry.
- **File:line:** `studio-web/src/components/timeline-master/TimelineInpaintWorkspace.tsx:83-91`
- **Severity:** Low. This is a presentation/legacy-bridge mapping, not a generation gate, so it does not bypass capability gating. Flagged for completeness because the audit explicitly asked for hardcoded provider-name conditionals. The mapping is consistent with `capabilities.py` ids.

### NOTE-W5 — TimelineEditorShell / ModelMenuDrawer hardcode provider display names

- **File:line:** `studio-web/src/components/timeline-master/TimelineEditorShell.tsx:37-40`; `studio-web/src/components/production-dock/ModelMenuDrawer.tsx:93,100-102,120-124,135,165`
- **Verdict:** Low-risk / informational. These are display-label helpers and the production-dock model menu, not Timeline generation gates. `ModelMenuDrawer` does use `model.capabilityLabel` for readiness badges (`ModelMenuDrawer.tsx:49-55,168`) but also hardcodes `model.id === "minimax-h3"` special-casing (`:93,120,121,124,135,165`). Not in the critical generation path; flagged for the capability-gating hygiene record.

## Confirmations

### C1 — Generate Scene honors orchestratorMode and stages immutable snapshots for the rest

- `orchestrator.py:917-918`: `mode = getattr(master, "orchestratorMode", "sequential_continuity") or "sequential_continuity"`; `sequential = mode != "parallel"`.
- `orchestrator.py:936-944`: in sequential mode, batches with `idx > 0` OR when any batch is already `Generating` are routed to `stage_batch_snapshot` (status `Queued`, immutable snapshot stored, no provider submission). Concurrency = 1.
- `orchestrator.py:945-951`: parallel mode submits each eligible batch immediately with its own immutable request/snapshot.
- `orchestrator.py:932-933`: in-flight (`Generating`) batches are never re-submitted.

### C2 — Eligible-batch identification order is deterministic

- `orchestrator.py:921`: `for batch in sorted(master.batchBlocks, key=lambda b: b.order)` — order is by `batch.order`.
- `orchestrator.py:922-930`: scope filters applied (`selected`, `ready`, `current`, `full`); `full` skips `Approved`/`CandidateReady`.
- `orchestrator.py:904-905`: strict preflight errors surface as `PREFLIGHT_STRICT` and block submission.

### C3 — Invalid batches are surfaced, not silently dropped

- `orchestrator.py:202-208`: missing `generatorId` → `GENERATOR_REQUIRED` with explicit "no silent default substitution" message.
- `orchestrator.py:217-223`: `supportsTimelineGeneration=False` → `GENERATOR_UNSUPPORTED_FOR_TIMELINE`.
- `orchestrator.py:231-234`: unknown generator → `GENERATOR_UNKNOWN`.
- `orchestrator.py:236-238`: duration exceeds max → `DURATION_EXCEEDS_GENERATOR`.
- `orchestrator.py:275-288`: generator mismatch / unauthorized fallback → `GENERATOR_MISMATCH` / `FALLBACK_NOT_AUTHORIZED`.
- `orchestrator.py:290-299`: adapter validation failures → `CAPABILITY_VALIDATION_FAILED` with errors/warnings.
- `orchestrator.py:957-966`: partial failures preserved — `ok = len(errors) == 0 or len(jobs) > 0`, `partialFailure` flag, both `jobs` and `errors` returned.

### C4 — Request contents are immutable and lineage-bound

- `request_builder.py:77-78`: `batchBlockId=batch.id`, `executionSnapshotId=snapshot.id` — both immutable identities.
- `request_builder.py:79`: `generatorId=canonical` (resolved via `registry.resolve_id`, `request_builder.py:23`).
- `request_builder.py:26-28`: `prompt` joined from non-empty `promptSegments`; `negativePrompt` only when `caps.supportsNegativePrompt`.
- `request_builder.py:30-46`: `startImageAssetId`/`endImageAssetId` resolved from `sourceAnchors` (image / end_frame kinds) with label-based "end" detection.
- `request_builder.py:56-66`: generation mode gated by capability flags (`supportsImageToVideo`, `supportsEndFrame`, `supportsTextToVideo`); unsupported start frames are NOT silently passed (`gen_start = None` for T2V).
- `request_builder.py:71-72`: reference assets dropped when capability disallows (`supportsMultipleImageReferences` / `maximumReferenceImages`).
- `request_builder.py:86`: `duration=float(batch.duration.plannedDuration or 5.0)`.
- `request_builder.py:87`: `seed=None` (deterministic default; not silently invented).
- `contracts.py:52-70`: `TimelineGenerationRequest` carries `executionSnapshotId` for lineage.
- `contracts.py:107-127`: `ExecutionSnapshot` is `immutable: Literal[True] = True`; `_prepare_and_store_snapshot` (`orchestrator.py:178-180`) stores once and never updates.

### C5 — Provider adapter registry is complete and capability-honest

- `registry.py:31-54`: adapters registered for MiniMax H3 T2V, MiniMax H3 I2V, LTX, Seedance, Kling, plus cert-stub when `ADEPT_TIMELINE_CERT_STUB=1`.
- `registry.py:56-70`: `resolve_id` raises `GeneratorNotFoundError` for unknown ids — no default substitution.
- `capabilities.py:17-145`: every generator declares honest `capabilityLabel`, `executable`, `maxDurationSec`, I2V/continuation flags, and `supportsTimelineGeneration`.
  - `minimax-h3-local` (`capabilities.py:18-32`): `capabilityLabel="Testing"`, `executable=True`, `supportsTimelineGeneration=True` (default) — READY.
  - `ltx-local` (`capabilities.py:33-45`): `capabilityLabel="Certified"`, `executable=True`, `supportsTimelineGeneration=True` (default) — READY.
  - `wan-local` (`capabilities.py:46-59`): `supportsTimelineGeneration=False` — capability-gated OFF.
  - `hunyuan-video-1.5-local` / `hunyuan-video-13b-local` (`capabilities.py:60-89`): `supportsTimelineGeneration=False` — capability-gated OFF.
  - `cert-stub-local` (`capabilities.py:126-144`): only when `stub_enabled()`.

### C6 — MiniMax H3 + LTX adapters are READY and refuse silent fallback

- `minimax_h3_local.py:24-50`: T2V caps, `executable=True`, `supportsImageToVideo=False`.
- `minimax_h3_local.py:62-67`: refuses `fallbackAllowed=true`; rejects `image_to_video` mode.
- `minimax_h3_local.py:233-241`: `collect_result` returns `H3_SILENT_FALLBACK` if `ltxUsed` — refuses silent LTX substitution.
- `minimax_h3_i2v_local.py:60-73`: I2V validation requires `generationMode=image_to_video`, `startImageAssetId`, refuses T2V-only generator ids.
- `minimax_h3_i2v_local.py:119-124`: submit fails closed if Comfy graph omits `LoadImage`/`first_frame`.
- `minimax_h3_i2v_local.py:276-284`: refuses I2V→T2V workflow downgrade.
- `ltx_local.py:25-48`: caps `executable=True`, supports T2V + I2V + start/end frame.
- `ltx_local.py:55-91`: validates against caps; enqueues a real `render_scene` Job row; best-effort worker enqueue.

### C7 — Capability validation is shared and strict

- `adapter.py:33-102`: `validate_against_capabilities` enforces mode-vs-capability, reference counts, prompt-required-for-T2V, start/end image requirements, duration max, negative-prompt/seed/camera no-silent-drop, and `executable` flag.
- `adapter.py:43-44`: `fallbackAllowed=true` always warns (requires explicit creator authorization).

### C8 — Cert stub is env-gated and replaces only the execution boundary

- `stub_cert.py:41-42`: `stub_enabled()` checks `ADEPT_TIMELINE_CERT_STUB`.
- `stub_cert.py:51-54` / `capabilities.py:125-144` / `registry.py:51-54`: stub adapter + capability only registered when env flag set.
- `stub_cert.py:170-199`: `submit` records the real `TimelineGenerationRequest` to a JSONL sink and returns a deterministic `queued` job — no GPU code.
- `router.py:334-387`: cert control endpoints return 404 unless `_require_stub()` passes.

### C9 — Completion binds by batchBlockId lineage, never selection/index/output_path

- `completion.py:178-226`: `place_approved_batches_on_timeline` iterates `sorted(master.batchBlocks, key=lambda b: b.order)` and uses `batch.approvedClip.assetId` + stable `bbclip_{batch.id}` id — idempotent upsert by batch identity, not completion order.
- `completion.py:42-43`: `asset_id = str(result.outputAssetIds[0])`; `duration = float(result.duration or 5.0)`.
- `completion.py:49-51`: batch lookup by `batch_id` (immutable).
- `completion.py:54-68`: idempotency check uses `batch.approvedClip.assetId` + `executionSnapshotId` + `status == "Approved"`.

### C10 — Retake preserves prior snapshots

- `router.py:309-321`: `retake_batch` calls `orchestrator.submit_batch_generation` (which creates a NEW immutable snapshot via `_prepare_and_store_snapshot` when no `precreated_snapshot_id` is given) and explicitly sets `priorSnapshotsPreserved = True`. Prior snapshots remain in `master.executionSnapshots` untouched (`orchestrator.py:179` only adds, never replaces).

## Items Needing Runtime Verification

- **W-RT1:** Whether the cert-stub 11/11 wiring + verifier 22/22 still pass against CURRENT code was not re-executed by this audit (read-only, no test run). Code paths appear intact per C8.
- **W-RT2:** Live provider submission through MiniMax H3 / LTX adapters (Comfy graph binding, library import polling) requires a running runtime — not verifiable by static read. Adapter code paths look correct per C6.
