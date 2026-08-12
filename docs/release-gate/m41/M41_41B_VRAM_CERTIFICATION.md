# M41 4.1B — VRAM Certification

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | [`artifacts/m41/41b/workflow_vram_profiles.json`](../../../artifacts/m41/41b/workflow_vram_profiles.json) |
| **Catalog profiles** | Embedded in Certified Registry `vramProfile` |

## Registry baseline profiles (planning)

| workflowKey | min / recommended | state |
|---|---|---|
| `ltx.simple_i2v` | 8 / 24 GB | TIGHT |
| `ltx.scene` | 12 / 24 GB | TIGHT |
| `ltx.ingredients_ic_lora` | 16 / 24 GB | HIGH_RISK |
| `wan.first_last_frame` | 20 / 24 GB | HIGH_RISK |
| `wan.three_frame` | 20 / 24 GB (×2 segments) | HIGH_RISK |
| `lipsync.latentsync` | 8 / 16 GB | SAFE |

## Live measurement

**SKIP** — ComfyUI offline; peak/heavy/safe-concurrency not observed. Profiles remain registry estimates until live harness records peaks.
