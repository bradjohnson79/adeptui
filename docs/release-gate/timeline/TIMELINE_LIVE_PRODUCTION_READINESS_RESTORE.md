# Timeline Production Readiness — Live Scene Wiring

**Governing document for this gate.**

| Field | Value |
| --- | --- |
| Date | 2026-09-16 |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Project | Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| Cert scene | Scene 1 `8a385844-3e0d-48e3-a759-d3fb242cd392` (establishing shot) |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

## Verdict

**GO — LIVE SCENE PRODUCTION READINESS**

Unanimous three-LLM AGREE. Production Readiness is computed from the current Timeline scene’s bindings. Preflight can force a refresh. Preflight is not the database.

## Root cause

The Inspector consumed Co-Director lifecycle booleans (`castReady`, `locationReady`, `imageReferencesReady`, `voiceReady`) written by wiki/casting assess and `upsert_scene_readiness`. Formal production then forced **BLOCKED until required cast is locked** even when the scene had no character or voice requirement.

Cade Scene 1 already had live truth:

- `#EarthHorizon` → environment binding `EarthHorizon2` / prompt name **Earth Horizon**
- `%VentureSpaceship` → prop binding **Venture Spaceship**
- `%CadeSStarfighter` → prop binding **Cade's Starfighter**

Generation could resolve those IDs. Readiness independently said Location/References Not ready and Voice Not ready.

A first live compute also double-counted tokens: project-wide Prompt Name catalog made `match_token_to_catalog` ambiguous (`EarthHorizon` vs `EarthHorizon2` across scenes), so tokens were marked missing even after the scene bindings resolved. Token matching for readiness is now scene-local, and a resolved scene binding covers the matching token.

## Architecture

- **Truth** = current scene director / Timed Prompt tokens + scene-scoped `SceneReferenceBinding` + `PromptNameBinding`
- **Resolve** = existing `resolve_binding_id` (same identity authority as generation)
- **Compute** = `compute_live_scene_readiness` — not a second resolver
- **Inspector read** = Timeline context package, every open / scene change / `reloadKey` mutation
- **Preflight** = existing director findings + snapshot of the same live compute
- **Departments** = READY | NOT REQUIRED | BLOCKED with structured evidence

Cast is required only when a character binding/`@` token is on the scene. Voice is required only when dialogue, lip-sync audio, or a speaking-character requirement is present.

## Cade establishing shot (measured)

| Department | Status | Evidence |
| --- | --- | --- |
| Location | READY | Earth Horizon |
| References | READY | 3/3 — Earth Horizon, Venture Spaceship, Cade's Starfighter |
| Cast | NOT REQUIRED | No character performance required |
| Voice | NOT REQUIRED | No dialogue or speaking character in current scene |
| Overall | READY | Only applicable departments count |

## Tests

| Suite | Result |
| --- | --- |
| pytest `test_live_scene_readiness.py` + preflight assess | **9 passed** |
| Vitest Inspector Preflight source | **5 passed** |
| Playwright `tests/e2e/timeline/timeline-live-production-readiness.spec.ts` live `:5173` / `:8758`, `ADEPT_ALLOW_CADE_MUTATION=1` | **1 passed** (6.7s) |

Playwright walk: open Timeline (no Preflight click) → Location/References READY with the three names → Cast/Voice NOT REQUIRED → reload same → DELETE Venture binding → References BLOCKED + missing Venture → reattach → READY. Venture remains on Scene 1 after the test.

## Peer LLM review

Question (verbatim): Confirm that Production Readiness is computed from actual scene identity/binding state rather than static/mock/default readiness flags, and that optional departments such as Cast and Voice support NOT REQUIRED instead of falsely blocking the scene.

| Reviewer | Verdict |
| --- | --- |
| Kimi K3 Max | **AGREE** |
| GLM 5.2 Max | **AGREE** |
| GPT-5.6 Sol | **AGREE** |

Unanimous **AGREE**.

## E2E TRACE

| Step | Result |
| --- | --- |
| User action — open Cade Timeline Scene 1 | PASS |
| Frontend — Production Readiness without Preflight click | PASS |
| API — GET timeline-context `liveComputed` + departments | PASS |
| Backend — `compute_live_scene_readiness` via `resolve_binding_id` | PASS |
| Persistence — scene bindings remain source of truth | PASS |
| Runtime — no GPU generate | N/A |
| Result — Location/References READY; Cast/Voice NOT REQUIRED | PASS |
| Reload — same readiness | PASS |
| Downstream — remove Venture BLOCKED; restore READY | PASS |

## Runtime / Comfy

| Check | Result |
| --- | --- |
| COMFY BEFORE | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY AFTER | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY RESTARTED? | **NO** |
| WHY? | Studio API recycle only; Vite HMR for UI |
| Studio API | `http://127.0.0.1:8758/api/healthz` **200** |
| Creator UI | `http://127.0.0.1:5173/` **200** |

## Limitations

- Scene-local token cover uses name/alias norms (`EarthHorizon` ↔ `EarthHorizon2`). Ambiguous project-wide forks are ignored on purpose.
- Voice READY (when required) currently means a speaking character is bound; it does not yet certify a selected Voice Engine clip.
- Chat-owned `upsert_scene_readiness` without `liveComputed` still uses the old boolean derivation.
- Working tree still contains unrelated uncommitted work. This gate certifies live Production Readiness only.

## Manual review

1. Open `http://127.0.0.1:5173/project/fb24ff0f-8772-4d50-a602-ac69d14b5a6b?workspace=timeline&sceneId=8a385844-3e0d-48e3-a759-d3fb242cd392`
2. Open Inspector → Production Readiness should already show Location READY (Earth Horizon), References READY 3/3, Cast/Voice NOT REQUIRED. Do not require Preflight first.
3. Reload → same.
4. Remove Venture from References → References BLOCKED naming Venture. Reattach → READY.
5. Do not restart Comfy.
