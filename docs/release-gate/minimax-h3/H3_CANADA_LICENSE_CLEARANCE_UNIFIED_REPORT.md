# MiniMax H3 — Canadian License Clearance Unified Report

**Date:** 2026-08-03  
**Task:** MiniMax H3 Canada Clearance (license re-audit + runtime reopen gate)  
**Primary branch:** `feature/ai-guided-setup` @ `fa09c99d6395c29461cdec4555055faad116c435` (+ working-tree clearance work)  
**Spike branch:** `spike/minimax-h3-33b-rtx5090` @ `c932214a233fbc0fddb009ef6f80638dd60c8082`  
**Worker package:** [H3 Canada clearance](8e35ae24-6a29-47d9-b2dc-f48abb63ed96) → `READY FOR PRIMARY REVIEW`  
**Disclaimer:** Technical compliance audit for Adept UI implementation gating. **Not** professional legal advice.

---

## Executive verdicts

| Gate | Verdict |
|---|---|
| **Territory (Canada local open-weight development)** | **`CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS`** |
| **Canadian local development gate (product)** | **GO** |
| **Excluded-territory local open weights (US / EU / UK / KR)** | **BLOCKED** / authorization-gated |
| **Local H3 media proof (Canadian RTX 5090)** | **NO-GO** — isolated runtime executed honestly, but neither Diffusers nor secondary isolated ComfyUI produced a genuine MP4 |
| **Adept UI surface wiring (prior cert)** | **GO** (separate; still valid) |
| **Overall local H3 production readiness** | **NO-GO** until real GPU proof + remaining clarifications |

**Authoritative label for this task:**  
**CANADA LICENSE CLEARANCE COMPLETE — RUNTIME SPIKE CLOSED NO-GO; MEDIA PROOF NOT PROVEN**

---

## Mission correction

Earlier H3 work treated all local open-weight use as blocked because Excluded Territories include the United States. That reading incorrectly stopped Canadian development.

Pinned official Community License Excluded Territories:

- European Union  
- United Kingdom  
- Republic of Korea  
- United States of America  

**Canada is not listed.** Adept UI development and the intended corporate holder (ANOINT Inc., Canadian corporation) operate in Canada. A Canada-only local spike must not be auto-blocked merely because U.S. users/deployments remain restricted.

---

## Authoritative sources (pinned)

| Item | Value |
|---|---|
| Repository | `MiniMaxAI/MiniMax-H3` |
| Revision | `5d9b308a59ab12e67147f191e184baf704185bd1` |
| LICENSE URL | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/5d9b308a59ab12e67147f191e184baf704185bd1/LICENSE |
| LICENSE SHA-256 | `59b99642b95ea21630e311198ddbfffbfe05aadba0c2f5d884cbdf4efcc90f44` |
| Model card | `README.md` @ same revision |
| Official Q&A | `docs/QA-about-License.md` @ same revision |
| Official API docs | MiniMax video-generation v2 create + H3 Context-IR |

Full clause extracts and interpretation:  
[`docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md`](../../models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md)

---

## Phase results

### Phase 1 — Territory interpretation

| Question | Finding |
|---|---|
| Licensee (ANOINT Inc.) | Canadian entity; Canada ∈ Applicable Territory on pinned text |
| Runtime location | Canadian RTX 5090 workstation assumption; open-weight OK on Canada infra under community license conditions |
| Hosted deployment | Corporate nationality ≠ host location; US/EU/UK/KR GPU hosts for open weights need authorization |
| User location | Section V.4 restricts use/display of works/outputs outside Applicable Territory; serving excluded-territory users via open weights needs MiniMax clarification — not silently assumed lawful |
| Distribution | Canadian download OK; instruct official HF preferred over redistributing; derivatives/redistribution only within Applicable Territory + Section III notices; Cloud must not ship weights into excluded infra |

**Territory section verdict:**  
`CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS`

### Phase 2 — Commercial obligations

| Obligation | Requirement |
|---|---|
| Attribution | Prominently display `MiniMax H3` in commercial UI (engine picker, plan panel, model badges, receipts) |
| User terms | Bind users to terms at least as protective as Section V / Exhibit A before H3 access |
| Revenue | Prior written MiniMax authorization if yearly revenue of H3-using commercial products/services exceeds **USD 20M** |
| Outputs | Territory, anti-model-improvement, unlawful use, safeguards, military, undisclosed machine content, etc. |
| Derivatives | Fine-tunes / quants / distillations treated as Model Derivatives within Applicable Territory |
| Redistribution | Section III: agreement, mark mods, NOTICE, Applicable Territory only |
| Hosted services | Section V.5 safeguards, reporting, mitigation |

### Phase 3 — Territory enforcement (implemented)

| Change | Detail |
|---|---|
| New helper | `studio-web/src/core/minimaxH3Territory.ts` |
| Resolution order | Explicit prop → `VITE_MINIMAX_H3_TERRITORY` → audited default **`CA`** |
| Removed | Hardcoded `territory="US"` on Text2Video, One/Three Frame, Timeline Master, MiniMaxH3PlanPanel, api helper |
| Backend test | `CA` blocked only by uncertified runtime, **not** by license |
| Unit suite | `pytest studio-api/app/minimax_h3/test_minimax_h3_surfaces.py` → **7 passed** |
| Fallback | LTX remains permanent **explicit** fallback; no silent switch |

### Phase 4 — Runtime reopen (conditional)

| Item | Status |
|---|---|
| Legal reopen for Canada-only spike | **Yes** |
| GPU observed | NVIDIA GeForce RTX 5090 · ~32607 MiB VRAM |
| Pinned HF repo size | ~499 GB (`FL2VA/` ~144 GB, `Ref2VA/` ~144 GB) |
| Official README examples | `--num-gpus 4` (multi-GPU) |
| Weights downloaded | **Yes** — `FL2VA/` minimum payload complete at `144,051,182,625 bytes` |
| Local worker started | **Yes** — isolated CUDA env and isolated ComfyUI server |
| Genuine H3 video+audio proof | **No** (Law 26 unmet; no MP4) |

### Phase 4b — Closed Canada runtime spike status

Latest isolated-worktree runtime evidence from `RUN-20260803-145133`, now accepted by primary as the
authoritative close for this spike:

- Gate A passed: FL2VA minimum download completed at
  `144,051,182,625 / 144,051,182,625 bytes` (`100.00%`)
- CUDA was proven on the isolated final env with `torch 2.11.0+cu128` on
  `NVIDIA GeForce RTX 5090`
- Primary local Diffusers load still failed because released `diffusers` did not expose
  `MiniMaxH3Pipeline` or `MiniMaxH3ModularPipeline`
- Secondary isolated ComfyUI was executed from `runtime/minimax-h3/comfyui/` on GPU without touching
  production Comfy Desktop
- The official Comfy H3 template expects single-file weights
  `minimax_h3_fl2va_pruned_int8_convrot.safetensors` and
  `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, but the local download only provides the
  Diffusers-style sharded `FL2VA/transformer/*` and `FL2VA/text_encoder/*` layout
- The isolated Comfy job queued successfully, then failed at `MiniMaxH3ImageToVideo` with
  `NotImplementedError: Cannot copy out of meta tensor; no data!` after CLIP/VAE missing-key
  warnings consistent with the layout mismatch
- No local MP4 or successful H3 sample was produced

Accepted runtime gate strings:

- Gate A: `PASS`
- Gate B: `FAIL`
- Gate C: `NO-GO`

Current runtime verdict string:

**CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO**

Primary accepted disposition for this spike:

**PRIMARY ACCEPTED — Canada runtime proof closed as NO-GO for this spike.**

### Phase 5 — Reports updated

- `docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md` (authoritative clearance memo)  
- `docs/models/minimax-h3/H3_SURFACE_WIRING.md`  
- `docs/release-gate/parallel/H3_POSECRAFT_PARALLEL_PROGRAM.md`  
- `docs/release-gate/parallel/MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md`  
- `docs/release-gate/minimax-h3/H3_ADEPT_UI_SURFACE_CERTIFICATION.md`  
- `AIVideoStudio-h3/docs/models/minimax-h3/H3_PARALLEL_SPIKE_HANDOFF.md`  
- `AIVideoStudio-h3/docs/models/minimax-h3/artifacts/rtx5090-canada/RUN-20260803-145133/H3_CANADA_RUNTIME_GATE_REPORT.md`  
- **This unified clearance report**

---

## Conditions attached to Canadian permission

1. Keep download, storage, execution, and open-weight hosting in **Applicable Territory** (Canada for this spike).  
2. Do not treat Canadian corporate identity as permission to run open weights on Excluded Territory infrastructure.  
3. Prominently display `MiniMax H3` in commercial UI.  
4. Bind users to protective terms before H3 access.  
5. Implement hosted-service safeguards if Adept exposes H3 generation.  
6. Obtain MiniMax written authorization before USD 20M revenue threshold if applicable.  
7. Do not silently serve open-weight H3 to excluded-territory users pending clarification.  
8. Preserve LTX fallback honesty; never claim local media GO without GPU proof.

---

## Clarifications still required from MiniMax

1. May a Canada-hosted **open-weight** deployment lawfully serve users physically in Excluded Territories?  
2. Does output **display** to excluded-territory viewers count as prohibited under Section V.4 for open-weight deployments?  
3. Does Canadian redistribution of quantized / derivative weights need anything beyond Section III?

Contact channel referenced in prior spike materials: MiniMax licensing / `api@minimax.io` (confirm via current official docs before outreach).

---

## Evidence checklist

```text
[x] Official LICENSE + Q&A re-read from pinned revision
[x] LICENSE hash recorded
[x] Canada vs Excluded Territories documented separately (licensee / runtime / host / user / distribution)
[x] Territory verdict: CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS
[x] Commercial obligations documented
[x] Capability gate no longer hardcodes US for Canadian development
[x] Unit tests: 7 passed
[x] Legal runtime reopen recorded
[x] H3 weights downloaded
[x] Isolated worker started
[ ] Genuine local video+audio generation (Law 26)
[x] Program / surface / spike reports updated
[x] Unified clearance report created
[x] Honest NO-GO on local media proof
```

---

## Unblock checklist for next spike

1. Wait for a released Diffusers stack that actually exposes `MiniMaxH3Pipeline` and/or
   `MiniMaxH3ModularPipeline` for the published H3 manifests.  
2. Or download the official single-file Comfy H3 weight pack and retry the isolated Comfy path on
   `http://127.0.0.1:8192` only; do **not** treat that as production Desktop wiring.  
3. Or retry via multi-GPU SGLang if suitable hardware becomes available.  
4. Keep LTX as the permanent explicit fallback until Gate B and Gate C both pass.  
5. Do not mark H3 as Adept UI Ready or production-wire local H3 runtime paths until genuine media proof
   exists and the runtime gate is upgraded honestly.  
6. Keep production ComfyUI untouched during any future retry.  
7. Continue user-terms / attribution / territory clarification work independently of runtime retries.

---

## Binary certification (this task)

| Question | Answer |
|---|---|
| Was the US-only hard block on Canadian development corrected? | **Yes** |
| Is Canadian local open-weight development license-permitted under pinned public sources? | **Yes, with conditions** |
| Is local H3 media generation certified on the Canadian RTX 5090? | **No** |
| Final task verdict | **GO on Canada license clearance** · **NO-GO on local media proof** |

**READY FOR PRIMARY REVIEW** (worker) · Runtime spike is now closed and primary-accepted as NO-GO for this
evidence package.

---

## Primary verification (accepted)

Performed by [H3 Canada primary verify](6e83b3fb-859d-47aa-892b-36e0311b299a) on 2026-08-03.

| Check | Result |
|---|---|
| Clearance memo + territory verdict string | Confirmed |
| Pinned repo / revision / LICENSE hash | Confirmed |
| No remaining `territory="US"` hardcoding in `studio-web/src` | Confirmed |
| `pytest …/test_minimax_h3_surfaces.py` | **7 passed in 0.36s** |
| `studio-web` rebuild + Beta restart | Done |
| Beta UI | http://127.0.0.1:8760/ |
| Beta API | http://127.0.0.1:8758/api/health |
| Beta health note | `DEGRADED` only because external ComfyUI `:8188` is down (not required for Canada license gate) |
| Weights / local media claim | None — media proof remains **NO-GO** |

**Primary disposition:** Canada clearance package **accepted**.  
Canadian local development gate **GO**. Local media proof **NO-GO**.  
The Canada runtime spike is **closed** for this evidence package: Gate A passed, Gate B failed, and Gate C
remains **NO-GO**. No further primary action is required on this spike beyond the explicit unblock options
listed above.
