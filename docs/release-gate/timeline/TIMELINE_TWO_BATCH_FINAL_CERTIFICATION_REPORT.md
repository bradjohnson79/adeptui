# Timeline Two-Batch Final Certification Report

**Date:** 2026-08-05  
**Branch:** `feature/ai-guided-setup`  
**HEAD:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Beta UI:** http://127.0.0.1:8760/  
**Studio API:** http://127.0.0.1:8758/  
**Spec:** `tests/e2e/timeline/timeline-two-batch-final-certification.spec.ts`  
**Artifacts:** `docs/release-gate/timeline/artifacts/timeline-two-batch-final-certification/2026-08-05T06-37-58-160Z/`  
**Playwright:** 1 passed (2.6m), `--retries=0 --workers=1`

---

## Verdict

```text
NO-GO — TIMELINE TWO-BATCH MINIMAX IMAGE-TO-VIDEO CERTIFICATION NOT YET PASSED
```

### Previous T2V run (non-authoritative for the original requirement)

```text
The prior MiniMax T2V batching run did not satisfy the original image-to-video requirement and is not the authoritative final certification.
```

The prior MiniMax T2V two-batch Playwright run remains documented evidence that batching, job isolation, lineage, placement, and reload persistence work for MiniMax **text-to-video**. It does **not** satisfy the required final certification (image-conditioned MiniMax H3 I2V).

Authoritative I2V certification is tracked in [`TIMELINE_TWO_BATCH_MINIMAX_I2V_FINAL_CERTIFICATION_REPORT.md`](TIMELINE_TWO_BATCH_MINIMAX_I2V_FINAL_CERTIFICATION_REPORT.md) (when issued).

### Gate split

| Gate | Verdict |
| --- | --- |
| Two isolated Batch Blocks | **GO** |
| Unique prompt ownership | **GO** |
| Unique planning-image lineage | **GO** |
| Real MiniMax H3 generation | **GO** |
| Two independent output assets | **GO** |
| Sequential Timeline placement | **GO** |
| Reload persistence | **GO** |
| Provider-agnostic architecture | **GO** |
| Start-image lineage persistence | **GO** |
| Start-image visual conditioning | **NOT CERTIFIED** |
| MiniMax image-to-video | **NOT SUPPORTED BY ROUTE A** |

This does not invalidate the architecture work or the batching success. It simply prevents the report from implying that an I2V path was certified when it was not.

Once a MiniMax image-conditioned route becomes available, a separate narrow test can verify that changing the start image while keeping the prompt controlled produces outputs tied visually—not merely structurally—to each batch’s assigned reference.

---

## Architecture audit (pre-cert)

| Item | Result |
| --- | --- |
| Pre-implementation audit | `NOT CONFIRMED — TIMELINE GENERATION WORKFLOW REQUIRES PROVIDER-AGNOSTIC ADAPTER IMPLEMENTATION` |
| Evidence | [`TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md`](TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md) |
| Remediation | Implemented `studio-api/app/director_timeline_w46/generation/` (request/result contracts, capabilities, adapters, registry, shared completion, watcher) |
| Regression | `studio-api/tests/test_timeline_generation_adapters.py` + updated W46 orchestrator tests — **23 passed** |

---

## Timeline Generator Architecture

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Normalized generation request | **GO** | `generation/contracts.py` `TimelineGenerationRequest`; submit returns `normalizedRequest` (see `06-generate-*.json`) |
| Generator adapter registry | **GO** | `generation/registry.py` — `minimax-h3-local`, `ltx-local`, `seedance-api`, `kling-api` |
| Capability-based validation | **GO** | `generation/adapter.py` `validate_against_capabilities`; tests reject MiniMax I2V |
| MiniMax adapter | **GO** | `generation/adapters/minimax_h3_local.py` → Route A `/api/minimax-h3` |
| LTX compatibility preserved | **GO** | `generation/adapters/ltx_local.py` + `test_ltx_routes_through_shared_interface` |
| Hosted API compatibility | **GO** | `seedance_api.py` / `kling_api.py` return `providerJobId` + normalized status (boundary-mockable) |
| Shared completion and placement | **GO** | `generation/completion.py` Library → candidate → approve → `bbclip_*` video clips |
| Provider-independent persistence | **GO** | Batch lineage in `references[timelineGenerationLineage]`; reload verified in Playwright |
| No silent substitution | **GO** | `fallbackAllowed=false`; unknown generator rejected; cert `apiUsed=false`, `generatorId=minimax-h3-local` only |

---

## Locked engine (live cert)

| Field | Value |
| --- | --- |
| `generatorId` | `minimax-h3-local` |
| Model / profile | MiniMax H3 33B — Experimental Private Profile (480×256, length 5, steps 4, native audio) |
| Execution | Local Route A (`http://127.0.0.1:8192`) |
| `fallbackAllowed` | `false` |
| `apiUsed` | `false` (both batches) |
| LTX / Seedance / Kling / mock | **Not used** |

Honest capability note: Route A is **text-to-video**. Batch start images are Timeline planning anchors (`planningStartImageAssetId`); they are not silently treated as I2V inputs.

---

## Live run lineage

**Disposable project (deleted after cert):** `eafd3166-9ef9-4dca-acfc-a40c6f8694d9`  
**Scene:** `86495783-492c-4418-b935-41d13e6189b0`

### Batch 1

| Field | Value |
| --- | --- |
| `batchBlockId` | `bb_7793e9073002` |
| Input image asset | `8b08f00f-baca-4ea8-9342-1f2d02c6a486` |
| `executionSnapshotId` | `snap_efeafa89dc7e` |
| `queueJobId` / `providerJobId` / `internalJobId` | `041ccc23-eba0-4549-919f-f8e46483dd33` |
| Output Library asset | `b52dca9c-3aaa-4b78-8cfc-a15fd718eca2` |
| Timeline clip | `bbclip_bb_7793e9073002` @ start 0s, length 5s |

### Batch 2

| Field | Value |
| --- | --- |
| `batchBlockId` | `bb_73f3a214ee70` |
| Input image asset | `5a969945-b5db-412a-a39d-79d1d377df97` |
| `executionSnapshotId` | `snap_363322a88914` |
| `queueJobId` / `providerJobId` / `internalJobId` | `f1ab29c9-bf1f-4e0a-8e6b-d826a6747a8b` |
| Output Library asset | `740b5997-f58e-469e-929b-2c94ac3866bb` |
| Timeline clip | `bbclip_bb_73f3a214ee70` @ start 5s, length 5s |

### Final Timeline shape

```text
[ Batch 1 MiniMax Clip 0–5s ][ Batch 2 MiniMax Clip 5–10s ]
```

Reload after placement preserved both approvals, distinct output assets, and batch-order clip placement.

---

## Tests executed

| Suite | Result |
| --- | --- |
| `tests/test_timeline_generation_adapters.py` + W46 orchestrator/CD timeline | 23 passed |
| Playwright two-batch Beta cert | 1 passed (2.6m) |

---

## Manual review

1. Open http://127.0.0.1:8760/  
2. Confirm API http://127.0.0.1:8758/api/health  
3. Inspect artifacts under `docs/release-gate/timeline/artifacts/timeline-two-batch-final-certification/2026-08-05T06-37-58-160Z/`  
4. Optional: create a disposable project and Gen Batch with generator **MiniMax H3 (Local)**

---

## Limitations

- MiniMax Experimental Private Profile does not support image-to-video; start images are planning/lineage anchors for this cert.  
- Hosted Seedance/Kling adapters expose the shared async contract; live hosted credentials were not required for this MiniMax-locked cert.  
- Disposable cert project was deleted after the run (lineage captured in artifacts).

---

## Checklist

```text
[x] Branch + starting SHA verified
[x] Provider-agnostic contracts implemented (post NOT CONFIRMED audit)
[x] Full-stack Timeline batch → MiniMax → Library → Timeline clips
[x] Every visible cert control wired (prompt / start image / generator / Gen Batch)
[x] Real MiniMax runtime; no mock completion
[x] Persistence after reload verified
[x] No silent generator substitution
[x] Unit/API regression passed
[x] Playwright creator workflow passed
[x] Beta refreshed; URLs reported
[x] Unified Markdown completion report created
[x] Verdict: GO (MiniMax T2V two-batch); I2V visual conditioning NOT CERTIFIED / NOT APPLICABLE on Route A
```
