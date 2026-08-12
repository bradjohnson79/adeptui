# M41 4.1B — Cancellation Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Runtime path** | 4.1A `cancel_and_halt` + `ComfyClient.halt_prompt` / confirm |

## Code path (implemented)

1. User cancel → job stage `cancelling`
2. Interrupt + delete queue prompt
3. Confirm prompt absent from running+pending
4. → `cancelled` or `cancel_failed_runtime_active` / `COMFY_CANCEL_NOT_CONFIRMED`

## Live evidence

| Workflow family | Live cancel cert |
|---|---|
| LTX / WAN / LatentSync | **SKIP** — ComfyUI not reachable |
| fal cloud | N/A (no Comfy interrupt; provider cancel TBD) |
| Orchestration (timeline/batch) | Propagates cancel between scene loops |

## Rule

A workflow **cannot** receive CERTIFIED without live cancel PASS (queue/load/sample/decode/write stages as applicable).
