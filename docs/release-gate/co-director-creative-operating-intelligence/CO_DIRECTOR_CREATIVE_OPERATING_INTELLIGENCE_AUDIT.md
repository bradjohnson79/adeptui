# Co-Director Creative Operating Intelligence & Project Bible Stewardship — Technical Appendix

> **SUPERSEDED AS GOVERNING DOC (Law 30).**  
> Authoritative unified completion report:  
> [`CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md`](./CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md)  
> This file remains a detailed technical appendix only.  
> Historical extract `_MASTER_PROMPT_EXTRACT.md` is prompt reference only — not governing.

**Date:** 2026-08-06  
**Branch:** `feature/ai-guided-setup`  
**HEAD (at audit):** `fa09c99d6395c29461cdec4555055faad116c435` (uncommitted COI work present in working tree)

---

## 1. Executive summary

Co-Director now has a unified **Creative Operating Intelligence** layer: five internal minds, an authoritative LISTEN→…→PREPARE NEXT OPENING decision loop, project-scoped initiative dial, curiosity threads with question budget, fact/interpretation/possibility separation, Project Bible Steward specialist, format-aware one-step-ahead suggestions, script/identity/correction helpers, and disagreement synthesis — all behind one creator-facing Co-Director voice.

Playwright certification passed. Independent verifier returned **VERIFIED**.

**Automated technical status:** GO (see governing completion report).  
**Final product acceptance:** HOLD until product-owner human experience review is scored in `HUMAN_EXPERIENCE_REVIEW.md`.

---

## 2. Branch and HEAD

| Field | Value |
|-------|--------|
| Branch | `feature/ai-guided-setup` |
| Base HEAD noted | `fa09c99d6395c29461cdec4555055faad116c435` |
| Commit | Not requested — changes remain in working tree |

---

## 3. Governing purpose

Locked into coaching doctrine + decision composition:

> Understand what the creator is building, protect what makes it distinctive, help continue developing it, organize everything important, and prepare the next meaningful decision — without taking control.

---

## 4. Five-minds implementation

`studio-api/app/codirector/creative_operating/minds.py` → `evaluate_minds()`

Internal lenses only (never creator-facing personalities):

- Companion  
- Storyteller  
- Project Bible Steward  
- Producer  
- Guardian of the Vision  

Notes attach to `CoDirectorCreativeDecision.mindNotes` and feed prompt composition.

---

## 5. Creative decision loop

`decision_loop.py` → `run_creative_decision_loop()`

```text
LISTEN → INTERPRET → EXTRACT → CONNECT → DECIDE → RESPOND → ORGANIZE → PREPARE_NEXT_OPENING
```

Wired on the hot path as **compact heuristics** (orchestrate.py) and again in **background** enrichment (`deferred_enrichment.py` → `process_creative_operating_turn`). Wiki/specialist heavy work stays background-first.

---

## 6. Creative-temperature behavior

Stage mapped from discovery temperature into `EMERGING|FORMING|STRUCTURING|REFINING|LOCKING|PRODUCING`. Emerging/forming protect momentum and suppress production pressure; refining/producing allow more analytical posture.

---

## 7. Initiative levels

Persistent `settings_json.creativeOperating.initiativeLevel`:

| Level | Creator label |
|-------|----------------|
| `QUIET_PARTNER` | Quiet Partner |
| `COLLABORATIVE_PARTNER` | Collaborative Partner |
| `PROACTIVE_PRODUCER` | Proactive Producer |
| `HANDS_ON_CO_CREATOR` | Hands-On Co-Creator |

API: `GET/PUT /api/codirector/projects/{id}/creative-operating[/initiative]`  
UI: More → Options → Partnership style (`CoDirectorInitiativeDial`)

---

## 8. Question-budget evidence

Max newly surfaced questions per response: initiative-gated; **0** when listening-only / Quiet Partner flow. Cert + verifier: Quiet flow → `questionBudget=0`, `listeningOnly=true`.

---

## 9. Curiosity-thread evidence

`CreativeCuriosityThread` stored project-scoped; max 5 active; resurface relevance-ranked; dismiss/answer APIs. Artifacts: `artifacts/creative_operating_state.json`.

---

## 10. Fact / interpretation / possibility separation

`canon_safety.py` — speculative kinds cannot carry `CONFIRMED`/`LOCKED`. Prompt block instructs composition. Verifier gate **Canon safety: GO**.

---

## 11. Project Bible Steward

- Specialist prompt: `prompts/specialists/project-bible-steward.md`  
- Modes: IMMEDIATE_INTAKE / BACKGROUND_ORGANIZATION / PERIODIC_STEWARDSHIP (`bible_steward.py`)  
- `creatorFacingAllowed=false` (hard in `build_contract`)  
- Routed into wiki domain map for world/canon  

---

## 12. Heading simplification

`simplify_heading` / `merge_duplicate_headings` collapse noisy theme/overview/episode labels into professional navigation labels.

---

## 13. Story and production importance

`WhyItMatters` / `why_it_matters_for_record` — evidence-grounded, format-aware, no invented production facts.

---

## 14. Creative openings

`openings.py` — strongest opening only surfaced into decision.

---

## 15. Forward-development logic

`ForwardDevelopmentSuggestion` — max 3 per pass, normally surface one, always `EXPLORATORY`, skipped in listening-only, dismissible without repetition.

---

## 16. Format awareness

`format_detect.py` — film / series / documentary / game / novel / music video / commercial / etc. Episodic progression **only** when format is episodic. Cert fixtures B–E verified no Episode-2 assumptions.

---

## 17. Script intelligence

`script_intelligence.py` + `POST .../creative-operating/script/analyze` — scenes, identities, installment breakdown (not attachment note).

---

## 18. Correction intelligence

Identity alias learning + preview; structural Wiki undo via existing reorganize undo path. Cert exercised both.

---

## 19. Specialist departments

Specialists return structured findings only. Roster hard-rule for steward. No specialist voice in creator chat.

---

## 20. Disagreement synthesis

`ProfessionalDisagreement` synthesized by orchestrator; cert verified coherent recommendation without specialist role names.

---

## 21. Response examples

Composition guidance: warm acknowledgement → specific observations → interpretation → invitation → optional soft next steps. Jargon strip preserved in existing response composer. Coaching doctrine injected into LLM context.

---

## 22. Latency regression

Decision heuristics measured in cert (`latencyMsQuiet` &lt; 5s gate). Background enrichment never blocks TTFT (`neverBlocksTtft: true`).

---

## 23. Cross-format fixtures

| Fixture | Result |
|---------|--------|
| A Dreamweaver / ADEPT_PROJECT_ID | GO |
| B Documentary disposable | GO — non-episodic |
| C Standalone film | GO — sequence logic |
| D Music video | GO |
| E Game | GO |

No fixture-specific ontology in product code.

---

## 24. Playwright

`tests/e2e/codirector/codirector-creative-operating-intelligence-cert.spec.ts`  
`ADEPT_BETA_TARGET=1`, `workers=1`, `retries=0` → **passed**  
Artifacts under `docs/release-gate/co-director-creative-operating-intelligence/artifacts/`

---

## 25. Independent verifier

`scripts/verify_codirector_creative_operating_intelligence.py` → **VERIFIED**  
Artifact: `artifacts/independent_creative_operating_verifier.json`

---

## 26. Limitations

1. Decision loop on hot path is heuristic (fast); deep specialist fan-out remains background.  
2. Script parser is structural/lightweight — not a full screenplay engine.  
3. Product-owner human review not scored in this audit (HOLD).  
4. Running Beta process may need restart after steward prompt front-matter fix to refresh in-process `PromptLibrary` cache (verifier loads a fresh Python process and already sees steward).  
5. Soft next-step chips reuse existing next-steps module; COI invitations are also injected via prompt composition.  
6. Uncommitted working tree includes this milestone plus other parallel work.

---

## 27. Product-owner scorecard

| Item | Status |
|------|--------|
| Feels like one partner | Pending human review |
| Quiet vs Proactive feel distinct | Pending human review |
| Bible stays clean | Pending human review |
| One-step-ahead useful | Pending human review |
| No specialist leakage | Automated GO; human confirm |

---

## 28. Final verdict (appendix — not governing)

Governing final product verdict lives only in  
`CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md`.

```text
AUTOMATED TECHNICAL GATES: GO
FINAL PRODUCT ACCEPTANCE: HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING
```

### Beta URLs (left running)

- Creator UI: http://127.0.0.1:8760/  
- Studio API: http://127.0.0.1:8758/  

### Gate matrix (automated)

All mandatory automated technical gates exercised by Playwright + verifier are **GO** / **VERIFIED**. Final product GO requires a passing owner scorecard.
