# Multi-LLM Peer Review

Reviewers were assigned distinct rubrics. Visual peers for M2/M3 candidates were not run because those images do not exist.

Law 27 asked for GPT 5.4 specialized subagents. Available Task models in this session were `inherit`, `composer-2.5-fast`, `cursor-grok-4.6-xhigh-fast`, `glm-5.2-max`, `kimi-k3-max`. GPT 5.4 was not available.

| Area | Reviewer | Rubric | Result |
| --- | --- | --- | --- |
| Schema / inheritance | Primary + focused tests (22 backend, 10 frontend) | State copy, M1 undeletable, limit 5 | PASS |
| Spatial UX | Primary live UI | Accordion, active M2, trash legality, arrows API | PASS |
| ERS geometry | Primary vision of `ers_official_assembled.png` | Core + camera band + M1/M2/M3 strip, no overlap | PASS |
| Qwen M1–M3 movement fidelity | Primary vision of `mini_M1_A.png` / `mini_M1_B.png` only | Spokesperson position M1≠M2≠M3 | FAIL — only M1 pair exists; both are top-down plates, not camera-true hallway blocking |
| Environment / camera continuity | Same M1 pair | Hallway identity vs atlas | REVIEW_REQUIRED — plates look like atlas/ERS crops, not C1 medium hallway |
| Production consistency | Same M1 pair | Spokesperson / shoes / no duplicate person | FAIL — no usable spokesperson/product read |
| Timeline compile | Primary of live `compile_layers_m1_m2.txt` | Layered UNCHANGED/START/END/ACTION/TIMED | PASS |
| Co-Director live | Not executed | Knowledge + Mini tool + plan vs build | NOT VERIFIED |
| Architecture one-store | Independent peer `glm-5.2-max` (`9c140daf-3709-4e67-a03d-1ade3edd27ed`) | Laws 1–3 + no parallel store | PASS |
| Request stability | Observed API/Comfy deaths | No storms / no silent hang | FAIL |

No averaging of the visual FAIL. Material disagreement is not the issue: the required six-image artifact class is incomplete.

## Distinct rubrics (Phase 19)

- ERS judged as index + strip, not as Mini candidates
- Camera references judged as viewpoint canon (C1/C2 not generated as stills; overlays on ERS only)
- Mini candidates judged as blocking-state stills — and they failed that rubric
- Timeline compile judged as layered request text, not as video

## Independent architecture peer (Phase 38)

Reviewer: GLM 5.2 Max. Returned **ARCHITECTURE: PASS** and `READY FOR PRIMARY REVIEW` only.

- Law 1: `inherit_segment` deep-copies production state and resets prose; `create_inherited_movement` write-throughs the live buffer before copy.
- Law 2: `compile_generation_layers` / `layers_as_provider_text` keep UNCHANGED / START / END / ACTION / TIMED PROMPT distinct.
- Law 3: all movement ops persist to `spatial_map_documents.document_json`; Co-Director routes through `spatial_service`; Mini packets and `computeClientArrows` are provenance / optimistic mirrors, not a second store.
- Parallel-store risk: LOW (mitigated). Mini take JSON embeds a compact snapshot for later interpretation; `regenerate_mini` re-reads the live Spatial Map.
- Runtime E2E blockers (API/Comfy, 2/6 images) were explicitly excluded from this architecture verdict.

## Independent final Subagent D (Phase 42)

Reviewer: Kimi K3 Max (`5f2a8fef-5c2a-42d1-91d3-40a4712a6a6b`). Returned `READY FOR PRIMARY REVIEW` only. Did not issue GO.

Core FAILs D recorded: Visual Difference, Qwen six-image (2/6), Request Stability.

Row disagreements with the primary scorecard (not averaged; `REVIEW_REQUIRED` on those rows only):

| Row | Primary | D |
| --- | --- | --- |
| Mini Selector | PARTIAL | NOT VERIFIED |
| Qwen Runtime | PARTIAL | FAIL |
| Events/Memory | PARTIAL | NOT VERIFIED |

Both reviewers agree the only legal milestone language is FAIL / NO-GO.
