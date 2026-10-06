# Final Certification — Movement Segment Full Production System

Date: 2026-08-18  
Branch: `feat/movement-segments`  
HEAD: `aa6b72bb0970e651bb25bd323c55ff3e40bb1b88`  
Working tree: Movement implementation is present and dirty; do not sweep Avatar Studio / LoRA / Timeline-finalization into a Movement commit.

## Scorecard

| Gate | Result |
| --- | --- |
| Movement Schema | PASS |
| M1 Migration | PASS (focused tests) |
| Inheritance | PASS (live Brand Ad + tests) |
| State Isolation | PASS (Mini packets) |
| Spatial UX | PASS |
| Arrows | PASS (API + UI path) |
| Save/Reload | PASS (UI Saved v17; Playwright reload of accordion) |
| ERS | PASS (assembled 2560×2220 with M1–M3 strip) |
| Mini Selector | REVIEW_REQUIRED — primary PARTIAL; D NOT VERIFIED (no live dropdown screenshot) |
| Qwen Runtime | REVIEW_REQUIRED — primary PARTIAL; D FAIL (queue not sustained) |
| M1/M2/M3 Visual Difference | FAIL |
| Mini Provenance | PASS |
| Standard Hydration | NOT VERIFIED live (code: selector + shot-override copy present) |
| Timeline Tags | PASS |
| Compile Layers | PASS |
| Multi-Batch Isolation | NOT VERIFIED live (compile architecture only) |
| Co-Director | NOT VERIFIED live |
| Events/Memory | REVIEW_REQUIRED — primary PARTIAL; D NOT VERIFIED (CD memory questions never asked) |
| Playwright | PASS (structure spec, 1 passed) |
| Request Stability | FAIL |

Independent architecture peer (Phase 38): **PASS**.  
Independent Subagent D (Phase 42): same core FAILs; same legal language FAIL / NO-GO. That does not lift Visual Difference or Request Stability.

Any core FAIL blocks GO.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — fresh Brand Ad project via UI |
| Frontend | PASS — Spatial Map movements, save, Mini enable path |
| API | PASS then FAIL — routes worked; process died mid-job twice |
| Backend | PASS — inheritance, packets, compile, strip |
| Persistence | PASS — map v17, ERS composite, M1 Mini assets |
| Runtime | FAIL — Comfy hung/refused after M2; four Mini jobs failed |
| Result | FAIL — 2/6 Qwen images; not camera-true blocking |
| Reload | PASS — movements survived; Playwright reload |
| Downstream | PARTIAL — Timeline refs compile; CD/Standard live not closed |

## Mandatory fresh-smoke verdict

```text
FAIL — FRESH BRAND AD MOVEMENT SEGMENT SMOKE
```

Missing: six real Qwen images and observed `M1 ≠ M2 ≠ M3` spokesperson blocking after reload.

## Governing verdict

```text
NO-GO — MOVEMENT SEGMENT FULL PRODUCTION SYSTEM NOT CERTIFIED
```

Do not treat implementation, unit tests, or ERS strip assembly as GO.

## What already holds (do not reopen)

- One Spatial Map Movement contract
- Inheritance is copied state
- Layered Timeline compile
- Mini packet isolation
- ERS movement strip geometry
- Creator-facing errors for delete M1 / sixth / missing activate

## What must be true before a re-cert

1. Healthy Studio API + Comfy for the full Mini queue (no mid-sample death)
2. Six Qwen Local images M1/M2/M3 × C1 × A/B
3. Independent vision peers agree M1≠M2≠M3 on **camera-true** stills (not atlas crops)
4. Live Co-Director answers from saved JSON + one real `scene_creator_mini.create_take`
5. Standard M2 hydration + reload
6. Request-stability soak: no poll storm from other projects starving 8758/8188

Local Qwen GPU proof remains local. Do not push/deploy from this dirty mixed tree.
