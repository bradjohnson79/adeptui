# Timeline MiniMax H3 Image-to-Video Path Audit

**Date:** 2026-08-05  
**Scope:** Real MiniMax H3 I2V (image conditioning) for Timeline two-batch certification

---

## Verdict

```text
NOT CONFIRMED — REAL MINIMAX H3 IMAGE-TO-VIDEO PATH MUST BE IMPLEMENTED
```

---

## Evidence (pre-implementation)

| Check | Result | Path |
| --- | --- | --- |
| Route A graph wires `first_frame` | **No** | `studio-api/app/minimax_h3/route_a_adapter.py` `build_t2va_graph` — `MiniMaxH3ImageToVideo` has prompt/size only |
| Capability `supportsImageToVideo` | **False** on private Route A | `capability.py` |
| Preflight allows `one-frame` on Route A | **Blocked** | `preflight.py` — T2V-only for Experimental Private Profile |
| Timeline MiniMax adapter I2V | **Rejected** | `generation/adapters/minimax_h3_local.py` |
| Start images on Timeline for MiniMax | **Planning anchors only** | `request_builder.py` → `planningStartImageAssetId` |
| Comfy node can accept image | **Yes (upstream)** | Optional `first_frame` / `last_frame` on `MiniMaxH3ImageToVideo` |
| Official I2V template | Reference only in spike | `AIVideoStudio-h3/.../video_minimax_h3_i2v.json` |

Do not infer I2V support from UI image pickers or the node class name alone.

---

## Implementation required

1. `build_i2va_graph` + Comfy upload + `submit_i2va`
2. Preflight/capability split for I2V profile
3. Timeline adapter `minimax-h3-i2v-local`
4. Persist submitted Comfy graph per job for certification proof
