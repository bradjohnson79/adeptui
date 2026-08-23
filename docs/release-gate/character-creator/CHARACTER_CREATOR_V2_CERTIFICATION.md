# Character Creator V2 — Certification

**Date:** 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**Review URLs:** local creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Retired:** do not use `:8760`

## Measured evidence

| Gate | Result | Evidence |
|---|---|---|
| 1. Legacy four-view/collage default retired | PASS | `collapse_retired_required_views`; leftover `start_visual_sheet_generation` enqueues Front only; `propose_visual_sheet` is `front_full` / `single_view` |
| 2. Express JSON + Front + vision lock + `@` | IMPLEMENTED / UI PASSED | Playwright Express 1 passed; vision fail-closed in `approve_view`; compact alias `@MiraVale` |
| 3. Back from Front pixels + Rev 2 + Comfy MCP graphs | GRAPH PASS / LIVE GPU NOT RUN | Comfy MCP `validate_workflow` **valid=true** for `character/flux/front` and `character/flux/back_from_front` against `:8188`. AUTO = `flux.txt2img` + `flux.img2img`. No GPU job executed this session. |
| 4. Express 21:9 sheet | UNIT PASS / LIVE COMPOSE NOT RUN | `compose_v2_character_sheet` 2560×1080; sheet button gated on Front+Back+Rev 2 |
| 5. Standard optional Close-up | UI PASS | Playwright Standard 1 passed; helper copy visible; compose keeps 21:9 with bottom-center close-up |
| 6. Global `@` + Co-Director E2E | PARTIAL | Resolver alias + V2 fields unit-tested. Full Co-Director conversation E2E not run. |

### Tests (measured)

- Backend rewritten suite: **51 passed** (`test_cc_v2.py` **10 passed**, plus former four-view enqueue tests rewritten to Front-only)
- Frontend vitest: **50 passed** (`characterSheetGenerate`, `characterSheetStage`, `activeCrsCard`)
- Playwright Beta (`ADEPT_BETA_TARGET=1`, Vite `:5173`, API `:8758`): **2 passed** (Express + Standard Mira Vale on Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1`)

### Comfy MCP

Cursor session does not load a `comfy` namespace. Repair: `comfy-mcp.exe` is installed; stdio MCP client listed tools and called `server_info`, `system_stats`, `which`, `nodes`, `validate_workflow`. Live Comfy `http://127.0.0.1:8188`, CUDA RTX 5090, `flux1-kontext-dev.safetensors` present. HTTP `/object_info` was not used as the certification substitute.

AUTO adapter: Certified `flux.txt2img` (Front) + Certified `flux.img2img` (Back binds Front pixels via `source_image`). Never-default: SenseNova, MiniMax H3, Krea, Z-Image silent remap.

## Owner fixtures

Do not mutate Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` or Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`. Cert character: **Mira Vale** on Adept Stability Cert.

## Peer review models

Law 27 requests GPT 5.4 for specialized subagents; that slug is not in the current Task allowlist. Review-only peers:

- [Peer A](a0fa12c7-b51d-4c87-aa36-1e323f7d8648) — GLM 5.2 Max — `READY FOR PRIMARY REVIEW`
- [Peer B](e5a37176-81c6-4b53-8da4-26840bc7635d) — Kimi K3 Max — `READY FOR PRIMARY REVIEW`

Peer B defects repaired in follow-up: Front remake invalidates Back/Rev 2/sheet; `@Name` `production_ready` follows the vision lock for V2 characters.

Remaining peer notes (not repaired this session): `character-json` Back/Close-up mapping still prefers legacy crop/sheet; Close-up re-approve re-calls vision; no V2 cancel-job route; `USER_PROTECTED_FIELDS` is documentation-only.

## Verdict

**NO-GO — LIVE GPU FRONT/BACK/REV2/SHEET AND CO-DIRECTOR @ CONVERSATION E2E NOT EXECUTED**

Implementation, retirement, MCP graph validation, unit/API tests, Express/Standard UI Playwright, and two review-only peers are complete. Production certification still requires one real Mira Vale Front job through Comfy, Front vision lock, pixel-ref Back, JSON Rev 2, 21:9 compose, and a Co-Director `@Mira Vale` resolve after reload.
