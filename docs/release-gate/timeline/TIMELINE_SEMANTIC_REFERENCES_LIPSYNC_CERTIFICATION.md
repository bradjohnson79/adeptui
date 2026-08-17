# Timeline Semantic References + Character Voice / Lip Sync — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-17  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Hosted:** `https://adeptui.vercel.app` (SHA match / hosted Schnick smoke after this local GO + scoped push)

Product law: References define the cast and visual language. Prompts direct the scene. Lip Sync assigns timed performance. Character profiles own voice. Canonical binding IDs power compile. Hot Keys dispatch the same Timeline actions; they stay off while typing.

## Verdict

`GO — TIMELINE SEMANTIC REFERENCES + CHARACTER VOICE / LIP SYNC CERTIFIED END TO END`

Independent source pass: [Review](94c2ef53-4e11-4709-b422-a6cd8e37dfa6) returned `READY FOR PRIMARY REVIEW` (Law 27 GPT 5.4 slug unavailable; inherit used, did not block). Primary verified the live Schnick Playwright chain below.

## Scope

Minimum-delta Timeline refinement. No second reference store, TTS engine, character store, shortcut backend, or Timeline rewrite. No `POST /api/projects`. MiniMax H3 caps remain honest (T2V `0`, I2V `1`); Hailuo “9 images” was not invented.

## What is implemented

- Prompt clips persist `reference_binding_ids`; Lip Sync clips persist `speaker_binding_id`.
- Idempotent hydration copies legacy image/video reference tracks onto overlapping Prompt clips (creates an empty Prompt when none overlap). Legacy JSON is kept; compile reads Prompt clips only.
- Compile refuses over-limit refs without deleting stored IDs; `request_builder` copies consumed `referenceAssetIds` (no silent clear).
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
| Lip Sync missing speaker blocks | PASS unit + Playwright | `LIPSYNC_SPEAKER_REQUIRED`; Schnick spec 3.5–4.1s |
| Lip Sync audio overrides Prompt TTS | PASS unit | spanning windows `speechKind=lipsync_audio` |
| One Prompt 0–5s + Korri 0–2.5s + Anadriya 2.5–5s | PASS unit + Playwright | shared `reference_binding_ids`; UI chrome `@` on one Prompt + two Lip Sync clips |
| Hot Keys defaults / conflict replace / text safety / localStorage | PASS unit + Playwright | `timelineHotkeys.test.ts`; live pane Save → reload still `K` |
| Lanes gone; sidebar feeds Prompt; persist by binding id | PASS Playwright | layout spec 12.2s; semantic persist 3.8s |
| Hosted Vercel SHA / Schnick smoke | PENDING push | local GO first |

## Unit evidence

- `studio-api`: `python -m pytest tests/test_timeline_prompt_refs_speech.py tests/test_timeline_reference_aliases.py -q` → **19 passed** in 0.78s
- `studio-web`: `node --test src/timelineMaster/timelineHotkeys.test.ts src/sceneReferences/referenceTokens.test.ts` → **14 passed**
- Production web build: `npx vite build` → `studio-web/dist/assets/index-C56Pooec.js` served at `http://127.0.0.1:8760/`

## Playwright (authoritative live run)

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-layout-library-references.spec.ts tests/e2e/timeline/timeline-semantic-references-lipsync.spec.ts --project=chromium --retries=0 --workers=1
```

**4 passed (38.0s)** against UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`. Schnick only. No `POST /api/projects`.

1. layout: resizable panes, one fullscreen, library-only, typed references, alias rename — **12.2s**
2. lanes retired, Prompt tokens persist by id, Inspector/Co-Director remain — **3.8s**
3. Lip Sync without speaker blocks; one Prompt spans Korri then Anadriya — **4.1s**
4. Hot Keys pane, defaults, Space, custom assign, conflict, typing safety, reload, reset — **6.1s**

Live GET director on Schnick scene `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`: `prompt_refs_migrated=true`; all Prompt segments include `reference_binding_ids`.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (Prompt tokens, Lip Sync speaker, Hot Keys, Inspector/Co-Director tabs) |
| Frontend | PASS `index-C56Pooec.js` |
| API | PASS `/api/health` 200 during the 4-test run |
| Backend | PASS compile/speech/hydration units |
| Persistence | PASS Prompt binding IDs + Hot Keys `adept_timeline_hotkeys_v1` after reload |
| Runtime | N/A (no GPU generate in this milestone; compile inspection) |
| Result | PASS |
| Reload | PASS alias + Hot Keys mapping |
| Downstream | PASS request builder does not drop refs; generate/preflight buttons remain |

## Limitations

- `tsc -b` was not the build path this session (`npx vite build` only).
- Studio API can wedge under Cloudflare tunnel connection pile-up; local cert used a recovered uvicorn on `:8758`.
- Schnick spanning spec creates `Anadriya` on the **existing** project if missing (not `POST /api/projects`).
- Unbound drawer Hot Keys (`toggleLeftDrawer` / `toggleRightDrawer` / `focusTimeline`) have empty defaults so they cannot steal G/R/I. V2 drawer chrome outside this scoped commit is not part of this verdict.
- `@/#/*` remain editor accelerators, not global Hot Keys.
- Hosted Vercel SHA match is the next deploy step after scoped push.

## Manual review

1. Open Schnick Coffee Timeline at `http://127.0.0.1:8760/`.
2. Confirm no Image/Video Reference lanes; Prompt chips use `@/#/*`; Lip Sync requires a character speaker.
3. Hot Keys tab: capture, Save, reload, Reset. Typing in Prompt must not fire Generate.
