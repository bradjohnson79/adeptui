# TIMELINE BATCH ARCHITECTURE — OWNER PROTECTION CHARTER

Status: **CANONICAL** (single governing document for the protected Timeline
batch architecture)
Established: 2026-09-18
Certified by: Live Take Q — 30-second / 2-batch Cade Scene 3 (ffprobe 30.048s,
stitch A+B, seam-verified frames)
Reference model: Korri Anadriya **Scene 12B** (`d774a22f-2b02-…`, Take A)
Authority: Adept UI owner (Brad) — **express authorization required per change**

---

## 1. Why this charter exists

Between Korri Anadriya Scene 12B (working) and Cade Scene Take N, uncommitted
agent modifications silently altered the Timeline batch setup: batch segments
were reassigned (Batch 1 stretched to full scene; later batches wiped), prompt
projection filtered later batches out of the UI lane, visual-track placement
preferred stale assets, and the current-take pointer went stale. The result was
the "15-second scene twice" regression plus invented dialogue. Root-cause
repairs restored the 12B behavior and Take Q certified the restoration live.

This charter makes that architecture **explicit, testable, and
owner-controlled** so any future agent/LLM modification is detectable and
unauthorized changes cannot silently land.

## 2. The protected architecture (12B model)

### 2.1 Batch decomposition — capability-driven, not hardcoded

- `app/codirector/production/generator_capability.py` resolves
  `maxSingleGenerationSeconds` from the generator capability registry
  (`maxDurationSec` or largest `supportedDurations`). It raises
  `GeneratorCapabilityError` when a generator declares neither — it never
  guesses.
- `capability_batch_plan` builds ordered `[start, end)` windows:
  `count = ceil(duration / maxWindow)`, final window partial (no padding),
  contiguous and gap-free.
- **Invariant**: no per-model-name batching logic anywhere; adding a generator
  requires only capability data.

### 2.2 Prompt-window ownership — start containment

- `app/director_timeline_w46/reconcile.py::_in_window` assigns a prompt
  segment to the window containing its **start** (half-open `[start, end)`).
  A segment starting exactly at a boundary belongs to the **later** batch.
- The scene-level Timed Prompt (start 0, length 30) belongs to the **root
  window only**. Later batches with no own segment are **inherit-render-
  windows** (`_is_render_window_batch`), and get continuation framing at
  request-build time.
- **Invariant**: the scene-level Timed Prompt is never duplicated into
  extension batches. (The Take P regression: midpoint matching put it in both
  windows; B2 then shipped `Seconds: 0-30` verbatim.)

### 2.3 Every batch gets its own complete execution prompt

- `app/codirector/production/prompt_compiler.py` compiles per-batch prompts
  scoped to the batch's temporal window only. The scene-level intent stays
  authoritative; the generator receives batch-specific execution text.
- Root batch scoping (`request_builder.py::_scope_root_batch_prompt`) and
  extension adaptation (`_adapt_scene_prompt_for_extension`) reframe inherited
  scene text at request build.
- **Invariant**: B1 of a 30s/2-batch scene ships `Seconds: 0-15. This segment
  renders only the first part of the scene…`; B2 ships `Seconds: 15-30. This
  segment continues the scene from 15s to 30s.` — never `Seconds: 0-30` on
  either.

### 2.4 Recursive Batch N → N+1 continuity

- Every completed batch is reviewed by Qwen Omni as a full video
  (`TemporalContinuityPacket`), stamped with `reviewedAssetId` so historical
  takes cannot contaminate.
- The packet gate (`video_intelligence/service.py::packet_blocks_submit`,
  `ensure_temporal_packet_before_submit`) resolves the predecessor asset via
  `current_source_batch_asset_id` (current-take membership), **not**
  `approvedClip.assetId`. Batch N+1 must not submit before the packet is
  `ready` (bounded retry) or the fail-closed degraded path fires.
- Visual handoff: `prior_frame` r2v slot = Batch N's actual last frame
  (`r2v.py::_add_bridge_prior_frame_slot`). Semantic handoff: Qwen observed
  state woven additively into the CONTINUATION block — observation, never
  authorship; authority reconciliation (`video_intelligence/authority.py`)
  filters invented characters/dialogue into artifacts.
- **Invariant**: no silent fallback from review-failure to root-regeneration;
  degraded packets never pretend continuity intelligence exists.

### 2.5 Take identity, visual track, stitch

- Every segment belongs to the same Scene Take; no per-segment take minting;
  no historical-take asset reuse.
- `_playable_take_for_batch` prefers current-take membership over stale
  `approvedClip`; `place_approved_batches_on_timeline` stamps
  `media_type="video"` + `metadata.sourceBatchId`; `make_current_take`
  re-places the visual track on take switch; `_heal_current_take_pointer`
  heals dead current pointers only (healthy older current is never stolen).
- `assemble_take_result` stitches **A then B** in member order; provenance
  records `sourceAssetIds` in stitch order.

### 2.6 Fail-closed dialogue/continuity states

- `NeedsDialogueRetake` + `UNAUTHORIZED_BACKGROUND_SPEAKER` are legitimate
  fail-closed states (RENDER ≠ FINISHED). Scene 12B itself ships in this
  state. QC observations never rewrite Manifest authority; speaker labels
  like "unknown" from non-diarized ASR are data, not authorization to relax
  the gate.

## 3. Protected files and functions

Changes to these require owner authorization (emergency exception in §5):

| File | Protected symbols |
|---|---|
| `studio-api/app/director_timeline_w46/reconcile.py` | `_in_window`, `_is_render_window_batch`, `has_scene_level_timed_prompt`, `batch_inherits_scene_timed_prompt`, `project_prompts_to_legacy`, `reconcile_legacy_prompts` |
| `studio-api/app/director_timeline_w46/generation/request_builder.py` | `_is_extension_batch`, `_extension_window`, `_adapt_scene_prompt_for_extension`, `_scope_root_batch_prompt`, `_frames_full_scene`, `_batch_windows_for_prompt` |
| `studio-api/app/codirector/production/generator_capability.py` | whole module |
| `studio-api/app/codirector/production/prompt_compiler.py` | `_batch_window`, `compile_batch` (window_note wording + en-dash contract) |
| `studio-api/app/codirector/production/timeline_builder.py` | `create_or_update_shot_from_spec` (per-batch window segments, batch-local `start: 0.0`) |
| `studio-api/app/codirector/video_intelligence/service.py` | `packet_blocks_submit`, `ensure_temporal_packet_before_submit`, `review_completed_batch` |
| `studio-api/app/codirector/video_intelligence/worker_client.py` | `_observation_from_payload` (confidence coercion robustness) |
| `studio-api/app/director_timeline_w46/generation/r2v.py` | `_add_bridge_prior_frame_slot` |
| `studio-api/app/director_timeline_w46/generation/completion.py` | `_playable_take_for_batch`, `place_approved_batches_on_timeline` |
| `studio-api/app/director_timeline_w46/scene_takes.py` | `_heal_current_take_pointer`, `sync_rendering_take`, `make_current_take`, `assemble_take_result` |

## 4. Fence suites (must pass before any protected change ships)

```
studio-api/tests/test_timeline_extension_duplication.py   # includes start-containment fence
studio-api/tests/test_temporal_continuity.py
studio-api/tests/test_scene_takes.py
studio-api/tests/test_scene_production_persistence.py
studio-api/tests/test_codirector_generator_capability.py
```

Run (repo root):

```powershell
studio-api\.venv\Scripts\python.exe -m pytest tests/test_timeline_extension_duplication.py tests/test_temporal_continuity.py tests/test_scene_takes.py tests/test_scene_production_persistence.py tests/test_codirector_generator_capability.py -q
```

Any behavioral change to a protected symbol must add/update a pinning test in
the same change (Build Law #13).

## 5. Change protocol (for agents)

1. **Scope check** — does the task touch a §3 symbol or a §2 invariant?
   If no, this charter does not apply.
2. **Authorization** — if yes, the task prompt must explicitly authorize the
   specific change. Ask the owner if ambiguous. Do not infer authorization
   from generic phrases like "fix the timeline".
3. **Fences** — run the §4 suites before and after.
4. **Repair ⇒ fence** — pin new behavior with a test.
5. **Live proof** — behavioral changes require a real take with per-batch
   shipped-prompt evidence, gate evidence, and stitch evidence.
6. **Report** — list changed protected files, fence results, and live
   evidence in the completion report.

### 5.1 Emergency exception

A live production failure may be minimally repaired before authorization ONLY
if the repair preserves every §2 invariant. The emergency must be reported
immediately with exact diff + fence results and is subject to owner rollback.

## 6. Unauthorized-change detection & recovery

If fences fail in a way that indicates an architecture change (not a flaky
test), or live behavior regresses to duplication/full-scene prompts:

1. STOP. Do not adapt to the changed behavior; do not write compensating code.
2. Identify the exact file/symbol and diff vs the §2 invariant.
3. Report: `UNAUTHORIZED TIMELINE ARCHITECTURE CHANGE DETECTED — <file>:<symbol>: <observed> vs <invariant>`.
4. Restore the invariant (git history or §2 definition), re-run fences, and
   re-certify live before returning GO.

## 7. Current live certification state

- **Take Q** (Cade Scene 3, `d0162b33-9ba6-…`): B1 `Seconds: 0-15` scoped,
  packet `tcp_01f3d9c8546b` ready reviewing B1's current-take asset, B2
  `Seconds: 15-30` continuation + Qwen weave + prior_frame `be0e1cf7…`,
  stitch A+B = 30.048s (`af08b8a5-9299-…`), visual track = two video clips
  (0–15, 15–30) resolving Take Q assets.
- Disclosed non-blocker: `NeedsDialogueRetake` on B2 from
  `UNAUTHORIZED_BACKGROUND_SPEAKER` with `speaker: "unknown"` (non-diarized
  ASR); transcript matches Cade's authorized line verbatim. Scene 12B ships
  in the same state — fail-closed gate working as designed.
- Regression fences: 101 + 24 passing at certification time.
