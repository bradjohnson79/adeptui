# Long-scene SOURCE REBUILD / TOTAL LEGACY PURGE — Phase 0+1

**Status:** READ-ONLY FORENSIC COMPLETE — NO EDITS  
**Machine:** BRAD-5090 (`2e617bbd-2bab-493a-a2e2-e98cb445b5cf`) hostname verified  
**Audit time (PT):** 2026-09-18 ~12:40 PM PT  
**Owner:** Timeline Generation + Comfy Pipeline Bot (crew role 2/3)  
**Mode:** Independent verify. Do not trust OpenCode. No Scene 12 generate. Comfy observe-only.

---

## 1. SMOKING GUN VERDICT

**Hypothesis (Chief):** `project_prompts_to_legacy` / `projected[0]` with `start=0`, `length=scene_duration`, `text=compiled_prompt` collapses multi-batch → one 0–scene prompt (15s rendered twice).

### Verdict: **NOT CONFIRMED as live code** — **CONFIRMED as former architecture (removed)**

| Claim | Live evidence |
|---|---|
| Trailing rewrite of `projected[0]` to `(0.0, scene_duration, compiled_prompt)` in `timeline_builder` | **ABSENT.** Comment-only at `codirector/production/timeline_builder.py` L666–675 documents the *former* trailing block and forbids post-processing the lane. Current path ends at `store.save_master(...)`. |
| `project_prompts_to_legacy` re-anchors/stretches to full scene | **ABSENT.** `director_timeline_w46/reconcile.py` L456–521: window projection only (`w_start + seg.start`, `seg.length`). Docstring L471–478 explicitly forbids re-anchor / stretch under REBUILD LAW. |
| Collapse still causes 15s×2 via this exact rewrite | **NOT supported by live source.** If 15s×2 still reproduces, cause is residual dual authority / empty-segment inheritance / duration framing — not the deleted `projected[0]` rewrite. |

### Residual dual-path risk (PARTIAL — still live)

Generation still compensates for scene-level / empty-batch cases:

- `generation/request_builder.py` L597–667: if batch has no own segment text → load scene-level Timed Prompt from **legacy** `director_json.prompt_segments`; root scopes / extension adapts. This is downstream compensation architecture Chief asked to remove, not the deleted collapse itself.
- `reconcile_legacy_to_master` still wired on load/save paths (orchestrator ×3, `routers/api.py` ~1100).
- `scene.prompt = compiled_prompt` still written on CD prepare (`timeline_builder.py` L371/380) — scene-row dual prompt authority.
- `has_scene_level_timed_prompt` still present (`reconcile.py` L400–409).

**Classification for Phase 2:** remove remaining **legacy↔master reconcile on generation path** and **scene-level prompt inheritance** so Timeline executes Co-Director batch windows only — do not reintroduce compensation.

---

## 2. FILE CLASSIFICATION

| Path | Class | Ownership |
|---|---|---|
| `codirector/production/timeline_builder.py` | BUILDER | **OWNED_BY_US** (CD prepare → master batches) |
| `director_timeline_w46/reconcile.py` | RECONCILE + PROJECTION | **OWNED_BY_US** — purge target |
| `director_timeline_w46/orchestrator.py` | GENERATION / RECONCILE callers | **OWNED_BY_US** |
| `director_timeline_w46/generation/request_builder.py` | GENERATION (prompt fidelity) | **OWNED_BY_US** — remove scene-level inheritance |
| `director_timeline_w46/generation/completion.py` | TRACK (place modern video clips) | **OWNED_BY_US** |
| `director_timeline_w46/contracts.py` | TRACK / schema | **OWNED_BY_US** (+ Systems if Take schema migrate) |
| `director_timeline_w46/scene_takes.py` | TRACK / stitch identity | **SHARED_COORDINATE** with Systems |
| `director_timeline_w46/scene_stitch.py` / `scene_publish.py` | STITCH | **OWNED_BY_US** (stitch from current-Take modern clips) |
| `director_timeline_w46/continuity.py` | GENERATION continuity | **OWNED_BY_US** |
| `director_timeline_w46/store.py` | persistence | **OWNED_BY_US** |
| `director_timeline_w46/visual_range.py` | TRACK / retake range | **OWNED_BY_US** |
| `director_timeline_w46/current_take.py` | TRACK | **SHARED_COORDINATE** Systems |
| `routers/api.py` (reconcile on director save) | RECONCILE entry | **OWNED_BY_US** for generation path; FE contract with Timeline UX |
| `codirector/production/generator_capability.py` | windows via `maxSingleGenerationSeconds` | **NOT_OURS** (Co-Director) — consume only |
| `codirector/production/prompt_compiler.py` | batch_prompts | **NOT_OURS** (Co-Director) |
| `codirector/production/orchestrator.py` | CD production | **NOT_OURS** |

---

## 3. MODERN VIDEO-TRACK FIELD STATUS

From `generation/completion.py` L613–625 (live):

| Field | Status |
|---|---|
| `media_type=video` | **PRESENT** on placed clips |
| `metadata.sourceBatchId` | **PRESENT** (= batch.id) |
| `metadata.sceneTakeId` | **PRESENT** (current take id) |
| `assetId` | **PRESENT** via clip asset binding (completion path) |
| `start` / `length` | **PRESENT** (scene-absolute cursor placement) |

Gap to verify in Phase 2 prove: reload persistence of metadata through FE/NLE; stitch consumes **current-Take** modern clips only (`scene_takes` / `sceneStitch.sourceBatchIds`).

---

## 4. RECOMMENDED PHASE 2 SURFACES (owned only — no edits yet)

1. **Stop generation-path reconcile** — remove/gate `reconcile_legacy_to_master` from generate/load paths that can re-stretch master from a collapsed legacy lane; keep read-only migration path if Systems needs it separately.
2. **One projection or none** — either delete master→legacy as generation authority or make it display-only; generation must read `batch.promptSegments` only (already mostly true for H3 Timed Prompt).
3. **Delete empty-batch scene-level inheritance** in `request_builder` (`_scene_level_timed_prompt` / `_adapt_scene_prompt_for_extension` as primary path) once builder always writes per-batch window prompts (builder already does under long-scene law when `batch_prompts` supplied).
4. **H3 R2V slot fidelity** — capture actual asset IDs reaching adapter (existing r2v path); prove against CD refs.
5. **Stitch** — current-Take modern clips only; no legacy clip projection.
6. **Live cert** (when Chief GO): 30s H3 = 2 batches / 2 prompts / 2 continuous clips; 45s = 3-batch; reload; no mock as live. Comfy BEFORE/AFTER/RESTARTED report.

Coordinate: Co-Director owns `batch_prompts` + `maxSingleGenerationSeconds` windows; Systems owns Take/revision schema migration — no overlapping edits.

---

## 5. COORDINATION ASKS

- **Co-Director:** confirm every multi-batch prepare always supplies `batch_prompts[N]` + `batchWindows` from capability registry (refuse even-split already in builder L406+).
- **Systems:** any Take/job schema change for `sceneTakeId` durability — declare ownership boundary before Gen edits contracts.
- **Chief:** GO/NO-GO on Phase 2 given smoking gun already excised; residual work is **purge dual authority + inheritance compensation**, not re-delete `projected[0]`.

---

## 6. END BLOCK

```
PHASE 0+1 COMPLETE — NO EDITS
SMOKING GUN LIVE: NOT CONFIRMED (former projected[0] rewrite REMOVED; window projection only)
RESIDUAL: reconcile_legacy_to_master + request_builder scene-level inheritance + scene.prompt dual authority
MODERN TRACK: media_type/sourceBatchId/sceneTakeId PRESENT on completion place
NEXT: await Chief GO for Phase 2 owned purge surfaces listed above
COMFY: observe-only this phase — not touched
SCENE 12: HOLD
```
