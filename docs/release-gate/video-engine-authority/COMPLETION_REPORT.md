# Video Engine Authority — Completion Report

**Date:** 2026-09-05  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455` (working tree dirty; this report is not a commit)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Surfaces:** Vite `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Governing:** `docs/release-gate/video-engine-authority/00_FREEZE.md`

Supersedes [docs/release-gate/local-video-runtime/COMPLETION_REPORT.md](../local-video-runtime/COMPLETION_REPORT.md) for “no local T2V / LTX 2.3 is the live LTX path” and generic hosted Seedance.

## Verdict

**E2E BLOCKED — Comfy MCP unavailable for workflow-level LTX/H3 graph cert; local Ready generate not re-run this session**

Authority join, versioned Seedance identities, CREATE pickers, Auto Select, and LTX 2.5 adapter bind are implemented and live-walked. That is not full-stack certification: no new local T2V/I2V job was executed, and Comfy MCP is not attached.

## Team note

Law 27 requires GPT 5.4 specialized subagents. The Task tool in this session does not expose `gpt-5.4-medium`. Primary executed all bounded streams and issues this verdict. Subagents were not launched with a substitute model.

## COMFY

| | |
|---|---|
| **COMFY BEFORE** | PID **69108** · HTTP 200 · Comfy 0.32.0 · torch 2.10.0+cu130 |
| **COMFY AFTER** | PID **69108** · HTTP 200 |
| **COMFY RESTARTED?** | **NO** |
| **WHY?** | Ordinary API recycle + UI/API edits. `:8188` left untouched. |

Studio API recycle via `scripts/restart_studio_api_only.py` timed out twice on health (120s) while Comfy PID stayed 69108. API later answered `GET /api/healthz` 200 on listener PID 47544. Vite `:5173` HTTP 200.

## What shipped

- `GET /api/engines` is a join view (`list_create_engines`): Auto Select, MiniMax H3, LTX 2.5, Seedance 2.0, Seedance 2.5, Kling/Veo/Runway. No `ltx` / `wan` / Hunyuan CREATE defaults. No generic `seedance-fal` / unlabeled “Seedance”.
- LTX 2.5 Timeline/CREATE execution bind is `ltx-2.5-distilled` (`Ltx25LocalAdapter`). `ltx-local` is LTX 2.3 only.
- Seedance 2.0 and 2.5 are distinct adapters and fal model IDs. Legacy `seedance-fal` / `seedance-api` / `fal_seedance` migrate to **2.0 only**. No 2.5↔2.0 remap.
- CREATE pickers consume `workflowCapabilities`. 3 Frame hides Seedance (no three-still workflow). Auto Select stays MiniMax H3 / LTX 2.5 — never fal, never retired locals.
- Co-Director: `seedance-2.5.md`; retired “Adept does not expose Seedance 2.5”; LTX 2.5 teaching distinguishes CREATE T2V from Timeline R2V.
- Capability queue no longer requires retired `ltx_checkpoint` as a gate for all video.
- Hosted discovery “Seedance 1 Pro” is legacy `seedance-1-pro-fal`, not a 2.0/2.5 product row.

## Live walk (Korri, 2026-09-05)

**T2V** `#txt2vid-engine`: Auto Select, MiniMax H3, LTX 2.5, Seedance 2.0, Seedance 2.5 enabled; Kling/Veo/Runway honest Testing/Requires Setup. No retired locals.

**1 Frame** (after join load): MiniMax H3 + LTX 2.5 + Seedance 2.0 + Seedance 2.5 enabled as separate versioned rows.

**3 Frame:** LTX 2.5 enabled. Seedance versions hidden. MiniMax remains only when it is the current scene engine, and then disabled (“does not accept three stills”).

**Timeline dock:** LTX 2.5 Ready (`ltx-2.5-distilled`), MiniMax H3 Ready, Seedance 2.0 Ready, Seedance 2.5 Ready. LTX 2.3 Requires Setup. No generic Seedance row.

Evidence: `evidence/LIVE_API_ENGINES.json`, `evidence/LIVE_TIMELINE_GENERATORS_AFTER.json`.

## Tests

| Suite | Result |
|---|---|
| `test_seedance_version_authority` + authority / local T2V / recommend / knowledge | **56 passed** |
| Adapter + Co-Director Seedance preference + R2V compile (targeted) | **22 passed** |
| `engineSurfacePolicy.test.ts` + `draftCapabilities.test.ts` | **19 passed** |
| Playwright `local-video-availability.spec.ts` | **updated, not run this session** |

Routing proofs (unit): 2.0 → `bytedance/seedance-2.0/*`; 2.5 → `bytedance/seedance-2.5/*`; Auto Select → `minimax-h3`; LTX 2.5 resolve ≠ `ltx-local`.

## E2E TRACE

| Stage | Verdict | Notes |
|---|---|---|
| User action | PASS | Korri T2V / 1F / 3F / Timeline pickers walked |
| Frontend | PASS | Versioned labels; no generic Seedance; retired locals not CREATE defaults |
| API | PASS | `/api/engines` join; Timeline generators versioned |
| Backend | PASS | Distinct adapters; no LTX 2.5→`ltx-local` bind |
| Persistence | N/A | No new generate this session |
| Runtime | N/A | No new local/hosted generate; MCP not attached |
| Result | N/A | No new asset |
| Reload | N/A | No new persist to prove |
| Downstream | N/A | Library/lineage not re-generated |

## Limitations

- Comfy MCP not attached (`comfy-mcp.exe` not found). CRT-D workflow cert remains blocked. Graphs were not changed (`ltx_25_builder` / H3 Ref2V JSON untouched).
- Local families claimed Ready (LTX 2.5 distilled, MiniMax H3) were **not** re-proven with a real generate this session.
- Paid Seedance generate not run. Routing unit tests + picker IDs prove no silent remap.
- Studio API recycle health probe exceeded 120s twice; process recovered. Pre-existing `reconcile_non_terminal_packs` ImportError on API startup.
- Seedance 2.0 and 2.5 both report Ready from the same fal key — independent rows, shared credential, not a cross-version paint of adapter truth.
- Playwright spec updated; not executed this session.
- Generator-knowledge JSON profiles still share compile packs (`ltx-local` / `seedance-api`); markdown KB is versioned. Execution bind is not that pack id.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=txt2vid`
2. Confirm Auto Select + LTX 2.5 + MiniMax H3 + Seedance 2.0 + Seedance 2.5
3. 1 Frame / 3 Frame / Timeline as in the live walk above
4. Do not restart Comfy `:8188`
