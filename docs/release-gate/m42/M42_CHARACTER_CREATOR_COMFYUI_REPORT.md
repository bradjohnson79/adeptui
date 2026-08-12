# M42 Character Creator ComfyUI Report

**Date:** 2026-07-31  
**Mock data:** false  
**ComfyUI:** `http://127.0.0.1:8188` (healthy during cert)  
**Adept API:** `http://127.0.0.1:8758` (Beta READY)

---

## Execution path

```text
QueueWorker._imagegen
  → resolve_image_workflow / build_leaf_graph
  → prepare_executable_graph (assert_no_graph_drift)
  → comfy.queue_prompt
  → _wait_comfy (history / websocket progress)
  → find_output_files
  → _imagegen_commit_asset
```

---

## Live job outcomes (cert project `040dc342-…`)

| Phase | Jobs | Status |
|---|---|---|
| Hero | 1× txt2img | done |
| Coverage | 6× txt2img | done |
| Details | 6× ref_edit | done |
| Performance | 2× ref_edit | done |
| **Total roles** | **15** | **all assets registered** |

Wall-clock for full pack + owner approve: ~74s (Z-Image Turbo, warm models).

---

## Comfy failure modes exercised / cleared

| Failure | Status |
|---|---|
| Latent shape crash (Omni+EmptyLatent) | Cleared by workflow rebuild |
| Graph drift reject | Cleared by registry re-fingerprint + Beta restart |
| Queue timeout | Not observed |
| Missing output files | Not observed |
| Asset write failure | Not observed |

---

## Runtime topology

- Beta supervisor: API + in-process worker on port `8758`  
- Web UI: `8760`  
- External ComfyUI: `8188`  
- Evidence log: `artifacts/m42/w43/korri/cert-run.log`

---

## ComfyUI verdict

**PASS** — ComfyUI executed Adept-built workflows without manual graph repair. Outputs returned and persisted for all 15 Character Creator roles.
