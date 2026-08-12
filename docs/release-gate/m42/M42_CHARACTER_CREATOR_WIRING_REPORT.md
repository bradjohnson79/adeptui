# M42 Character Creator Wiring Report

**Date:** 2026-07-31  
**Mock data:** false

---

## End-to-end wiring (verified live)

```text
Character Creator
  → POST /characters/seed-korri
  → POST /characters/{id}/visual-sheet/generate
  → Prompt Builder (_identity_prompt + role prompts)
  → Image Product compile / enqueue_imagegen_job
  → QueueWorker._imagegen
  → build_leaf_graph + prepare_executable_graph (drift check)
  → ComfyUI /prompt + history poll
  → _imagegen_commit_asset (disk + assets row)
  → visual-sheet/advance attaches roleAssets + character_reference_assets
  → details/performance via zimage.ref_edit (sourceAssetId=hero)
  → READY_FOR_OWNER
  → POST visual-sheet/owner-approve
  → OWNER_APPROVED gates
```

No stage was bypassed with mock assets. Coverage uses real `zimage.txt2img` jobs; details/performance use real `zimage.ref_edit` jobs.

---

## Link checks

| Link | Evidence |
|---|---|
| UI/API → seed | Cert created project + `seed-korri` |
| Seed → prompts | Prompt package includes locked Korri traits |
| Prompts → workflow | Jobs list `zimage.txt2img` / `zimage.ref_edit` |
| Workflow → Comfy | Comfy healthy; 15 assets written |
| Comfy → assets | PNG paths under `data/projects/{pid}/assets/` |
| Assets → sheet | `roleAssets` map 15/15 |
| Sheet → owner | `approvedGates` = hero/turnaround/facial/detail/performance |
| Reload | GET visual-sheet → `OWNER_APPROVED`, 15 roles |

---

## Corrected architecture notes

1. **ref_edit** no longer uses Omni image conditioning + EmptyLatent.  
2. **Registry fingerprints** updated for the new graph.  
3. **Coverage** remains txt2img-per-role for stability; legacy `character_sheet` multi-view job remains available but is not the pack driver.

---

## Wiring verdict

**PASS** — No broken or mock-bypassed links on the production Character Creator → ComfyUI path.
