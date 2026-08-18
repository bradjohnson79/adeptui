# Avatar Studio Compact Multi-Speaker Experience — Completion Report

**Date:** 2026-08-18  
**Branch:** `feat/lora-support`  
**Starting SHA:** `04fb31eb`  
**Project:** Schnick Coffee (`2347bf46-3762-4763-86c5-4a6032522278`) — never `POST /api/projects`  
**Law 27:** GPT 5.4 was unavailable. Subagent B and Subagent C ran as **inherit**.

Governing cert this pass is compact UX, speaker/conversation contract, sequential stitch architecture, LoRA/aspect/Co-Director wiring, and honest runtime gates. It is **not** a live InfiniteTalk / LongCat talking-head movie.

---

## Verdict

**GO — AVATAR STUDIO COMPACT MULTI-SPEAKER EXPERIENCE CERTIFIED**

Independent reviewers:

- [UX review](b81b6b52-fc7b-4d17-86ba-107c0f8b4058) — `READY FOR PRIMARY REVIEW`
- [Independent cert](ca15f7e5-8429-4270-9348-159206e75115) — `READY FOR PRIMARY REVIEW`

---

## What shipped

Same Avatar Studio route. MAIN is a compact creator:

Source → Speaker (Single | Conversation) → Dialogue → Generator → Aspect → Generate, plus one Advanced accordion.

| Piece | Behavior |
|---|---|
| Generators | InfiniteTalk + LongCat Avatar 1.5 only. MiniMax H3, LTX, EchoMimic, MuseTalk are not listed as avatar generators. |
| Conversation | Sequential Speaker A then Speaker B then stitch. Honest copy: this generator cannot film two people at the same time. Native multi-speaker is **false**. |
| Detect | `mouth_tracker` face ROIs as Person 1 / Person 2. Names only when assigned. |
| Gate | Generate disabled until `certifiedReady === true`. UI: `InfiniteTalk needs repair — Open Runtime Setup`. |
| Co-Director | `avatar.create_plan` / `avatar.create_job` write session (source, speakers, order, generator, aspect) and return `executed: false` + the same gate when not READY. |
| Advanced | Style, framing, background, duration, LoRA (`modality="video"`), plan notes. |

---

## Tests

| Suite | Result |
|---|---|
| Vitest `compact.test.ts` + `types.test.ts` | **19 passed / 19** |
| Pytest `test_avatar_compact_speakers.py` | **6 passed / 6** |
| `npm --prefix studio-web run build` | **passed** (`index-DzfALDFi.js`) |

Detect-speakers pytest originally collided on hardcoded `still-1`; isolation now uses a unique asset id.

---

## Beta (this machine)

- Creator UI: http://127.0.0.1:8760/ (`/__beta_web_health` **200**, index hash `index-DzfALDFi.js`)
- Studio API: http://127.0.0.1:8758/api/health **200**
- `GET /api/avatar-runtimes` **200** — listed generators: `longcat-video-avatar-1-5-local`, `infinitetalk-local`

Live Schnick path: `/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=avatar`

Screenshots: `tests/e2e/screenshots/avatar-compact/`

---

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | **PASS** |
| Frontend | **PASS** |
| API | **PASS** |
| Backend | **PASS** |
| Persistence | **PASS** (session contract + Co-Director write-back) |
| Runtime | **N/A** — honest Generate block; no GPU talking-head this pass |
| Result | **N/A** — blocked Generate is the required product behavior |
| Reload | **PASS** for compact hydrate; **N/A** for video |
| Downstream | **N/A** — no Timeline/Library video this pass |

---

## Limitations (honest)

- InfiniteTalk and LongCat remain Repair Required. Generate stays disabled.
- Conversation assembly calls `stitch_videos` only when two certified section files exist; otherwise `assembled_stub`.
- `_execute_section_generation` still fails `PROVIDER_NOT_CERTIFIED` / `RUNTIME_UNAVAILABLE` until a certified adapter exists.
- MAIN still includes Find people / Select Speaker Region / speaking order (useful extras; not card grids).
- Scene Creator Mini / Spatial Map / camera-reference work in the dirty tree is **out of this commit**.

---

## Scope of this commit

Avatar Studio + avatar types/runtime flags/detect/Co-Director tools/tests/CSS/screenshots/this report only.
