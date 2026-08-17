# Spatial Prop + ERS Production Binding — Certification

**Status:** Governing document for this closure.
**Date:** 2026-08-17
**Closure commit:** `6536b243fea5b7741e7c2a03ea950709d7a6c651` (pushed; local == origin/beta)
**Deployed:** alias `adeptui.vercel.app` -> `adeptui-6cz6x2o3r-anoint` (Ready, built from closure push)
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`
**Branch:** beta
**Live API:** `http://127.0.0.1:8758` · **Tunnel:** `https://api-beta.adeptui.org` · **Hosted UI:** `https://adeptui.vercel.app`

---

## Verdict

**GO — SPATIAL MAP PROP + ERS PRODUCTION HANDOFF CERTIFIED END TO END**

Qwen local ERS I2I outcome: **QWEN LOCAL ERS I2I — NOT AVAILABLE; UI CAPABILITY HONEST** (the graph consumes the source image but the pixel result is a dark void, not a usable ERS; selection-time honesty added; GPT Image 2 remains the working API I2I path).

---

## Part A — Prop #2 production binding

### Root cause

The live Spatial Map (`6bc36d92` v109+) has **one** canonical-bound prop (Clear Glass Cup `78c5be96`, slot 0). The mission's "Prop #2" is the second prop **slot** (brown, slot 1). A placement created from a **Library / Character** saved option carries `propId: null` and category `prop`/`character_prop` — the frontend only allowed binding an approved Project Prop **at add time** (the "Select Saved Prop" dropdown renders only in the unassigned branch). An assigned map-only placement had **no re-bind control**, so Prop #2 could never be promoted to production. That is the blocker.

### Canonical truth (audited)

| PropEntity | Label | approved_asset_id | Asset row exists? | Notes |
| --- | --- | --- | --- | --- |
| `78c5be96` | Clear Glass Cup | `b157845d` | YES (approved) | slot 0, bound |
| `a8d48a46` | Coffee Cup | `c8738572` | **NO (deleted)** | stale legacy ref in shots (ERS snapshot) |
| `8d59f076` | E2E Standard Cup | `f88c531d` | YES (approved) | used for live bind proof |

### Fix (smallest delta, no second prop system)

- **Backend (small hardening)**: `update_prop` (PATCH) already validates CDX-013 (propId must resolve to a project-owned PropEntity). `_prop_ids_from_map` (production_handoff.py) and `_placed_project_prop_ids` (service.py) already enforce the CDX-015 approved-only filter; **hardened** so the approved asset row must still exist — a prop whose approved asset was deleted (stale/deleted prop ID, e.g. Coffee Cup `a8d48a46` -> deleted `c8738572`) is excluded instead of propagating a dangling reference.
- **Frontend**:
  - `PlacementSlot.tsx`: assigned map-only prop placements now show a **"Select Saved Prop" bind control** (approved `project` options only) + three honest states: map-only warning, "Bound to approved Project Prop — included in Scene Creator shots." (positive), "Project Prop selected, but it is not approved for production." (unapproved).
  - `SpatialMapPanel.tsx`: `handleBindProp` PATCHes `propId` + `category: "project"` via the existing `updateProp` API.
  - `types.ts`: `propPlacementIsBoundApproved` + bound/unapproved message constants.

### Live proof (Schnick Coffee, real API)

1. Placed map-only prop in slot 1 (Prop #2) → `propId: null`, category `prop` (map-only warning state).
2. Bound it to **E2E Standard Cup `8d59f076`** (approved Project Prop) via PATCH → `propId` set, category `project`.
3. Workspace (`GET /api/scene-creator/projects/{pid}/workspace`) now lists the prop: `8d59f076 | E2E Standard Cup | approved_asset f88c531d`.
4. Production handoff sync (the "Continue to Scene Creator" path) → shot `88539183` `prop_entity_ids` = `['a8d48a46', '78c5be96', '8d59f076']` — **canonical Project Prop ID propagated into Scene Creator**.
5. Reload (GET) → binding persists: slot 1 still `propId: 8d59f076`, workspace still lists both props.
6. No cross-project IDs (CDX-013/015 enforced; foreign prop rejected with `PROP_ENTITY_NOT_FOUND`).

Approval law preserved: unapproved bound props stay excluded (test-proven); map-only placements stay excluded until bound to an approved Project Prop.

---

## Part B — Qwen local ERS I2I

### Audit result

| Item | Finding |
| --- | --- |
| Workflow registry | `qwen2512.ref` IS **Certified** (record `phase2-qwen2512-ref-ers-i2i-2026-08-16`), supports `image.reference`, `LoadImage` + `TextEncodeQwenImageEdit` |
| Models on disk | `verify_component("qwen_image_2512_models")` → **healthy** (weights present) |
| Provider readiness | `qwen-image-2512-local` → `readiness: "draft"` (capability "Available" not "Certified"; setup-lifecycle cert record missing) |
| FE gate | `isQwenI2IReady` requires readiness `ready` + reference token → **false** → honest block |

### Live Qwen ERS run (real, decisive)

Enqueued a real Qwen ERS job via the codirector execution API (exact FE call):
- Execution `6b736697`, child job `ed5068d2` → **`resolvedWorkflowKey: qwen2512.ref`**, `operationIntent: image_to_image_reference`, provider local.
- ComfyUI executed the certified graph (`UNETLoader qwen_image_2512_fp8_e4m3fn.safetensors` + `qwen_2.5_vl_7b` CLIP), **source consumed**: asset `4e9e5ae7` prompt_meta `parentImages: ["4d3062e8-…"]` (original café photo), referenceHash recorded, 2560×1440.
- **Pixel verdict: FAIL.** Output is a dark void: 71% pure-black pixels, median RGB (0,3,2), mean (10,12,14), negative correlation with the warm café source (mean 47,33,23). This reproduces the Phase 2 documented "dark void" failure; bounded repairs previously failed.

### Decision (per mission §17)

**QWEN LOCAL ERS I2I — NOT AVAILABLE; UI CAPABILITY HONEST.** The graph consumes the source image (proven) but does NOT produce a usable ERS (pixel proof fails), so it is not certified for ERS. No fake Qwen I2I, no capability inflation.

### Fix

- `ersGenerator.ts`: `ersGeneratorOptionDisabled` — a generator whose I2I path is unavailable is **disabled at selection time** (option shows "_— Unavailable for ERS"), not just blocked by a late runtime message.
- `SpatialMapPanel.tsx`: the ERS generator select applies it; GPT Image 2 (readiness `ready`, supports `edit`) stays selectable.
- `useErsGeneration.ts`: exposes `qwenI2IReady`/`gptI2IReady` to the UI.

### GPT Image 2 regression (§18) — PASS

Real API ERS job `fce2791e` → child `171d6bb0` **`kie:gpt-image-2-image-to-image`** completed `done p=1.0`, output `imagegen_kie_d95eaf44.png` (asset `bd053577`). Pixel check: mean RGB (49,41,32) vs source (47,33,23), only 9.4% black — a real café-preserving ERS. Explicit creator choice; no silent switching.

---

## Part C — Combined Schnick E2E

API-level chain (authoritative backend truth; Playwright browser spawn is sandbox-blocked — see Limitations):

```
Spatial Map Prop #2 (slot 1, map-only)
  → bind approved Project Prop 8d59f076 (PATCH, CDX-013 validated)
  → workspace props include 8d59f076 (approved asset f88c531d)
  → production handoff sync (revision 29→30)
  → shot prop_entity_ids += 8d59f076
  → reload → binding persists
  → ERS generator: Qwen disabled (unavailable), GPT Image 2 selectable → GPT ERS completes (real café output)
```

No cross-project IDs. No second prop system. No second ERS architecture.

---

## Part D — Tests

| Suite | Result |
| --- | --- |
| Backend `test_spatial_prop_ers_binding.py` (new) | **7 passed** — map-only excluded; approved bind propagates; unapproved stays excluded; deleted-approved-asset excluded; foreign rejected; ERS key; no silent GPT |
| Backend spatial + grounding + ERS handoff regression | **40 passed** |
| Frontend SpatialMap suite | **112 passed** (11 files) incl. new binding-state + disabled-option tests (34 in the 3 targeted files) |
| `tsc -b` | exit 0 |
| Production build | sandbox-blocked at config-load spawn (documented); Vercel builds from clean checkout |
| Playwright | `tests/e2e/spatial-prop-ers-binding.spec.ts` written; execution blocked by DSH sandbox spawn EPERM (full-access escalation failed closed — no answerer). Not faked; the API-level chain above is the authoritative evidence. |

---

## Limitations (honest)

1. Playwright browser render not executed in this session (sandbox spawn EPERM; escalation fail-closed). Spec is committed for CI.
2. Qwen local ERS I2I is NOT certified for ERS (pixel proof fails); selection-time disabled + honest label added.
3. Coffee Cup `a8d48a46` approved asset deleted (legacy); it remains in shots via the ERS package snapshot (CDX-014 design, authoritative-at-generation-time) — not a current-map leak, documented.
4. The mission's Prop #2 (slot 1) did not pre-exist in the live map; the fix makes the binding path available for any map-only placement.

---

## Independent verifier

Required verdict: **VERIFIED — SPATIAL PROP + ERS PRODUCTION BINDING PASSED** (independent verifier `6a22a4c2`, re-verified on settled tree) ·
Qwen: **QWEN LOCAL ERS I2I — NOT AVAILABLE; UI CAPABILITY HONEST**.
Deployment: commit `6536b24` pushed, Vercel Ready, hosted bundle carries the new bound/unavailable strings; hosted tunnel smoke passed (map slot 1 bound, workspace shows E2E Standard Cup, Qwen draft / GPT ready).
