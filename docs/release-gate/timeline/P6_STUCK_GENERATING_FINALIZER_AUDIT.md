# P6 Stuck-Generating Finalizer — AUDIT (live BRAD)

**When:** 2026-09-18 19:15 PT  
**Lane:** Gen ownership (P6 hygiene)  
**Scope:** No mute / windows / Batch UX changes in this audit.

## Live smoking guns (file:line)

### A. In-process watcher dies on API bounce
studio-api/app/director_timeline_w46/generation/watcher.py
- start_completion_watcher runs a **daemon thread** in the API process.
- On :8758 restart the thread is gone. Job may still finish in queue_worker (media on disk, Job.status=done) while Timeline atch.status stays **Generating** and generationJobs[].status stays **
unning**.
- BATCH_ALREADY_IN_FLIGHT then blocks Generate (orchestrator.py ~341–347).

### B. Completion path exists but is not bounce-durable
orchestrator.py ~780–934 (pply path via generation/completion.py → shared completion):
- Creates candidate, sets job completed, runs Omni dialogue QC, sets terminal batch status.
- If watcher never calls pply_shared_completion after bounce → **no candidate attach**, permanent Generating.

### C. QC infra statuses exist in CD module but NOT in Gen BatchStatus contract
pp/codirector/dialogue_authority.py:
- STATUS_QC_PENDING = "QC_Pending" (L43)
- STATUS_QC_RETRY_REQUIRED = "QC_RetryRequired" (L44)
- pply_qc_to_batch_status: Omni unavailable → **QC_RetryRequired** (L2054–2057); content fail → NeedsDialogueRetake; never masquerade OMNI_UNAVAILABLE as retake (docstring L2048).

pp/director_timeline_w46/contracts.py BatchStatus Literal (L32–44):
- Includes Generating / CandidateReady / NeedsDialogueRetake / Failed / Cancelled …
- **Missing:** QC_Pending, QC_RetryRequired
- Orchestrator L918–932 already allows those strings in a soft guard, but pydantic Master validate/save can drop or reject them → observed live mute prove landed **NeedsDialogueRetake** on OMNI_UNAVAILABLE instead of QC_RetryRequired.

### D. Scene 4 master wipe (foreign-elim prove, 2026-09-18 ~7:10 PM PT)
During W2 prove, API connection refused mid-poll; after recovery:
- Job e556e388… **done**, raw video-only output present (generate_audio=false honored).
- Master had **one** batch b_30c851e8c0a5 status **Draft** (W1/W2/stk_ae5b66e9d0a7 gone).
- Restored from p6_v3_master_terminal.json; Take forced back to stk_ae5b66e9d0a7.
- Suspected contributors: rematerialize/fill-empty path (execution_window_materialize.py L603+ "Fill empty batchBlocks") and/or store replace after crash — **needs implement-phase confirm** before blaming one function. Treat as P0 with stuck-Generating.

### E. queue_worker recovery is Job-row oriented, not Timeline-master oriented
queue_worker.recover_interrupted (~L521+): reconciles Job rows / Comfy harvest; does **not** call Timeline pply_shared_completion or a master reconciler. Media can land without Timeline terminalization.

## State machine gaps

| Evidence | Desired terminal | Today |
|----------|------------------|-------|
| Job done + asset, QC not run / Omni down | QC_Pending / QC_RetryRequired | Often stuck Generating, or wrong NeedsDialogueRetake |
| Job done + QC PASS | CandidateReady / READY | Works when watcher survives |
| Job failed | Failed / FAILED_GENERATION | Watcher _mark_job_failed if alive |
| Cancel | Cancelled | Partial |
| Superseded Take | SUPERSEDED / immutable | Not modeled as batch status |
| Stale rev generate | reject | Partial fingerprint paths |

## One reconciler law (proposed)

**Law:** After any Job reaches provider-terminal (done/ailed/cancelled) OR durable output_path/output_asset_id exists for a Timeline generationJobs queue id, a single **Timeline Generation Reconciler** (API startup + periodic + on master GET optional) MUST:

1. Load master by job’s project/scene + atchBlockId from params.
2. If batch already in creator-terminal set → no-op (TERMINAL_STATUS_GUARD).
3. Else if media success → ensure candidate/asset bound (idempotent), set job status completed, then:
   - if QC not run → **QC_Pending** (MEDIA_COMPLETE_QC_PENDING)
   - if QC infra miss → **QC_RetryRequired**
   - if QC content fail → **NeedsDialogueRetake / FAILED_QC**
   - if QC PASS → **CandidateReady**
4. Else if provider fail → **Failed** (FAILED_GENERATION); cancel siblings per halt law.
5. Else if cancel → **Cancelled**.
6. Never auto-regen. Never rematerialize windows. Never invent CandidateReady on Omni miss.

Map Brad names → existing where possible:
| Brad | Existing / add |
|------|----------------|
| MEDIA_COMPLETE_QC_PENDING | add QC_Pending to BatchStatus |
| READY | CandidateReady (+ Approved after creator) |
| FAILED_GENERATION | Failed |
| FAILED_QC | NeedsDialogueRetake |
| CANCELLED | Cancelled |
| SUPERSEDED | Take-level flag / status (not batch wipe) |

## QC retry without regen (proposed minimal)

Endpoint or orchestrator action: POST .../batches/{id}/qc-retry
- Same SceneTake, same revision, same window, same ssetId
- Reuse frozen language-authority packet (reeze_language_authority_packet already exists)
- Re-run Omni dialogue QC only; no H3, no rematerialize, no new Take
- CD owns classification; Gen owns status transition + asset preserve

## Bounce / refresh recovery

On API startup after 
ecover_interrupted:
- Scan non-terminal Timeline batches with matching done Jobs → run reconciler.
- On master GET: if Generating but durable job done + asset → derive terminal (lazy reconcile), **do not** auto-regen.
- Browser hard refresh must show derived terminal from durable evidence.

## Tests 4–7 mapping

4. **Bounce recovery:** start Generating → kill API → job done → restart → reconciler → not Generating; asset preserved; no new job.
5. **Failed gen ≠ QC_PENDING:** provider fail → Failed; never QC_Pending.
6. **Superseded Take immutable:** new Take; old Take batches/assets unchanged by reconcile.
7. **Stale rev rejected:** generate with stale revision → 409/reject; no job.

## Live proof Scene 4 Omni-unavailable

Blocked until reconciler + BatchStatus enum fix land. Hook already exists (is_omni_infra_unavailable). After fix: controlled Omni-down → expect QC_RetryRequired, asset kept, H3 not rerun, refresh correct.

## Brad scorecard — Gen fields (audit phase)

| Field | Status |
|-------|--------|
| Smoking guns identified | PASS (this doc) |
| BatchStatus includes QC_* | **FAIL** (gap) |
| Bounce-durable reconciler | **FAIL** (missing) |
| QC retry without regen API | **FAIL** (helpers exist; no Gen surface) |
| Master wipe root cause proven | **PARTIAL** (observed; function TBD) |
| Mute/windows/Batch reopened | NO (held) |

## Next implement order
1. Add QC_Pending / QC_RetryRequired to BatchStatus (+ FE labels via UX bot later).
2. Timeline Generation Reconciler on startup + lazy GET.
3. QC-retry endpoint (coordinate CD packet schema — already frozen).
4. Tests 4–7.
5. Live Omni-unavailable proof on Scene 4 when safe.

Evidence also: foreign-elim scorecard bounce wipe; mute prove stuck-Generating blip.
