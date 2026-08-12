# MiniMax H3 Adept UI Surface Wiring — Certification

**Date:** 2026-08-03  
**Branch:** `feature/ai-guided-setup`  
**Starting / baseline SHA:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Working tree:** H3 surface wiring present (uncommitted relative to baseline)  
**Beta:** http://127.0.0.1:8760/  
**API:** http://127.0.0.1:8758/  
**Manual handoff project:** `77a4b96c-8e3f-4501-897c-51bab99bedb7` (unchanged)

## Verdict

**GO — H3 ADEPT UI SURFACE WIRING READY**

This certifies Adept UI surface honesty and wiring only.  
Surface wiring GO ≠ Creator production enablement.

> **Supersession (local runtime):** The earlier note that local GPU weight generation was `NOT LOCALLY FEASIBLE YET` applied to the pre–Route A state. For current local-runtime status, use [`H3_UNIFIED_MILESTONE_REPORT.md`](H3_UNIFIED_MILESTONE_REPORT.md) — Route A is PRIMARY ACCEPTED as `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED`; Creator H3 remains Disabled. Canada-only license correction remains in `docs/models/minimax-h3/H3_CANADA_LICENSE_CLEARANCE.md`.

## Mission result

MiniMax H3 is wired through Adept UI surfaces. ComfyUI is not the creator-facing workflow.

| Surface | Wiring | Evidence |
|---|---|---|
| Co-Director | `minimax_h3.*` tools (capability, plan, three-frame, LTX fallback) | Playwright A |
| Text2Video | Engine `minimax-h3` + MiniMax H3 Plan panel + explicit LTX fallback | Playwright B |
| One Frame | Start Frame labeling + draft motion prompt + H3 plan panel | Playwright C |
| Three Frame | Start / Middle Guidance / End strip + Strategy A (segmented) honesty | Playwright D + API plan |
| Timeline | H3 plan panel on Timeline Master | Code + registry |
| Production Dock / Model Library | MiniMax H3 Requires Setup (not fake Coming Soon) | UI copy |
| Library / provenance | Plan receipts + fallback acceptance records | Playwright E artifacts |
| Native audio | Import/metadata helper; no false stem claims | Backend `audio_import` |
| Audio Studio | Consumes project audio assets once imported; no separate H3 stem UI claimed | Limitation noted |

## Runtime truth (certified)

1. **FL2VA accepts 0/1/2 frames only** — not three native temporal anchors.  
2. **`threeFrameNative: false`** — Adept defaults to **Strategy A** (Start→Middle, Middle→End) with creator disclosure.  
3. **Excluded-territory local weights blocked; Canada-only local development reopened with conditions.**  
4. **LTX permanent fallback** — explicit accept only; never silent switch; jobs do not invent completed H3 assets.  
5. Creator-facing copy avoids ComfyUI nodes, workflow JSON, checkpoint filenames, and filesystem paths.

## Evidence commands

```text
python -m pytest studio-api/app/minimax_h3/test_minimax_h3_surfaces.py -q
# result: 7 passed

ADEPT_BETA_TARGET=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 STUDIO_API_BASE=http://127.0.0.1:8758
npx playwright test tests/e2e/minimax-h3/minimax-h3-adept-ui-surface-cert.spec.ts --project=chromium
# result: 6 passed (11.8s)
```

## Playwright scenarios

| ID | Scenario | Result |
|---|---|---|
| A | Co-Director tools registered; no Comfy jargon in titles | PASS |
| B | Text2Video selects MiniMax H3; prepare plan; LTX fallback accept | PASS |
| C | One Frame Start Frame plan via Adept UI | PASS |
| D | Three Frame Strategy A honesty + UI strip | PASS |
| E | Local blocked; explicit LTX; no fake completed H3 job | PASS |
| F | Capability matrix `threeFrameNative: false`, `segmented-a` | PASS |

Artifacts: `docs/release-gate/minimax-h3/artifacts/H3-SURFACE-AUTONOMOUS-CERT-2026-08-03T21-24-57-798Z/`

- `D-three-frame-plan.json` — `strategy: segmented-a`, two intervals, no ComfyUI leak  
- `E-fallback.json` — blocked preflight + accepted LTX fallback  
- `F-capability.json` — US local `territoryAllowed: false`, `threeFrameNative: false`  
- `cleanup.json` — disposable cert project removed; handoff untouched  

## Shared contract

Canonical request surface: `AdeptMiniMaxH3Request` via `/api/minimax-h3/*`  
Docs: `docs/architecture/minimax-h3/ADEPT_MINIMAX_H3_REQUEST_CONTRACT.md`  
Three-frame truth: `docs/models/minimax-h3/H3_THREE_FRAME_RUNTIME_TRUTH.md`  
Wiring overview: `docs/models/minimax-h3/H3_SURFACE_WIRING.md`

## Checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved / intentionally frozen (H3 request + three-frame strategy)
[x] Full-stack surface wiring completed (API + Co-Director + Adept UI)
[x] Visible H3 plan controls wired (prepare / LTX fallback)
[x] Real runtime honesty; no mock completed H3 generation
[x] Plan/fallback persistence records verified via API
[x] Error/fallback recovery verified (blocked local → explicit LTX)
[x] Handoff project isolation preserved
[x] Unit + Playwright surface cert passed
[x] Failures repaired (One/Three Frame prompt scoping + nav)
[x] Production web build refreshed; Beta restarted
[x] Beta URL reported: http://127.0.0.1:8760/
[x] Limitations honest
[x] Verdict: GO (surface wiring) | local GPU generation still blocked
[x] No silent CPU/model fallback; LTX only on explicit accept
[ ] Local H3 weights executable on GPU — still unproven on Canadian runtime (out of scope for this GO)
```

## Limitations (honest)

- Canada-only local development is license-permitted with conditions, but no local H3 GPU proof is certified here; API deployment remains approval-gated.  
- Three Frame is **honest Strategy A**, not native three-keyframe conditioning.  
- Segmented Timeline join polish (crossfade ambience, retake-one-interval UX depth) is planned on the Strategy A intervals contract; full join editor polish is not claimed complete.  
- Native audio stem separation is not claimed.  
- Playwright suite certifies Adept UI surfaces and honesty gates; it does not open ComfyUI and does not prove a finished H3 media file under local Canadian runtime conditions.

## Manual review

1. Open http://127.0.0.1:8760/  
2. Open a disposable project (not Manual Beta Handoff).  
3. Text to Video → engine **MiniMax H3** → Prepare plan → confirm blocked preflight + LTX offer.  
4. One Frame / Three Frame → confirm Start / Middle Guidance / End language and MiniMax H3 Plan panel.  
5. Confirm no ComfyUI workflow is required for planning or fallback acceptance.

## Final binary certification

**GO — H3 ADEPT UI SURFACE WIRING READY**
