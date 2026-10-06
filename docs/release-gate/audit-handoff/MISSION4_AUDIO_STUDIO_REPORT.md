# Mission 4 — Audio Studio production path

**Date:** 2026-09-02  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Branch:** `feat/character-creator-final-closure`  
**Verdict:** H-P1-05 / H-P1-06 / H-P1-07 **CLOSED — GO**

Ordinary recycle only. Comfy `:8188` was not restarted.

| | Before | After |
|---|---|---|
| Studio API | PID 64188 | PID 4668 |
| Comfy `:8188` | PID 77152 / 0.32.0 | PID 77152 / 0.32.0 |
| Vite `:5173` | PID 56720 | PID 56720 |
| COMFY RESTARTED? | | **NO** |

## H-P1-05 — Clone style is refused, not ignored

Qwen3-TTS `generate_voice_clone` has no `instruct` parameter. DESIGN still uses `performance_instruct`.

Live: `POST …/voice-profiles/283e8cf8-…/generate-dialogue` with `emotional_direction=whisper` returned **400 `STYLE_UNSUPPORTED`**. No clone GPU job.

Voice Performance omits style fields on Qwen clone and labels `supportMode=Unsupported` instead of pretending Prompt-guided.

## H-P1-06 — Approve ingests a durable Library asset

Root causes:

1. `workspace.library` called missing `project_library.list_items` and returned `[]`.
2. Approve only set a draft flag and did not stamp `Asset.production_approval` or copy a sandbox WAV into the project.

Live re-approve of auditor take `32c9339f` / `84946a4a`:

- `ingested=true`, `approvedAssetInLibrary=true`, `approvalState=approved`
- Path: `data/projects/beffd3d8-…/assets/sfx_generate_86b9fa9265.wav` (not `m210b-sandbox`)
- Present in workspace.library and `GET /api/projects/…/library`
- File GET **200** `audio/wav` RIFF

## H-P1-07 — Music CTA follows ACE-Step health

Provider cache + independent `/providers?kind=music` fetch. Empty payload is **Checking**, not unavailable. `sandboxOnly` does not disable the CTA.

Live API: ACE-Step `ready (CUDA: NVIDIA GeForce RTX 5090)`, `mode=local`.  
Live UI: badge **Music Engine**; after prompt fill, **Generate 1 Track** enabled. No music GPU job.

Screenshot: `artifacts/audit-handoff/mission4-hp107-music-ready.png`

## Tests

- `studio-api/tests/test_voice_performance_qwen_bridge.py` — 2 passed
- `studio-api/tests/test_m42_w45_audio_studio.py` — 15 passed
- `studio-web` `audioStudioSource.test.ts` — 7 passed
