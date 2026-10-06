# Co-Director Hosted Image Availability + API-to-Local Fallback Orchestration

**Date:** 2026-08-31  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651` (working tree; this mission uncommitted unless requested)  
**Project reused:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` — no `POST /api/projects`

## Verdict

`GO — CODIRECTOR HOSTED IMAGE AVAILABILITY + API-TO-LOCAL FALLBACK ORCHESTRATION E2E CERTIFIED`

## Diagnosis (read-only re-probe)

The Venture “hosted generator unavailable” refusal was **not** a fal funds failure. Fal was never called for GPT Image 2.

| Item | Observed |
|---|---|
| Requested identity | `gptimage2` → catalog `gpt-image-2-kie` |
| Provider | **Kie** (`family=imagen`) — not fal |
| Catalog executable | `False` (Testing) |
| Fal image rows | `flux-fal`, `krea2-*-fal` only — **no GPT Image 2** |
| Hosted executable pool | `flux-fal`, `krea2-turbo-fal`, `krea2-medium-fal`, `krea2-large-fal` |
| Kie card | configured=true, state=verified, `availableBalance=null` |
| Fal card | configured=true, state=verified, `availableBalance=null` |
| Fal `funding_state` | **unknown** (balance is None — never treated as exhausted) |
| Old handler | non-executable exact match → *“I will not switch…”* |

Old parser classified “GPT Image 2” as `provider_kind=fal`. That is fixed: model identity stays `gptimage2`; provider is not forced to fal.

## Architecture

New module: `studio-api/app/codirector/image_route/`

- Typed availability per candidate (configured / reachable / funded / known / supported / available)
- `funding_state`: `sufficient | low | exhausted | unknown`
- Lock parse on the **current utterance**: UNLOCKED / PREFERRED / STRICT
- `plan_image_route`: exact → same provider → other configured hosted (Production Control + hosted cards) → AUTO local
- Attempted-route set per execution
- Brief disclose in chat; full `fallbackAudit` on the pack snapshot

Lock default confirmed: “use GPT Image 2” without “only” is **PREFERRED**.

## Live evidence (same project)

| Turn | Result |
|---|---|
| Read-only catalog/probe | Table above. Comfy PID **77152** left alone. |
| `Retry with same prompt again and use GPT Image 2.` | Execution `f865e388…`, job `ad5df904…`. Exact `gpt-image-2-kie` **model_unavailable** (catalog not executable). Same-provider Kie rows not executable. Selected **`flux-fal`**. `funding_state=unknown`. Disclose: *GPT Image 2 isn't available on that API, so I'm using the next available image API.* 0 clarifications. |
| `Retry with the same prompt and use GPT Image 2 only.` | Execution `c0091cb7…`, status **failed**, **0 jobs**. Error: *GPT Image 2 isn't available (catalog row is not executable). You asked me to use only that model, so I stopped.* `lockLevel=STRICT`. |
| Playwright after API recycle | `tests/e2e/codirector/codirector-image-route-fallback.spec.ts` **1 passed** |

API recycle only: `74324 → 80404 → 41068`. Comfy `:8188` PID **77152** unchanged both times.

## Tests

`studio-api/tests/test_codirector_image_route_fallback.py` — **15 passed** (matrix A–J plus lock/inherit extras).

Combined image/memory/authority run: **70 passed**.

## Playwright

`npx playwright test tests/e2e/codirector/codirector-image-route-fallback.spec.ts` with `ADEPT_BETA_TARGET=1` → **1 passed** (after recycle: 3.0s).

## Peer review

Law #27 `gpt-5.4-medium` is unavailable. Primary review plus two inherit reviewers.

- [Peer A](dd2d2bdb-1780-4cbc-8cc1-6704516b29eb) — raised STRICT inherit / named-model-vs-hosted / kie-not-local. **Repaired** before GO.
- [Peer B](e48567e5-9f25-4c05-bc89-718c0c925f57) — BLOCKER none on memory/lock allowlists.

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | PASS — PREFERRED retry + STRICT only, same project |
| Frontend | PASS — Vite `:5173` 200; stream path |
| API | PASS — Studio API `:8758` healthz ok (PID 41068) |
| Backend | PASS — `plan_image_route` before enqueue |
| Persistence | PASS — `lockLevel`, `fallbackAudit` on pack snapshot |
| Runtime | PASS — fal selected only after Kie miss; funds unknown; real job id |
| Result | PASS — hosted Flux job when PREFERRED; no job when STRICT |
| Reload | PASS — Playwright reload + second stream |
| Downstream | N/A — image job enqueue is the required result |

## Manual review

- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/`
- Project: Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`

## Limitations

- Hosted **enqueue transport** still uses the existing `source=fal` job body for hosted rows. That is the current Image Generator pipeline, not a GPT Image 2→Flux alias. The selected model is recorded on `fallbackAudit.selectedModelId`.
- GPT Image 2 (Kie) remains **not executable** in the catalog. PREFERRED hops; STRICT stops.
- Latest pack original instructions follow **most recent** canonical image request on this project (may be a later regenerate line, not the first Venture paragraph). Fail-forward still used that stored brief without asking to paste.
- `test_codirector_generation_authority.py` video/CRS classify_intent failures are **pre-existing** on this branch and were not caused by this module.

## COMFY

- COMFY BEFORE: PID **77152** / health ok  
- COMFY AFTER: PID **77152** / health ok  
- COMFY RESTARTED?: **NO**  
- WHY?: Ordinary API recycle + unit/Playwright only.

## Checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated (lockLevel/lockScope/fallbackAudit on snapshot)
[x] Full-stack implementation completed
[x] Every visible control wired (stream retry → orchestrator → job or precise STRICT error)
[x] Real runtime; no mock completion
[x] Persistence after reload verified
[x] Error/cancel/retry/recovery verified (STRICT block; PREFERRED hop)
[x] Authz + project isolation verified (reuse Korri only)
[x] Unit/API/integration/regression passed (15 fallback + 70 combined related)
[x] Playwright creator workflow passed
[x] Failures repaired and documented (peer A STRICT inherit)
[x] Subagents second-pass done; primary reviewed
[x] Beta updated and running; URL reported
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO
[x] Creator workflows inside Adept UI; runtimes not exposed
[x] One governing doc per milestone
```
