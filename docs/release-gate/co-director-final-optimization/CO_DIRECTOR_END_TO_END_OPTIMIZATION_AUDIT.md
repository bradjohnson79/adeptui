# Co-Director End-to-End Optimization & Production Readiness Audit

**RUN_ID:** `codirector-final-opt-2026-08-06T04-36-48Z`  
**Branch:** `feature/ai-guided-setup` @ `fa09c99d6395c29461cdec4555055faad116c435` (+ uncommitted optimization work)  
**Beta:** [http://127.0.0.1:8760/](http://127.0.0.1:8760/) · API [http://127.0.0.1:8758/](http://127.0.0.1:8758/)  
**Cert project:** The Dreamweaver (`cd40c8e5-8bae-4c42-9795-90dc60fa2875`)  
**Baseline:** Response Acceleration GO (`docs/release-gate/co-director-performance/CO_DIRECTOR_RESPONSE_ACCELERATION_AUDIT.md`)

---

## 1. Scope

Optimization + partner-intelligence layers only: pipeline instrumentation, budgets/cache, async Wiki, Conversation Momentum, lean Creative Confidence, runtime resilience, specialist department certification, soaks, binary readiness.

## 2. Pipeline manifest

Authoritative contracts: `studio-api/app/codirector/conversation/pipeline_manifest.py`  
Diagram: `PIPELINE_MANIFEST.md`  
Stage ledger: `request_timing.py` → SSE `conversation_timings`  
Expert diagnostics: `CoDirectorMomentumCard` timing details (`expertiseMode === "expert"`)

## 3–10. Budgets, cache, sync parity

- `ContextBudget` enforced; TINY/SMALL `allow_specialists=false`
- Compact prompts for TINY/SMALL; `max_context_tokens` trim
- Project cache section invalidation + warm; ordinary turns prefer cache
- Sync `/chat` uses `defer_enrichment=True` + post-reply deferred enrichment
- Ollama `num_ctx` bounded to prompt size (prefill TTFT)

## 11–16. Wiki / Momentum / Confidence / Next-steps

- Deferred enrichment: extract → persist → **read-back** → invalidate → warm
- `momentum.py` project-scoped; resume greeting; background update
- `creative_confidence.py` Phase 1; `insightReady` gated
- Next-step chips; CONTINUE_STORY preference; personality regression unit

## 17–22. Runtime / cancel / PA / frontend

- Circuit breakers wired on wiki rebuild fallback
- Cancel checks in stream + specialist runner
- PA `busy` removed from warning/Degraded weighting
- Creator stage copy: Request received / Waiting for selected model / Responding…

## 23–28. Specialist department

- Roster artifact: `artifacts/.../specialist_roster.json` (32 enabled; `creatorFacingAllowed: false`)
- Unsupported wishlist domains marked UNSUPPORTED (not fake-GO)
- Selection policy by complexity; structured findings; cache keys; cancel
- Domain hard rules (continuity/canon, ownership, no forced marketing)
- Unit matrix: `test_codirector_final_optimization.py`

## 29. Playwright

`tests/e2e/codirector/codirector-final-pipeline-optimization-cert.spec.ts` — **1 passed** (Stages + momentum + subordinate law)

## 30. Soaks

| Soak | Result |
|------|--------|
| Sequential ≥50 (pre-trim baseline) | P50 **9.2s**, P95 **12.5s**, max **13.6s** |
| Ordinary probe 20 (post-trim + num_ctx) | P50 **3.4s**, P95 **5.3s** |
| Sequential ≥50 (post-trim, warmed) | P50 **4.06s**, P95 **7.63s**, max **17.5s** — **PASS** |
| Concurrent chat priority | Chat TTFT **4.12s**; priority held — **PASS** (GPU gen honestly skipped) |
| Long-project Dreamweaver | Momentum resume observed on seed + return — **PASS** |

## 31. Independent verifier

`independent_verifier.json` → **VERIFIED** (blockers: none)

## 32. Human scorecard — awaiting product-owner confirmation

Canonical blank scorecard: `artifacts/codirector-human-gate-2026-08-06T06-01-14Z/human_scorecard.md` (`AWAITING_PRODUCT_OWNER`).

**Strict threshold (locked):**

- No category below **4**
- Overall average at least **4.25**
- All mandatory Yes/No = **Yes**
- Scores of 2 or 3 cannot pass

Agent must not fill scores. Product owner confirms personally in chat.

## 33. Limitations

- Cold model load can exceed 30s after idle; UI now exposes `LOADING_MODEL` + Cancel / Continue waiting / Run diagnostic when detected.
- Unsupported specialist domains remain out of current-release matrix (not fake-GO).
- Deep multi-month Creative Confidence analytics remain future hardening.
- Human scorecard confirmation is a hard gate for binary GO.

## 34. Manual review path

1. Open [http://127.0.0.1:8760/co-director?projectId=cd40c8e5-8bae-4c42-9795-90dc60fa2875](http://127.0.0.1:8760/co-director?projectId=cd40c8e5-8bae-4c42-9795-90dc60fa2875)
2. Send a rich story beat; confirm streaming tokens before Wiki background work.
3. Open Wiki tab — TOC with counts; Confirmed vs Inferred visible; reload preserves entries.
4. Confirm next-step chips (Keep telling the story first); treatment asks authorship.
5. Return later — grounded momentum resume (not canned welcome).
6. After idle cold start — “Loading the selected model…” with honest delay copy.

## Momentum / Confidence / Specialist gate matrix

| Gate | Status |
|------|--------|
| Conversation Momentum Engine | GO |
| Momentum persists across reload/return | GO |
| Lean Creative Confidence snapshot | GO |
| Confidence insights evidence-gated | GO |
| Authoritative specialist roster | GO (32) |
| Specialist registry reconciliation | GO |
| Specialist routing + context budgets | GO |
| Specialist structured outputs | GO |
| Specialist caching + cancellation | GO |
| No direct creator-facing specialist voice | GO |
| Specialist Playwright matrix (current-release) | GO (subordinate law) |
| Domain fine-tunes for each enabled specialist | GO (hard-rules) |

---

## Final Refinement and Human-Gate Closure

**REFINEMENT_RUN_ID:** `codirector-human-gate-2026-08-06T06-01-14Z`

### Program status (locked until owner confirms)

```text
TECHNICAL OPTIMIZATION: PASS
PLAYWRIGHT: PASS (Stages A–H)
INDEPENDENT REFINEMENT VERIFIER: VERIFIED
HUMAN EXPERIENCE GATE: PENDING
FINAL VERDICT: HOLD
```

### Preserved technical results

- Warm soak P50 **4.06s** / P95 **7.63s** / max **17.5s** (prior optimization run)
- True streaming, defer enrichment, specialist subordination, budgets/cache preserved
- Unit regression: `test_codirector_final_optimization.py` + acceleration suite

### Wiki integrity

- Law: `WIKI_VERIFICATION_NEVER_BLOCKS_TTFT` — full read-back only in deferred enrichment
- `WikiWriteVerification` separates `persistenceState` vs `presentationState`
- Claim laws expanded; “Added to Wiki” forbidden until `persistenceState === VERIFIED`
- UI: refetch on `background_job` / `wiki_status`; “Wiki update still processing…”; Refresh Wiki vs Retry documentation
- Evidence: `wiki_write_trace.json`, `wiki_api_records.json`, screenshots

### Wiki TOC

- Live TOC in `ProjectWikiPanel` — hide empty categories, show counts, selected article, Confirmed vs Inferred/Learning

### Contextual options + treatment ownership

- CONTINUE_STORY first; whyNow + preview surfaced; ownership includes Keep developing the story
- Treatment only when readiness AVAILABLE

### Momentum resume

- Grounded varied resume (no mechanical “Continue developing:” prefix); resume on return intents

### Cold-load behavior

- Ollama `/api/ps` probe → `LOADING_MODEL` stage + timings (`coldStart`, `modelLoadMs`)
- UI: Cancel / Continue waiting / Run diagnostic (no silent model swap)

### Corrected concurrent endpoints

- Wiki `GET /api/codirector/projects/{id}/wiki`
- Library create/import → read-back → binding → cleanup
- PA `GET .../status/registry` + `POST .../status/check`
- Evidence: `concurrent_valid_routes.json`

### Specialist spot-check

- `specialist_spotcheck.json` — enabled IDs GO; Treatment Writer / Dialogue / Marketing UNSUPPORTED

### Personality regression

- Cert asserts no “as an AI language model” / canned next-step closer

### Independent refinement verifier

- `scripts/codirector_perf/verify_refinement.py` → `independent_refinement_verifier.json`

### Product-owner scores / average / Yes-No

- Blank in `human_scorecard.md` — **AWAITING_PRODUCT_OWNER**
- Threshold: no score &lt; 4; average ≥ **4.25**; all Yes/No = Yes

### Final binary verdict

**HOLD** until product-owner confirmation.

On confirmation meeting the strict threshold:

`GO — CO-DIRECTOR END-TO-END OPTIMIZATION AND PRODUCTION READINESS VERIFIED`

Otherwise:

`NO-GO — CO-DIRECTOR PIPELINE REMAINS DEGRADED, INEFFICIENT OR INCOMPLETE`

