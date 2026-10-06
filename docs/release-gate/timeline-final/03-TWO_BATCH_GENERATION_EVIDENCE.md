# 03 — Two-Batch Generation Evidence

**Project:** Timeline Two-Batch Production Smoke — Modern Shoe Hallway Ad
**Project ID:** 42dcee6d-eb0d-430e-a16a-e62ee05b4ac1
**Scene:** 638a86a1-64fa-474a-be36-c47dcf3333dc
**Primary generator (live):** LTX 2.3 (local, ltx-local, Certified)
**Aspect / resolution (final):** 16:9 → 1280×720 requested (LTX native 1280×704 — 16:9 within LTX model constraints)
**Codec / fps:** h264, 24 fps
**Branch:** feat/timeline-final-certification

## 1. Source media (real Library assets, generated through Adept UI image paths)

| Shot | Asset ID | Tag | Generator | Size | Provenance |
|---|---|---|---|---|---|
| 1 Establishing | 6ae64c5f-3add-4ef4-9810-0bccdc0215e4 | shot1-establishing | Qwen-Image-2512 (local) | 1280×720 PNG | workflowKey qwen2512.txt2img, checksum sha256:9e8e1af5…, cert record m42-w43-qwen2512-txt2img-smoke-2026-07-31 |
| 2 Walking | 1b0da2a0-c1fe-47c4-91a9-4f19dac9e5bf | shot2-walking | Qwen-Image-2512 (local) | 1280×720 PNG | same path |
| 3 Shoes | b47eab10-fd42-408d-895f-2173c6c24c97 | shot3-shoes | Qwen-Image-2512 (local) | 1280×720 PNG | same path |
| 4 Closing | fe0fd8f9-e226-4414-9f2e-de02f50176b9 | shot4-closing | Qwen-Image-2512 (local) | 1280×720 PNG | same path |

## 2. Timeline construction (lane → batches, real code paths)

- 4 image clips on the VISUAL lane (start 0/5/10/15, length 5, roles start/guide/guide/end).
- 4 Timed Prompt segments on the TIMED PROMPT lane (0–5, 5–10, 10–15, 15–20), each with authored text,
  userDirection mirror, and dialogue on Shots 2/3 ("Built to move with you." / "Every step. Every day.").
- Reconcile (legacy lane → master) distributed the lane prompts into the batch containers by time window:
  - Batch 1 (bb_41bfcf57540f, 10 s window 0–10): Shot 1 + Shot 2 prompts + anchors (img 1, img 2).
  - Batch 2 (bb_77a6dc9c2134, 10 s window 10–20): Shot 3 + Shot 4 prompts + anchors (img 3, img 4).

## 3. Batch 1 live generation (approved run)

| Field | Value |
|---|---|
| batchBlockId | bb_41bfcf57540f |
| executionSnapshotId | snap_15c12467ecb1 |
| completed job | d8c31ff9-1a84-44bd-9ce9-503c1c9a5221 (render_scene, engine ltx) |
| generationMode | image_to_video |
| startImageAssetId | 6ae64c5f-3add-4ef4-9810-0bccdc0215e4 (exact Timeline source) |
| prompt | Shot 1 + Shot 2 timed prompts (compiled, both segments) |
| output asset | eb139b0b-dfed-41e3-a88b-bba75b11da75 (video, h264 1280×704 24fps, 8.04 s) |
| approvedClip | eb139b0b-dfed-41e3-a88b-bba75b11da75 @ snap_15c12467ecb1 |
| lineage | timelineGenerationLineage: ltx-local, apiUsed=false, resolution 1280x720, aspect 16:9 |

## 4. Batch 2 live generation (approved run)

| Field | Value |
|---|---|
| batchBlockId | bb_77a6dc9c2134 |
| executionSnapshotId | snap_a438dcff8918 |
| completed job | 3d5f346b-055c-4118-bea2-4a93a61bcaa7 (render_scene, engine ltx) |
| generationMode | image_to_video |
| startImageAssetId | b47eab10-fd42-408d-895f-2173c6c24c97 (exact Timeline source) |
| prompt | Shot 3 + Shot 4 timed prompts (compiled, both segments) |
| output asset | 0748f2c9-1a2e-48c1-92fe-2558d8c00149 (video, h264 1280×704 24fps, 8.04 s) |
| approvedClip | 0748f2c9-1a2e-48c1-92fe-2558d8c00149 @ snap_a438dcff8918 |
| lineage | timelineGenerationLineage: ltx-local, apiUsed=false, resolution 1280x720, aspect 16:9 |

## 5. Cross-batch integrity (approved run)

- Distinct outputs: eb139b0b… ≠ 0748f2c9… (no duplicate/misbound clips).
- Distinct source images per batch (6ae64c5f… vs b47eab10…) — no cross-batch leakage.
- No prompt leakage: Batch 1 prompt contains "far end… hallway" only; Batch 2 contains "close product beat…" only.
- Placed NLE clips (idempotent bbclip_ upsert, sequential order):
  - bbclip_bb_41bfcf57540f @ 0 s → eb139b0b…
  - bbclip_bb_77a6dc9c2134 @ 5 s → 0748f2c9…
- Both batches restored to **Approved** through the real approve endpoint after interrupted later attempts;
  the approved media (approvedClip + snapshots) survived every API restart unharmed.

## 6. Resilience evidence (honest failure handling)

The certification environment suffered repeated API restarts and GPU contention (shared machine). Every
interruption produced honest, creator-facing state:

- "Interrupted by an API restart before it finished" — Job row, exact reason.
- "Timeline generation watcher timed out" — batch Failed, no zombie Generating state (stale-Generating
  reconciliation, 120 s done-grace window).
- "Job completed but completion processing was interrupted (API restart). Regenerate to capture this
  batch's output." — done-but-unprocessed jobs fail honestly with a regenerate instruction.
- Duplicate submissions refused: "BATCH_ALREADY_IN_FLIGHT" (idempotency guard).
- Approved media never destroyed by failed later attempts (TERMINAL_STATUS_GUARD + approval preservation).

## 7. Artifacts

- docs/release-gate/timeline-final/artifacts/two-batch-production/live-run/ — per-batch pre-state,
  generate responses (normalized requests), terminal states, cross-batch summary, VERDICT.
- Source images: tests/e2e/timeline-final/fixtures/shot{1..4}-*.png
- Generated videos: data/projects/42dcee6d-eb0d-430e-a16a-e62ee05b4ac1/renders/scene_1_*.mp4