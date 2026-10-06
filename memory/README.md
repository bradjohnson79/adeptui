# Co-Director 2.0 â€” Session Memory

## Project Overview

Adept UI's Co-Director is an AI creative-production assistant. Co-Director 2.0
rebuilt it from a regex-based chat tool into a professional creative-producer
relationship with verified execution, structured story intelligence, workflow
awareness, specialist crew, and professional conversation.

## Architecture (simplified)

```
Creator message
  â†’ Phase 3 RouteDecision (11 action classes)
  â†’ Phase 2 Verified Operator (NAVIGATE) | Proposal/approval (mutations) | Conversation (DISCUSS)
  â†’ Phase 4 Story Intelligence Compiler (Logline/Short/Long Summary)
  â†’ Phase 5 Script Writer + Wiki Integration
  â†’ Phase 6 Workflow Engine (format-aware, evidence-derived)
  â†’ Phase 7 Specialist Crew (RouteDecision-aware, MAX=3)
  â†’ Phase 8 Professional Conversation (known-fact suppression, goal tracking, no leakage)
```

## Current State

- **Timeline V2 / H3 Director (2026-09-27 evening through 2026-09-28 ~8:30 PM PT):** Render Shot + H3 legal canvas GO; Preview Cancel always visible; H3 Director cutover live; Continuity 15+5 GO; R2V eradication GO (LIVE_GPU_PARTIAL); Aspect Ratio thin slice GO then H3 non-16:9 hard-refuse **superseded** by Director Aspect Unify (D1 ResolutionSelector — IN FLIGHT); Library Remove X COMPLETE; Director R2V workflow verify DERIVED / KEEP AS-IS. Detail: `memory/session-2026-09-27-28-timeline-v2-h3.md`. Prior day note: `memory/session-2026-09-26-27-timeline-v2.md`.

- **Co-Director and ERS (2026-09-24 through 2026-09-25):** Eleven completed tasks are recorded in `memory/session-2026-09-24-25-codirector-ers.md`. Durable single-owner architecture, 6-test command acceptance, Character Creator and reference sheets, creator tool completeness, ERS legend navigation, ERS zoom and environment scope, Environment Creator provider binding, character auto-resolution, semantic intent, entity resolution and receipt projection, and a 60-minute approval lifetime. The movable ERS legend insert is not certified. Working tree is uncommitted on `feat/character-creator-final-closure` at `ca8f3c0c`.

- **Timeline Master Single-Stack (2026-09-20):** Dual-stack retirement Primary GO — Timed Prompt SoT = SceneTimelineMaster; Take-P rematerialize fence; put_director Master shim; FE Master-FIRST; speech Master-only; CD01 Env/Image nav live CERT on disposable project. Detail: `memory/session-2026-09-20-timeline-master-single-stack.md`. Law 65: post-task FE parse check mandatory.

- **Beta running**: http://127.0.0.1:8760/ (web) + :8758/ (API) + https://adeptui.vercel.app (Vercel)
- **Provider**: Ollama + qwen3.6:35b-a3b
- **Regression baseline (core)**: 262/262 pass (Phases 2-11); Full suite: ~2173 tests
- **Certification**: All phases + Hosted Beta Infrastructure GO. Final verdict: GO for creator manual Beta.
- **Stability**: 2 uvicorn workers, /healthz fast endpoint, 5-failure hysteresis, TTL cache.
- **Hosted Beta**: Cloudflare Tunnel (822658ce), api-beta.adeptui.org â†’ localhost:8758, Aurora UI parity confirmed
- **Avatar Studio (2026-09-13)**: Character dropdown wired to canonical project character authority (`character_identity_v1`); footer cards/tabs/buttons converged onto Adept design tokens; live E2E GO. Branch `feat/character-creator-final-closure` @ `99665cf7`.
- **Timeline H3 (2026-09-13)**: Timeline = R2V only (FM4/FM5 3-ref Quality SHA `33fa6665â€¦`). Track Integrity in flight. Spatial Correct Area = zimage.inpaint only (Atlas stays GPT Image 2). NEW mission: Timeline Re-Take must be R2V not T2V â€” audit at `theme_walk/timeline_retake_r2v/AUDIT.md`.
- **Timeline Batch Architecture (2026-09-18)**: Take N "15-second scene twice" regression root-caused (`reconcile._in_window` midpoint test) and fixed to start-containment (12B model). Batch architecture now owner-protected by a 4-layer safeguard (Cursor rule + Charter + 15 fence tests + in-code guard markers). Co-Director long-scene preparation (12B shape) audited as ALREADY IMPLEMENTED end-to-end â€” capability plan â†’ N distinct window-scoped prompts â†’ per-batch persistence â†’ additive Qwen weave. `NeedsDialogueRetake` = designed fail-closed `UNAUTHORIZED_BACKGROUND_SPEAKER` (Omni ASR `speaker: "unknown"`), same as 12B â€” not a regression. Final protection run 117 passed / 0 failed; live takes Kâ€“Q certified. Detail: `memory/session-2026-09-18-timeline-batch-architecture.md`.

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

## Binding laws (read first)

- `/memory/files/MODEL_INSTALL_ROOT.md` â€” new model/runtime installs land under `D:\01_Models` (Model Storage `preferredRoot`). Do not move `data_dir`; do not set `STUDIO_COMFY_MODELS_DIR` to that root. (2026-08-14)
- `/memory/FULL_STACK_E2E_COMPLETION_LAW.md` â€” UI complete â‰  feature complete. Hosted defects require hosted verification. Independent verifier required. (2026-08-14)

## Fresh Start Reading Order

1. `/memory/README.md` â€” this file
2. `/memory/FULL_STACK_E2E_COMPLETION_LAW.md` â€” full-stack E2E completion law (binding)
3. `/memory/phases/phase-spatial-map-ers-scene-creator.md` â€” Spatial Map + Atlas + ERS + Scene Creator (latest, 2026-08-11)
4. `/memory/session-2026-09-26-27-timeline-v2.md` — Timeline V2 tasks, 2026-09-26 through 2026-09-27
4-prev. `/memory/session-2026-09-24-25-codirector-ers.md` — completed Co-Director and ERS tasks, 2026-09-24 through 2026-09-25
4a. `/memory/session-2026-09-13-avatar.md` â€” Avatar Studio character propagation + UI style convergence (latest, 2026-09-13)
4b. `/memory/session-2026-09-13-timeline.md` â€” Timeline H3 R2V law + Track Integrity + Correct Area + Re-Take R2V mission (2026-09-13)
4c. `/memory/session-2026-09-18-timeline-batch-architecture.md` â€” Take N regression fix, batch-architecture Protection Charter, long-scene audit (2026-09-18)
5. `/memory/session-2026-08-11.md` â€” session memory for Spatial Map implementation day
6. `/memory/phases/phase-10-11-final.md` â€” Co-Director 2.0 certification summary
7. `/memory/project/state.md` â€” current project state
8. `/memory/infrastructure/beta-server-stability.md` â€” if working on stability
9. `/memory/infrastructure/knowledge-cards.md` â€” if working on Knowledge Cards
10. Any phase-specific file as needed

