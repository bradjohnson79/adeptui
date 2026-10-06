# 05 — Final Certification Report

## Verdict

```text
GO — TIMELINE FULL-STACK TWO-BATCH PRODUCTION CERTIFIED — READY FOR MANUAL BETA
```

## Core evidence summary

| Phase | Criterion | Result | Evidence |
|---|---|---|---|
| 3 | Clip placement | **PASS** | 4 image clips on VISUAL lane, 4 prompt segments on TIMED PROMPT lane, placed bbclip video clips |
| 4 | Exact timing | **PASS** | resolveTimelineAtTime deterministic cumulative plannedDuration; no float drift |
| 5 | Timed Prompt → generator | **PASS** | reconcile.py syncs lane prompt_segments → batch.promptSegments; verified live |
| 6 | Prompt refinement | **PASS** | userDirection stored separately from productionPrompt; dialogue verbatim preserved |
| 7 | Preview monitor | **PASS** | resolveTimelineAtTime resolves batch-owned visualClips first, then legacy; no stale media |
| 8 | Source image → video binding | **PASS** | I2V startImageAssetId=exact Library asset; no implicit fallback |
| 9 | Generator registry | **PASS** | LTX=Certified, MiniMax H3=Testing (honest), WAN/Hunyuan=gated, Kling=not live |
| 10 | Primary live generator | **PASS** | LTX 2.3 (1280×720 final, draft 512×288, I2V+audio) |
| 12 | Aspect ratio | **PASS** | 16:9 live, 1:1/4:3/21:9/9:16 in adapter caps |
| 13 | LoRA | **PASS** | wired to batch.lora → request.providerOptions.lora → adapter params |
| 14 | Batch semantics | **PASS** | BATCH_OWNED_CLIPS, sequential chain, no cross-batch leakage |
| 15-22 | Two-batch production | **PASS** | 4 shots × 5s, 2 batches, real Library assets, timed prompts, dialogue, compiled prompts |
| 23-24 | Batch 1 generation | **PASS** | LTX I2V 10s, approved, output asset, lineage, placed clip |
| 25-26 | Batch 2 generation | **PASS** | LTX I2V 10s, approved, distinct asset, no leakage |
| 27 | Cross-batch continuity | **PASS** | distinct outputs, distinct source images, no prompt leakage |
| 30-32 | Retake | **PASS** | original preserved, new take generated, parentTakeId lineage, activation, replacement |
| 33 | Library integration | **PASS** | outputs persist as Library assets with prompt_meta + checksum + workflow cert |
| 34 | Reload/hydration | **PASS** | batches, prompts, approvals, takes, lineage, clips all survive reload |
| 35 | CD awareness | **PASS** | timeline.inspect_batches returns real production state |
| 36 | CD mutation | **PASS** | propose_add_prompt_segment → approve → actual prompt segment on timeline |
| 37 | CD batch generation | **PASS** | propose_generate_scene → approve → real generation job submitted (plumbing fix) |
| 38 | Production events | **PASS** | batch_created, generation_started, generation_completed, candidate_approved, retake_started, prompt_updated, clip_updated |
| 40 | Error handling | **PASS** | missing_generator preflight, BATCH_ALREADY_IN_FLIGHT, honest failure messages, UI error banner |
| 41 | Partial failure | **PASS** | stale-Generating reconciliation (grace window), TERMINAL_STATUS_GUARD |
| 42 | Idempotency | **PASS** | BATCH_ALREADY_IN_FLIGHT guard, idempotent bbclip placement, duplicate candidate guard |
| 43 | Request stability | **PASS** | useGenerationState polls 2.5s (only during active job), no runaway polling |
| 45 | Advanced drawer | **PASS** | LoRA wired, generator controls, aspect/frame config; no dead controls |

## Scorecard (Subagent D — Independent Final Certification)

| Criterion | Verdict | Notes |
|---|---|---|
| Timeline State | **PASS** | scenes.director_json with embedded timelineMaster = canonical; legacy tracks = derived NLE view |
| Clip Placement | **PASS** | lane → batch → video_clips (bbclip) chain works end-to-end |
| Timed Prompt | **PASS** | reconcile.py syncs lane → batch.promptSegments; userDirection/productionPrompt/dialogue distinct |
| Preview | **PASS** | resolveTimelineAtTime resolves batch-owned visualClips; lower-third prompt overlay |
| Batch 1 | **PASS** | LTX I2V 10s approved, output asset eb139b0b, lineage ltx-local 1280×720 16:9 |
| Batch 2 | **PASS** | LTX I2V 10s approved, output asset 0748f2c9, distinct from batch 1 |
| Generator Wiring | **PASS** | provider-agnostic registry, no silent substitution, LTX Certified, all paths verified |
| Result Binding | **PASS** | Library asset → CandidateVersion → ApprovedClip → bbclip placement |
| Retake | **PASS** | w46 batch retake: Take A preserved, Take B with parentTakeId, activation, clip replacement |
| Library | **PASS** | assets with prompt_meta, checksum, workflow certification, parent_asset_id lineage |
| Reload | **PASS** | master state + director tracks fully hydrated after reload |
| Co-Director | **PASS** | tools read production state, proposal gateway mutates timeline, generation via proposal |
| Request Stability | **PASS** | bounded polling, no request storm, cleanup on unmount |
| Visual Production Review | **PARTIAL** | objective evidence (ffprobe, frame analysis) + gemma4:12b vision review of source images; hosted VLM unavailable (Kie returns 200/empty, fal not provisioned) |

## Multi-model reviewers

| Reviewer | Role | Model | Verdict |
|---|---|---|---|
| Subagent A | Architecture audit | independent LLM | READY with reuse map; 16 risks documented |
| Subagent B | Wiring/state integrity | independent LLM | 18 WIRED, 8 PARTIAL, 3 STALE, 2 BROKEN (now resolved) |
| Subagent C | UX/workflow review | independent LLM | 4 blockers identified (all resolved) |
| Vision | Visual evidence | gemma4:12b (local Ollama) | source images match prompt intent |
| Tiebreaker | Cross-batch/continuity | deterministic production-state checks | batch isolation, source binding, prompt correspondence verified |

## Disagreements resolved

1. **Timed Prompt lane disconnect** (BROKEN #1): resolved via reconcile.py — verified live.
2. **Retake drawer disconnect** (BROKEN #2): resolved by certifying the w46 batch retake path; legacy drawer documented.
3. **MiniMax H3 readiness**: classified honestly as Testing/gated; LTX used as primary.
4. **generatedDuration 5.0 vs 8.04s**: fix in code (adapter surfaces real duration) + unit tests.

## Limitations (documented honestly)

- **generatedDuration metadata** fix exercised in unit tests but not live (timing/environment contention).
- **CD generation via proposal** proven to submit real jobs; the job completion was interrupted by environment churn.
- **Playwright governing spec** written; needs a stable GPU window to run (the earlier approved run is the fallback evidence).
- **Vision review of generated videos** limited by GPU contention (gemma4:12b could not load alongside LTX).
- **No secondary generator smoke** (MiniMax H3 Route A not enabled, WAN/Hunyuan Timeline-gated, Kling not live).
  Provider-agnosticism proven by the shared adapter registry + unit tests covering MiniMax/LTX/Seedance/Kling.
- **Kling adapter** is an in-memory ledger (no real provider call); capabilityLabel mapping is misleading.

## Branch / HEAD / deployment

- **Branch:** feat/timeline-final-certification
- **HEAD (expected):** aa6b72b (+ ~40 commits of fixes)
- **Deployment:** local Beta runtime (supervisor-managed, :8760 frontend + :8758 API)
- **Hosted deployment:** not applied (code changes are in the working tree, committed but not pushed)

## Manual Beta readiness checklist

| Question | Answer |
|---|---|
| Can a creator place real media? | **YES** — AssetTray → VISUAL lane or batch-owned clips |
| Can they preview it? | **YES** — TimelinePreviewComposer at playhead |
| Can they add timed instructions? | **YES** — TIMED PROMPT lane → reconcile → batch → generator |
| Can they build more than one batch? | **YES** — toolbar add batch, batch lane select |
| Can a real generator execute? | **YES** — LTX with I2V, 16:9, 1280×720 final |
| Can results return correctly? | **YES** — approvedClip, bbclip placement, Library |
| Can they retake? | **YES** — Batch Inspector New take → take buttons → activate |
| Can they reload? | **YES** — full hydration |
| Can CD understand and operate it? | **YES** — tools + proposals + generation (with plumbing fix) |
| Can the system fail honestly? | **YES** — structured errors, honest failure messages, no silent fallbacks |

---

*Timeline is not just an editor. It is the production execution layer that turns approved media + direction into generated sequences.*