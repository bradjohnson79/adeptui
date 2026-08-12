# M41 4.1B-L — Wave 6 Consumer Contract Certification (L-10B)

| Field | Value |
|---|---|
| **Generated** | 2026-07-29T17:13:43Z |
| **wave6ConsumerContractPassed** | `True` |
| **Verdict** | **PASS** |

## Scope

4.1B-L proves the Certified Workflow Library and its public contract are ready for Wave 6.
This L-10B gate proves Wave 6 product surfaces (Co-Director, Director, Generate Studio,
timeline/batch) consume that library **only** through `WorkflowResolver` →
`CanonicalWorkflowContract` — not by importing builders or selecting engines imperatively.

Dedicated Wave 6 product implementation and beta certification remain separate prompts.

## Checks

- **resolutions**: PASS
- **blockedDeferredRejected**: PASS
- **noDirectBuilderImports**: PASS
- **noImperativeEngineSelection**: PASS
- **noBypassExecutionControls**: PASS
- **statusConsistency**: PASS

## Resolution matrix

- `codirector.scene_i2v` → `ltx.simple_i2v`@1.0.0 (WF-SCENE-001) **PASS**
- `director.shot_render` → `ltx.simple_i2v`@1.0.0 (WF-SHOT-001) **PASS**
- `director.scene_render_keyframes` → `ltx.scene`@1.0.0 (WF-SCENE-001) **PASS**
- `generate_studio.ltx_simple_i2v` → `ltx.simple_i2v`@1.0.0 (WF-SCENE-001) **PASS**
- `generate_studio.wan_flf` → `wan.first_last_frame`@1.0.0 (WF-SCENE-001) **PASS**
- `generate_studio.wan_three_frame` → `wan.three_frame`@1.0.0 (WF-SCENE-001) **PASS**
- `generate_studio.txt2vid_local_i2v` → `ltx.simple_i2v`@1.0.0 (WF-SCENE-001) **PASS**
- `generate_studio.extend` → `ltx.simple_i2v`@1.0.0 (WF-EXTEND-001) **PASS**
- `generate_studio.lipsync` → `lipsync.latentsync`@1.0.0 (WF-LIPSYNC-001) **PASS**
- `director.timeline_render` → `director.timeline_render`@1.0.0 (WF-TIMELINE-001) **PASS**
- `director.batch_timeline` → `director.batch_timeline`@1.0.0 (WF-TIMELINE-002) **PASS**

## Artifact

`artifacts/m41/41bl/wave6_consumer_contract_results.json`

## Gate coupling

`evaluate_gate().wave6ConsumerContractPassed` must be true for
`wave6ProductionActivationUnlocked`.
