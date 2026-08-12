# Co-Director Response Acceleration Audit

**RUN_ID:** `codirector-accel-2026-08-06T02-45-45Z`  
**Beta:** [http://127.0.0.1:8760/](http://127.0.0.1:8760/) · API [http://127.0.0.1:8758/](http://127.0.0.1:8758/)  
**Cert project:** The Dreamweaver (`cd40c8e5-8bae-4c42-9795-90dc60fa2875`)

## Wave 0 — Isolation (dominant causes)

Pre-fix `isolation_matrix.json`:

| Path | TTFT | Notes |
|------|------|-------|
| A direct Ollama stream | ~11.1s | Provider path OK |
| E full Co-Director (pre-fix) | ~23.5s · 9 tokens | Fake-chunk / sync Core |

**Dominant causes:** sync Conversation Core before SSE; fake Ollama streaming; `/api/tags` every generate; optimistic “Understanding the request”; full Wiki rebuild each prepare.

## Post-fix evidence

| Evidence | Result |
|----------|--------|
| Isolation E TTFT | **10.5s** · **284 tokens** (true stream) |
| Isolation A TTFT | **3.9s** |
| Playwright cert | **1 passed** (Stages 1–12 + N1–N10) |
| Onboarding TTFT | 9.7s |
| Story TTFT | 13.4s |
| Next-step options | 4 incl. CONTINUE_STORY |
| Sequential soak (3 turns) | P50 **9.5s**, max **11.9s**; chips do not inflate TTFT |
| Unit tests | `test_codirector_response_acceleration.py` **6 passed** |
| Independent verifier | **VERIFIED** (`independent_verifier.json`) |

## Implementation delivered

1. **True streaming** — Ollama `stream: true` NDJSON; health TTL; `keep_alive`; cancel-aware; `WAITING_FOR_MODEL` / `STREAMING_RESPONSE`
2. **Response-first Core** — `defer_enrichment` + `run_deferred_enrichment` after tokens; Wiki via `background_job`
3. **Budgets + cache** — complexity classifier; `ProjectIntelligenceCache`; compact cache preferred over full Wiki rebuild
4. **Honest UI** — SSE stages; delay hint + Cancel; Wiki background chip; immediate tokens
5. **Next-step invitations** — engine + SSE + chips + ownership + defer API (settings_json-safe)
6. **Cancel / PA** — stream cancel checks; circuit breakers; busy no longer scores as Degraded

## Hard gates

- Typical TTFT &lt; 20s — **PASS**
- Hard TTFT &lt; 30s — **PASS**
- Visible reply &lt; 60s — **PASS**
- No fake streaming — **PASS** (token counts 100–280+)
- Wiki not sync before dispatch — **PASS** (`defer_enrichment: true`)
- Soft invitations with continue path — **PASS**
- No silent model substitution — **PASS**

## Limitations

- Soak was 3 sequential turns (not full 30-turn overnight); P50/P95 within gate on that sample.
- Next-step chips intentionally suppress on short/repetitive follow-ups; rich story turns still offer 2–4.
- Full concurrent Wiki+PA soak not re-run in this window; PA busy remapping + weighting fix are unit/code covered.

## Manual review path

1. Open [http://127.0.0.1:8760/co-director?projectId=cd40c8e5-8bae-4c42-9795-90dc60fa2875](http://127.0.0.1:8760/co-director?projectId=cd40c8e5-8bae-4c42-9795-90dc60fa2875)
2. Send a short onboarding / story beat; confirm stages advance past “Receiving” and tokens appear without a multi-minute stall.
3. After a rich story share, confirm soft chips (Keep telling the story first); treatment asks ownership before drafting.

## Verdict

**GO — CO-DIRECTOR RESPONSE ACCELERATION AND NON-BLOCKING INTELLIGENCE VERIFIED**
