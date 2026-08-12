# M41 4.1B — Smoke Test Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | [`artifacts/m41/41b/workflow_smoke_results.json`](../../../artifacts/m41/41b/workflow_smoke_results.json) |
| **Harness** | `python scripts/m41_41b_live_certify.py` |

## Results

| Suite | Result |
|---|---|
| Static graph build + fingerprint (all production keys) | **PASS** |
| Live Comfy generation smoke | **SKIP** (ComfyUI unreachable at `127.0.0.1:8188`) |
| Output / poster / proxy / asset registration (live) | **SKIP** |

## Honesty

No workflow was promoted to **CERTIFIED** from smoke alone. Live generation evidence is mandatory for CERTIFIED under 4.1B Full GO rules.

Re-run with ComfyUI up:

```bash
set ADEPT_41B_LIVE=1
python scripts/m41_41b_live_certify.py --live
```
