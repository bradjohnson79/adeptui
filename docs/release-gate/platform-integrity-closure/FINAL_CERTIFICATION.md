# Adept UI Platform Integrity Closure — Final Certification

Owner-facing unified report: [`ADEPT_UI_PLATFORM_INTEGRITY_CLOSURE_UNIFIED_REPORT.md`](ADEPT_UI_PLATFORM_INTEGRITY_CLOSURE_UNIFIED_REPORT.md).

**Date:** 2026-08-30  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651`  
**Surface:** CURRENT DEVELOPMENT (dirty worktree; no commit/push/deploy)

## Verdict

**GO — ADEPT UI PLATFORM INTEGRITY CLOSURE + OWNER-TESTING READINESS E2E CERTIFIED**

## Gate O — Owner double-check

| Question | Answer |
|---|---|
| Did we fix sources? | Yes — scoped assets, one generator join, watcher `auto_approve=False`, knowledge compile on W46, MiniMax 5/24, supervisor Route A adopt, Timed Prompt X → master. |
| Did we remove superseded architecture? | Unscoped file/thumb 403; Timeline catalog is a view; fossil engine lists use `EngineAuthoritySelect`. Unused workspaces not deleted (no zero-consumer proof). |
| Did we introduce a second authority? | No. Join + presenters. Peers confirmed. |
| Are any fake states left? | MiniMax does not claim 15s. Home no longer first-use-while-loading. Library approval tag can lag Timeline Approve (disclosed). |
| Does UI agree with runtime? | Live join: LTX 2.3 Ready/exec; LTX 2.5 Testing/not exec; WAN/Hunyuan Unsupported; MiniMax Testing max 0.2083. |
| Does reload work? | Playwright X-delete survives reload. LTX Approved batch + scoped file survive later API reads. |
| Can creator controls be trusted? | Generate → CandidateReady → Approve. X deletes both lanes. Resume copy = requeue. |
| Does generator selection equal actual execution? | Live LTX used `ltx-local` / `ltx.simple_i2v` / `ltx-2.3-22b-distilled-fp8.safetensors`. |
| Does MiniMax duration equal actual output? | No 15s claim. Advertised max 5/24. No new MiniMax generate this closure. |
| Did Comfy MCP verify the relevant graph? | Stdio MCP verified live `:8188` instance, GPU, nodes, checkpoints. Per-job graph dump of `bb_c1eb5` was not re-run via MCP this pass (Comfy prompt id is on the asset meta). |
| Can the owner now use Adept normally? | Yes, for owner-testing on this dirty tree. See `18_REMAINING_NON_BLOCKING_ITEMS.md`. |

## Peer supervision

| Reviewer | Per-gate | Final |
|---|---|---|
| Kimi K3 | A–H PASS or PASS WITH NON-BLOCKING | **PASS WITH NON-BLOCKING** (`eda327f4`) |
| GLM 5.2 | A–H PASS or PASS WITH NON-BLOCKING | **PASS WITH NON-BLOCKING** (`a8130809`) |

No FAIL. No BLOCKING finding left open.

## Tests (measured)

- Backend A–G + LoRA kwargs: **78 passed**
- Adapters + production dock: **41 passed**
- Frontend `draftCapabilities.test.ts`: **4 passed**
- Playwright chromium (live :5173/:8758): **2 passed** (Home hydration + Timed Prompt X undo/redo/reload)

## E2E TRACE

| Stage | Result |
|---|---|
| User action | Home library + Timeline X + SenseNova LTX Generate/Approve |
| Frontend | Vite `:5173` 200; Home cards (SenseNova, Schnick) after load; X on Timed Prompt |
| API | `:8758/api/healthz` 200; scoped file 200; unscoped 403 |
| Backend | W46 generate `ltx-local`; approve requires `candidateId`; `auto_approve=False` |
| Persistence | Master + director; Approved `bb_c1eb5212d68b` |
| Runtime | Comfy Desktop `:8188`; model `ltx-2.3-22b-distilled-fp8.safetensors` |
| Result | MP4 688043 bytes; ffprobe 1280×704, 24 fps, 113 frames, **4.708s** |
| Reload | Playwright X stays gone; Approved batch still Approved |
| Downstream | Library row present; scoped playback 200 |

## Live URLs (left running)

- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/`
- Do not treat `:8760` as product UI.

## Limitations (non-blocking)

See `18_REMAINING_NON_BLOCKING_ITEMS.md`. Notable: no MiniMax 15s media (honest ~0.21s); supervisor `restart` may reuse uvicorn; dirty tree not committed; Character/Prop/ERS Playwright not re-run this pass.

## Release safety

No commit, push, merge, tag, or deploy was performed.
