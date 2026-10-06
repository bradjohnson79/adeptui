# Co-Director Generate-Means-Execute Certification

**Verdict:** `GO — CODIRECTOR GENERATE-MEANS-EXECUTE E2E CERTIFIED`

**Date:** 2026-08-31  
**Branch:** current working tree (not committed unless requested)  
**Governing law:** When the creator asks for an artifact, instructions for making it are not the artifact. GENERATE + READY success = a submitted job ID.

## What closed

The existing still-image ACT classifier (`is_executable_image_turn`) was not wired into `classify_intent` or chat dispatch. Complete briefs plus “create this image now” fell through to LISTEN → LLM coaching → Flux prompt tutorial, with no job.

This repair is last-mile only. The four classifiers were not restacked. Character Creator, Spatial Map, Timeline, Scene Creator, Runtime Service, Comfy lifecycle, and fal routing were not changed.

## Live evidence

Canonical fixture (CORRIDOR + closer) posted to existing project **Korri Anadriya** (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`) via `POST /api/codirector/chat/stream`.

| Check | Observed |
|---|---|
| Prompt draft / “when you run this locally” | None |
| World-rule / next-step interview | None |
| SSE | `execution_status` then progress |
| Job ID | `d49c5028-2b3a-4277-982e-7bc4f0de3405` |
| Job row | `kind=imagegen`, `status=running`, corridor prompt persisted |
| Comfy prompt | `33ab1f88-0c56-4cb8-b79e-420f1c78dab6` |
| Engine | project-default Qwen-Image-2512 (not asked to pick Local vs API) |

## Tests

`studio-api/tests/test_codirector_visual_image_intent.py` — **14 passed**

| Case | Result |
|---|---|
| CORRIDOR + “Please create this image for me now.” | EXECUTION / `image.generate` / DETERMINISTIC; questions 0 |
| “Give me a Flux prompt… Don’t generate it.” | CONVERSATION; no job |
| After drafted prompt: “Great. Generate it now.” | ACT; inherits prior brief |
| “Generate this with Flux Local.” + Flux not configured | one fal.ai blocker; empty `child_jobs` |
| GENERATE+READY conversational-only with no job/execution id | `generate_means_execute_valid` fails |

## Peer review (mission §PEER REVIEW)

| # | Question | Answer |
|---|---|---|
| 1 | Did GENERATE+READY still produce a prompt-only reply? | **NO** |
| 2 | Did dispatch failure fall through to ordinary chat? | **NO** (error yield + `return`) |
| 3 | Did the reply become a generator tutorial? | **NO** |
| 4 | Did Bible / next-step interview interrupt the turn? | **NO** |
| 5 | Did success include a job ID? | **YES** |

YES on 1–4 would be blocking. None were YES.

Second-pass: parent review of `classify_intent`, `service.py` ACT gate, interview suppression, and live SSE. Specialized DeepSeek Pro v4 / Qwen 3.6 were not launched (Law #27 / available slugs).

## Runtime

| | |
|---|---|
| Studio API | `http://127.0.0.1:8758/` — recycled to load this change; health 200 |
| Creator UI | `http://127.0.0.1:5173/` — 200 |
| **COMFY BEFORE** | PID **22220** / ready / owned |
| **COMFY AFTER** | PID **22220** / busy (this job) / owned |
| **COMFY RESTARTED?** | **NO** |
| **WHY?** | API-only recycle. `start_all` reused Adept-owned Comfy. |

## Limitations (honest)

- Video / CRS / `timeline.generate_shot` `classify_intent` wiring remains unused. Out of scope; those tests were not part of this gate.
- This cert proves **job submit**, not Library thumbnail after the GPU run finishes.
- First recycle attempt reused a stale API PID; a verified stop/start of the uvicorn master was required before live chat saw the new code.

## Manual review

In Co-Director on **Korri Anadriya**, send the Venture Corridor brief plus “Please create this image for me now.” Expect a generation surface and a real job — not a prompt to paste.
