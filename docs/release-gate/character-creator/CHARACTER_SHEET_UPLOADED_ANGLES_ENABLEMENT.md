# Character Sheet creation from uploaded / generated angles

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure` @ `99665cf7` plus this working tree  
**Project:** Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`  
**Character:** Cade O'Connor `85e37d4b-a32e-4374-888b-1389fc0b3720`  
**Review:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/  
**Verdict:** **GO — CHARACTER SHEET CREATION FROM UPLOADED / GENERATED ANGLES CERTIFIED**

## Root cause

`Save and Create Character Sheet` was gated on Co-Director vision lock and live Qwen generation waits, not on four approved canonical views. The live Cade helper that said **Approve Front** was truthful at that moment (Front `3869398f-…` was a ready, unapproved candidate). After Approve Front, the old lock requirement would have kept the button disabled (`Wait for Co-Director…`) even though Side / 3/4 / Back were already approved uploads.

## Contract

`canCreateSheet` is now:

- approved Front asset id
- approved Side asset id
- approved 3/4 asset id
- approved Back asset id
- same `characterId` when `prompt_meta.characterId` is present

Source (`uploaded` | `generated`) and visual lock are not a gate. Compose stitches those four approved assets locally. No Qwen, no missing-angle fallback.

## Live Cade

| Check | Result |
| --- | --- |
| Front | Approved `3869398f-0304-4f4d-bd61-f9042d0436e0` (prior candidate; not auto-approved) |
| Side | Approved uploaded `4cd47b9c-5bc0-44b1-85f0-21709f1c9c78` |
| 3/4 | Approved uploaded `9ba8fa3c-9031-4de4-943a-24c0300f823f` |
| Back | Approved uploaded `61621aa5-f613-40cc-b8e5-d3e1ade654d1` |
| Gate while lock=`running` | `ready=true`, next=`Character Sheet ready to create.` |
| Button | Enabled immediately after Front approval |
| Helper | `Approve Front` while Front unapproved; then `Uses the current approved Front, Side, 3/4, and Back.` / `Character Sheet ready to create.` |
| Click compose | Local stitch; UI showed `Creating Character Sheet…` then `Character Sheet Ready 100%` |
| Sheet asset | `b6565a04-4f83-4452-b587-461e74ad9369` 2560×1080 PNG, Library HTTP 200 |
| Lineage | `sourceAssetIds` + `viewAssetIds` = the four approved ids above; `characterId` + `@Cade O'Connor` |
| Qwen | Job list unchanged (5 jobs; no new `imagegen_edit`) |
| Reload | Sheet image still bound; phase `SHEET_READY` |
| Co-Director | `get_angles` / `inspect_readiness` return the same `sheetGate`; next=`Character Sheet ready to create.` |

## Tests

`studio-api` `tests/test_cc_v3.py`: **42 passed**  
Includes lock-ignored, mixed A–D (all-generated / all-uploaded / mixed both ways), missing Front, unapprove / replace-upload disables, foreign `characterId` bind, local compose without Qwen.

`studio-web` presence: **3 passed**

## Runtime

- Studio API recycled only (`42740` → `34116` → `9968`)
- Vite `:5173` 200 (HMR)
- **COMFY BEFORE:** PID `34484` / health 200  
- **COMFY AFTER:** PID `34484` / health 200  
- **COMFY RESTARTED?:** NO  
- **WHY?:** Ordinary Character Creator / API work. `:8188` is Comfy Desktop `python.exe` — observe only.
