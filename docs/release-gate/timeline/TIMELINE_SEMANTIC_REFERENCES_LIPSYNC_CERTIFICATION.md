# Timeline Semantic References + Character Voice / Lip Sync — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-17  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**HEAD:** `81f702ff966ae63e98629c77d206bc1962a60fce` (working tree includes this milestone; not committed)  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Hosted:** `https://adeptui.vercel.app` (SHA match / hosted smoke **not run** — no local GO, no push)

Product law: References define the cast and visual language. Prompts direct the scene. Lip Sync assigns timed performance. Character profiles own voice. Canonical binding IDs power compile. Hot Keys dispatch the same Timeline actions; they stay off while typing.

## Verdict

`NO-GO — TIMELINE SEMANTIC REFERENCES + CHARACTER VOICE / LIP SYNC NOT FULLY LIVE-VERIFIED`

Independent line: not issued (Law 27 GPT 5.4 subagent slug unavailable in this session; primary did not substitute a fake independent pass).

**Exact blocker:** After a healthy Playwright pass of layout + Prompt-token persistence, Studio API `:8758` stopped answering `/api/health` (connection timeout). The listener PID recorded by `netstat` (`24968`) is not stoppable from this agent session (`taskkill` / `Stop-Process` report process not found). Dozens of `ESTABLISHED` sockets remain, many from `cloudflared`. Spanning Prompt / sequential Lip Sync UI chrome and Hot Keys save/reload were therefore not re-certified on a healthy API. Commit / push `beta` / Vercel SHA match are withheld until that live chain is green.

## Scope

Minimum-delta Timeline refinement. No second reference store, TTS engine, character store, shortcut backend, or Timeline rewrite. No `POST /api/projects`. MiniMax H3 caps remain honest (T2V `0`, I2V `1`); Hailuo “9 images” was not invented.

## What is implemented

- Prompt clips persist `reference_binding_ids`; Lip Sync clips persist `speaker_binding_id`.
- Idempotent hydration copies legacy image/video reference tracks onto overlapping Prompt clips (creates an empty Prompt when none overlap). Legacy JSON is kept; compile reads Prompt clips only.
- Compile refuses over-limit refs without deleting stored IDs; `request_builder` no longer silently clears `referenceAssetIds`.
- Speech hierarchy: Lip Sync audio → Prompt `@Token says "…"` via Character `active_voice_profile_id` → none. Missing Lip Sync speaker blocks with `Assign a character to this Lip Sync clip.`
- Image/Video Reference **lanes** are hidden. Prompt chrome shows token summary; Lip Sync chrome shows `@alias` + audio filename.
- Prompt Inspector: chips, `@/#/*` autocomplete, `n / max` counts, Relink, over-limit refuse.
- Right pane: Inspector | Co-Director | Hot Keys. Registry in `studio-web/src/timelineMaster/timelineHotkeys.ts`, persistence `adept_timeline_hotkeys_v1`. Capture uses a ref so the first key after click is recorded.

## §82 matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Hydration overlap / empty Prompt / idempotent | PASS unit | `tests/test_timeline_prompt_refs_speech.py` |
| MiniMax/provider N never faked as 9 | PASS unit | same + `test_timeline_reference_aliases.py` |
| Over-limit refuse without deleting stored IDs | PASS unit | `test_timeline_prompt_refs_speech.py` |
| Video unsupported honesty | PASS unit | `test_timeline_reference_aliases.py` |
| Lip Sync missing speaker blocks | PASS unit; Playwright API preflight observed before hang | `LIPSYNC_SPEAKER_REQUIRED` |
| Lip Sync audio overrides Prompt TTS | PASS unit | spanning windows `speechKind=lipsync_audio` |
| One Prompt 0–5s + Korri 0–2.5s + Anadriya 2.5–5s | PASS unit; Playwright UI chrome **not re-verified** after API hang | compile keeps shared `referenceBindingIds` |
| Hot Keys defaults / conflict replace / text safety / localStorage | PASS unit | `timelineHotkeys.test.ts` |
| Lanes gone; sidebar feeds Prompt; persist by binding id | PASS Playwright (one healthy run) | `timeline-layout-library-references.spec.ts` 1 passed (5.4s); semantic persist test 1 passed (2.0s) |
| Hot Keys pane / Space / custom / conflict / typing / reload | NOT VERIFIED live | capture-before-state-fix failed (`Space` still shown after Save); API hung before rerun |
| Hosted Vercel SHA / Schnick smoke | NOT VERIFIED | no push |

## Unit evidence

- `studio-api`: `python -m pytest tests/test_timeline_prompt_refs_speech.py tests/test_timeline_reference_aliases.py -q` → **19 passed** in 0.93s
- `studio-web`: `node --test src/timelineMaster/timelineHotkeys.test.ts src/timelineMaster/workspaceLayout.test.ts src/sceneReferences/referenceTokens.test.ts` → **19 passed**
- Production web build: `npx vite build` (official `tsc -b` not used this session — prior Timeline/Magi dirty tree). Latest dist `studio-web/dist/assets/index-Buu4sXEm.js`

## Playwright

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-layout-library-references.spec.ts tests/e2e/timeline/timeline-semantic-references-lipsync.spec.ts --project=chromium --retries=0
```

Healthy run (API had `reference_binding_ids` + `prompt_refs_migrated`):

- layout: **1 passed** (5.4s)
- semantic persist / tabs: **1 passed** (2.0s)
- spanning + missing speaker: **1 failed** (prompt clip not in DOM within 20s while Timeline still showed “Loading Timeline tracks…” after director PUT)
- hot keys: **did not run** (serial describe at that moment)

Later rerun: API `/api/health` timed out 90s in `waitApiReady` for two tests; hot keys reached the pane but Save did not keep `K` (fixed afterward with `capturingIdRef`).

Target: UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`. Schnick only.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS partial (Prompt token pick, Inspector/Co-Director/Hot Keys tabs, layout panes) / FAIL later (API hang) |
| Frontend | PASS source + dist build; Hot Keys capture ref fix **not live-replayed** |
| API | PASS while healthy (`reference_binding_ids` on GET); FAIL timeout afterward |
| Backend | PASS unit compile/speech/hydration |
| Persistence | PASS Prompt binding IDs on healthy GET after chip commit |
| Runtime | N/A (no GPU generate in this milestone) |
| Result | FAIL overall live gate |
| Reload | PASS layout panes + alias; FAIL Hot Keys mapping on the one live attempt |
| Downstream | PASS unit (request builder does not drop refs) |

## Limitations

- Studio API `:8758` is currently unresponsive from this session; Cloudflare tunnel processes still hold sockets to it. Restart the Localhost Studio API, then re-run `timeline-semantic-references-lipsync.spec.ts`.
- Schnick had no Anadriya character at start; the spanning spec creates `Anadriya` on the **existing** project if missing (not `POST /api/projects`).
- `tsc -b` was not the build path this session (`npx vite build` only).
- No scoped git commit / push (user rule + no local GO).
- `@/#/*` remain editor accelerators, not global Hot Keys (empty Reference Authoring accordion is omitted).

## Manual recovery

1. Stop the hung Studio API process that owns `:8758` (Task Manager / Localhost Background Manager). Do not kill ComfyUI or unrelated Python.
2. `.\Restart-AdeptBetaBackend.ps1 -Service studio_api`
3. Confirm `http://127.0.0.1:8758/api/health` → 200 and GET director includes `reference_binding_ids`.
4. `npm run test:e2e:beta -- tests/e2e/timeline/timeline-semantic-references-lipsync.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0`
5. Only then scoped commit / push `beta` / Vercel SHA match.

## Required final language (when the live chain is green)

`GO — TIMELINE SEMANTIC REFERENCES + CHARACTER VOICE / LIP SYNC CERTIFIED END TO END`  
Independent: `VERIFIED — TIMELINE SEMANTIC REFERENCES + CHARACTER VOICE / LIP SYNC PASSED`
