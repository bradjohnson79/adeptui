# 02 — Gate B Generator Authority

**Surface:** BOTH (PC + Timeline inventories existed on released and current). Repair is CURRENT DEVELOPMENT.  
**Date:** 2026-08-29

## Defect

Three competing truths:

1. Production Control `_CATALOG` invented `executable` / Certified / Available.
2. Timeline `list_generators()` was a second catalog (WAN / Hunyuan / LTX 2.5 advertised executable without adapters).
3. Adapter registry was the only real execution proof.

Frontend `joinProductionControlVideoOptions` was missing. Inspector / settings / JobPanel / Txt2Vid used fossil `LTX 2.5` / `fal_*` lists.

## Repair

One join: [studio-api/app/production_control/generator_authority.py](../../../studio-api/app/production_control/generator_authority.py)

- Identity: Production Control catalog + hosted discovery
- Execution proof: Timeline adapter registry
- Aliases only at the boundary (`kling-kie` → `kling-api`, `minimax-h3` → `minimax-h3-t2v-local`)
- LTX 2.5 may alias to `ltx-local` for routing; it is never Ready via the 2.3 adapter
- WAN / Hunyuan / Runway: `Unsupported in this workflow`, `executable=False`
- Mocks (`mock-chat`, cert-stub) hidden from production inventory; cert stub stays env-gated
- Audio Certified + not executable → Requires Setup

Timeline `list_generators()` is now a **view** of that join. Veo adapter registered in the existing registry (not a fourth catalog).

Frontend presenter restored: `joinProductionControlVideoOptions` formats the backend-joined `generators[]`. `useVideoGeneratorOptions` is a thin presenter over the same hook. Fossil engine dropdowns use `EngineAuthoritySelect`.

## Tests

`cd studio-api; python -m pytest tests/test_generator_authority.py tests/test_timeline_generation_adapters.py tests/test_production_dock.py tests/test_stability_cull_batch4_labels.py -q`

`node --test src/timelineMaster/draftCapabilities.test.ts` — **4 passed**

## Classification

| Finding | Surface | After repair |
|---|---|---|
| Second Timeline catalog | BOTH | HISTORICAL; current is a join view |
| WAN/Hunyuan Available+exec | BOTH | Unsupported / not executable |
| LTX 2.5 Ready via 2.3 alias | BOTH | Testing / not executable |
| Missing frontend join | CURRENT DEVELOPMENT | Presenter only |
| Fossil LTX 2.5 / fal_* lists | BOTH | EngineAuthoritySelect |
| Veo adapter file unused | CURRENT DEVELOPMENT | Registered in existing registry |

## Peer close

- Kimi K3 (`b9c442a5`): **PASS WITH NON-BLOCKING** — one join, not a fourth catalog. WAN/Hunyuan/LTX 2.5 non-executable. Hosted discovery shadowing is conservative. **ACCEPTED NON-BLOCKING**.
- GLM 5.2 (`f9fb54a7`): **PASS WITH NON-BLOCKING** — same join verdict. Residual `fal_*` tokens in Inpaint default mapping only. **ACCEPTED NON-BLOCKING**.

**Gate B: CLOSED**
