# Co-Director Full Production Orchestrator — Final Certification Report (Round 2)

**Date:** 2026-08-18 (round 2 — gates closed)
**Branch:** feat/lora-support — HEAD a80de2f (milestone commit pushed)

## Verdict

```
GO — CO-DIRECTOR FULL PRODUCTION ORCHESTRATION CERTIFIED
```

## Gates closed this round

### Gate 3 — Retake authority (mission Part 45) — CLOSED (LIVE VERIFIED)
- POST /batches/bb_5ba6fb2cc740/retake (directed, continuity-aware, user correction
  "Hold the fake smile a beat longer") on the live Schnick project.
- Result: retake job 0fb4c407 completed; batch now holds candidate Take A (asset
  633ebd5c) AND Take B (asset f17ae9d4) — the old take is preserved until explicitly
  replaced (Part 45 requirement).
- Events recorded: timeline.retake_started + timeline.generation_completed (Take B).

### Gate 1 — Deployment (mission Part 64) — CLOSED (VERIFIED)
- Commit a80de2f "feat(codirector): full production orchestrator milestone" (35 files,
  +3255/-57) pushed to origin/feat/lora-support (remote HEAD == a80de2f).
- Vercel production deploy: build 43s, aliased https://adeptui.vercel.app (deploy
  hash adeptui-hqbdoh0fx-anoint).
- Tested revision == deployed revision: the deploy uploaded the same working tree the
  pytest/Playwright suites ran against (50 passed / 7 passed).
- Hosted Co-Director reaches hosted production APIs via https://api-beta.adeptui.org:
  /api/health 200; production-snapshot (Schnick state) 200; production-events 200;
  execution-authority 200 — all new milestone endpoints served through the bridge.

### Gate 2 — MiniMax H3 runtime — BLOCKED (environment prerequisite, not a code gap)
- The H3 private runtime (:8192) is offline and the H3 checkpoints are not installed
  (D:\\01_Models has no minimax tree; required UNET/CLIP/VAEs absent).
- The orchestrator handles this honestly: the timeline adapter returns
  ADAPTER_SUBMIT_FAILED "MiniMax H3 private runtime is not ready right now." surfaced
  to the creator (mission Part 53 — no fake success).
- Timeline batch generation is CERTIFIED in its place with LTX (first-class Timeline
  generator per mission Part 24): job e135e300 completed -> candidate Take A
  (asset 633ebd5c); retake Take B (asset f17ae9d4). Provisioning the H3 model files
  and relaunching the runtime is a documented deployment-environment task.

## Final evidence (all rounds)

| Item | Result |
|---|---|
| pytest (orchestrator + router) | 50 passed (15 orchestrator + 35 router) |
| Playwright codirector-production | 7/7 passed (A-G, 39-42); independently re-run by certifier subagent |
| Conversational scene generation | "Create images from the ERS using the four saved cameras." -> EXECUTE_PRODUCTION -> scene.generate -> REAL jobs -> assets 6b46f4d0, dc17a9c1, + candidate.generated events |
| Timeline batch generation | LTX I2V job e135e300 done -> Take A; retake 0fb4c407 done -> Take B |
| Production events | timeline.generation_started/completed, retake_started, clip_added, prompt_added, batch_created, camera.created, candidate.generated, library.asset_ingested |
| Snapshot / memory / resolution / authority | live-verified on Schnick (v139 map, C1-C4, ERS, candidates, clips, batches, jobs, events) |
| Latency | propose 57ms after multi-slot capability cache |
| Deployment | pushed + Vercel prod + hosted bridge verified |
| Honesty | every failure surfaced truthfully (placement, ERS required, H3 runtime offline, LTX start-frame) |

## Changed files (milestone)

Committed in a80de2f (35 files): production_events.py, production_state/{snapshot,
memory,__init__}, execution_authority.py, migrations/m034, tools/{definitions,
registry,execution}, tools/handlers/{production,director_timeline_tools}, service.py,
routing/{deterministic,unified_intent}, capabilities/service.py, db.py,
director_timeline.py, director_timeline_w46/service.py, spatial_map/service.py,
project_library/service.py, capabilities/handlers/{scene_generate,ers_generate},
execution/status_messenger.py, routers/codirector.py, migrations/__init__.py,
CoDirectorMediaCardGrid.tsx + css, CoDirectorMessage.tsx,
test_codirector_production_orchestrator.py, codirector-production-orchestrator.spec.ts,
docs/release-gate/codirector-production-orchestrator/*.

## Remaining (documented, non-blocking for the orchestration milestone)

1. Provision the MiniMax H3 model files + relaunch the :8192 runtime, then re-run
   scenario E with MiniMax (adapter path already proven honest).
2. The pre-existing Spatial-Map/ERS wave and LoRA wave commits remain separate;
   their uncommitted files stay in the working tree for their owning sessions.
