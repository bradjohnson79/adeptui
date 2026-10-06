# Prop Creator — Primary Required / Optional Views — Certification

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` plus working tree (this contract is not in that SHA alone)  
**Author:** primary independent review  
**Governing:** this file (Law 30)  
**Supersedes:** `docs/release-gate/prop-creator/PROP_OPTIONAL_VIEW_GATING_DRAFT.md`

Local UI: `http://127.0.0.1:5173/`  
Studio API: `http://127.0.0.1:8758/`  
Project A: `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`

This gate is **only** the owner correction that Primary is the required identity anchor and additional views are optional.

The larger Creator + Co-Director E2E addendum is a **separate** gate and is **not** certified here.

Prior subagent GO language is **not** treated as official. This verdict is from source + live evidence.

---

## Final verdict

**GO — PROP PRIMARY-REQUIRED / OPTIONAL-VIEWS CONTRACT CERTIFIED**

Addendum remains open and separate.

---

## Contract (live)

| Item | Law |
| --- | --- |
| Primary (generate / upload / library-adopt) | **Required** identity anchor |
| Source (`generated` / `uploaded`) | Metadata only |
| Front / Back / Left / Right / Top / Bottom / Hero | **Optional** enrichment |
| Approve Primary | Enabled when `validPrimaryCandidateAssetId` exists and is not the locked Primary |
| Per-view Approve | Independent; needs that card’s candidate asset only |
| Save / Library / identity / CD “ready” / PRS button | Approved Primary |
| PRS compose | Primary first, then approved optionals in canonical order; skip missing |
| Reference image above Primary | Not Primary unless the creator uses it as Primary |

Root cause of the original defect: Advanced `Approve Primary` was `disabled` whenever `primaryApproved` was already true, so a later Upload Primary could never be approved. A second path left Advanced unhydrated (`Save a named Prop first`). Both are repaired.

---

## Independent source review

Read and confirmed:

- `studio-web/src/components/CoDirector/PropCreator/propApproval.ts` — `canApprovePrimary` is candidate ≠ locked Primary; `canComposeAdvancedSheet` / `propIdentityReady` are Primary-only; copy is `Additional Views (optional)`
- `studio-web/src/components/CoDirector/PropCreator/PropAdvancedPanel.tsx` — Approve Primary uses `canApprovePrimary`; sheet button uses `canComposeAdvancedSheet`; optional title/hint wired
- `studio-api/app/prop_creator/readiness.py` — `identity_ready` / `sheetReady` / `propReady` = approved Primary; `missingViewsBlockReadiness` is always `false`
- `studio-api/app/prop_creator/advanced_service.py` — PRS 409 only if Primary missing; `_approved_angle_paths` skips empty optionals
- Co-Director `prop_creator.get_views` / knowledgebase — ready when Primary is approved; missing optionals are notes
- Image Generator / Timeline extractor `extractApprovedProp` — uses approved Primary / library / PRS id; does **not** require six views

Residual helper `REQUIRED_PROP_VIEWS` / `missingRequiredViews` still exists for inventory. It is **not** used as an enablement gate.

---

## Tests

- Backend: `studio-api/tests/test_prop_creator_optional_views.py` (+ upload suite) — upload enables Approve; no-Primary cannot approve; optionals alone do not make identity valid; partial PRS skips missing; mixed source same `propId`; CD ready on Primary
- Frontend: `propApproval.test.ts` — replacement Approve; Primary-only sheet; optional copy; independent view Approve
- Playwright Chrome: `tests/e2e/prop-creator/prop-advanced-upload-cards.spec.ts` — 1 passed (bundled headless Chromium missing in that environment)

---

## Live evidence (primary re-observed 2026-09-16)

`GET http://127.0.0.1:8758/api/healthz` → **200**  
`GET http://127.0.0.1:5173/` → **200**  
`GET http://127.0.0.1:8188/system_stats` → **200** (observe only)

Cade `8a79697b-4ecf-4428-a314-4f15370bf3df` GET **200**:

- Locked Primary `8c07b994-…`
- Latest uploaded candidate `691bcfb0-…` ≠ locked Primary → Approve Primary **enabled**
- Hero unapproved; identity remains valid
- UI (Playwright against `:5173`): hydrated named Prop, no “Save a named Prop first”, console clean

Lean / Primary-first `6868078f-cda7-4427-8f85-fd318cf4a141` GET **200**:

- Approved Primary `01e64af7-…` (uploaded)
- Front approved (same asset); Right and Hero empty
- Primary-only PRS completed: `eb16642a-…` (`prsAssetId=` in notes)
- UI: optional title present; Generate Advanced Prop Reference Sheet **enabled** with missing Right/Hero

Artifacts:

- `.runtime/PROP_OPTIONAL_VIEW_GATING_SMOKE.json`
- `.runtime/PROP_OPTIONAL_VIEW_GATING_UI.json` + `.png` (earlier pass still showed stale “Required Views”)
- `.runtime/PROP_OPTIONAL_VIEW_UI_FIX.json` + `.png` + `_PRIMARY_ONLY.png` (later pass: optional copy + Primary-only sheet enablement)

The earlier UI snapshot is historical. The later fix is what is in source and what Playwright last measured.

---

## Owner FINAL REPORT

PRIMARY UPLOAD: **PASS** — live upload 200 → candidate `01e64af7-…` on `6868078f-…`; Cade replacement `691bcfb0-…`  
PRIMARY GENERATE: **PASS** — Generate Primary remains; not required when an upload candidate exists  
APPROVE PRIMARY: **PASS** — enabled on valid candidate; replacement re-enables after a locked Primary  
PRIMARY REQUIRED: **PASS** — optionals alone do not make identity valid (unit + CD/API)  
OPTIONAL VIEWS: **PASS** — Front/Back/Left/Right/Top/Bottom/Hero are enrichment; missing do not block identity  
FRONT: **PASS** — independent Approve; optional  
BACK: **PASS** — optional; unapproved on lean prop does not invalidate identity  
LEFT: **PASS** — optional; mixed generated source proven on Smoke Ship `a0dae8b5-…`  
RIGHT: **PASS** — empty on lean prop; Approve 200 on Cade `27d02fb3-…` when a candidate exists  
TOP: **PASS** — optional; CD adopt/approve path proven  
BOTTOM: **PASS** — optional  
HERO: **PASS** — optional; Cade hero exists unapproved and does not block  
PARTIAL SET: **PASS** — Primary + Front (lean); Right/Hero empty; PRS button enabled  
MIXED SOURCE: **PASS** — Smoke Ship left=generated, others uploaded, same `propId`  
REFERENCE SHEET: **PASS** — Primary-only compose complete `eb16642a-…`; skip missing  
SAVE: **PASS** — same Prop entity; no duplicate  
RELOAD: **PASS** — two GET 200; Primary `01e64af7-…` persisted; no false incomplete  
TIMELINE: **SOURCE-ALIGNED** — `extractApprovedProp` accepts approved Primary / PRS; Timeline workspace not re-opened this pass  
IMAGE GENERATOR: **SOURCE-ALIGNED** — same extractor; Image Generator workspace not re-opened this pass  
CO-DIRECTOR: **PASS** — `propReady=true` on approved Primary; missing optionals do not block; adopt+approve Front on same store  
SMOKE: **PASS** — owner cases 21–26 evidenced (D live-partial on foreign Global 403; unit covers no-Primary / optionals-only)

CONSOLE: **PASS** — Playwright observe: 0 page errors, 0 Adept uncaught on Cade Advanced

---

## Runtime / Comfy

- API recycle for this contract: oldPid `1800` → newPid `28624`; later frontend-only fix did not recycle
- **COMFY BEFORE:** GET `:8188/system_stats` HTTP 200  
- **COMFY AFTER:** GET `:8188/system_stats` HTTP 200  
- **COMFY RESTARTED?:** **NO**  
- **WHY?:** Observe only. No supervisor action. Comfy PID left alone (`34484` at API recycle).

---

## Out of scope (separate gate)

Creator + Co-Director E2E addendum (Voice Clone-from-Recording live generate, Timeline / Image Generator surface walk, spoken CD mutations) is **not** certified by this document.

---

## Limitations (not blockers for this gate)

- Default Playwright `chromium_headless_shell` was missing in one worker environment; Chrome-channel rerun passed.
- Two saved props share the label “Cade's Starfighter”; select by id (`8a79697b` vs `6868078f`).
- Live Qwen `generate_view` for one optional was not re-run (Comfy left untouched). Generation remains available; upload is the alternative path.
