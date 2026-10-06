# Prop Creator — Optional View Gating (Owner Correction) — Draft

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` (working tree not committed)  
**Author:** implementation + live-verification worker  
**Status:** SUPERSEDED — official governing document is `docs/release-gate/prop-creator/PROP_OPTIONAL_VIEW_GATING_CERTIFICATION.md`

Local UI: `http://127.0.0.1:5173/`  
Studio API: `http://127.0.0.1:8758/`  
Project A: `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`

---

## Draft verdict recommendation (not official)

**Recommend GO on the contract change**, with primary doing one browser click on Advanced → Cade's Starfighter.

Approve Primary should now be **active** on Cade (`8a79697b-…`) because a replacement upload (`691bcfb0-…`) is not the locked Primary (`8c07b994-…`). That is the exact owner defect.

---

## Root cause of disabled Approve Primary

Two independent gates:

1. **Replacement lock (main functional defect).** Advanced Approve Primary was  
   `disabled={busy || primaryApproved || !candidates.some(complete+asset)}`.  
   After a named Prop already had an approved Primary, **any later Upload Primary stayed unapprovable**. Cade still shows this: latest candidate `691bcfb0` ≠ approved `8c07b994`.

2. **Unhydrated Advanced panel.** Status `Save a named Prop first` when local `prop` was null. Advanced tab had no Saved Prop picker, so Upload/Approve stayed dead if the creator opened Advanced without a hydrated entity.

Secondary: PRS / Co-Director `sheetReady` required all of front/back/left/right/top/bottom. Missing optional views were treated as blockers.

---

## What is required vs optional

| Item | Law |
|---|---|
| Primary (generated / uploaded / library-adopt) | **Required** identity anchor |
| Source metadata (generated vs uploaded) | Metadata only |
| Front / Back / Left / Right / Top / Bottom / Hero | **Optional** enrichment |
| Approve Primary | Enabled when `validPrimaryCandidateAssetId` exists and is not the locked Primary |
| Per-view Approve | Independent; needs that card's asset only |
| Save / Library / Timeline / Image Generator / CD "ready" | Primary approved |
| PRS | Primary first, then approved optionals in canonical order; skip missing; no empty placeholders |
| Reference image above Primary | Not Primary unless the creator uses it as Primary |

---

## Live smoke (owner 21–26)

Evidence: `.runtime/PROP_OPTIONAL_VIEW_GATING_SMOKE.json`

| Case | Result | IDs / HTTP |
|---|---|---|
| A Upload Primary → Approve → valid without other views | **PASS** | Prop `6868078f-cda7-4427-8f85-fd318cf4a141` (existing second Cade, not a new project). Upload 200, approve 200, asset `01e64af7-…`. Optionals empty at approve. |
| A PRS primary-only | **PASS** | Sheet generate 200 → complete, sheet asset `eb16642a-…` |
| B Partial Front/Back/Top; Right/Hero not required | **PASS** | Cade `8a79697b-…`. Approve Right 200 (`27d02fb3-…`). Hero remains unapproved. Identity still ready. |
| C Mixed uploaded/generated, same propId | **PASS** | Smoke Ship `a0dae8b5-…`. left=generated, others uploaded. |
| D No Primary / optionals-only | **PARTIAL LIVE** | Foreign Global empties 403. Unit tests cover both. Live: after lock, `canApprovePrimary=False` on `6868078f`; unknown candidate 400. Cade still has an unapproved replacement candidate (old UI would keep Approve dead). |
| E CD ready on Primary; one optional; others empty | **PASS** | `propReady=true`, `missingViewsBlockReadiness=false`. Adopt+approve Front on `6868078f`. Generate-via-Qwen not live-run (Comfy left untouched). |
| F Reload | **PASS** | Two GET 200; Primary `01e64af7-…` persisted; no false incomplete. |

Browser MCP / Playwright browser binary were unavailable in this worker. Vite HMR is live at `:5173`.

---

## Tests

- Backend: `tests/test_prop_creator_optional_views.py` + `tests/test_prop_creator_view_upload.py` → **13 passed**
- Frontend: `propApproval.test.ts` + `propCreatorContracts.test.ts` → **20 passed**

---

## Runtime

- Studio API recycle only: `scripts/restart_studio_api_only.py` → oldPid 1800, newPid 28624, **comfyPid 34484 unchanged**
- `GET http://127.0.0.1:8758/api/healthz` → 200
- `GET http://127.0.0.1:5173/` → 200
- **COMFY BEFORE:** GET `:8188/system_stats` HTTP 200  
- **COMFY AFTER:** GET `:8188/system_stats` HTTP 200  
- **COMFY RESTARTED?:** NO  
- **WHY?:** Ordinary API recycle; supervisor left `:8188` owned/unchanged

---

## Remaining for primary

- Click Advanced on Cade `8a79697b` and confirm Approve Primary is enabled for the replacement upload.
- Optional: live Qwen `generate_view` for one angle (not run here).
- Do not treat this draft as official GO.

READY FOR PRIMARY REVIEW
