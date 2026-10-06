# Session Memory: 2026-09-18 — Timeline Batch Architecture: Take N regression, 12B restoration, Protection Charter, Long-Scene audit

Context: 48 hours of Timeline work on the `AdeptFilmWorks/AIVideoStudio` repo (branch work continued from `feat/character-creator-final-closure` family). Everything below is OBSERVED state, not predicted.

---

## 1. Take N regression — root cause and fix

**Symptom (owner-reported):** A 30-second Cade scene rendered as "the 15-second scene twice" — Batch 2 replayed Batch 1's full 0–30s choreography instead of continuing 15–30. Also: no video-track clip in the first 15s, and invented dialogue before Cade's authorized line.

**Root cause:** `studio-api/app/director_timeline_w46/reconcile.py::_in_window` used an inclusive **midpoint** window-membership test. The scene-level Timed Prompt (start 0, length 30) has its midpoint exactly on the B1/B2 boundary (15.0), so it matched into BOTH windows. Batch 2 received its own copy of the full-scene segment, `_is_extension_batch` saw non-empty segments and skipped continuation framing, and B2 shipped `Seconds: 0-30` verbatim.

**Fix:** window ownership = **start containment** (12B model). A segment belongs to the window that CONTAINS ITS START, half-open `[win_start, win_end)`; a boundary start belongs to the later batch. The whole-scene segment (start 0) is owned by the root window only; later windows stay inherit-render-windows and get continuation framing at runtime.

**Data repair:** one-time purge of the duplicated scene-level segment in Batch 2.

**Fence:** `tests/test_timeline_extension_duplication.py::test_prompt_window_ownership_uses_start_containment`.

## 2. NeedsDialogueRetake is designed fail-closed behavior (not a regression)

Take Q/P B2 repeatedly ended `NeedsDialogueRetake`. Inspected Take P (current take `stk_74640a37b1a4`, batch `bb_01c16da7ea2e`): the Dialogue QC diagnostics verdict is `FAIL` with reason `UNAUTHORIZED_BACKGROUND_SPEAKER` — Qwen Omni ASR observed `speaker: "unknown"` against the authorized manifest (`Cade`, line "Tell me where the Adept is!"). Continuity QC on the same batch: PASS. This is the SAME behavior as the reference Scene 12B — strict speaker-identity gate marking RENDER ≠ FINISHED. It is a creator-actionable retake state, not a defect.

Open product question (NOT actioned): whether/when to loosen the `speaker: "unknown"` ASR attribution. That is a QC-gate product decision — requires owner authorization.

## 3. Timeline Batch Architecture Protection (owner request: "safeguard the restored Timeline")

Four-layer safeguard system installed so no LLM/AI can silently alter the batch architecture:

1. **Always-on Cursor rule** — `.cursor/rules/timeline-batch-architecture-guard.mdc`: owner-protected invariants, protected files/symbols, change protocol.
2. **Canonical governance doc** — `docs/release-gate/timeline/TIMELINE_BATCH_ARCHITECTURE_PROTECTION_CHARTER.md`.
3. **Executable fence suite** — `studio-api/tests/test_timeline_architecture_guard.py` (15 new guard tests pinning the 12B-model batch architecture). All pass.
4. **In-code guard markers** — `OWNER-PROTECTED` comments on all 10 protected functions: `reconcile._in_window`, `reconcile._is_render_window_batch`, `request_builder._is_extension_batch`, `request_builder._adapt_scene_prompt_for_extension`, `r2v._add_bridge_prior_frame_slot`, `generator_capability.capability_batch_plan`, `video_intelligence/service.packet_blocks_submit`, `completion._playable_take_for_batch`, `scene_takes._heal_current_take_pointer`, `prompt_compiler._batch_window`, `timeline_builder.create_or_update_shot_from_spec`.

Final combined protection run: **117 passed, 0 failed** (architecture guard + extension duplication + temporal continuity + scene takes + production persistence + generator capability). Preceded by 135 passed (five regression suites) and 101 passed (extension fences).

## 4. Co-Director long-scene preparation — mission opened, then closed as ALREADY IMPLEMENTED

Owner mission: "Make Co-Director prepare long scenes like Scene 12B" (N batches, N distinct window-scoped prompts, Qwen refinement, no post-generation rescue). Audit verdict: **already implemented end-to-end** by the earlier generator-capability work. Mission closed at owner direction ("already been done") with no code changes.

Verified in place:

- **Capability planning up front** — `codirector/production/generator_capability.py::plan_spec_batches`: `batchCount = ceil(duration / maxSingleGenerationSeconds)` from the Timeline capability registry (H3 30s → `(0,15) (15,30)`; LTX 40s → 2×20s; partial final windows; creator-stated counts honored only within capability). No hardcoded model names.
- **N distinct prompts compiled before generation** — orchestrator calls `compile_batch_prompts`; one full execution prompt per batch, window-scoped, `CONTINUATION` framing on later batches, beat allocation via start-containment (`_beats_in_window`), cross-batch event dedup (`_dedupe_action_across_batches`) so B2 never restages B1.
- **Persistence per batch** — `timeline_builder.create_or_update_shot_from_spec` writes one window-scoped segment per batch (batch-local start 0.0), refuses to mint prompt-less batches for multi-batch scenes, prunes surplus draft batches on retry.
- **Qwen refinement reaches owned-segment batches** — `request_builder.py` `H3_CONTINUATION_WEAVE` appends the verified continuity block additively after the batch's own planned text (CD refines, Qwen observes — no raw-prose replacement).
- **Fences** — `test_codirector_generator_capability.py`, `test_scene_understanding_universal.py` (Scene 3 dialogue-in-B2, no restaging, B1 ≠ B2), `test_scene_production_persistence.py` (2 batches / 2 segments / batch-local starts), plus the 15 architecture-guard fences.

Design note: the scene-level Timed Prompt lane projection writes the compiled full prompt at 0–30 into legacy `director_json` — this is by design (the lane is the derived NLE view). `reconcile_legacy_prompts` keeps Batch 2's own segment intact via start-containment; generation input comes from batch-owned `productionPrompt`. Not the Take N regression path.

## 5. Live extension certification (Takes K → Q)

Every take walked the full chain: Batch 1 render → ContinuityBridge Applied → Qwen packet → Batch 2 submit → Batch 2 render. Batch 2 submitted only after B1 settled and the bridge was Ready. All takes end with both batches owning real assets (B2 asset present, 15.0s, correct `currentTakeId` on the newest take, scene result asset present). The 12B video-track contract holds.

---

## Verification counts (observed)

- Final protection run: **117 passed, 0 failed** (2026-09-18 ~15:46 UTC)
- Five regression suites: **135 passed**
- Extension fences: **101 passed**
- Live takes certified: K, L, M, N, O, P, Q

## Pointers

- Charter: `docs/release-gate/timeline/TIMELINE_BATCH_ARCHITECTURE_PROTECTION_CHARTER.md`
- Guard rule: `.cursor/rules/timeline-batch-architecture-guard.mdc`
- Guard tests: `studio-api/tests/test_timeline_architecture_guard.py`
- Prior session: `memory/session-2026-09-13-timeline.md`, `memory/session-2026-09-13-h3-voice-wire.md`
