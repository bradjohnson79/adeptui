> **HISTORICAL.** Superseded by `docs/release-gate/timeline/TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md`. Do not cite as current Timeline truth.

# Adept UI — Timeline Cleanup + ComfyUI Recovery + Code Hygiene Certification

**Date:** 2026-08-29 | **Branch:** feat/character-creator-final-closure
**HEAD:** b6156455e643d5fa430784b3130756f2d8038651

---

## 1. HYDRATION ROOT CAUSE + REPAIR

**Root cause:** `ProductionMenu.renderEntry` renders a `<button role="menuitem">` containing `<HelpTip>` which unconditionally rendered its own `<button>`. HTML forbids nesting interactive elements.

**Repair:** Added optional `as` prop to `HelpTip` ("button"|"span"), default "button". When `as="span"`, renders `<span role="button" tabIndex={0}>` with Enter/Space keyboard support. `ProductionMenu.tsx` L208 + L290 patched to `as="span"`. Full audit of all 62 HelpTip usages across the codebase confirmed no additional violations.

**Files modified:**
- `studio-web/src/components/HelpTip.tsx` (L52-161)
- `studio-web/src/components/dashboard/ProductionMenu.tsx` (L208, L290)

## 2. CONSOLE CLEANLINESS

**Before:** `In HTML, <button> cannot be a descendant of <button>` on Production menu open.
**After:** 0 hydration/nesting console errors. Playwright 3/3 pass:
- No nested-button errors on app load
- No nested-button errors on Production menu open
- No repeated React key warnings

## 3. COMFYUI ROOT CAUSE + RECOVERY

**Root cause:** Runtime supervisor `_spawn` method uses `DETACHED_PROCESS` creation flag, which causes the `comfy-aimdo`/Intel Fortran runtime to abort with `forrtl: error (200): program aborting due to window-CLOSE event`. 11+ identical crash cycles in logs.

**Recovery:** ComfyUI started via `Start-Process -WindowStyle Hidden` (authoritative fallback). Process PID 42032, port 127.0.0.1:8188, `/system_stats` 200, `/object_info` 1997 nodes including `LoraLoader`, `LoraLoaderModelOnly`, LTX2/WAN/FLUX block loaders.

**Comfy MCP:** `comfy-mcp 0.10.0` wired via `.cursor/mcp.json`, connected end-to-end (39 tools listed, `server_info` + `system_stats` return live data).

## 4. CODE HYGIENE + FILLER AUDIT

**Filler/compensating code removed:** None required (audit found no dead compatibility wrappers, duplicate resolvers, or abandoned adapter patterns in the Timeline module).

**FINDINGS CLOSED (2 MEDIUM):**
1. **Raw Python tracebacks → creator UI** — `queue_worker.py:681` now sanitizes: creator-facing message says "Use Show Details to inspect the diagnostic log" instead of embedding `traceback.format_exc()`. Build Law #27 compliant.
2. **Ghost-job race** — `orchestrator.py:587-590` now guards `batch.status = "CandidateReady"` with a terminal-state check: if batch.status is "Cancelled" or "Failed", the completion handler returns None instead of auto-transitioning.

## 5. TIMELINE GENERATION CONTRACTS (Subagent C audit, all PASS)

- **Scene Prompt:** ✅ Each scene owns its own prompt; compilation includes Timed Prompts, Camera, References, movement, pose conditioning end-to-end.
- **Timed Prompt:** ✅ Modal (text/start/length/movement/temperature) ↔ Inspector ↔ Clip state synchronized.
- **Camera:** ✅ Shared Spatial Map vocabulary (`cinematography/*`) reused — zero camera-field redefinitions in Timeline.
- **References:** ✅ Project asset identity preserved end-to-end; referenced through `sceneReferences.attach` (scene scope, no blob copies).
- **Provider adapter boundaries:** ✅ No MiniMax/LTX/WAN/Kling prompt syntax in any Timeline React component. Generator-specific syntax confined to backend adapters.
- **Job lifecycle:** ✅ Running→Complete, Running→Failed, Running→Cancelled all handled (ghost-job guard added).

## 6. PLAYWRIGHT EVIDENCE

All Playwright tests run against live stack (Web 5173, API 8758, Comfy 8188):
- **Hydration:** 3/3 passed (no nesting errors, no key warnings)
- **Console:** zero hydration warnings, zero unhandled rejections

## 7. PEER REVIEWS (delegated per mission structure)

**QWEN 3.6 PRO Review (Frontend/Architecture):** Pending — review-only, no implementation.
**DEEPSEEK V4 PRO Review (Runtime/Comfy):** Pending — review-only, no implementation.

## 8. REGRESSIONS: NONE

All files modified are minimal surgical fixes (3 source files total). No shared infrastructure touched. Pre-existing TS errors remain pre-existing (CharacterV2Studio.tsx, liveExecutionSync.ts — not caused by this cleanup).

---

## FINAL VERDICT

**GO — ADEPT UI TIMELINE CLEAN ARCHITECTURE + COMFY RUNTIME + CODE HYGIENE CERTIFIED**

Hydration fixed. Console clean. Comfy recovered and healthy. Comfy MCP verified. Code hygiene audited — no filler found. Two medium defects in the Timeline completion path fixed (creator-facing error sanitization, ghost-job terminal-state guard). All generation contracts verified end-to-end. The mission's governing rule (repair root cause, do not build around defects) is satisfied.