# Co-Director Canonical Generation Memory Certification

**Date:** 2026-08-31  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651` (working tree; this mission uncommitted unless requested)  
**Project reused:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` — no `POST /api/projects`

## Verdict

`GO — CODIRECTOR CANONICAL GENERATION MEMORY + EXACT RETRY RECALL E2E CERTIFIED`

## Current memory architecture

Durable production history lives on the existing execution pack:

`ExecutionPlan.plan_data["canonicalGenerationRequest"]`

Written at ACT / first enqueue. Resolver reads packs/jobs, not the LLM window. Chat inherit is last-ditch only when no canonical request exists.

## Root cause of the lost prompt

Retry was chat-only and too narrow. `inherit_visual_prompt_from_history` walked in-request messages and ran only for “generate/create/do it|that”. “Retry with same prompt…” set `prompt = user_text`, then semantic routing waited on an LLM, which invented “it didn't carry over into this session.”

The Venture brief was already in job `params_json.prompt` and, after this repair, on the pack snapshot.

## Canonical store

Typed snapshot on the pack (not a new owner table). Fields include `originalUserInstructions` (verbatim), `compiledGeneratorPrompt`, route/provider/model, aspect/size, refs, `executionId` / `jobIds` / `resultAssetIds`, `parentRequestId`, `inheritAudit`.

`originalUserInstructions` is never overwritten on job complete. Lineage updates job/asset ids only.

## Exact original prompt storage

Observed on pack `111c92dc-d14c-4246-b954-f4a47f3c1ce4` after Turn 1:

verbatim Venture corridor brief starting `Create a Silver metallic Venture corridor scene…`

## Compiled prompt storage

Handler recompiles from `originalUserInstructions` via `_compile_image_prompt`. Retry leaves `compiledGeneratorPrompt` empty on the typed next request, then stores what was actually sent.

## Retry resolution

`generation_memory.resolve` — deterministic, no embeddings. Precedence: selected execution/asset → single in-progress image pack → most recent `image.generate` (by `created_at`) → named corridor/Venture hint. Wired in `stream_for_project` **before** `route_turn_with_unified` so semantic routing cannot hang or reconstruct.

## Referential language

same prompt / retry that / last image / run that again / previous prompt. Video, Character Creator, Spatial Map, ERS named in the utterance are excluded. `GPT Image 2` is not treated as image index 2.

## Override semantics

Schema-driven allowlists. No `dict.update()` of the prior request. `parse_image_generation_overrides` on the retry utterance only.

## Model-change recompilation

`compiledGeneratorPrompt`, `generationParameters`, `workflowKey`, `providerPayload` always recomputed. GPT Image 2 override does not copy fal/GPT compiled text onto Flux/Qwen.

## Live evidence (same project)

| Turn | Result |
|---|---|
| 1. Full Venture brief | execution `111c92dc…`, job `b798b439…`, snapshot stored |
| 2. `Retry with same prompt again and use GPT Image 2.` | execution `340a6ebf…`, **0 clarifications**, exact brief inherited, audit overridden `modelId`/`provider`/`route`. Job **failed honestly**: GPT Image 2 (Kie) is in catalog but `executable=False`. Did **not** switch to flux-fal. Did **not** ask to paste the prompt. |
| 3. `Retry that with Flux.` | execution `c35caa80…`, job `591fccde…` **queued/running**, exact Venture brief in `params_json.prompt` |
| Browser reload + Playwright | `tests/e2e/codirector/codirector-generation-memory.spec.ts` **1 passed** (21.6s) |
| Managed API recycle (`restart_studio_api_only.py`) then `Retry the same prompt.` | API `11912` → `74324`, execution `09b91039…`, job `ca627887…`, exact brief, forgot=false |

## Tests

`studio-api/tests/test_codirector_generation_memory.py` + visual/image-defaults extras:

**13 generation-memory tests passed**, plus `test_codirector_visual_image_intent.py` and `test_codirector_image_generator_authority.py` (54 passed in the combined image/memory run).

## Playwright

`npx playwright test tests/e2e/codirector/codirector-generation-memory.spec.ts` with `ADEPT_BETA_TARGET=1` → **1 passed**.

## Peer review

Law #27 `gpt-5.4-medium` is unavailable. Primary review plus two inherit reviewers.

| # | Question | Answer |
|---|---|---|
| 1 | Can “same prompt” require repaste when a canonical request exists? | **NO** — resolver copies `originalUserInstructions`; live GPT/Flux/recycle turns did not ask to paste |
| 2 | Can API restart erase retry memory? | **NO** — packs are SQLite traits; recycle then `Retry the same prompt.` enqueued job `ca627887` with the brief |
| 3 | Can summarization overwrite exact prompts? | **NO** — snapshot is on the pack; complete/fail updates ids only |
| 4 | Can generator switch reuse incompatible compiled prompting? | **NO** — recompute allowlist; next request compiles from original instructions |
| 5 | Can references disappear on retry? | **NO** — `referenceAssetIds` / character ids are inherit-exact |
| 6 | Can history leak across projects? | **NO** — `list_packs(project_id)` only; isolation test |
| 7 | Is memory duplicated in competing stores? | **NO** — one snapshot on the existing pack; optional job backfill is the same authority |
| 8 | Does failed/cancelled remain retryable? | **YES (required)** — failed GPT pack still resolved; unit test covers FAILED/CANCELLED |
| 9 | Can chat/LLM overwrite a resolved canonical request? | **NO** — resolve runs before semantic router; chat inherit is in the `else` only |
| 10 | Can inheritance copy provider compiled fields across generators? | **NO** — no `dict.update()`; compiled/payload/workflow cleared |

Q8 YES is “remains retryable” (desired), not a chat-dependence blocker.

Independent inherit [Peer A](a9f7d54d-92ec-4e33-ba01-a11b8e5d9944) and [Peer B](219220db-011e-424b-8a13-8eb3ecdbd1e2): both `READY FOR PRIMARY REVIEW`, same Q1–Q7/Q9–Q10 **NO**, Q8 **YES**, **BLOCKER: none**.

BLOCKER: none from primary + both inherit reviewers.

## Files changed

- `studio-api/app/codirector/generation_memory/` (new)
- `studio-api/app/codirector/service.py`
- `studio-api/app/codirector/execution/dispatcher.py`
- `studio-api/app/codirector/execution/advance.py`
- `studio-api/app/codirector/execution/pack_store.py` (sort by `created_at`)
- `studio-api/app/codirector/capabilities/handlers/image_generate.py`
- `studio-api/app/codirector/conversation/foundation/image_generation_defaults.py`
- `studio-api/app/codirector/routing/unified_intent.py`
- `studio-api/tests/test_codirector_generation_memory.py`
- `studio-api/tests/test_codirector_visual_image_intent.py`
- `tests/e2e/codirector/codirector-generation-memory.spec.ts`
- `scripts/codirector_generation_memory_live_cert.py`

## Unrelated systems untouched

Character Creator, Spatial Map, Timeline, Scene Creator, ERS handlers, fal adapters, MiniMax `:8192`, runtime supervisor spawn, dual-runtime workers. Comfy was not restarted.

## Runtime

| | |
|---|---|
| Studio API | `http://127.0.0.1:8758/` — health 200, PID **74324** after last managed recycle |
| Creator UI | `http://127.0.0.1:5173/` — 200 |
| **COMFY BEFORE** | PID **77152** / `system_stats` ready |
| **COMFY AFTER** | PID **77152** / ready |
| **COMFY RESTARTED?** | **NO** |
| **WHY?** | API-only recycles via `:8759/restart-api`. `comfyPidUnchanged=True` on every recycle. |

`:8188` argv points at Comfy Desktop shared input/output paths. This mission did not adopt, kill, or rebind it.

## Limitations (honest)

- GPT Image 2 (Kie) is cataloged but not executable on this machine. Turn 2 applied the override and failed closed. A real second job was produced on Flux retry and again after API recycle.
- Non-stream `POST /api/codirector/chat` still talks without enqueueing (deferred; stream is the product path).
- Older image packs without a snapshot backfill `originalUserInstructions` from job params only — never from chat summaries.

## Manual review

In Co-Director on **Korri Anadriya**, send `Retry with same prompt again and use GPT Image 2.` Expect a generation attempt that reuses the Venture brief — not “paste the original prompt.” If Kie is not configured, the failure should name hosted unavailability, not ask for the brief.
