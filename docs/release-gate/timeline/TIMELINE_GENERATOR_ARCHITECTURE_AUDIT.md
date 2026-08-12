# Timeline Generator Architecture Audit

**Date:** 2026-08-05  
**Scope:** Timeline Batch → generation → Library → candidate → approve → Timeline placement  
**Method:** Traced live call paths (not filenames alone)

---

## Call graph (as found)

```text
TimelineToolbar.generateScene("selected"|"full")
  → api.directorTimelineGenerateBatch / directorTimelineGenerateScene
  → POST /api/director-timeline/.../batches/{id}/generate
     or POST /api/director-timeline/.../scenes/{id}/generate
  → director_timeline_w46.router
  → orchestrator.submit_batch_generation / generate_scene
       → validate_duration(batch.generatorId)
       → get_generator(batch.generatorId)   # capabilities.py dock list
       → create_execution_snapshot(...)
       → append GenerationJobRef(status="queued")  # NO queueJobId
       → store.save_master
       → return stub payload (comment: "Assembly stub")
```

**No path** from `submit_batch_generation` into:

- `minimax_h3.service.create_job_or_block`
- `queue_worker` / `Job` enqueue for LTX/WAN
- Seedance / Kling hosted clients

Completion APIs exist (`complete_batch_candidate`, `approve_candidate`) but are **not** invoked by submit.  
`approve_candidate` sets `batch.approvedClip` only — it does **not** write `DirectorTimeline.video_clips`.

MiniMax Re-take is a **separate** surface (`timeline_retakes` + `/api/minimax-h3/*`) and is not the batch orchestrator.

---

## Evidence

| Check | Result | Path |
| --- | --- | --- |
| Real enqueue from batch submit | **Missing** | `orchestrator.py` `submit_batch_generation` returns after snapshot; comment admits stub |
| Normalized TimelineGenerationRequest | **Missing** | No such type under `director_timeline_w46` |
| VideoGeneratorAdapter registry | **Missing** | `capabilities.py` is a static dock list, not submit/status/collect adapters |
| MiniMax in Timeline generators | **Missing** | `list_generators()` has `ltx-local`, `wan-local`, Hunyuan, `seedance-kie`, `kling-fal` — no MiniMax |
| Provider translation in adapters | **N/A** | Orchestration never reaches providers |
| Shared Library→place path | **Partial** | Candidate/approve helpers exist; no auto Library import or `video_clips` placement |
| Hosted vs local shared batching | **Not wired** | Locality only labels the stub job |

---

## Verdict

```text
NOT CONFIRMED — TIMELINE GENERATION WORKFLOW REQUIRES PROVIDER-AGNOSTIC ADAPTER IMPLEMENTATION
```

Do not start the live two-batch Playwright certification until the shared layer is implemented and regression-covered.

### MiniMax cert note (honest capability)

Experimental Private Profile Route A is **text-to-video with native audio** (`supportsImageToVideo: False` in `minimax_h3/capability.py`). Batch cert will attach a start **image as a Timeline sourceAnchor** for isolation/lineage and generate via MiniMax T2VA from the batch prompt. Image-to-video mode must be rejected by capability validation for `minimax-h3-local` (no silent drop / no LTX fallback).
