# Co-Director 2.0 — Session Memory

## Project Overview

Adept UI's Co-Director is an AI creative-production assistant. Co-Director 2.0
rebuilt it from a regex-based chat tool into a professional creative-producer
relationship with verified execution, structured story intelligence, workflow
awareness, specialist crew, and professional conversation.

## Architecture (simplified)

```
Creator message
  → Phase 3 RouteDecision (11 action classes)
  → Phase 2 Verified Operator (NAVIGATE) | Proposal/approval (mutations) | Conversation (DISCUSS)
  → Phase 4 Story Intelligence Compiler (Logline/Short/Long Summary)
  → Phase 5 Script Writer + Wiki Integration
  → Phase 6 Workflow Engine (format-aware, evidence-derived)
  → Phase 7 Specialist Crew (RouteDecision-aware, MAX=3)
  → Phase 8 Professional Conversation (known-fact suppression, goal tracking, no leakage)
```

## Current State

- **Beta running**: http://127.0.0.1:8760/ (web) + :8758/ (API) + https://adeptui.vercel.app (Vercel)
- **Provider**: Ollama + qwen3.6:35b-a3b
- **Regression baseline (core)**: 262/262 pass (Phases 2-11); Full suite: ~2173 tests
- **Certification**: All phases + Hosted Beta Infrastructure GO. Final verdict: GO for creator manual Beta.
- **Stability**: 2 uvicorn workers, /healthz fast endpoint, 5-failure hysteresis, TTL cache.
- **Hosted Beta**: Cloudflare Tunnel (822658ce), api-beta.adeptui.org → localhost:8758, Aurora UI parity confirmed

## Phase History

| Phase | Name | Tests | Key deliverable |
|---|---|---|---|
| P2 | Verified Operator + Production State | 40 | Operator request/ack/timeout, 14-domain projection |
| P3 | Intent + Stage Router | 10 | RouteDecision (11 action classes), deterministic + semantic |
| P4 | Story Intelligence Compiler | 43 | StoryEvidenceModel, instruction split, 3 compilers |
| P5 | Script Writer + Wiki Integration | 0 frontend | Wiki dropdown fixes, workspace.open_scriptwriter tool |
| P6 | Professional Workflow Engine | 28 | 4 format-aware workflows, reconciliation, ranking |
| P7 | Specialist Crew Rewire | 29 | RouteDecision-aware selector (MAX=3), permission enforcement |
| P8 | Professional Conversation | 14 | Known-fact suppression, "no phantom knowledge", leakage guards |
| P9 | Acceptance Scenarios | 54 | Sustained conversation across 5 scenario types |
| P10 | Two-Tier Certification | 29 | 10 deterministic + 19 real-model (qwen3.6:35b-a3b) |
| P11 | Final Release Closure | 16 | Architecture audit (0 dangerous paths), full regression |
| HB | Hosted Beta Infrastructure | 79+24 | Cloudflare Tunnel, Vercel parity, useStudioHealth fix, GO |

## Key Files by Subsystem

- **Operator**: `app/codirector/operator/`
- **Router**: `app/codirector/routing/` (RouteDecision schema, deterministic classifier)
- **Production State**: `app/codirector/production_state/` (14-domain projection)
- **Story Intelligence**: `app/codirector/story_intelligence/` (model, compilers, proposal)
- **Workflow**: `app/codirector/workflow/` (definitions, reconciliation, recommendations)
- **Specialists**: `app/codirector/intelligence/` (selector, policies, synthesis)
- **Conversation**: `app/codirector/conversation/` (foundation, planner, response_composer)
- **Knowledge Cards**: `app/codirector/story_intelligence/knowledge_card.py`
- **Cross-check**: `app/codirector/status/` (runner, registry, probe_context)
- **Beta runtime**: `scripts/beta_runtime/` (supervisor, web_server)

## Fresh Start Reading Order

1. `/memory/README.md` — this file
2. `/memory/phases/phase-10-11-final.md` — certification summary
3. `/memory/project/state.md` — current project state
4. `/memory/infrastructure/beta-server-stability.md` — if working on stability
5. `/memory/infrastructure/knowledge-cards.md` — if working on Knowledge Cards
6. Any phase-specific file as needed
