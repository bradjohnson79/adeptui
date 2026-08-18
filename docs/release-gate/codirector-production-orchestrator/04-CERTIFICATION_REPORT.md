# Co-Director Full Production Orchestrator — Certification Report

**Date:** 2026-08-18
**Branch:** feat/lora-support — HEAD 31e6e48f (working tree also carries a pre-existing Spatial-Map save-gate + ERS wave from before this milestone)
**Governing gate:** mission parts 1-64; AGENTS.md Build Laws #30/#31 (binary certification, evidence-based).

## Verdict

```
NO-GO — CO-DIRECTOR FULL PRODUCTION ORCHESTRATION NOT CERTIFIED
```

Reason: the orchestration capability itself is implemented, tested, and live-verified
(scenarios A-G + 39-42 all pass with REAL generation evidence), but three milestone
gates remain open: (1) deployment (Part 64 - commit/push/deploy + hosted verification
not performed this session; the working tree also contains a separate pre-existing
in-flight wave that must not be swept into this milestone's commit), (2) MiniMax H3
runtime provisioning (the H3 model is not installed on D:\\01_Models, so
MiniMax-specific generation reports an honest "runtime not ready"; LTX generation was
certified in its place), (3) a live retake re-run (Part 45; the retake machinery is
pre-certified and unchanged, but was not re-executed this session).

## Evidence table

| # | Item | Method | Observed | Status |
|---|---|---|---|---|
| 1 | Production state snapshot (Part 1) | GET /production-snapshot on Schnick | Spatial Map v139 saved, cameras C1-C4, ERS sheet, 12 candidates, timeline revision+batches+clips+prompt segments, jobs, events | PASS (LIVE VERIFIED) |
| 2 | Snapshot auto-injection | service.py _prepare_chat_request | Block appended after wiki; bounded | IMPLEMENTED (code) |
| 3 | Production events (Part 2, 27) | GET /production-events | timeline.generation_started/completed, clip_added, prompt_added, batch_created, camera.created, candidate.generated, spatial_map.saved, library.asset_ingested | PASS (LIVE VERIFIED) |
| 4 | Manual-change awareness (39-42) | Playwright 39-42 test | Manual batch + map save visible in events + snapshot | PASS |
| 5 | Production memory + resolution (3-4) | GET /production-memory; resolve-reference | C1-A / "the first C2 shot" / "shot frame 1" resolve; duplicates flagged ambiguous | PASS |
| 6 | Candidate awareness (9) | snapshot candidates + candidate.list/resolve | scene_creator_mini_* parsed to camera/variant; approved state | PASS |
| 7 | Direct execution authority (35-36) | PUT authority + propose | Proposal auto-completed; batch landed; propose latency 75-137s -> 57ms after cache fix | PASS (LIVE VERIFIED) |
| 8 | Conversational Scene Creator (6, A) | CD chat: "Create images from the ERS using the four saved cameras." | EXECUTE_PRODUCTION -> scene.generate -> REAL imagegen jobs -> assets 6b46f4d0 + dc17a9c1 + candidate.generated events | PASS (LIVE VERIFIED) |
| 9 | Shot build + timed prompt + dialogue (17-22, C+D) | build_shot tool | clips 0-5s / 5-10s sequential (no drift), userDirection/productionPrompt/dialogue persisted | PASS |
| 10 | Batch + generation (23-28, E) | batch + generator + generate | LTX I2V job e135e300 completed -> candidate Take A, asset 633ebd5c; MiniMax path reached adapter (honest runtime-offline error - model not installed) | PASS (LIVE VERIFIED, MiniMax blocked by deployment prerequisite) |
| 11 | Result cards in chat (10) | CoDirectorMediaCardGrid + wiring | Component renders result_asset_ids grid; typecheck clean; screenshot captured | IMPLEMENTED |
| 12 | Prompt provenance (13-16, 19-20, 52) | segment fields | dialogue exact; userDirection vs productionPrompt separate | PASS |
| 13 | Honesty (53) | live failures | "placement missing a world position", "Select an Environment Reference Sheet first", "MiniMax H3 private runtime is not ready" - all honest, no fake success | PASS (LIVE VERIFIED) |
| 14 | Latency / no polling explosion (49) | profiling | capability snapshot multi-slot cache; propose 57ms | PASS |
| 15 | Integration tests (61) | pytest | 15 passed (snapshot, events, memory, resolution, authority, provenance, sequential placement) | PASS (TESTED) |
| 16 | E2E certification (62) | Playwright 7 tests | 7/7 passed (A, B, C+D, E, F, 39-42, G); independently re-run by certifier subagent: "7/7 passed, 0 flaky, 0 skipped" | PASS |
| 17 | Router regression | pytest | 205 passed; 6 pre-existing failures unrelated (working-tree in-flight code) | PASS |
| 18 | Frontend typecheck | tsc | clean | PASS |
| 19 | Evidence docs | docs/release-gate/codirector-production-orchestrator/ | 01-CAPABILITY_REUSE_MAP, 02-ARCHITECTURE_DESIGN, 03-IMPLEMENTATION_REPORT, evidence/cd-chat-schnick.png | DONE |
| 20 | Deployment (64) | - | not performed (post-certification step; working tree also holds a separate wave) | NOT VERIFIED |
| 21 | Retake live run (45) | - | retake machinery pre-certified, unchanged; not re-run | DEFERRED |
| 22 | MiniMax-specific generation | - | H3 model not installed (D:\\01_Models missing minimax folder) | BLOCKED (deployment prerequisite) |

## Deliverables (changed files)

Backend (studio-api/app): production_events.py (new), production_state/snapshot.py (new),
production_state/memory.py (new), execution_authority.py (new), migrations/m034 (new),
codirector/tools/handlers/production.py (new), codirector/tools/definitions.py (+6 tools),
codirector/tools/registry.py, codirector/tools/execution.py (auto-approval),
codirector/tools/handlers/director_timeline_tools.py (build_shot + events + provenance),
director_timeline.py + director_timeline_w46/contracts.py (provenance fields),
director_timeline_w46/service.py + orchestrator.py (event hooks), spatial_map/service.py
(event hooks), capabilities/handlers/ers_generate.py + scene_generate.py (events +
output_count coercion), queue_worker.py (events + uuid4 fix), project_library/service.py
(events), capabilities/service.py (multi-slot cache + TTL), routing/deterministic.py +
routing/unified_intent.py (production command patterns), routers/codirector.py (+6
endpoints), codirector/service.py (snapshot/memory injection + execution context ERS/shot
derivation), codirector/execution/status_messenger.py (import fix).

Frontend (studio-web/src): components/CoDirector/CoDirectorMediaCardGrid.tsx (new),
codirectorMediaCards.css (new), CoDirectorMessage.tsx (media grid wiring).

Tests: studio-api/tests/test_codirector_production_orchestrator.py (new, 15 tests),
tests/e2e/codirector-production/codirector-production-orchestrator.spec.ts (new, 7 tests).

## Reused (not rebuilt)

499-tool registry (+6 = 505), proposal/approval machinery, execution dispatcher,
timeline w46 engine + adapters + gates, scene.generate shared engine, spatial/ERS
stores, vision approvals, prompt intelligence, executive jobs.

## Remaining gates to GO

1. Part 64 deployment: commit the milestone files (separate from the in-flight wave),
   push, deploy via the Adept UI workflow, verify hosted revision == tested revision,
   verify hosted CD reaches hosted production APIs.
2. Provision the MiniMax H3 private runtime (models on D:\\01_Models) and re-run
   scenario E with MiniMax; the LTX path is already certified.
3. Re-run a retake (Part 45) live.
